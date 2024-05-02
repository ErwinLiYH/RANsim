from . import Slice
from typing import List, Dict
from .utils import OnOffAppConfig, SinkAppConfig
import logging
from ns import ns
import numpy as np


class OnOffSlice(Slice.BasicRanSlice):
    """
    An example for functional slice. When creating a OnOffSlice, it will install a OnOff client for each UE, and do all action in BasicRanSlice.
    """
    def __init__(self, N_UEs:int, initial_RB:int, onoff_config:OnOffAppConfig, sink_config:SinkAppConfig, RB_resolution: int = 1, min_RB: int = 1, max_RB: int = 100, logger:None|logging.Logger = None, unlim_RB=True):
        super().__init__(N_UEs, initial_RB, RB_resolution, min_RB, max_RB, logger, unlim_RB)

        # Install onoff client to UEs
        for i in range(self.N_UEs):
            client = ns.OnOffHelper(onoff_config.socket_type, ns.InetSocketAddress(Slice.p2p_ip_interface.GetAddress(1), sink_config.port).ConvertTo())
            client.SetAttribute("OnTime", onoff_config.on_time)
            client.SetAttribute("OffTime", onoff_config.off_time)
            client.SetAttribute("DataRate", onoff_config.data_rate)
            client.SetAttribute("PacketSize", onoff_config.packet_size)
            client.SetAttribute("EnableSeqTsSizeHeader", ns.BooleanValue(1))
            # if not set Local attr, the source ip when using UDP will be 0.0.0.0
            ue_adress = ns.InetSocketAddress(self.ue_ip_interface.GetAddress(i), onoff_config.port)
            client.SetAttribute("Local", ns.AddressValue(ue_adress.ConvertTo()))
            self.client_apps = client.Install(self.ue_nodes.Get(i))
            self.client_apps.Start(onoff_config.start_time)
            self.client_apps.Stop(onoff_config.stop_time)

    def stat_report(self, step_time):
        """
        An example of stat report function. It will call the parent's stat_report function, and then return averate data per UE.
        """
        # Call parent's stat_report to get all stat data
        stat = super().stat_report(step_time)
        # or you can design brand new stat_report function here.
        
        # Clip or Process data
        # Simple avg here as example
        avg_data = stat.iloc[:,1:].mean()

        # Save data to stat_df, if add/remove/change columns, remember to change the self.stat_df in the __init__.
        self.stat_df.loc[len(self.stat_df)] = avg_data

        return avg_data
        

    def get_reward(self, step_time):
        """
        An example of reward function. It just returns the average rate per UE of the slice in this step.
        """
        stat = self.stat_report(step_time)
        return stat["throughput"]
    
class EmbbSlice(Slice.BasicRanSlice):
    def __init__(self, N_UEs: int, CQI_info: Dict[int, int], SLAs: Dict[int, Dict[str, float]], initial_RB: int, onoff_configs: List[OnOffAppConfig], sink_config: SinkAppConfig, RB_resolution: int = 1, min_RB: int = 1, max_RB: int = 100, logger: None | logging.Logger = None, unlim_RB=True):
        super().__init__(N_UEs, initial_RB, RB_resolution, min_RB, max_RB, logger, unlim_RB)

        self.SLAs = SLAs
        self.SLA_violation_list = []

        self.SE_list = []

        total_n_cqi = 0
        for i in CQI_info.values():
            total_n_cqi += i
        assert total_n_cqi == N_UEs, "The sum of CQI_info should be equal to N_UEs"

        # Activate GBR/NGBR bearer for GBR UEs
        self.ueip_cqi = {}
        CQI_info_list = (k for k, v in CQI_info.items() for _ in range(v))
        tft = ns.Create["EpcTft"]()
        for i, q in zip(range(self.N_UEs), CQI_info_list):
            assert q in range(1, 9), "CQI should be in range 1-9"
            assert isinstance(q, int), "CQI should be integer"
            bearer = ns.EpsBearer(q)
            Slice.lte_helper.ActivateDedicatedEpsBearer(self.ue_devices.Get(i), bearer, tft)
            self.ueip_cqi[self.ue_ips[i]] = q

        # Initialize onoff client on Remotehost to UE
        for i in range(self.N_UEs):
            Slice.InitRemoteOnOffApp(sink_config, onoff_configs[i], self.ue_ip_interface.GetAddress(i))

        # Install sink app to all UEs
        for i in range(self.N_UEs):
            sink = ns.PacketSinkHelper(sink_config.socket_type, ns.InetSocketAddress(ns.Ipv4Address.GetAny(), sink_config.port).ConvertTo())
            sink.SetAttribute("EnableSeqTsSizeHeader", ns.BooleanValue(1))
            sink_apps = sink.Install(self.ue_nodes.Get(i))
            sink_apps.Start(sink_config.start_time)
            sink_apps.Stop(sink_config.stop_time)

    def stat_report(self, step_time):
        stat = super().stat_report(step_time, "rx")
        # Default stat format:
        # ["UEIP", "step", "nSend", "nRecv", "nRecvStep", "minDelay", "maxDelay", "avgDelay", "minRate", "maxRate", "avgRate", "delivRate", "throughput"]
        stat = stat[["UEIP", "maxDelay", "throughput", "tx_throughput", "pacSizeSum", "nRecv"]]
        stat["CQI"] = stat["UEIP"].map(self.ueip_cqi)
        total_throughput = stat.groupby("CQI")["throughput"].sum()
        total_tx_throughput = stat.groupby("CQI")["tx_throughput"].sum()
        max_delay = stat.groupby("CQI")["maxDelay"].max()
        total_n_recv = stat.groupby("CQI")["nRecv"].sum()
        total_pac_size = stat.groupby("CQI")["pacSizeSum"].sum()
        self.stat = (total_throughput, total_tx_throughput, max_delay, total_n_recv, total_pac_size)

    def get_reward(self):
        # Calculate SLA violation
        SLA_violation = 0
        throughput_violation_rate = 0
        delay_violation_rate = 0
        for cqi, sla in self.SLAs.items():
            throughput_violation_rate += (self.stat[0][cqi] - sla["throughput"]) / sla["throughput"]
            delay_violation_rate += (sla["delay"] - self.stat[2][cqi]) / sla["delay"]
            if self.stat[0][cqi] < sla["throughput"]:
                if self.stat[1][cqi] >= sla["throughput"]:
                    SLA_violation = 1
            if self.stat[2][cqi] > sla["delay"]:
                SLA_violation = 1
        self.SLA_violation_list.append((SLA_violation, delay_violation_rate, throughput_violation_rate))

        # Calculate SE (spectral efficiency)
        SE = self.stat[0].sum()*1024*1024 / (180000 * self.current_RB) # bps/Hz
        self.SE_list.append(SE)

        # Bandwidth changing panalty
        # P = 1 if self.changed_RB else 0

        # Calculate reward
        # reward = 1 * SE - 1 * SLA_violation # - 1 * P
        reward = SE + delay_violation_rate + throughput_violation_rate

        return reward
    
    def get_observation(self):
        n_recv = self.stat[3].sum()
        avg_packet_size = self.stat[4].sum() / n_recv
        return np.array([self.current_RB, self.last_RB, n_recv, avg_packet_size])

