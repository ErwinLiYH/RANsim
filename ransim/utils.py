import logging
import os
from ns import ns
from typing import Literal


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