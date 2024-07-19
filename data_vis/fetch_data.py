# Fetch data from pkl files and save them to csv files
# For results stored by ransim directly

import pandas as pd
import glob

max_step = 21

group1 = glob.glob('test_logs_0/*.pkl')
group2 = glob.glob('test_logs_1/*.pkl')
group3 = glob.glob('test_logs_2/*.pkl')

groups = [group1, group2, group3]

# pkl file is dict in form of:
# {
#     "plot_data": self.plot_data,
#     "acc_SLA_vio": self.accumulated_SLA_violation,
#     "acc_rew": self.accumulated_reward,
#     "acc_reconfig": self.accumulated_reconfig_times
# }

# create a datafram to store the data
dfs = []
for i in range(len(groups)):
    df = pd.DataFrame(columns=["index", "acc_SLA_vio", "acc_rew", "acc_reconfig"])
    dfs.append(df)

# append data to the dataframe
for e, g in enumerate(groups):
    for i in range(len(g)):
        index = int(g[i].split("/")[-1].split(".")[0].split("_")[-1])
        data = pd.read_pickle(g[i])
        print(data["acc_SLA_vio"])
        print(data["acc_rew"])
        print(data["acc_reconfig"])
        new_row = pd.DataFrame({"index": [index], "acc_SLA_vio": [data["acc_SLA_vio"]], "acc_rew": [data["acc_rew"]], "acc_reconfig": [data["acc_reconfig"]]})
        dfs[e] = pd.concat([dfs[e], new_row], ignore_index=True)


# sort the data by index column
for df in dfs:
    df.sort_values(by=["index"], inplace=True)

# clip the data to max_step
for i in range(len(dfs)):
    dfs[i] = dfs[i].iloc[:max_step, :]

# tranfer index to steps
for df in dfs:
    df["index"] = (df["index"] -1) * 6000

# concatentate the data
all_data = pd.concat(dfs, ignore_index=True)

# generate acc_slavio data with upper bound and lower bound
sla_df = all_data.groupby("index").agg({"acc_SLA_vio": ["mean", lambda x: x.mean() - 1.96 * x.sem(), lambda x: x.mean() + 1.96 * x.sem()]})
sla_df = sla_df.rename(columns={"<lambda_0>": "lower_bound", "<lambda_1>": "upper_bound"})
sla_df.columns = sla_df.columns.droplevel(0)

# generate acc_rew data with upper bound and lower bound
rew_df = all_data.groupby("index").agg({"acc_rew": ["mean", lambda x: x.mean() - 1.96 * x.sem(), lambda x: x.mean() + 1.96 * x.sem()]})
rew_df = rew_df.rename(columns={"<lambda_0>": "lower_bound", "<lambda_1>": "upper_bound"})
rew_df.columns = rew_df.columns.droplevel(0)

# generate acc_reconfig data with upper bound and lower bound
reconfig_df = all_data.groupby("index").agg({"acc_reconfig": ["mean", lambda x: x.mean() - 1.96 * x.sem(), lambda x: x.mean() + 1.96 * x.sem()]})
reconfig_df = reconfig_df.rename(columns={"<lambda_0>": "lower_bound", "<lambda_1>": "upper_bound"})
reconfig_df.columns = reconfig_df.columns.droplevel(0)

# save the data to csv without index
sla_df.to_csv("sla_data.csv", index=False)
rew_df.to_csv("rew_data.csv", index=False)
reconfig_df.to_csv("reconfig_data.csv", index=False)