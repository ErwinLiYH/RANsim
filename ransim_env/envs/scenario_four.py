from . import WarpperForPtP

class ScenarioFour(WarpperForPtP):
    def init_station(self):
        from ransim import func_slice
        from ransim_utils import utils
        from ransim import station
        from ransim import base_slice
        import os

        # get logger
        log_helper = utils.logging_helper()

        embb_log = log_helper.get_simple_file_logger("embb", os.path.join(self.root_path, f"embb_{self.env_name}.log"))
        urllc_log = log_helper.get_simple_file_logger("urllc", os.path.join(self.root_path, f"urllc_{self.env_name}.log"))
        mmtc_log = log_helper.get_simple_file_logger("mmtc", os.path.join(self.root_path, f"mmtc_{self.env_name}.log"))
        station_log = log_helper.get_simple_file_logger("station", os.path.join(self.root_path, f"station1_{self.env_name}.log"))

        rv_string1 = "ns3::ExponentialRandomVariable[Mean=15]"

        rv_string2 = "ns3::ExponentialRandomVariable[Mean=10]"
        rv_string3 = "ns3::ExponentialRandomVariable[Mean=30]"

        rv_string4 = "ns3::ExponentialRandomVariable[Mean=1]"
        rv_string5 = "ns3::ExponentialRandomVariable[Mean=50]"

        assigner = utils.PortAssigner()

        # eMBB conf
        # max throughtput = 10Mbps+8Mbps, distr=N(5,1.25)+N(4,4)=N(9,5.25), 3theta throughtput(99.73%) = 15.87Mbps
        onoff_configs1 = [[], []]
        for _ in range(20):
            onoff_configs1[0].append(utils.OnOffAppConfig(0.1, 99999, data_rate="0.5Mb/s", port=assigner(), on_time=rv_string1, off_time=rv_string1))
        for _ in range(20, 24):
            onoff_configs1[1].append(utils.OnOffAppConfig(0.1, 99999, data_rate="2Mb/s", port=assigner(), on_time=rv_string1, off_time=rv_string1))

        # uRLLC conf
        # max throughtput = 20Mbps, distr=N(5,3.75), 3theta throughtput(99.73%) = 10.8Mbps
        onoff_configs2 = [[]]
        for _ in range(20):
            onoff_configs2[0].append(utils.OnOffAppConfig(0.1, 99999, data_rate="1Mb/s", port=assigner(), on_time=rv_string2, off_time=rv_string3, packet_size=64))

        # max throughtput = 250Mbps, distr=N(4.9,2.4), 3theta throughtput(99.73%) = 9.547Mbps
        onoff_configs3 = [[]]
        for _ in range(500):
            onoff_configs3[0].append(utils.OnOffAppConfig(0.1, 99999, data_rate="0.5Mb/s", port=assigner(), on_time=rv_string4, off_time=rv_string5, packet_size=128))

        sink_config = utils.SinkAppConfig(0, 99999)

        embb_sla = {
            1: {
                "delay": 0.01,  # 10ms
                "throughput": 5,
            },
            7:{
                "delay": 0.05,  # 50ms
                "throughput": 10,
            }
        }

        urllc_sla = {
            1: {
                "delay": 0.005,  # 5ms
                "throughput": 5,
            }
        }

        mmtc_sla = {
            7: {
                "delay": 0.3,    # 300ms
                "throughput": 0.01, # means no requirement on throughput
            }
        }

        embb_slice = func_slice.EmbbSlice(2, {1:1, 7:1}, embb_sla, 26, onoff_configs1, sink_config, logger=embb_log, unlim_RB=True, RB_resolution=1, unchange_terminate=self.unchange_terminate, min_RB=6, max_RB=40, no_termi=self.no_termi)

        urllc_slice = func_slice.EmbbSlice(1, {1:1}, urllc_sla, 26, onoff_configs2, sink_config, logger=urllc_log, unlim_RB=True, RB_resolution=1, unchange_terminate=self.unchange_terminate, min_RB=6, max_RB=40, no_termi=self.no_termi)

        mmtc_slice = func_slice.EmbbSlice(1, {7:1}, mmtc_sla, 26, onoff_configs3, sink_config, logger=mmtc_log, unlim_RB=True, RB_resolution=1, unchange_terminate=self.unchange_terminate, min_RB=6, max_RB=50, no_termi=self.no_termi)

        base_slice.init_cellId_map(embb_slice.cellId2nodeId, urllc_slice.cellId2nodeId, mmtc_slice.cellId2nodeId)

        env = station.MarlStation(self.env_name, [embb_slice, urllc_slice, mmtc_slice], self.max_step, logger=station_log, warmup_times=5, step_time=0.1, plot=self.plot, root_path=self.root_path)

        return env

def upper(n, a, b, t):
    mean = n*(a/(a+b))
    var = (n*(a/(a+b))*(b/(a+b)))**0.5
    mean_t = mean*t
    var_t = var*t
    upper_t_0 = mean_t+2*var_t
    upper_t_1 = mean_t+3*var_t
    upper_t_2 = mean_t+4*var_t
    print(f"mean: {mean_t}\nvar: {var_t}\nupper: {upper_t_0}\n99.7 upper: {upper_t_1}\n99.99 upper: {upper_t_2}")