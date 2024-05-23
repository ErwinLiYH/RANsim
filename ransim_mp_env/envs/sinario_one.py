from . import MultiProcessWrapperForGym

class SinarioOne(MultiProcessWrapperForGym):
    # Simplest sinario: constant traffic, one slice
    def _worker(self):
        # Make the environment in other process since ns3 can't be re-initialized in the same process
        from ransim import func_slice
        from ransim import base_slice
        from ransim import utils
        from ransim import station


        log_helper = utils.logging_helper()
        embb_log = log_helper.get_simple_file_logger("embb", f"embb_{self.env_name}.log")
        station_log = log_helper.get_simple_file_logger("station", f"station_{self.env_name}.log")

        onoff_config1 = utils.OnOffAppConfig(0.1, 99999, data_rate="5Mb/s")
        onoff_config2 = utils.OnOffAppConfig(0.1, 99999, data_rate="5Mb/s", port=49154)
        onoff_config3 = utils.OnOffAppConfig(0.1, 99999, data_rate="20Mb/s", port=49155)

        sink_config = utils.SinkAppConfig(0, 99999)

        base_slice.InitRemoteSinkApp(sink_config)

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

        embb_slice = func_slice.EmbbSlice(3, {1:2, 7:1}, embb_sla, 26, [onoff_config1, onoff_config2, onoff_config3], sink_config, logger=embb_log, unlim_RB=True, RB_resolution=1, unchange_terminate=self.unchange_terminate)

        env = station.SingelSliceStation(embb_slice, self.max_step, logger=station_log, warmup_times=5, step_time=0.1)
        
        # Must put the observation_space and action_space to the result_queue
        self.result_queue.put(env.observation_space)
        self.result_queue.put(env.action_space)

        # Must add a loop to keep the worker running and waiting for the command
        while True:
            command, para = self.action_queue.get()
            if command == 'reset':
                self.result_queue.put(env.reset())
            elif command == 'step':
                self.result_queue.put(env.step(para))
