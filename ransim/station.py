from ns import ns
from . import base_slice
import logging
import gymnasium as gym
from gymnasium import spaces
import numpy as np
import random


class SingelSliceStation(gym.Env):
    def __init__(self, slice:base_slice.BasicRanSlice, max_step, step_time=0.05, warmup_times=10, logger:None|logging.Logger = None, enb_distance=5000, ue_range=100):
        
        # Connect callback functions
        ns.Config.Connect("/NodeList/*/ApplicationList/*/$ns3::OnOffApplication/TxWithSeqTsSize", base_slice.TxWithSeqTsSize_callback_cpp)
        ns.Config.Connect("/NodeList/*/ApplicationList/*/$ns3::PacketSink/RxWithSeqTsSize", base_slice.RxWithSeqTsSize_callback_cpp)

        self.Slice = slice
        self.step_time = step_time
        self.warmup_times = warmup_times
        self.logger = logger

        # time limit
        self.max_step = max_step

        # Action space and observation space
        self.action_space = spaces.Discrete(len(slice.candidate_RBs))
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(5,), dtype=float)

        # Set location of eNodeBs and UEs
        self.Slice.set_enb_location(0)
        self.Slice.set_ue_location(0, ue_range)

        # Log information
        self.log_info()

        # Warmup
        self.warmup()

    def log_info(self):
        if self.logger:
            self.logger.info(f"-------------------- Slice --------------------")
            for line in self.Slice.get_info().split("\n"):
                self.logger.info(line)

    def warmup(self):
        self.logger.info(f"Begin warmup for {self.warmup_times} times......")
        ns.Simulator.Stop(ns.Seconds(self.step_time*self.warmup_times))
        ns.Simulator.Run()
        base_slice.merge_records()
        self.Slice.stat_report(self.step_time*self.warmup_times)
        base_slice.clean_all_records()
        base_slice.current_time += self.step_time*self.warmup_times
        self.logger.info("Warmup finished.")

    def _get_info(self):
        return {}

    def reset(self):
        self.logger.info("Resetting......")

        base_slice.clean_all_records()

        random_RB = random.choice(self.Slice.candidate_RBs)

        self.Slice.handoverTo(random_RB)

        self.Slice.clean_RB_record(random_RB)

        self.warmup()
        self.Slice.clean_stat()

        # Run simulation for one step
        ns.Simulator.Stop(ns.Seconds(self.step_time))
        ns.Simulator.Run()

        base_slice.merge_records()
        self.Slice.stat_report(self.step_time)
        obs = self.Slice.get_observation()
        base_slice.step_records()
        base_slice.current_time += self.step_time

        self.logger.info("Reset finished.")
        return obs, self._get_info()

    def step(self, action):
        # Do handover actions
        action = action*self.Slice.RB_resolution + self.Slice.min_RB
        assert action in self.Slice.candidate_RBs, f"Action {action} is not in the action space {self.Slice.candidate_RBs}"
        self.Slice.handoverTo(action)
        
        # Run simulation for one step
        ns.Simulator.Stop(ns.Seconds(self.step_time))
        ns.Simulator.Run()

        # Get terminated
        terminated = False
        if base_slice.step >= self.max_step:
            terminated = True
        if self.Slice.get_terminated():
            terminated = True

        # Get info
        info = self._get_info()

        # Get rewards and local observations
        base_slice.merge_records()
        self.Slice.stat_report(self.step_time)
        reward = self.Slice.get_reward()
        obs = self.Slice.get_observation()
        base_slice.step_records()
        base_slice.current_time += self.step_time
        
        # return [observation, reward, terminated, truncated, info] according to gym.Env v26
        # reference: https://gymnasium.farama.org/api/env/#methods
        # terminated and truncated reference: https://gymnasium.farama.org/tutorials/gymnasium_basics/handling_time_limits/
        return obs, reward, terminated, False, info