class MmtcSlice(Slice.BasicRanSlice):
    def __init__(self, N_UEs: int, initial_RB: int, onoff_config: OnOffAppConfig, sink_config: SinkAppConfig, RB_resolution: int = 1, min_RB: int = 1, max_RB: int = 100, logger: None | logging.Logger = None, unlim_RB=True):
        super().__init__(N_UEs, initial_RB, RB_resolution, min_RB, max_RB, logger, unlim_RB)

        # Install onoff client to UEs
        for i in range(self.N_UEs):
            client = ns.OnOffHelper(onoff_config.socket_type, ns.InetSocketAddress(Slice.p2p_ip_interface.GetAddress(1), sink_config.port).ConvertTo())
            client.SetAttribute("OnTime", onoff_config.on_time)
            client.SetAttribute("OffTime", onoff_config.off_time)
            client.SetAttribute("DataRate", onoff_config.data_rate)
            client.SetAttribute("PacketSize", onoff_config.packet_size)
            client.SetAttribute("EnableSeqTsSizeHeader", ns.BooleanValue(1))
            # if not set Local attr, the source ip when using UDP will be 0.0.0.0
            ue_adress = ns.InetSocketAddress(self.ue_ip_interface.GetAddress(i), onoff_config.port)
            client.SetAttribute("Local", ns.AddressValue(ue_adress.ConvertTo()))
            self.client_apps = client.Install(self.ue_nodes.Get(i))
            self.client_apps.Start(onoff_config.start_time)
            self.client_apps.Stop(onoff_config.stop_time)

    def stat_report(self, step_time):
        stat = super().stat_report(step_time)
        avg_data = stat.iloc[:,1:].mean()
        self.stat_df.loc[len(self.stat_df)] = avg_data

    def get_reward(self, step_time):
        stat = self.stat_report(step_time)
        return stat["throughput"]

class UrllcSlice(Slice.BasicRanSlice):
    def __init__(self, N_UEs: int, initial_RB: int, onoff_config: OnOffAppConfig, sink_config: SinkAppConfig, RB_resolution: int = 1, min_RB: int = 1, max_RB: int = 100, logger: None | logging.Logger = None, unlim_RB=True):
        super().__init__(N_UEs, initial_RB, RB_resolution, min_RB, max_RB, logger, unlim_RB)

        # Install onoff client to UEs
        for i in range(self.N_UEs):
            client = ns.OnOffHelper(onoff_config.socket_type, ns.InetSocketAddress(Slice.p2p_ip_interface.GetAddress(1), sink_config.port).ConvertTo())
            client.SetAttribute("OnTime", onoff_config.on_time)
            client.SetAttribute("OffTime", onoff_config.off_time)
            client.SetAttribute("DataRate", onoff_config.data_rate)
            client.SetAttribute("PacketSize", onoff_config.packet_size)
            client.SetAttribute("EnableSeqTsSizeHeader", ns.BooleanValue(1))
            # if not set Local attr, the source ip when using UDP will be
            ue_adress = ns.InetSocketAddress(self.ue_ip_interface.GetAddress(i), onoff_config.port)
            client.SetAttribute("Local", ns.AddressValue(ue_adress.ConvertTo()))
            self.client_apps = client.Install(self.ue_nodes.Get(i))
            self.client_apps.Start(onoff_config.start_time)
            self.client_apps.Stop(onoff_config.stop_time)
        
    def stat_report(self, step_time):
        stat = super().stat_report(step_time)
        avg_data = stat.iloc[:,1:].mean()
        self.stat_df.loc[len(self.stat_df)] = avg_data

    def get_reward(self, step_time):
        stat = self.stat_report(step_time)
        return stat["throughput"]