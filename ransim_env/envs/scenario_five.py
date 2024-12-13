from . import WarpperForPtP

class SinarioFive(WarpperForPtP):
    def init_station(self):
        from ransim import func_slice
        from ransim_utils import utils
        from ransim import station
        from ransim import base_slice
        import os

        # get logger
        log_helper = utils.logging_helper()

        embb_log1 = log_helper.get_simple_file_logger("embb1", os.path.join(self.root_path, f"embb1_{self.env_name}.log"))
        embb_log2 = log_helper.get_simple_file_logger("embb2", os.path.join(self.root_path, f"embb2_{self.env_name}.log"))
        embb_log3 = log_helper.get_simple_file_logger("embb3", os.path.join(self.root_path, f"embb3_{self.env_name}.log"))
        station_log = log_helper.get_simple_file_logger("station1", os.path.join(self.root_path, f"station1_{self.env_name}.log"))

        rv_string = "ns3::ExponentialRandomVariable[Mean=15]"

        assigner = utils.PortAssigner()

        # max throughtput = 10Mbps+8Mbps, distr=N(5,1.25)+N(4,4)=N(9,5.25), 3theta throughtput(99.73%) = 15.87Mbps
        onoff_configs1 = [[], []]
        for _ in range(20):
            onoff_configs1[0].append(utils.OnOffAppConfig(0.1, 99999, data_rate="0.5Mb/s", port=assigner(), on_time=rv_string, off_time=rv_string))
        for _ in range(10, 14):
            onoff_configs1[1].append(utils.OnOffAppConfig(0.1, 99999, data_rate="2Mb/s", port=assigner(), on_time=rv_string, off_time=rv_string))

        # max throughtput = 10Mbps+8Mbps, distr=N(5,1.25)+N(4,4)=N(9,5.25), 3theta throughtput(99.73%) = 15.87Mbps
        onoff_configs2 = [[], []]
        for _ in range(20):
            onoff_configs2[0].append(utils.OnOffAppConfig(0.1, 99999, data_rate="0.5Mb/s", port=assigner(), on_time=rv_string, off_time=rv_string))
        for _ in range(10, 14):
            onoff_configs2[1].append(utils.OnOffAppConfig(0.1, 99999, data_rate="2Mb/s", port=assigner(), on_time=rv_string, off_time=rv_string))

        # max throughtput = 10Mbps+8Mbps, distr=N(5,1.25)+N(4,4)=N(9,5.25), 3theta throughtput(99.73%) = 15.87Mbps
        onoff_configs3 = [[], []]
        for _ in range(20):
            onoff_configs3[0].append(utils.OnOffAppConfig(0.1, 99999, data_rate="0.5Mb/s", port=assigner(), on_time=rv_string, off_time=rv_string))
        for _ in range(10, 14):
            onoff_configs3[1].append(utils.OnOffAppConfig(0.1, 99999, data_rate="2Mb/s", port=assigner(), on_time=rv_string, off_time=rv_string))

        sink_config = utils.SinkAppConfig(0, 99999)

        embb_sla = {
            1: {
                "delay": 0.05,      # 50 ms
                "throughput": 5,
            },
            7:{
                "delay": 0.1,     # 100 ms
                "throughput": 10,
            }
        }

        embb_slice1 = func_slice.EmbbSlice(2, {1:1, 7:1}, embb_sla, 26, onoff_configs1, sink_config, logger=embb_log1, unlim_RB=True, RB_resolution=1, unchange_terminate=self.unchange_terminate, min_RB=6, max_RB=40, no_termi=self.no_termi)

        embb_slice2 = func_slice.EmbbSlice(2, {1:1, 7:1}, embb_sla, 26, onoff_configs2, sink_config, logger=embb_log2, unlim_RB=True, RB_resolution=1, unchange_terminate=self.unchange_terminate, min_RB=6, max_RB=40, no_termi=self.no_termi)

        embb_slice3 = func_slice.EmbbSlice(2, {1:1, 7:1}, embb_sla, 26, onoff_configs3, sink_config, logger=embb_log3, unlim_RB=True, RB_resolution=1, unchange_terminate=self.unchange_terminate, min_RB=6, max_RB=40, no_termi=self.no_termi)

        base_slice.init_cellId_map(embb_slice1.cellId2nodeId, embb_slice2.cellId2nodeId, embb_slice3.cellId2nodeId)

        env = station.MarlStation(self.env_name, [embb_slice1, embb_slice2, embb_slice3], self.max_step, logger=station_log, warmup_times=5, step_time=0.1, plot=self.plot, root_path=self.root_path, max_RB=30)

        return env