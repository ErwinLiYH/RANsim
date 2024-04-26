from ns import ns
from typing import List
from . import Slice
import logging
import gymnasium as gym
from gymnasium import spaces


class Station(gym.Env):
    def __init__(self, slice_list:List[Slice.BasicRanSlice], step_time=0.05, warmup_times=10, logger:None|logging.Logger = None, enb_distance=5000, ue_range=100):
        
        # Connect callback functions
        ns.Config.Connect("/NodeList/*/ApplicationList/*/$ns3::OnOffApplication/TxWithSeqTsSize", Slice.TxWithSeqTsSize_callback_cpp)
        ns.Config.Connect("/NodeList/*/ApplicationList/*/$ns3::PacketSink/RxWithSeqTsSize", Slice.RxWithSeqTsSize_callback_cpp)

        self.Slice_list = slice_list
        self.N_slices = len(slice_list)
        self.step_time = step_time
        self.warmup_times = warmup_times
        self.logger = logger

        self.action_space = spaces.Box(low=0, high=1, shape=(self.N_slices,), dtype=float)
        # TODO: observation space
        # self.observation_space = 

        # Set location of eNodeBs and UEs
        x = 0
        for i in range(len(self.Slice_list)):
            self.Slice_list[i].set_enb_location(x)
            self.Slice_list[i].set_ue_location(x, ue_range)
            x += enb_distance

        # Log information
        self.log_info()

        # Warmup
        self.warmup()

    def log_info(self):
        if self.logger:
            for i, j in enumerate(self.Slice_list):
                self.logger.info(f"-------------------- Slice {i} --------------------")
                for line in j.get_info().split("\n"):
                    self.logger.info(line)

    def warmup(self):
        self.logger.info(f"Begin warmup for {self.warmup_times} times......")
        ns.Simulator.Stop(ns.Seconds(self.step_time*self.warmup_times))
        ns.Simulator.Run()
        Slice.merge_records()
        for i in self.Slice_list:
            i.stat_report(self.step_time*self.warmup_times)
        Slice.clean_all_records()
        Slice.current_time += self.step_time*self.warmup_times
        self.logger.info("Warmup finished.")

    def _get_obs(self):
        pass

    def _get_info(self):
        pass

    def reset(self):
        self.logger.info("Resetting......")
        Slice.clean_all_records()
        for i in self.Slice_list:
            i.clean_stat()
        self.logger.info("Reset finished.")

    def step(self, action):
        # Do handover actions
        for i, j in enumerate(self.Slice_list):
            j.handoverTo(action[i])
        
        # Run simulation for one step
        ns.Simulator.Stop(ns.Seconds(self.step_time))
        ns.Simulator.Run()

        # Get rewards
        Slice.merge_records()
        rewards = []
        for i in self.Slice_list:
            rewards.append(i.reward(self.step_time))
        Slice.step_records()
        Slice.current_time += self.step_time
        return rewards