import gymnasium as gym
from gymnasium import ObservationWrapper
from pettingzoo import ParallelEnv
import numpy as np
import os

try:
    from ray.rllib.env.multi_agent_env import ENV_STATE
except ImportError:
    ENV_STATE = "state"


class WarpperForGym(gym.Env):
    def __init__(self, env_name, max_step:int, unchange_terminate:int=0, plot:bool=False, \
                 root_path:str="./", no_termi = False, num_obs_history:int=3, warmup_times=10, random_seed=None):
        self.env_name = env_name
        self.max_step = max_step
        self.unchange_terminate = unchange_terminate
        self.plot = plot
        self.root_path = root_path
        self.no_termi = no_termi
        self.random_seed = random_seed
        from ransim import config as ransim_config
        if random_seed is not None:
            ransim_config.reset_random_seed(self.random_seed)
        if not os.path.exists(self.root_path):
            os.makedirs(self.root_path)
        self.num_obs_history = num_obs_history
        self.warmup_times = warmup_times
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
    def __init__(self, env_name, max_step:int, unchange_terminate:int=0, plot:bool=False, 
                 root_path:str="./", no_termi = False, num_obs_history:int=3, warmup_times=10, random_seed=None):
        self.env_name = env_name
        self.max_step = max_step
        self.unchange_terminate = unchange_terminate
        self.plot = plot
        self.root_path = root_path
        self.no_termi = no_termi
        self.random_seed = random_seed
        from ransim import config as ransim_config
        if random_seed is not None:
            ransim_config.reset_random_seed(self.random_seed)
        if not os.path.exists(self.root_path):
            os.makedirs(self.root_path)
        self.num_obs_history = num_obs_history
        self.warmup_times = warmup_times
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
    
class AddStatePtP(ParallelEnv):
    def __init__(self, env):
        self.env = env
        self.agents = self.env.agents
        self.possible_agents = self.env.possible_agents
        self.action_spaces = self.env.action_spaces

        self.observation_spaces = {}
        for agent, space in self.env.observation_spaces.items():
            self.observation_spaces[agent] = gym.spaces.Dict(
                {
                    "obs": space,
                    ENV_STATE: self.env.state_space
                }
            )

    def reset(self, seed = None, options=None):
        obs, info = self.env.reset()
        return {agent: {"obs": o, ENV_STATE: self.env.state()} for agent, o in obs.items()}, info
    
    def step(self, action):
        obs, reward, done, info = self.env.step(action)
        return {agent: {"obs": o, ENV_STATE: self.env.state()} for agent, o in obs.items()}, reward, done, info
    
    def observation_space(self, agent):
        return self.observation_spaces[agent]
    
    def action_space(self, agent):
        return self.env.action_space(agent)
    
    def state(self):
        return self.env.state()