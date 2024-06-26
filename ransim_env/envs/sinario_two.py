from . import WarpperForGym
import os

class SinarioTwo(WarpperForGym):
    def init_station(self):
        from ransim import func_slice
        from ransim import utils
        from ransim import station
        from ransim import base_slice


        log_helper = utils.logging_helper()
        embb_log = log_helper.get_simple_file_logger("embb", os.path.join(self.root_path, f"embb_{self.env_name}.log"))
        station_log = log_helper.get_simple_file_logger("station", os.path.join(self.root_path, f"station_{self.env_name}.log"))

        rv_string = "ns3::NormalRandomVariable[Mean=15|Variance=5|Bound=10]"

        onoff_configs = [[], []]
        for i in range(10):
            onoff_configs[0].append(utils.OnOffAppConfig(0.1, 99999, data_rate="1Mb/s", port=49153+i, on_time=rv_string, off_time=rv_string))
        for i in range(10, 16):
            onoff_configs[1].append(utils.OnOffAppConfig(0.1, 99999, data_rate="5Mb/s", port=49153+i, on_time=rv_string, off_time=rv_string))

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

        embb_slice = func_slice.EmbbSlice(2, {1:1, 7:1}, embb_sla, 26, onoff_configs, sink_config, logger=embb_log, unlim_RB=True, RB_resolution=1, unchange_terminate=self.unchange_terminate, min_RB=6, max_RB=40, no_termi=self.no_termi)

        base_slice.init_cellId_map(embb_slice.cellId2nodeId)

        env = station.SingelSliceStation(self.env_name, embb_slice, self.max_step, logger=station_log, warmup_times=5, step_time=0.1, plot=self.plot, root_path=self.root_path)

        return env