# ray libs
import ray
from ray import tune, air
from ray.rllib.evaluation.episode_v2 import EpisodeV2
from ray.tune.registry import register_env
from ray.rllib.algorithms.callbacks import DefaultCallbacks
from ray.rllib.utils.metrics import ENV_RUNNER_RESULTS
from ray.rllib.env.wrappers.pettingzoo_env import ParallelPettingZooEnv
from ray.rllib.connectors.env_to_module import FlattenObservations
from ray.rllib.algorithms.ppo import PPO, PPOConfig

# ransim envs
from ransim_env.envs import sinario_three

# for stats calculation
import scipy
import numpy as np

# control experiment result path
from expfolder_allocator import path_allocator

# general python libs
import os
import pickle
from pathlib import Path
import re
import pprint
import sys


gamma = float(sys.argv[1])

eval_episodes = 10

episode_len = 300

train_runner = 20
collect_steps_per_runner = 150
batch_size = train_runner * collect_steps_per_runner

exp_folder = path_allocator("exp", "")
exp_folder = Path(exp_folder).resolve().as_posix()
print("experiment result path:", exp_folder)
print("gamma:", gamma)

ray.init()

def train_env_sina3_creator(env_config):
    return ParallelPettingZooEnv(sinario_three.SinarioThree(
            f"train_{env_config.worker_index}", episode_len,
            unchange_terminate = 0,
            root_path=os.path.join(exp_folder, f"train_{env_config.worker_index}"),
            no_termi=True,
            plot = False
        ))

def eval_env_sina3_creator(env_config):
    return ParallelPettingZooEnv(sinario_three.SinarioThree(
            f"eval_{env_config.worker_index}", episode_len,
            unchange_terminate = 0,
            root_path=os.path.join(exp_folder, f"eval_{env_config.worker_index}"),
            no_termi=True,
            plot = True
        ))

register_env("sina3_train", train_env_sina3_creator)
register_env("sina3_eval", eval_env_sina3_creator)

