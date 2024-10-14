import ray
import scipy.stats
from ray.tune.registry import register_env
from ray.rllib.algorithms.callbacks import DefaultCallbacks
from ray.rllib.utils.metrics import ENV_RUNNER_RESULTS

from ransim_env.envs import sinario_two
from ransim_env.envs import FlattenObsGym

from rllib_nsreq import NSREQConfig, NSREQ

from ray import tune, air

import scipy
import numpy as np
import pprint

from expfolder_allocator import path_allocator
import os
import pickle
from pathlib import Path

eval_episodes = 3

episode_len = 300

train_steps_per_runner = episode_len
train_runner = 20
train_steps = train_steps_per_runner * train_runner

exp_folder = path_allocator("exp", "")
exp_folder = Path(exp_folder).resolve().as_posix()
print("experiment result path:", exp_folder)

ray.init()

def train_env_sina2_creator(env_config):
    return FlattenObsGym(sinario_two.SinarioTwo(
            f"train_{env_config.worker_index}", episode_len,
            unchange_terminate = 0,
            root_path=os.path.join(exp_folder, "train_logs"),
            no_termi=True,
            plot = False
        ))

def eval_env_sina2_creator(env_config):
    return FlattenObsGym(sinario_two.SinarioTwo(
            f"eval_{env_config.worker_index}", episode_len,
            unchange_terminate = 0,
            root_path=os.path.join(exp_folder, f"eval_{env_config.worker_index}"),
            no_termi=True,
            plot = True
        ))

register_env("sina2_train", train_env_sina2_creator)
register_env("sina2_eval", eval_env_sina2_creator)

class MyCallbacks(DefaultCallbacks):
    def on_episode_start(
        self,
        *,
        worker,
        base_env,
        policies,
        episode,
        env_index,
        **kwargs,
    ):
        # Create a new user_data dict for this episode.
        episode.user_data["sla_vio_times"] = 0
        episode.user_data["reconf_times"] = 0

    def on_episode_step(
        self,
        *,
        worker,
        base_env,
        policies,
        episode,
        env_index,
        **kwargs,
    ):
        # Make sure this episode is ongoing.
        assert episode.length > 0, (
            "ERROR: `on_episode_step()` callback should not be called right "
            f"after env reset! {episode.length}"
        )
        sla = episode.last_info_for()["SLA_violation"]
        reconf = int(episode.last_info_for()["changed_RB"])

        episode.user_data["sla_vio_times"] += sla
        episode.user_data["reconf_times"] += reconf

    def on_episode_end(
        self,
        *,
        worker,
        base_env,
        policies,
        episode,
        env_index,
        **kwargs,
    ):
        episode.custom_metrics["sla_vio_times"] = episode.user_data["sla_vio_times"]
        episode.custom_metrics["reconf_times"] = episode.user_data["reconf_times"]

    def on_evaluate_end(
        self,
        *,
        algorithm,
        metrics_logger = None,
        evaluation_metrics,
        **kwargs,
    ) -> None:
        custom_metrics = evaluation_metrics[ENV_RUNNER_RESULTS]["custom_metrics"]
        sla = custom_metrics["sla_vio_times"]
        custom_metrics["sla_vio_mean"] = np.mean(sla)
        custom_metrics["sla_vio_var"] = np.var(sla)
        custom_metrics["sla_vio_sem"] = scipy.stats.sem(sla)

        reconf = custom_metrics["reconf_times"]
        custom_metrics["reconf_mean"] = np.mean(reconf)
        custom_metrics["reconf_var"] = np.var(reconf)
        custom_metrics["reconf_sem"] = scipy.stats.sem(reconf)

        rew = evaluation_metrics[ENV_RUNNER_RESULTS]["hist_stats"]["episode_reward"]
        custom_metrics["rew_mean"] = np.mean(rew)
        custom_metrics["rew_var"] = np.var(rew)
        custom_metrics["rew_sem"] = scipy.stats.sem(rew)
        pprint.pprint(custom_metrics)

        path = path_allocator(os.path.join(exp_folder, "eval_metrics.pkl") , is_directory=False)
        with open(path, "wb") as f:
            pickle.dump(custom_metrics, f)

config = (
    NSREQConfig()
    .environment("sina2_train")
    .framework("torch")
    .env_runners(
        num_env_runners = train_runner,
        num_envs_per_env_runner = 1,
        num_cpus_per_env_runner = 1,
        rollout_fragment_length = train_steps_per_runner,
        batch_mode = "truncate_episodes",
        sample_timeout_s = 6000,
    )
    .resources(num_gpus = 1)
    .training(
        gamma = 0,
        train_batch_size = 64,
        lr = 1e-3,
        collect_size = train_steps,
    )
    .evaluation(
        evaluation_interval = 1,
        evaluation_duration = eval_episodes,
        evaluation_duration_unit = "episodes",
        evaluation_sample_timeout_s = 6000,
        evaluation_num_env_runners = eval_episodes,
        evaluation_parallel_to_training = False,
        evaluation_config = {
            "env": "sina2_eval",
            "explore": False,
            "callbacks": MyCallbacks,
        }
    )
    .reporting(keep_per_episode_custom_metrics=True)
    .callbacks(MyCallbacks)
)

config.exploration_config.update({
    "initial_epsilon": 0.5,
    "final_epsilon": 0.1,
    "epsilon_timesteps": 120000,
})

res = tune.Tuner(
    NSREQ,
    param_space=config.to_dict(),
    run_config=air.RunConfig(
        storage_path = exp_folder,
        stop={"training_iteration":20},
        checkpoint_config = air.CheckpointConfig(
            checkpoint_frequency = 1
        )
    )
).fit()

print(res)

with open(os.path.join(exp_folder, "tune_res.pkl"), "wb") as f:
    pickle.dump(res, f)
