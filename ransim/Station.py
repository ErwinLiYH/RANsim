from ns import ns
from typing import List
from . import Slice
import logging


class Station:
    def __init__(self, slice_list:List[Slice.RanSlice], step_time=0.05, warmup_times=10, logger:None|logging.Logger = None):
        
        # Connect callback functions
        ns.Config.Connect("/NodeList/*/ApplicationList/*/$ns3::OnOffApplication/TxWithSeqTsSize", Slice.TxWithSeqTsSize_callback_cpp)
        ns.Config.Connect("/NodeList/*/ApplicationList/*/$ns3::PacketSink/RxWithSeqTsSize", Slice.RxWithSeqTsSize_callback_cpp)

        self.Slice_list = slice_list
        self.step_time = step_time

        # Set location of eNodeBs

        # Set location of UEs

        self.warmup(warmup_times)

    def warmup(self, times):
        ns.Simulator.Stop(ns.Seconds(self.step_time*times))
        ns.Simulator.Run()
        Slice.clean_all_records()

    def step(self):
        ns.Simulator.Stop(ns.Seconds(self.step_time))
        ns.Simulator.Run()
        Slice.merge_records()
        for i in self.Slice_list:
            i.stat_report()
        Slice.step_records()
