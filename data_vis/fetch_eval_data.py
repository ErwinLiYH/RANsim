import os
import pickle
import pandas as pd


EXP_PATHS = ["exps/exp86", "exps/exp87", "exps/exp88", "exps/exp89"]

for exp_idx, exp_path in enumerate(EXP_PATHS):
    acc_sla = {}
    acc_reconf = {}
    average_se = {}

    eval_dirs = [d for d in os.listdir(exp_path) if os.path.isdir(os.path.join(exp_path, d)) and d.startswith("eval_")]

    for eval_dir in eval_dirs:
        _accu_sla = 0
        _accu_reconf = 0

        eval_path = os.path.join(exp_path, eval_dir)
        sla_cumulative = []
        reconf_cumulative = []
        se_values = []

        iteration_files = [f for f in os.listdir(eval_path) if f.startswith("plot_info_") and f.endswith(".pkl")]
        iteration_files = sorted(iteration_files)
        all_iteration_data = []

        for iteration_file in iteration_files:
            with open(os.path.join(eval_path, iteration_file), "rb") as f:
                x = pickle.load(f)
                all_iteration_data += x

        for step_data in all_iteration_data:
            _accu_sla += sum(agent_info["SLA_violation"] for agent_info in step_data.values())
            sla_cumulative.append(_accu_sla)

            _accu_reconf += sum(int(agent_info["changed"]) for agent_info in step_data.values())
            reconf_cumulative.append(_accu_reconf)

            total_throughput = sum(agent_info["throughput"] for agent_info in step_data.values())
            total_rb = sum(agent_info["RB"] for agent_info in step_data.values())
            se_values.append((total_throughput*1000000) / (180000 * total_rb) if total_rb > 0 else 0)

        acc_sla[eval_dir] = sla_cumulative
        acc_reconf[eval_dir] = reconf_cumulative
        average_se[eval_dir] = se_values

    accu_sla_df = pd.DataFrame(acc_sla)
    accu_reconf_df = pd.DataFrame(acc_reconf)
    average_se_df = pd.DataFrame(average_se)

    accu_sla_df.to_csv(os.path.join(exp_path, "accu_sla.csv"), index=False)
    accu_reconf_df.to_csv(os.path.join(exp_path, "accu_reconf.csv"), index=False)
    average_se_df.to_csv(os.path.join(exp_path, "average_se.csv"), index=False)
