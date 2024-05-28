from ns import ns
from . import base_slice
import logging
import gymnasium as gym
from gymnasium import spaces
import numpy as np
import random

from pettingzoo import ParallelEnv

from typing import List
import functools


class SingelSliceStation(gym.Env):
    def __init__(self, slice:base_slice.BasicRanSlice, max_step, step_time=0.05, warmup_times=10, logger:None|logging.Logger = None, ue_range=100):
        
        # Connect callback functions
        ns.Config.Connect("/NodeList/*/ApplicationList/*/$ns3::OnOffApplication/TxWithSeqTsSize", base_slice.TxWithSeqTsSize_callback_cpp)
        ns.Config.Connect("/NodeList/*/ApplicationList/*/$ns3::PacketSink/RxWithSeqTsSize", base_slice.RxWithSeqTsSize_callback_cpp)
        ns.Config.Connect("/NodeList/*/DeviceList/*/LteUeRrc/HandoverEndOk", base_slice.NotifyHandoverEndOkUe_callback_cpp)
        ns.Config.Connect("/NodeList/*/DeviceList/*/LteUeRrc/HandoverStart", base_slice.NotifyHandoverStartUe_callback_cpp)

        self.Slice = slice
        self.step_time = step_time
        self.warmup_times = warmup_times
        self.logger = logger
        self.reset_result = None   # To avoid repeated reset, reset() will set this value to the result of reset, step() will clean this value

        # time limit
        self.max_step = max_step

        # Action space and observation space
        self.action_space = spaces.Discrete(len(slice.candidate_RBs))
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(6,), dtype=float)

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
        
        # Skip the off time of onoff application
        while True:
            obs = self.simple_step()
            if any([i != 0 for i in obs[2:]]):
                break
        
        if self.warmup_times >= 1:
            ns.Simulator.Stop(ns.Seconds(self.step_time*self.warmup_times))
            ns.Simulator.Run()
            base_slice.merge_records()
            self.Slice.stat_report(self.step_time*self.warmup_times, if_log=False)
            base_slice.clean_all_records()
            base_slice.current_time += self.step_time*self.warmup_times
            self.logger.info("Warmup finished.")

    def simple_step(self):
        # Don't do handover actions, just run simulation for one step and get observation
        ns.Simulator.Stop(ns.Seconds(self.step_time))
        ns.Simulator.Run()
        base_slice.merge_records()
        self.Slice.stat_report(self.step_time, if_log=False)
        obs = self.Slice.get_observation(if_log=False)
        base_slice.clean_all_records()
        base_slice.current_time += self.step_time
        return obs

    def _get_info(self):
        return {}

    def reset(self):
        if self.reset_result:
            self.logger.info("Repeated reset, skip this")     # repeated reset, skip
            return self.reset_result
        else:    
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

            self.reset_result = (obs, self._get_info())
            return obs, self._get_info()

    def step(self, action):
        # clean reset result
        if self.reset_result:
            self.reset_result = None

        # Do handover actions
        if action is not None:
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
    
class MultiSliceStation(gym.Env):
    pass

