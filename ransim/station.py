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

import os
import copy
import warnings


class SingelSliceStation(gym.Env):
    def __init__(self, env_name:str, slice:base_slice.BasicRanSlice, max_step, step_time=0.05, warmup_times=10, logger:None|logging.Logger = None, ue_range=100, plot=False, root_path:str="./"):
        
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
        self.is_ready = False      # To avoid repeated warmup, warmup() will set this value to True, step() will set this value to False

        # time limit
        self.max_step = max_step

        # episode
        self.episode = 0

        # polt args
        self.plot = plot
        self.env_name = env_name
        self.root_path = root_path

        # Action space and observation space
        self.action_space = spaces.Discrete(len(slice.candidate_RBs))
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(3,5), dtype=float)

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
        if self.is_ready == False:
            self.logger.info(f"Begin warmup for {self.warmup_times} times......")
            
            # Skip the off time of onoff application
            n_skip_times = -1
            while True:
                obs = self.simple_step()
                n_skip_times += 1
                if any([i != 0 for i in obs[:, -3]]):
                    break
            if n_skip_times > 0:
                self.logger.info(f"Skip {n_skip_times} times to avoid off time of onoff application.")
            
            if self.warmup_times >= 1:
                ns.Simulator.Stop(ns.Seconds(self.step_time*(self.warmup_times-1)))  # -1 here because it runs will run one step when check off time
                ns.Simulator.Run()
                base_slice.merge_records()
                self.Slice.stat_report(self.step_time*(self.warmup_times-1), if_log=False)
                base_slice.clean_all_records()
                base_slice.current_time += self.step_time*self.warmup_times
            
            self.logger.info("Warmup finished.")
            self.is_ready = True
        else:
            self.logger.info("Repeated warmup, skip this")

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

            # Plot last episode
            if self.episode != 0 and self.plot:
                self.Slice.plot(os.path.join(self.root_path, f"{self.env_name}_{self.episode}.png"))
                self.Slice.clean_plot_data(os.path.join(self.root_path, f"{self.env_name}_{self.episode}.pkl"))
            else:
                self.Slice.clean_plot_data() # seems not needed
            self.episode += 1

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
            info = self.Slice.get_rl_info()
            base_slice.step_records()
            base_slice.clean_all_buffer_record()
            base_slice.current_time += self.step_time

            self.logger.info("Reset finished.")

            self.reset_result = (obs, info)
            return obs, info

    def step(self, action):
        # clean reset result
        if self.reset_result:
            self.reset_result = None

        # clean is_ready
        if self.is_ready:
            self.is_ready = False

        # Do handover actions
        if action is not None:
            if self.Slice.action_process_fn:
                action = self.Slice.action_process_fn(action)
            else:
                action = action*self.Slice.RB_resolution + self.Slice.min_RB
            assert action in self.Slice.candidate_RBs, f"Action {action} is not in the action space {self.Slice.candidate_RBs}"
            self.Slice.handoverTo(action)
        
        # Run simulation for one step
        ns.Simulator.Stop(ns.Seconds(self.step_time))
        ns.Simulator.Run()

        # Get info
        # info = self._get_info()

        # Get rewards and local observations and info
        base_slice.merge_records()
        self.Slice.stat_report(self.step_time)
        reward = self.Slice.get_reward()
        obs = self.Slice.get_observation()
        info = self.Slice.get_rl_info()

        # Get terminated
        terminated = False
        if base_slice.step >= self.max_step:
            terminated = True
        if self.Slice.get_terminated():
            terminated = True

        base_slice.step_records()
        base_slice.clean_all_buffer_record()
        base_slice.current_time += self.step_time
        
        # return [observation, reward, terminated, truncated, info] according to gym.Env v26
        # reference: https://gymnasium.farama.org/api/env/#methods
        # terminated and truncated reference: https://gymnasium.farama.org/tutorials/gymnasium_basics/handling_time_limits/
        return obs, reward, terminated, False, info
    
class MultiSliceStation(gym.Env):
    pass

