# ray libs
import ray
from ray import tune, air
from ray.rllib.evaluation.episode_v2 import EpisodeV2
from ray.tune.registry import register_env
from ray.rllib.algorithms.callbacks import DefaultCallbacks
from ray.rllib.utils.metrics import ENV_RUNNER_RESULTS
from ray.rllib.env.wrappers.pettingzoo_env import ParallelPettingZooEnv
from ray.rllib.connectors.env_to_module import FlattenObservations

# ransim envs
from ransim_env.envs import sinario_three

# ESEQR config and algorithm
from rllib_nsreq import NSREQConfig, NSREQ

# for stats calculation
import scipy
import numpy as np

# control experiment result path
from ..utils.expfolder_allocator import path_allocator

# general python libs
import os
import pickle
from pathlib import Path
import re
import pprint

from ..utils.ray_callbacks import MaPrjCallbacks


eval_episodes = 10

episode_len = 300

collect_steps_per_runner = 300
train_runner = 20
collect_steps = collect_steps_per_runner * train_runner

exp_folder = path_allocator("exp", "")
exp_folder = Path(exp_folder).resolve().as_posix()
print("experiment result path:", exp_folder)

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

class MyCallbacks(MaPrjCallbacks):
    def __init__(self):
        super().__init__()
        self.exp_folder = exp_folder

config = (
    NSREQConfig()
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
        train_batch_size = collect_steps,
        lr = 1e-3,
        # collect_size = collect_steps,
        # train_times_per_step = 0.5,
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

config.exploration_config.update({
    "initial_epsilon": 0.9,
    "final_epsilon": 0.2,
    "epsilon_timesteps": 160000,
})

# config.replay_buffer_config.update({
#     "capacity": 6000*20,
# })

config["num_sgd_iter"] = 5
config["sgd_minibatch_size"] = 64

res = tune.Tuner(
    NSREQ,
    param_space=config.to_dict(),
    run_config=air.RunConfig(
        storage_path = exp_folder,
        stop={"training_iteration":80},
        checkpoint_config = air.CheckpointConfig(
            checkpoint_frequency = 1
        )
    )
).fit()

print(res)
print("------------------------------- result -------------------------------")
pprint.pprint(res._results)
