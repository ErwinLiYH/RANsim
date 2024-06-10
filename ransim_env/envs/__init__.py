import gymnasium as gym
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
    
    def reset(self):
        return self.station.reset()
    
    def step(self, action):
        return self.station.step(action)