import gymnasium as gym
from gymnasium import ObservationWrapper
from pettingzoo import ParallelEnv
import numpy as np
import os


class WarpperForGym(gym.Env):
    def __init__(self, env_name, max_step:int, unchange_terminate:int=0, plot:bool=False, root_path:str="./", no_termi = False):
        self.env_name = env_name
        self.max_step = max_step
        self.unchange_terminate = unchange_terminate
        self.plot = plot
        self.root_path = root_path
        self.no_termi = no_termi
        if not os.path.exists(self.root_path):
            os.makedirs(self.root_path)
        self.station = self.init_station()
        self.observation_space = self.station.observation_space
        self.action_space = self.station.action_space

    def init_station(self):
        raise NotImplementedError
    
    def reset(self, seed = None, options = None):
        return self.station.reset()
    
    def step(self, action):
        return self.station.step(action)
    
class FlattenObsGym(ObservationWrapper):
    def __init__(self, env):
        super(FlattenObsGym, self).__init__(env)
        obs_space = self.env.observation_space
        if isinstance(obs_space, gym.spaces.Box):
            self.observation_space = gym.spaces.Box(
                low=obs_space.low.flatten(),
                high=obs_space.high.flatten(),
                dtype=obs_space.dtype
            )
        else:
            raise NotImplementedError("Not implemented for obs_space: ", obs_space)

    def observation(self, observation):
        return np.array(observation).flatten()
    
class WarpperForPtP(ParallelEnv):
    def __init__(self, env_name, max_step:int, unchange_terminate:int=0, plot:bool=False, root_path:str="./", no_termi = False):
        self.env_name = env_name
        self.max_step = max_step
        self.unchange_terminate = unchange_terminate
        self.plot = plot
        self.root_path = root_path
        self.no_termi = no_termi
        if not os.path.exists(self.root_path):
            os.makedirs(self.root_path)
        self.station = self.init_station()

        self.observation_spaces = self.station.observation_spaces
        self.action_spaces = self.station.action_spaces
        self.agents = self.station.agents
        self.possible_agents = self.station.possible_agents

    def init_station(self):
        raise NotImplementedError
    
    def reset(self, seed = None, options=None):
        return self.station.reset()
    
    def step(self, action):
        return self.station.step(action)
    
    def observation_space(self, agent):
        return self.station.observation_space(agent)
    
    def action_space(self, agent):
        return self.station.action_space(agent)
    
    def state(self):
        return self.station.state()