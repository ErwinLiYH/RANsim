from . import WarpperForGym

class SinarioTwo(WarpperForGym):
    def init_station(self):
        from ransim import func_slice
        from ransim import utils
        from ransim import station


        log_helper = utils.logging_helper()
        embb_log = log_helper.get_simple_file_logger("embb", f"embb_{self.env_name}.log")
        station_log = log_helper.get_simple_file_logger("station", f"station_{self.env_name}.log")

        rv_string = "ns3::NormalRandomVariable[Mean=15|Variance=5|Bound=10]"

        onoff_configs = [[], []]
        for i in range(6):
            onoff_configs[0].append(utils.OnOffAppConfig(0.1, 99999, data_rate="3Mb/s", port=49153+i, on_time=rv_string, off_time=rv_string))
        for i in range(6, 12):
            onoff_configs[1].append(utils.OnOffAppConfig(0.1, 99999, data_rate="3Mb/s", port=49153+i, on_time=rv_string, off_time=rv_string))

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

        embb_slice = func_slice.EmbbSlice(2, {1:1, 7:1}, embb_sla, 26, onoff_configs, sink_config, logger=embb_log, unlim_RB=True, RB_resolution=1, unchange_terminate=self.unchange_terminate)

        env = station.SingelSliceStation(embb_slice, self.max_step, logger=station_log, warmup_times=5, step_time=0.1)

        return env