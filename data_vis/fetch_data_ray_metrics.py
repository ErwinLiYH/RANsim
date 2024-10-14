# %% [markdown]
# scripts to process data in ray's metrics

# %%
import os
import glob
import pprint

EXP_PATH  = "../exp46/"
with_se = True

# %%
import Kkit

# %%
import pandas as pd
import numpy as np

# %%
metrics_path = glob.glob(os.path.join(EXP_PATH, "evaluation_metrics.pkl_*"))
Kkit.print_list(metrics_path, 4)

# %%
path_dict = {p: int(p.split("_")[-1]) for p in metrics_path}
path_dict = Kkit.sort_dic_by_value(path_dict)
metrics_path = list(path_dict.keys())
Kkit.print_list(metrics_path, 4)

# %%
import re

class RegexDict(dict):
    def __init__(self, *args, **kwargs):
        super(RegexDict, self).__init__(*args, **kwargs)
        for key, value in self.items():
            if isinstance(value, dict):
                self[key] = RegexDict(value)
        self.__abbrdict_keys = list(super(RegexDict, self).keys())
        for i in self.__abbrdict_keys:
            if isinstance(i, str)==False:
                raise TypeError("all keys of AbbrDict must be str")

    def __getitem__(self, key):
        keys = list(super(RegexDict, self).keys())
        filtered = [k for k in keys if re.match(key, k)]
        return {k: super(RegexDict, self).__getitem__(k) for k in filtered}

# %%
metrics = []
for path in metrics_path:
    metrics.append(Kkit.load(path))
pprint.pprint(metrics[0])

# %%
np.mean([np.array(v) for v in RegexDict(metrics[0]["env_runners"]["custom_metrics"])["^reconf_times_agent_"].values()], axis=0)

# %%
reconf_times = []
sla_vio_times = []
reward = []
global_SE = []
for metric in metrics:
    reconf = np.mean([np.array(v) for v in RegexDict(metric["env_runners"]["custom_metrics"])["^reconf_times_agent_"].values()], axis=0)
    sla_vio = np.mean([np.array(v) for v in RegexDict(metric["env_runners"]["custom_metrics"])["^sla_vio_times_agent_"].values()], axis=0)
    rew = metric["env_runners"]["hist_stats"]["episode_reward"]

    reconf_times.append(reconf)
    sla_vio_times.append(sla_vio)
    reward.append(rew)
    try:
        global_SE.append(metric["env_runners"]["custom_metrics"]["global_SE"])
    except:
        with_se = False

# %%
if with_se:
    se_df = pd.DataFrame(global_SE)
    se_df

# %%
sla_df = pd.DataFrame(sla_vio_times)
sla_df

# %%
reconf_df = pd.DataFrame(reconf_times)
reconf_df

# %%
rew_df = pd.DataFrame(reward)
rew_df

# %%
# store all data
sla_df.to_csv(os.path.join(EXP_PATH, "sla_vio_times.csv"), index=False)
reconf_df.to_csv(os.path.join(EXP_PATH, "reconf_times.csv"), index=False)
rew_df.to_csv(os.path.join(EXP_PATH, "reward.csv"), index=False)
if with_se:
    se_df.to_csv(os.path.join(EXP_PATH, "se.csv"), index=False)

