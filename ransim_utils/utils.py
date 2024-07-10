import logging
import os
from ns import ns
from typing import Literal
import numpy as np


class logging_helper:
    def __init__(self, level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s'):
        self.level = level
        self.format = format

    def get_simple_file_logger(self, name:str, log_file_path:str) -> logging.Logger:
        logger = logging.getLogger(name)
        logger.setLevel(self.level)
        formatter = logging.Formatter(self.format)
        fh = logging.FileHandler(os.path.expanduser(log_file_path), mode='w', delay=True)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        return logger
    
    def get_simple_print_logger(self, name:str) -> logging.Logger:
        logger = logging.getLogger(name)
        logger.setLevel(self.level)
        formatter = logging.Formatter(self.format)
        sh = logging.StreamHandler()
        sh.setFormatter(formatter)
        logger.addHandler(sh)
        return logger
    
def set_ns_env(ns_build_path:str):
    pass

class SinkAppConfig:
    def __init__(self, start_time:int, stop_time:int, 
                 socket_type:Literal["ns3::UdpSocketFactory", "ns3::TcpSocketFactory"] = "ns3::UdpSocketFactory",
                 port=1234):
        self.start_time = ns.Seconds(start_time)
        self.stop_time = ns.Seconds(stop_time)
        self.socket_type = socket_type
        self.port = port

class OnOffAppConfig:
    def __init__(self, start_time:int, stop_time:int, 
                 socket_type:Literal["ns3::UdpSocketFactory", "ns3::TcpSocketFactory"] = "ns3::UdpSocketFactory",
                 data_rate = "3Mb/s", 
                 packet_size = 512, 
                 on_time = "ns3::ConstantRandomVariable[Constant=1]", 
                 off_time = "ns3::ConstantRandomVariable[Constant=0]", 
                 port=49153):
        self.start_time = ns.Seconds(start_time)
        self.stop_time = ns.Seconds(stop_time)
        self.socket_type = socket_type
        self.data_rate = ns.StringValue(data_rate)
        self.packet_size = ns.UintegerValue(packet_size)
        self.on_time = ns.StringValue(on_time)
        self.off_time = ns.StringValue(off_time)
        self.port = port

def list_to_abbr_str(lst, max_display=3):
    if len(lst) <= max_display:
        return str(lst)
    else:
        res = "["
        for i in range(len(lst)):
            if i == max_display:
                res += "..., "
            if i < max_display:
                res += (str(lst[i]) + ", ")
            if i == len(lst) - 1:
                res += str(lst[i])
        res += "]"
        return res

class PortAssigner:
    def __init__(self, start_ip=49153, step=1):
        self.start_ip = start_ip
        self.step = step
        self.current_ip = start_ip

    def __call__(self):
        self.current_ip += self.step
        return self.current_ip
    
    def __repr__(self):
        return f"<PortAssigner start_ip={self.start_ip}, step={self.step}, current_ip={self.current_ip}>"
    
    def __str__(self):
        return f"PortAssigner start_ip={self.start_ip}, step={self.step}, current_ip={self.current_ip}"

# Running std mean updater, similar to Wellford's algorithm for online mean and variance calculation

class RunningStdMeanUpdater(object):
    # ref from https://github.com/openai/baselines/blob/ea25b9e8b234e6ee1bca43083f8f3cf974143998/baselines/common/running_mean_std.py
    # and https://www.reddit.com/r/reinforcementlearning/comments/gocj1n/help_normalizing_observations_for_ppo/
    # Similar to Welford's online algorithm
    # https://github.com/openai/gym/blob/master/gym/wrappers/normalize.py
    def __init__(self, shape, epsilon=1e-4):
        self.mean = np.zeros(shape, 'float64')
        self.var = np.ones(shape, 'float64')
        self.count = epsilon

    def update(self, x):
        batch_mean = np.mean(x, axis=0)
        batch_var = np.var(x, axis=0)
        batch_count = x.shape[0]
        self.update_from_moments(batch_mean, batch_var, batch_count)

    def normalize(self, x, epsilon=1e-8, zero_mean=True):
        if zero_mean:
            return (x - self.mean) / np.sqrt(self.var + epsilon)
        else:
            return x / np.sqrt(self.var + epsilon)

    def update_from_moments(self, batch_mean, batch_var, batch_count):
        self.mean, self.var, self.count = update_mean_var_count_from_moments(
            self.mean, self.var, self.count, batch_mean, batch_var, batch_count)
        
    def __str__(self) -> str:
        return f"mean: {self.mean}, var: {self.var}, count: {self.count}"
    
    def __repr__(self) -> str:
        return f"<Welford {self.__str__()}>"

def update_mean_var_count_from_moments(mean, var, count, batch_mean, batch_var, batch_count):
    delta = batch_mean - mean
    tot_count = count + batch_count

    new_mean = mean + delta * batch_count / tot_count
    m_a = var * count
    m_b = batch_var * batch_count
    M2 = m_a + m_b + np.square(delta) * count * batch_count / tot_count
    new_var = M2 / tot_count
    new_count = tot_count

    return new_mean, new_var, new_count