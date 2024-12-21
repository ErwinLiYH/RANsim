import os
import glob
import pandas as pd
import numpy as np
import Kkit


EXP_PATHS = ["./exps/exp78/", "./exps/exp79/" ,"./exps/exp82/", "./exps/exp81/"]

with_se = True

for EXP_PATH in EXP_PATHS:
    eval_paths = glob.glob(os.path.join(EXP_PATH, "eval_*"))
    eval_path_dict = {p: int(p.split("_")[-1]) for p in eval_paths}
    eval_path_dict = Kkit.sort_dic_by_value(eval_path_dict)
    eval_paths = list(eval_path_dict.keys())

    exceed_times = []

    for eva in eval_paths:
        data_paths = glob.glob(os.path.join(eva, "global_*.pkl"))
        data_path_dict = {p: int(p.split("_")[-1].split(".")[0]) for p in data_paths}
        data_path_dict = Kkit.sort_dic_by_value(data_path_dict)

        for data_path, epoch in data_path_dict.items():
            data = Kkit.load(data_path)
            exceed_times.append({"epoch": epoch, "eval": eval_path_dict[eva], "exceed_times": data["exceed_RB_times"]})

    exceed_times_df = pd.DataFrame(exceed_times)

    result_df = exceed_times_df.pivot(index="epoch", columns="eval", values="exceed_times")

    result_df.to_csv(os.path.join(EXP_PATH, "exceed_times.csv"), index=False)
