import gymnasium as gym


class WarpperForGym(gym.Env):
    def __init__(self, env_name, max_step:int, unchange_terminate:int=0):
        self.env_name = env_name
        self.max_step = max_step
        self.unchange_terminate = unchange_terminate
        self.station = self.init_station()
        self.observation_space = self.station.observation_space
        self.action_space = self.station.action_space

    def init_station(self):
        raise NotImplementedError
    
    def reset(self):
        return self.station.reset()
    
    def step(self, action):
        return self.station.step(action)