from ray.rllib.algorithms.callbacks import DefaultCallbacks
from ray.rllib.utils.metrics import ENV_RUNNER_RESULTS
from ray.rllib.evaluation.episode_v2 import EpisodeV2

from .expfolder_allocator import path_allocator

import scipy
import numpy as np

import pickle
import os
import re

class MaPrjCallbacks(DefaultCallbacks):
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
        episode.user_data["global_SEs"] = []
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
        total_throughput = 0
        total_RB = 0
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

            total_throughput += episode.last_info_for(a)["throughput"]
            total_RB += episode.last_info_for(a)["RB"]

        episode.user_data["global_SEs"].append((total_throughput*1000000) / (180000 * total_RB))

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
        episode.custom_metrics["global_SE"] = sum(episode.user_data["global_SEs"])/episode.length

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

        custom_metrics["global_SE_mean"] = np.mean(custom_metrics["global_SE"])
        custom_metrics["global_SE_var"] = np.var(custom_metrics["global_SE"])
        custom_metrics["global_SE_sem"] = scipy.stats.sem(custom_metrics["global_SE"])
        
        episode_rew = evaluation_metrics[ENV_RUNNER_RESULTS]["hist_stats"]["episode_reward"]
        custom_metrics["rew_mean_episode"] = np.mean(episode_rew)
        custom_metrics["rew_var_episode"] = np.var(episode_rew)
        custom_metrics["rew_sem_episode"] = scipy.stats.sem(episode_rew)
        
        policies = list(evaluation_metrics[ENV_RUNNER_RESULTS]["policy_reward_max"].keys())
        for p in policies:
            custom_metrics[f"rew_mean_{p}"] = np.mean(evaluation_metrics[ENV_RUNNER_RESULTS]["hist_stats"][f"policy_{p}_reward"])
            custom_metrics[f"rew_var_{p}"] = np.var(evaluation_metrics[ENV_RUNNER_RESULTS]["hist_stats"][f"policy_{p}_reward"])
            custom_metrics[f"rew_sem_{p}"] = scipy.stats.sem(evaluation_metrics[ENV_RUNNER_RESULTS]["hist_stats"][f"policy_{p}_reward"])

        exp_folder = self.exp_folder
        path = path_allocator(os.path.join(exp_folder, "evaluation_metrics.pkl") , is_directory=False)
        with open(path, "wb") as f:
            pickle.dump(evaluation_metrics, f)