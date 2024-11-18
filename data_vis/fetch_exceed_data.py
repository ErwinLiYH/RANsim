# %%
import os
import glob
import pprint

EXP_PATH  = "../exps/exp55/"
with_se = True

# %%
import Kkit

# %%
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# %%
eval_paths = glob.glob(os.path.join(EXP_PATH, "eval_*"))
eval_path_dict = {p: int(p.split("_")[-1]) for p in eval_paths}
eval_path_dict = Kkit.sort_dic_by_value(eval_path_dict)
eval_paths = list(eval_path_dict.keys())
Kkit.print_list(eval_paths, 4)

# %%
exceed_times = [] #{"epoch": int, "exceed_times":list}
for eva in eval_paths:
    data_paths = glob.glob(os.path.join(eva, "global_*.pkl"))
    data_path_dict = {p: int(p.split("_")[-1].split(".")[0]) for p in data_paths}
    data_path_dict = Kkit.sort_dic_by_value(data_path_dict)
    for  data_path, epoch in data_path_dict.items():
        data = Kkit.load(data_path)
        exceed_times.append({"epoch": epoch, "eval": eval_path_dict[eva], "exceed_times": data["exceed_RB_times"]})
# %%
# plot exceed times, plot average exceed times across all evals
exceed_times_df = pd.DataFrame(exceed_times)
exceed_times_df.groupby("epoch")["exceed_times"].mean().plot()

# %%
# change to form like:
# eval1 eval2 eval3 ...
result_df = exceed_times_df.pivot(index="epoch", columns="eval", values="exceed_times")
result_df.to_csv(os.path.join(EXP_PATH, "exceed_times.csv"), index=False)