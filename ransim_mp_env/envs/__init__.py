import gymnasium as gym
import multiprocessing

class MultiProcessWrapperForGym(gym.Env):
    def __init__(self, env_name, max_step:int, unchange_terminate:int=0) -> None:
        self.env_name = env_name
        self.max_step = max_step
        self.unchange_terminate = unchange_terminate
        self.action_queue = multiprocessing.Queue()
        self.result_queue = multiprocessing.Queue()
        self.process = multiprocessing.Process(target=self._worker)
        self.process.daemon = True
        self.process.start()
        self.observation_space = self.result_queue.get()
        self.action_space = self.result_queue.get()

    def _worker(self):
        raise NotImplementedError
    
    def reset(self):
        self.action_queue.put(('reset', None))
        return self.result_queue.get()

    def step(self, action):
        self.action_queue.put(('step', action))
        return self.result_queue.get()