class MyCallbacks(DefaultCallbacks):
    def on_episode_start(
        self,
        *,
        worker,
        base_env,
        policies,
        episode: EpisodeV2,
        env_index,
        **kwargs,
    ):
        # Create a new user_data dict for this episode.
        episode.user_data["sla_vio_times"] = {}
        episode.user_data["reconf_times"] = {}
        # on start, the get_agents() will return empty list

    def on_episode_step(
        self,
        *,
        worker,
        base_env,
        policies,
        episode: EpisodeV2,
        env_index,
        **kwargs,
    ):
        # Make sure this episode is ongoing.
        assert episode.length > 0, (
            "ERROR: `on_episode_step()` callback should not be called right "
            f"after env reset! {episode.length}"
        )
        # get agents
        agents = episode.get_agents()
        for a in agents:
            sla = episode.last_info_for(a)["SLA_violation"]
            reconf = int(episode.last_info_for(a)["changed_RB"])

            if a not in episode.user_data["sla_vio_times"]:
                episode.user_data["sla_vio_times"][a] = sla
            else:
                episode.user_data["sla_vio_times"][a] += sla
            if a not in episode.user_data["reconf_times"]:
                episode.user_data["reconf_times"][a] = reconf
            else:
                episode.user_data["reconf_times"][a] += reconf

    def on_episode_end(
        self,
        *,
        worker,
        base_env,
        policies,
        episode: EpisodeV2,
        env_index,
        **kwargs,
    ):
        for a in episode.get_agents():
            episode.custom_metrics[f"sla_vio_times_{a}"] = episode.user_data["sla_vio_times"][a]
            episode.custom_metrics[f"reconf_times_{a}"] = episode.user_data["reconf_times"][a]

    def on_evaluate_end(
        self,
        *,
        algorithm,
        metrics_logger = None,
        evaluation_metrics,
        **kwargs,
    ) -> None:
        # Tips: after on_evaluate_end, all value in custom_metrics should be value or a list of value.
        # So can't use dict in custom_metrics.
        custom_metrics = evaluation_metrics[ENV_RUNNER_RESULTS]["custom_metrics"]
        agents = [re.findall(r"sla_vio_times_(\S+)", i)[0] for i in custom_metrics.keys() if "sla_vio_times" in i]

        for a in agents:
            custom_metrics[f"sla_vio_mean_{a}"] = np.mean(custom_metrics[f"sla_vio_times_{a}"])
            custom_metrics[f"sla_vio_var_{a}"] = np.var(custom_metrics[f"sla_vio_times_{a}"])
            custom_metrics[f"sla_vio_sem_{a}"] = scipy.stats.sem(custom_metrics[f"sla_vio_times_{a}"])

            custom_metrics[f"reconf_mean_{a}"] = np.mean(custom_metrics[f"reconf_times_{a}"])
            custom_metrics[f"reconf_var_{a}"] = np.var(custom_metrics[f"reconf_times_{a}"])
            custom_metrics[f"reconf_sem_{a}"] = scipy.stats.sem(custom_metrics[f"reconf_times_{a}"])

        episode_rew = evaluation_metrics[ENV_RUNNER_RESULTS]["hist_stats"]["episode_reward"]
        custom_metrics["rew_mean_episode"] = np.mean(episode_rew)
        custom_metrics["rew_var_episode"] = np.var(episode_rew)
        custom_metrics["rew_sem_episode"] = scipy.stats.sem(episode_rew)
        
        policies = list(evaluation_metrics[ENV_RUNNER_RESULTS]["policy_reward_max"].keys())
        for p in policies:
            custom_metrics[f"rew_mean_{p}"] = np.mean(evaluation_metrics[ENV_RUNNER_RESULTS]["hist_stats"][f"policy_{p}_reward"])
            custom_metrics[f"rew_var_{p}"] = np.var(evaluation_metrics[ENV_RUNNER_RESULTS]["hist_stats"][f"policy_{p}_reward"])
            custom_metrics[f"rew_sem_{p}"] = scipy.stats.sem(evaluation_metrics[ENV_RUNNER_RESULTS]["hist_stats"][f"policy_{p}_reward"])

        path = path_allocator(os.path.join(exp_folder, "evaluation_metrics.pkl") , is_directory=False)
        with open(path, "wb") as f:
            pickle.dump(evaluation_metrics, f)

config = (
    PPOConfig()
    .environment("sina3_train")
    .framework("torch")
    .env_runners(
        num_env_runners = train_runner,
        num_envs_per_env_runner = 1,
        num_cpus_per_env_runner = 1,
        rollout_fragment_length = collect_steps_per_runner,
        batch_mode = "truncate_episodes",
        sample_timeout_s = 6000,
        env_to_module_connector=lambda env: FlattenObservations(multi_agent=True)
    )
    .resources(num_gpus = 1)
    .training(
        gamma = gamma,
        train_batch_size = batch_size,
        lr = 1e-3,
    )
    .evaluation(
        evaluation_interval = 1,
        evaluation_duration = eval_episodes,
        evaluation_duration_unit = "episodes",
        evaluation_sample_timeout_s = 6000,
        evaluation_num_env_runners = eval_episodes,
        evaluation_parallel_to_training = True,
        evaluation_config = {
            "env": "sina3_eval",
            "explore": False,
            "callbacks": MyCallbacks,
        }
    )
    .multi_agent(
        policies = {'p0', 'p1' ,'p2'},
        policy_mapping_fn=lambda aid, episode, worker: re.sub("^agent_", "p", aid),
        count_steps_by = "env_steps"
    )
    .reporting(keep_per_episode_custom_metrics=True)
    .callbacks(MyCallbacks)
)

res = tune.Tuner(
    PPO,
    param_space=config.to_dict(),
    run_config=air.RunConfig(
        storage_path = exp_folder,
        stop={"training_iteration":40},
        checkpoint_config = air.CheckpointConfig(
            checkpoint_frequency = 1
        )
    )
).fit()

print(res)
print("------------------------------- result -------------------------------")
pprint.pprint(res._results)
