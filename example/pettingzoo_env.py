# This file is used to provide an example of how to create a pettingzoo environment.
# Each process can only have *one* environment (ns3 limitation).

from ransim import func_slice
from ransim_utils import utils
from ransim import station
from ransim import base_slice
import random

# get logger
log_helper = utils.logging_helper()

embb_log1 = log_helper.get_simple_file_logger("embb1", "embb1.log")
embb_log2 = log_helper.get_simple_file_logger("embb2", "embb2.log")
embb_log3 = log_helper.get_simple_file_logger("embb3", "embb3.log")
station_log = log_helper.get_simple_file_logger("station1", "station1.log")

rv_string = "ns3::NormalRandomVariable[Mean=15|Variance=5|Bound=10]"

assigner = utils.PortAssigner()

onoff_configs1 = [[], []]
for _ in range(10):
    onoff_configs1[0].append(utils.OnOffAppConfig(0.1, 99999, data_rate="1Mb/s", port=assigner(), on_time=rv_string, off_time=rv_string))
for _ in range(10, 14):
    onoff_configs1[1].append(utils.OnOffAppConfig(0.1, 99999, data_rate="5Mb/s", port=assigner(), on_time=rv_string, off_time=rv_string))

onoff_configs2 = [[], []]
for _ in range(10):
    onoff_configs2[0].append(utils.OnOffAppConfig(0.1, 99999, data_rate="1Mb/s", port=assigner(), on_time=rv_string, off_time=rv_string))
for _ in range(10, 12):
    onoff_configs2[1].append(utils.OnOffAppConfig(0.1, 99999, data_rate="5Mb/s", port=assigner(), on_time=rv_string, off_time=rv_string))

onoff_configs3 = [[], []]
for _ in range(10):
    onoff_configs3[0].append(utils.OnOffAppConfig(0.1, 99999, data_rate="1Mb/s", port=assigner(), on_time=rv_string, off_time=rv_string))
for _ in range(10, 12):
    onoff_configs3[1].append(utils.OnOffAppConfig(0.1, 99999, data_rate="5Mb/s", port=assigner(), on_time=rv_string, off_time=rv_string))

sink_config = utils.SinkAppConfig(0, 99999)

embb_sla = {
    1: {
        "delay": 0.01,
        "throughput": 5,
    },
    7:{
        "delay": 0.05,
        "throughput": 10,
    }
}

embb_slice1 = func_slice.EmbbSlice(2, {1:1, 7:1}, embb_sla, 26, onoff_configs1, sink_config, logger=embb_log1, unlim_RB=True, RB_resolution=1, unchange_terminate=0, min_RB=6, max_RB=40, no_termi=True)

embb_slice2 = func_slice.EmbbSlice(2, {1:1, 7:1}, embb_sla, 26, onoff_configs2, sink_config, logger=embb_log2, unlim_RB=True, RB_resolution=1, unchange_terminate=0, min_RB=6, max_RB=40, no_termi=True)

embb_slice3 = func_slice.EmbbSlice(2, {1:1, 7:1}, embb_sla, 26, onoff_configs3, sink_config, logger=embb_log3, unlim_RB=True, RB_resolution=1, unchange_terminate=0, min_RB=6, max_RB=40, no_termi=True)

base_slice.init_cellId_map(embb_slice1.cellId2nodeId, embb_slice2.cellId2nodeId, embb_slice3.cellId2nodeId)

env = station.MarlStation("MarlStation", [embb_slice1, embb_slice2, embb_slice3], 3000, logger=station_log, warmup_times=5, step_time=0.1, plot=True, root_path=".")

print(type(env))

env.reset()

for _ in range(100):
    action = {slice.name: random.randint(0, env.action_space(slice.name).n - 1) for slice in env.Slice_lst}
    observations, rewards, terminations, truncations, infos = env.step(action)

env.reset()

for _ in range(1000):
    action = {slice.name: random.randint(0, env.action_space(slice.name).n - 1) for slice in env.Slice_lst}
    observations, rewards, terminations, truncations, infos = env.step(action)

env.reset()

print("finished! check log files (embb.log, station.log) and plot files in current directory")