class MarlStation(ParallelEnv):
    def __init__(self, slice_lst:List[base_slice.BasicRanSlice], max_step, step_time=0.05, warmup_times=10, logger:None|logging.Logger = None, enb_distance=5000, ue_range=100):
        
        # Connect callback functions
        ns.Config.Connect("/NodeList/*/ApplicationList/*/$ns3::OnOffApplication/TxWithSeqTsSize", base_slice.TxWithSeqTsSize_callback_cpp)
        ns.Config.Connect("/NodeList/*/ApplicationList/*/$ns3::PacketSink/RxWithSeqTsSize", base_slice.RxWithSeqTsSize_callback_cpp)

        self.Slice_lst = slice_lst
        self.step_time = step_time
        self.warmup_times = warmup_times
        self.logger = logger

        for i in range(len(slice_lst)):
            slice_lst[i].name = f"agent_{i}"
        self.agent_names = [slice.name for slice in slice_lst]
        self.agent_name_map = {slice.name: slice for slice in slice_lst}

        # action space map
        self.action_space_map = {slice.name: spaces.Discrete(len(slice.candidate_RBs)) for slice in slice_lst}

        # observation space
        # [if_changed, n_sent, avg_sent_size, n_recv, avg_recv_size, sum_other_n_sent, sum_other_avg_sent_size, sum_other_n_recv, sum_other_avg_recv_size]
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(11,), dtype=float)

        # time limit
        self.max_step = max_step

        # Set location of eNodeBs and UEs
        loc = 0
        for i, slice in enumerate(self.Slice_lst):
            slice.set_enb_location(loc)
            slice.set_ue_location(loc, ue_range)
            loc += enb_distance

        # Log information
        self.log_info()

        # Warmup
        self.warmup()

    def log_info(self):
        if self.logger:
            for slice in self.Slice_lst:
                self.logger.info(f"-------------------- Slice --------------------")
                for line in slice.get_info().split("\n"):
                    self.logger.info(line)

    @functools.lru_cache(maxsize=None)
    def observation_space(self, agent):
        return self.observation_space

    @functools.lru_cache(maxsize=None)
    def action_space(self, agent: str):
        return self.action_space_map[agent]

    def warmup(self):
        self.logger.info(f"Begin warmup for {self.warmup_times} times......")
        ns.Simulator.Stop(ns.Seconds(self.step_time*self.warmup_times))
        ns.Simulator.Run()
        base_slice.merge_records()
        for slice in self.Slice_lst:
            slice.stat_report(self.step_time*self.warmup_times)
        base_slice.clean_all_records()
        base_slice.current_time += self.step_time*self.warmup_times
        self.logger.info("Warmup finished.")

    def _get_info(self):
        return {name: {} for name in self.agent_names}
    
    def aggregate_obs(data: dict, num_slices: int):
        aggregated_data = {}

        for key, value in data.items():
            sum_col1 = sum(val[0] for k, val in data.items() if k != key)
            sum_col2 = sum(val[1] for k, val in data.items() if k != key)
            sum_col4 = sum(val[3] for k, val in data.items() if k != key)
            
            weighted_avg_col3 = sum(val[2] * val[1] for k, val in data.items() if k != key) / sum_col2 if sum_col2 != 0 else 0
            weighted_avg_col5 = sum(val[4] * val[3] for k, val in data.items() if k != key) / sum_col4 if sum_col4 != 0 else 0

            aggregated_value = np.array([sum_col1, num_slices, sum_col2, weighted_avg_col3, sum_col4, weighted_avg_col5])
            
            concatenated_value = np.concatenate((value, aggregated_value))
            
            aggregated_data[key] = concatenated_value

        return aggregated_data

    def reset(self):
        self.logger.info("Resetting......")

        base_slice.clean_all_records()

        for slice in self.Slice_lst:
            random_RB = random.choice(slice.candidate_RBs)
            slice.handoverTo(random_RB)
            slice.clean_RB_record(random_RB)

        self.warmup()
        for slice in self.Slice_lst:
            slice.clean_stat()

        # Run simulation for one step
        ns.Simulator.Stop(ns.Seconds(self.step_time))
        ns.Simulator.Run()

        obs_raw = {}
        base_slice.merge_records()
        for slice in self.Slice_lst:
            slice.stat_report(self.step_time)
            obs_raw[slice.name] = slice.get_observation()
        base_slice.step_records()
        base_slice.current_time += self.step_time

        obs = self.aggregate_obs(obs_raw, len(self.Slice_lst))

        self.logger.info("Reset finished.")
        return obs, self._get_info()
    
    def step(self, action: dict):
        # Do handover actions
        for slice in self.Slice_lst:
            action = action[slice.name]*slice.RB_resolution + slice.min_RB
            assert action in slice.candidate_RBs, f"Action {action} is not in the action space {slice.candidate_RBs}"
            slice.handoverTo(action)
        
        # Run simulation for one step
        ns.Simulator.Stop(ns.Seconds(self.step_time))
        ns.Simulator.Run()

        # Get terminated
        terminated = False
        if base_slice.step >= self.max_step:
            terminated = True
        terminated = any(slice.get_terminated() for slice in self.Slice_lst)
        terminated = {name: terminated for name in self.agent_names}

        # Get info
        info = self._get_info()

        # Get rewards and local observations
        reward = {}
        obs_raw = {}
        base_slice.merge_records()
        for slice in self.Slice_lst:
            slice.stat_report(self.step_time)
            reward[slice.name] = slice.get_reward()
            obs_raw[slice.name] = slice.get_observation()
        base_slice.step_records()
        base_slice.current_time += self.step_time
        
        obs = self.aggregate_obs(obs_raw, len(self.Slice_lst))

        return obs, reward, terminated, False, info
