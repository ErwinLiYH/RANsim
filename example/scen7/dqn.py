# evaluate the trained policy
from concurrent.futures import ProcessPoolExecutor
from ..utils.expfolder_allocator import path_allocator
import os
import pickle
from pathlib import Path
from ray.rllib.policy.policy import Policy


def work(exp_folder, worker_id):
    from ransim_env.envs import scenario_seven_nosf


    episode_len = 300
    num_of_episodes = 10

    env = scenario_seven_nosf.ScenarioSevenNoSF(
        f"eval", episode_len,
        unchange_terminate = 0,
        root_path=os.path.join(exp_folder, f"eval_{worker_id}"),
        no_termi=True,
        plot = True
    )

    # Use the `from_checkpoint` utility of the Policy class:
    p0 = Policy.from_checkpoint("/home/yl1118/Desktop/RANsim/exps/exp75/DQN_2024-12-08_06-16-04/DQN_ransim_train_d94e1_00000_0_2024-12-08_06-16-04/checkpoint_000079/policies/p0")
    p1 = Policy.from_checkpoint("/home/yl1118/Desktop/RANsim/exps/exp75/DQN_2024-12-08_06-16-04/DQN_ransim_train_d94e1_00000_0_2024-12-08_06-16-04/checkpoint_000079/policies/p0")
    p2 = Policy.from_checkpoint("/home/yl1118/Desktop/RANsim/exps/exp75/DQN_2024-12-08_06-16-04/DQN_ransim_train_d94e1_00000_0_2024-12-08_06-16-04/checkpoint_000079/policies/p1")
    p3 = Policy.from_checkpoint("/home/yl1118/Desktop/RANsim/exps/exp75/DQN_2024-12-08_06-16-04/DQN_ransim_train_d94e1_00000_0_2024-12-08_06-16-04/checkpoint_000079/policies/p2")

    for i in range(num_of_episodes):
        plot_info = []
        obs,info = env.reset()
        action_0 = p0.compute_single_action(obs["agent_0"], explore=False)[0]
        action_1 = p1.compute_single_action(obs["agent_1"], explore=False)[0]
        action_2 = p2.compute_single_action(obs["agent_2"], explore=False)[0]
        action_3 = p3.compute_single_action(obs["agent_3"], explore=False)[0]

        terminate = False
        step = -1
        while not terminate:
            obs, _, termi, _, info = env.step({ "agent_0": action_0, "agent_1": action_1, "agent_2": action_2, "agent_3": action_3 })
            step += 1

            agent_0_info = info["agent_0"]
            agent_1_info = info["agent_1"]
            agent_2_info = info["agent_2"]
            agent_3_info = info["agent_3"]

            plot_info.append({
                "agent_0":{
                    "step": step,
                    "throughput": agent_0_info["throughput"],
                    "RB": agent_0_info["RB"],
                    "changed": agent_0_info["changed_RB"],
                    "SLA_violation": agent_0_info["SLA_violation"]
                },
                "agent_1":{
                    "step": step,
                    "throughput": agent_1_info["throughput"],
                    "RB": agent_1_info["RB"],
                    "changed": agent_1_info["changed_RB"],
                    "SLA_violation": agent_1_info["SLA_violation"]
                },
                "agent_2":{
                    "step": step,
                    "throughput": agent_2_info["throughput"],
                    "RB": agent_2_info["RB"],
                    "changed": agent_2_info["changed_RB"],
                    "SLA_violation": agent_2_info["SLA_violation"]
                },
                "agent_3":{
                    "step": step,
                    "throughput": agent_3_info["throughput"],
                    "RB": agent_3_info["RB"],
                    "changed": agent_3_info["changed_RB"],
                    "SLA_violation": agent_3_info["SLA_violation"]
                }
            })

            terminate = all(termi.values())
            action_0 = p0.compute_single_action(obs["agent_0"], explore=False)[0]
            action_1 = p1.compute_single_action(obs["agent_1"], explore=False)[0]
            action_2 = p2.compute_single_action(obs["agent_2"], explore=False)[0]
            action_3 = p3.compute_single_action(obs["agent_3"], explore=False)[0]

        with open(os.path.join(exp_folder, f"eval_{worker_id}", f"plot_info_{i}.pkl"), "wb") as f:
            pickle.dump(plot_info, f)
    return True

exp_folder = path_allocator("exps/exp", "")
exp_folder = Path(exp_folder).resolve().as_posix()
print("experiment result path:", exp_folder)

num_workers = 10
with ProcessPoolExecutor(max_workers=num_workers) as executor:
    futures = [executor.submit(work, exp_folder, i) for i in range(num_workers)]

print("All workers are done.")