class MarlStation(ParallelEnv):
    def __init__(self, env_name:str, slice_lst:List[base_slice.BasicRanSlice], max_step, step_time=0.05, warmup_times=10, logger:None|logging.Logger = None, enb_distance=5000, ue_range=100, plot=False, root_path:str="./", max_RB=100):
        
        # Connect callback functions
        ns.Config.Connect("/NodeList/*/ApplicationList/*/$ns3::OnOffApplication/TxWithSeqTsSize", base_slice.TxWithSeqTsSize_callback_cpp)
        ns.Config.Connect("/NodeList/*/ApplicationList/*/$ns3::PacketSink/RxWithSeqTsSize", base_slice.RxWithSeqTsSize_callback_cpp)
        ns.Config.Connect("/NodeList/*/DeviceList/*/LteUeRrc/HandoverEndOk", base_slice.NotifyHandoverEndOkUe_callback_cpp)
        ns.Config.Connect("/NodeList/*/DeviceList/*/LteUeRrc/HandoverStart", base_slice.NotifyHandoverStartUe_callback_cpp)

        self.Slice_lst = slice_lst
        self.step_time = step_time
        self.warmup_times = warmup_times
        self.max_RB = max_RB
        self.logger = logger

        self.reset_result = None   # To avoid repeated reset, reset() will set this value to the result of reset, step() will clean this value
        self.is_ready = False      # To avoid repeated warmup, warmup() will set this value to True, step() will set this value to False

        # time limit
        self.max_step = max_step

        # episode
        self.episode = 0

        # polt args
        self.plot = plot
        self.env_name = env_name
        self.root_path = root_path

        # ---------- Pettingzoo parameters ----------
        for i in range(len(slice_lst)):
            slice_lst[i].name = f"agent_{i}"
        self.agents = [slice.name for slice in slice_lst]
        self.possible_agents = self.agents.copy()

        # action space map
        self.action_spaces = {slice.name: spaces.Discrete(len(slice.candidate_RBs)) for slice in slice_lst}

        # observation space
        # TODO: need to change the observation space
        self.observation_spaces = {slice.name: spaces.Box(low=-np.inf, high=np.inf, shape=(3,5), dtype=float) for slice in slice_lst}
        # -------------------------------------------

        # name -> slice dict
        self.agent_name_map = {slice.name: slice for slice in slice_lst}

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

        # for return state
        self.obs = None

    def log_info(self):
        if self.logger:
            for slice in self.Slice_lst:
                self.logger.info(f"-------------------- Slice --------------------")
                for line in slice.get_info().split("\n"):
                    self.logger.info(line)

    @functools.lru_cache(maxsize=None)
    def observation_space(self, agent: str):
        return self.observation_spaces[agent]

    @functools.lru_cache(maxsize=None)
    def action_space(self, agent: str):
        return self.action_spaces[agent]
    
    def simple_step(self):
        # Don't do handover actions, just run simulation for one step and get observation
        ns.Simulator.Stop(ns.Seconds(self.step_time))
        ns.Simulator.Run()
        base_slice.merge_records()
        obs = {}
        for slice in self.Slice_lst:
            slice.stat_report(self.step_time, if_log=False)
            obs[slice.name] = slice.get_observation(if_log=False)
        base_slice.clean_all_records()
        base_slice.current_time += self.step_time
        return obs
    
    def warmup(self):
        if self.is_ready == False:
            self.logger.info(f"Begin warmup for {self.warmup_times} times......")
            
            # Skip the off time of onoff application
            n_skip_times = -1
            while True:
                obs = self.simple_step()
                n_skip_times += 1
                has_no_zero = any([any([i != 0 for i in o[:, -3]]) for o in obs.values()])
                if has_no_zero:  # TODO: need change according to obs
                    break
            if n_skip_times > 0:
                self.logger.info(f"Skip {n_skip_times} times to avoid off time of onoff application.")
            
            if self.warmup_times >= 1:
                ns.Simulator.Stop(ns.Seconds(self.step_time*(self.warmup_times-1)))  # -1 here because it runs will run one step when check off time
                ns.Simulator.Run()
                base_slice.merge_records()
                for slice in self.Slice_lst:
                    slice.stat_report(self.step_time*(self.warmup_times-1), if_log=False)
                base_slice.clean_all_records()
                base_slice.current_time += self.step_time*self.warmup_times
            
            self.logger.info("Warmup finished.")
            self.is_ready = True
        else:
            self.logger.info("Repeated warmup, skip this")

    def _get_info(self):
        return {name: {} for name in self.agents}

    def reset(self):
        if self.reset_result:
            self.logger.info("Repeated reset, skip this")     # repeated reset, skip
            return self.reset_result
        else:    
            self.logger.info("Resetting......")

            # Plot last episode
            if self.episode != 0 and self.plot:
                for slice in self.Slice_lst:
                    slice.plot(os.path.join(self.root_path, f"{slice.name}_{self.episode}.png"))
                    slice.clean_plot_data(os.path.join(self.root_path, f"{slice.name}_{self.episode}.pkl"))
            else:
                for slice in self.Slice_lst:
                    slice.clean_plot_data() # seems not needed
            self.episode += 1

            base_slice.clean_all_records()

            # set too a random RB for each slice
            random_RBs = {slice: random.choice(slice.candidate_RBs) for slice in self.Slice_lst}
            # make sure sum of RBs is less than max_RB
            iteration_times = 0
            while sum(random_RBs.values()) > self.max_RB:
                # random choose one slice to decrease
                k = random.choice(list(random_RBs.keys()))
                if random_RBs[k] == k.min_RB:   # can't decrease since it's already min_RB
                    continue
                random_RBs[k] -= 1
                iteration_times += 1
                if iteration_times > 1000:
                    if self.logger:
                        self.logger.warning(f"Too many iterations to decrease the total RBs, actions: {actions}")
                    else:
                        warnings.warn(f"Too many iterations to decrease the total RBs, actions: {actions}")
            for slice in self.Slice_lst:
                slice.handoverTo(random_RBs[slice])
                slice.clean_RB_record(random_RBs[slice])

            self.warmup()
            for slice in self.Slice_lst:
                slice.clean_stat()

            # Run simulation for one step
            ns.Simulator.Stop(ns.Seconds(self.step_time))
            ns.Simulator.Run()

            obs = {}
            info = {}
            base_slice.merge_records()
            for slice in self.Slice_lst:
                slice.stat_report(self.step_time)
                obs[slice.name] = slice.get_observation()
                info[slice.name] = slice.get_rl_info()
            base_slice.step_records()
            base_slice.clean_all_buffer_record()
            base_slice.current_time += self.step_time

            self.logger.info("Reset finished.")

            self.reset_result = (obs, info)
            self.obs = obs
            return obs, info
    
    def step(self, action: dict):
        # clean reset result
        if self.reset_result:
            self.reset_result = None

        # clean is_ready
        if self.is_ready:
            self.is_ready = False

        # Do handover actions
        exceed_RB = 0
        actions = copy.deepcopy(action)
        for slice in self.Slice_lst:                            # preprocess actions
            if slice.action_process_fn:
                actions[slice.name] = slice.action_process_fn(action[slice.name])
            else:
                actions[slice.name] = action[slice.name]*slice.RB_resolution + slice.min_RB
        if sum(actions.values()) > self.max_RB:
            exceed_RB = 1
        iteration_times = 0
        while sum(actions.values()) > self.max_RB:              # make sure sum of RBs is less than max_RB
            # random choose one slice to decrease
            k = random.choice(list(actions.keys()))
            if actions[k] == self.agent_name_map[k].min_RB:     # can't decrease since it's already min_RB
                continue
            actions[k] -= 1
            iteration_times += 1
            if iteration_times > 1000:
                if self.logger:
                    self.logger.warning(f"Too many iterations to decrease the total RBs, actions: {actions}")
                else:
                    warnings.warn(f"Too many iterations to decrease the total RBs, actions: {actions}")
        for slice in self.Slice_lst:
            a = actions[slice.name]
            assert a in slice.candidate_RBs, f"Action {a} is not in the action space {slice.candidate_RBs}"
            slice.handoverTo(a)
        
        # Run simulation for one step
        ns.Simulator.Stop(ns.Seconds(self.step_time))
        ns.Simulator.Run()

        # Get rewards and local observations
        reward = {}
        obs = {}
        info = {}
        terminated = {}
        base_slice.merge_records()
        max_step_termi = (base_slice.step >= self.max_step)
        for slice in self.Slice_lst:
            slice.stat_report(self.step_time)
            reward[slice.name] = slice.get_reward()
            obs[slice.name] = slice.get_observation()
            info[slice.name] = slice.get_rl_info()

            # Get terminated
            terminated[slice.name] = max_step_termi or slice.get_terminated()

        # If the total number of RBs exceeds the maximum RBs, give all agents a negative reward
        if exceed_RB == 1:
            if self.logger:
                self.logger.warning(f"Exceed the maximum RBs in episode {self.episode} step {base_slice.step}, do actions: {actions} instead of {action}")
            reward = {agent: -20 for agent, _ in reward.items()}

        base_slice.step_records()
        base_slice.clean_all_buffer_record()
        base_slice.current_time += self.step_time

        # TODO: process obs

        self.obs = obs
        return obs, reward, terminated, {slice.name: False for slice in self.Slice_lst}, info
    
    def state(self):
        # concatenate all observations
        result_obs = np.array([])
        for sub_obs in self.obs.values():
            result_obs = np.concatenate((result_obs, sub_obs))
    
    def obs_process(obs):
        # TODO: process obs
        pass