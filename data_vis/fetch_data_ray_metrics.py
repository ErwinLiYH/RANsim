import os
import glob
import Kkit
import pandas as pd
import numpy as np
import re


EXP_PATHS = ["./exps/exp78/", "./exps/exp79/" ,"./exps/exp82/", "./exps/exp81/"]
with_se = True

class RegexDict(dict):
    def __init__(self, *args, **kwargs):
        super(RegexDict, self).__init__(*args, **kwargs)
        for key, value in self.items():
            if isinstance(value, dict):
                self[key] = RegexDict(value)
        self.__abbrdict_keys = list(super(RegexDict, self).keys())
        for i in self.__abbrdict_keys:
            if isinstance(i, str) == False:
                raise TypeError("all keys of AbbrDict must be str")

    def __getitem__(self, key):
        keys = list(super(RegexDict, self).keys())
        filtered = [k for k in keys if re.match(key, k)]
        return {k: super(RegexDict, self).__getitem__(k) for k in filtered}


for EXP_PATH in EXP_PATHS:
    metrics_path = glob.glob(os.path.join(EXP_PATH, "evaluation_metrics.pkl_*"))

    path_dict = {p: int(p.split("_")[-1]) for p in metrics_path}
    path_dict = Kkit.sort_dic_by_value(path_dict)
    metrics_path = list(path_dict.keys())

    metrics = []
    for path in metrics_path:
        metrics.append(Kkit.load(path))

    reconf_times = []
    sla_vio_times = []
    reward = []
    global_SE = []

    for metric in metrics:
        reconf = np.mean(
            [np.array(v) for v in RegexDict(metric["env_runners"]["custom_metrics"])["^reconf_times_agent_"].values()],
            axis=0,
        )
        sla_vio = np.mean(
            [np.array(v) for v in RegexDict(metric["env_runners"]["custom_metrics"])["^sla_vio_times_agent_"].values()],
            axis=0,
        )
        rew = metric["env_runners"]["hist_stats"]["episode_reward"]

        reconf_times.append(reconf)
        sla_vio_times.append(sla_vio)
        reward.append(rew)
        try:
            global_SE.append(metric["env_runners"]["custom_metrics"]["global_SE"])
        except:
            with_se = False

    sla_df = pd.DataFrame(sla_vio_times)
    reconf_df = pd.DataFrame(reconf_times)
    rew_df = pd.DataFrame(reward)

    sla_df.to_csv(os.path.join(EXP_PATH, "sla_vio_times.csv"), index=False)
    reconf_df.to_csv(os.path.join(EXP_PATH, "reconf_times.csv"), index=False)
    rew_df.to_csv(os.path.join(EXP_PATH, "reward.csv"), index=False)

    if with_se and global_SE:
        se_df = pd.DataFrame(global_SE)
        se_df.to_csv(os.path.join(EXP_PATH, "se.csv"), index=False)
