from . import base_slice
from typing import List, Dict
from .utils import OnOffAppConfig, SinkAppConfig
import logging
from ns import ns
import numpy as np


THRESHOLD = 0.05

class OnOffSlice(base_slice.BasicRanSlice):
    """
    An example for functional slice. When creating a OnOffSlice, it will install a OnOff client for each UE, and do all action in BasicRanSlice.
    """
    def __init__(self, N_UEs:int, initial_RB:int, onoff_config:OnOffAppConfig, sink_config:SinkAppConfig, RB_resolution: int = 1, min_RB: int = 6, max_RB: int = 100, logger:None|logging.Logger = None, unlim_RB=True, unchange_terminate:int=0):
        super().__init__(N_UEs, initial_RB, RB_resolution, min_RB, max_RB, logger, unlim_RB, unchange_terminate)

        # Install onoff client to UEs
        for i in range(self.N_UEs):
            client = ns.OnOffHelper(onoff_config.socket_type, ns.InetSocketAddress(base_slice.p2p_ip_interface.GetAddress(1), sink_config.port).ConvertTo())
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
    
class EmbbSlice(base_slice.BasicRanSlice):
    def __init__(self, N_UEs: int, CQI_info: Dict[int, int], SLAs: Dict[int, Dict[str, float]], initial_RB: int, onoff_configs: List[List[OnOffAppConfig]], sink_config: SinkAppConfig, RB_resolution: int = 1, min_RB: int = 6, max_RB: int = 100, logger: None | logging.Logger = None, unlim_RB=True, unchange_terminate:int=0, no_termi = False):
        super().__init__(N_UEs, initial_RB, RB_resolution, min_RB, max_RB, logger, unlim_RB, unchange_terminate)

        self.SLAs = SLAs
        self.SLA_violation_list = []
        self.SLA_violations = []
        self.SLA_violation = 0
        self.bad_SE = 0

        self.SE_list = []

        self.no_termi = no_termi

        total_n_cqi = 0
        for i in CQI_info.values():
            total_n_cqi += i
        assert total_n_cqi == N_UEs, "The sum of CQI_info should be equal to N_UEs"
        assert len(CQI_info) == len(SLAs), "The length of CQI_info should be equal to the length of SLAs"
        assert len(onoff_configs) == N_UEs, "The length of onoff_configs should be equal to N_UEs"

        # Activate GBR/NGBR bearer for GBR UEs
        self.ueip_cqi = {}
        CQI_info_list = (k for k, v in CQI_info.items() for _ in range(v))
        tft = ns.Create["EpcTft"]()
        for i, q in zip(range(self.N_UEs), CQI_info_list):
            assert q in range(1, 9), "CQI should be in range 1-9"
            assert isinstance(q, int), "CQI should be integer"
            bearer = ns.EpsBearer(q)
            base_slice.lte_helper.ActivateDedicatedEpsBearer(self.ue_devices.Get(i), bearer, tft)
            self.ueip_cqi[self.ue_ips[i]] = q

        # Initialize onoff client on Remotehost to UE
        for i in range(self.N_UEs):
            for j in onoff_configs[i]:
                base_slice.InitRemoteOnOffApp(sink_config, j, self.ue_ip_interface.GetAddress(i))

        # Install sink app to all UEs
        for i in range(self.N_UEs):
            sink = ns.PacketSinkHelper(sink_config.socket_type, ns.InetSocketAddress(ns.Ipv4Address.GetAny(), sink_config.port).ConvertTo())
            sink.SetAttribute("EnableSeqTsSizeHeader", ns.BooleanValue(1))
            sink_apps = sink.Install(self.ue_nodes.Get(i))
            sink_apps.Start(sink_config.start_time)
            sink_apps.Stop(sink_config.stop_time)

    def stat_report(self, step_time, if_log=True):
        stat = super().stat_report(step_time, "rx", if_log)
        # Default stat format:
        # ["UEIP", "step", "nSend", "nRecv", "nRecvStep", "minDelay", "maxDelay", "avgDelay", "minRate", "maxRate", "avgRate", "delivRate", "throughput", "tx_throughput", "pacSizeSum", "tx_pacSizeSum"]
        stat = stat[["UEIP", "maxDelay", "throughput", "tx_throughput", "pacSizeSum", "nRecv", "nRecvStep", "nSend", "tx_pacSizeSum"]]
        stat["CQI"] = stat["UEIP"].map(self.ueip_cqi)
        total_throughput = stat.groupby("CQI")["throughput"].sum()
        total_tx_throughput = stat.groupby("CQI")["tx_throughput"].sum()
        max_delay = stat.groupby("CQI")["maxDelay"].max()
        total_n_recv = stat.groupby("CQI")["nRecv"].sum()
        total_n_recvstep = stat.groupby("CQI")["nRecvStep"].sum()
        total_pac_size = stat.groupby("CQI")["pacSizeSum"].sum()
        total_n_send = stat.groupby("CQI")["nSend"].sum()
        total_tx_pac_size = stat.groupby("CQI")["tx_pacSizeSum"].sum()
        self.stat = (total_throughput, total_tx_throughput, max_delay, total_n_recv, total_pac_size, total_n_send, total_tx_pac_size, total_n_recvstep)

    def get_reward(self):
        # Calculate SLA violation
        SLA_violation = 0
        throughput_violation_rate = []
        delay_violation_rate = []
        for cqi, sla in self.SLAs.items():
            throughput_violation_rate_temp = (self.stat[0][cqi] - sla["throughput"]) / sla["throughput"] if self.stat[1][cqi] >= sla["throughput"] else 0
            # throughput_violation_rate.append((self.stat[0][cqi] - sla["throughput"]) / sla["throughput"])
            throughput_violation_rate.append(throughput_violation_rate_temp)
            delay_violation_rate.append((sla["delay"] - self.stat[2][cqi]) / sla["delay"])
            if self.stat[0][cqi] < sla["throughput"] and throughput_violation_rate_temp < -THRESHOLD:
                if self.stat[1][cqi] >= sla["throughput"]:
                    SLA_violation = 1
            if self.stat[2][cqi] > sla["delay"] and delay_violation_rate[-1] < -THRESHOLD:
                SLA_violation = 1
        
        n_recv_step = self.stat[7].sum()
        n_send = self.stat[5].sum()
        deliv_rate = n_recv_step/n_send if n_send!=0 else 0
        if deliv_rate<0.95:
            SLA_violation = 1

        self.SLA_violation_list.append((SLA_violation, delay_violation_rate, throughput_violation_rate))
        self.SLA_violation = SLA_violation
        self.logger.info(f"in get_rew() SLA_vio:{self.SLA_violation}")
        self.SLA_violations.append(SLA_violation)

        # Calculate SE (spectral efficiency)
        SE = (self.stat[0].sum()*1000*1000) / (180000 * self.current_RB) # bps/Hz
        self.SE_list.append(SE)
        if SE < 4:
            self.bad_SE = 1
        else:
            self.bad_SE = 0
        self.logger.info(f"in get_rew() bad_SE:{self.bad_SE}")

        # Bandwidth changing panalty
        # P = 1 if self.changed_RB else 0

        # Calculate reward
        # reward = 1 * SE - 1 * SLA_violation # - 1 * P
        SE_threshold = 4
        if SLA_violation == 0:
            if SE < SE_threshold:
                reward = -5
            else:
                reward = 2*SE
        else: 
            # reward = -np.log(1-(sum([i for i in delay_violation_rate if i < 0]) + sum([i for i in throughput_violation_rate if i < 0])))
            total_violation_rate = sum([i for i in delay_violation_rate if i < 0]) + sum([i for i in throughput_violation_rate if i < 0])
            reward = -10

        if self.changed_RB:
            reward -= 5

        if self.logger:
            self.logger.info(f"Reward: {reward}, SE: {SE}, SLA_violation: {SLA_violation}, delay_violation_rate: {delay_violation_rate}, throughput_violation_rate: {throughput_violation_rate}, deliv_rate: {deliv_rate}")

        return reward
    
    def get_observation(self, if_log=True):
        n_recv = self.stat[3].sum()
        n_send = self.stat[5].sum()
        recv_avg_packet_size = self.stat[4].sum() / n_recv if n_recv != 0 else 0
        tx_avg_packet_size = self.stat[6].sum() / n_send if n_send != 0 else 0
        try:
            SE = self.SE_list[-1]
        except IndexError:
            SE = (self.stat[0].sum()*1000*1000) / (180000 * self.current_RB) # bps/Hz
    
        # [current_RB, if_changed, n_recv, avg_recv_packet_size, n_send, avg_send_packet_size]
        throughput = self.stat[1].sum()
        obs = [self.current_RB, SE*10, self.stat[1].sum()]
        if self.logger and if_log:
            self.logger.info(f"Observation: {obs}")
        return np.array(obs)
    
    def get_terminated(self):
        self.logger.info(f"in get_term() SLA_vio:{self.SLA_violation}")
        self.logger.info(f"in get_term() bad_SE:{self.bad_SE}")
        if self.no_termi:
            unchange_terminated = self.get_unchange_terminated()
            SLA_terminated = bool(self.SLA_violation)
            bad_SE_terminated = bool(self.bad_SE)
            self.logger.info(f"{unchange_terminated} {bad_SE_terminated} {SLA_terminated}")
            return False
        else:
            unchange_terminated = self.get_unchange_terminated()
            SLA_terminated = bool(self.SLA_violation)
            bad_SE_terminated = bool(self.bad_SE)
            self.logger.info(f"{unchange_terminated} {bad_SE_terminated} {SLA_terminated}")
            return unchange_terminated or SLA_terminated or bad_SE_terminated

class MmtcSlice(base_slice.BasicRanSlice):
    def __init__(self, N_UEs: int, SLA: Dict[str, float], initial_RB: int, onoff_config: OnOffAppConfig, sink_config: SinkAppConfig, RB_resolution: int = 1, min_RB: int = 6, max_RB: int = 100, logger: None | logging.Logger = None, unlim_RB=True, unchange_terminate:int=0):
        super().__init__(N_UEs, initial_RB, RB_resolution, min_RB, max_RB, logger, unlim_RB, unchange_terminate)

        self.SLA = SLA
        self.SLA_violation_list = []

        # Install onoff client to UEs
        for i in range(self.N_UEs):
            client = ns.OnOffHelper(onoff_config.socket_type, ns.InetSocketAddress(base_slice.p2p_ip_interface.GetAddress(1), sink_config.port).ConvertTo())
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

    def stat_report(self, step_time, if_log=True):
        stat = super().stat_report(step_time, "tx", if_log)
        # Default stat format:
        # ["UEIP", "step", "nSend", "nRecv", "nRecvStep", "minDelay", "maxDelay", "avgDelay", "minRate", "maxRate", "avgRate", "delivRate", "throughput", "tx_throughput", "pacSizeSum", "tx_pacSizeSum"]
        stat = stat[["UEIP", "maxDelay", "throughput", "tx_throughput", "pacSizeSum", "nRecv", "nSend", "tx_pacSizeSum"]]
        total_throughput = stat["throughput"].sum()
        total_tx_throughput = stat["tx_throughput"].sum()
        max_delay = stat["maxDelay"].max()
        total_n_recv = stat["nRecv"].sum()
        total_pac_size = stat["pacSizeSum"].sum()
        total_n_send = stat["nSend"].sum()
        total_tx_pac_size = stat["tx_pacSizeSum"].sum()
        self.stat = (total_throughput, total_tx_throughput, max_delay, total_n_recv, total_pac_size, total_n_send, total_tx_pac_size)

    def get_reward(self):
        SLA_violation = 0
        throughput_violation_rate = (self.stat[0] - self.SLA["throughput"]) / self.SLA["throughput"] if self.stat[1] >= self.SLA["throughput"] else 0
        delay_violation_rate = (self.SLA["delay"] - self.stat[2]) / self.SLA["delay"]
        if self.stat[0] < self.SLA["throughput"]:
            if self.stat[1] >= self.SLA["throughput"]:
                SLA_violation = 1
        if self.stat[2] > self.SLA["delay"]:
            SLA_violation = 1

        self.SLA_violation_list.append((SLA_violation, delay_violation_rate, throughput_violation_rate))

        # Calculate SE (spectral efficiency)
        SE = (self.stat[0]*1000*1000) / (180000 * self.current_RB) # bps/Hz

        # Calculate reward
        if SLA_violation == 0:
            reward = SE**2
        else:
            delay_violation_rate = delay_violation_rate if delay_violation_rate < 0 else 0
            throughput_violation_rate = throughput_violation_rate if throughput_violation_rate < 0 else 0
            reward = -np.log(1 - (delay_violation_rate + throughput_violation_rate))

        return reward
    
    def get_observation(self, if_log=True):
        n_recv = self.stat[3].sum()
        n_send = self.stat[5].sum()
        recv_avg_packet_size = self.stat[4].sum() / n_recv if n_recv != 0 else 0
        tx_avg_packet_size = self.stat[6].sum() / n_send if n_send != 0 else 0
        # [if_changed, n_recv, avg_recv, avg_recv_packet_size, n_send, avg_send_packet_size]
        if self.logger and if_log:
            self.logger.info(f"Observation: {[self.current_RB, int(self.changed_RB), n_recv, recv_avg_packet_size, n_send, tx_avg_packet_size]}")
        return np.array([self.current_RB, int(self.changed_RB), n_recv, recv_avg_packet_size, n_send, tx_avg_packet_size])

class UrllcSlice(base_slice.BasicRanSlice):
    def __init__(self, N_UEs: int, initial_RB: int, onoff_config: OnOffAppConfig, sink_config: SinkAppConfig, RB_resolution: int = 1, min_RB: int = 6, max_RB: int = 100, logger: None | logging.Logger = None, unlim_RB=True, unchange_terminate:int=0):
        super().__init__(N_UEs, initial_RB, RB_resolution, min_RB, max_RB, logger, unlim_RB, unchange_terminate)

        # Install onoff client to UEs
        for i in range(self.N_UEs):
            client = ns.OnOffHelper(onoff_config.socket_type, ns.InetSocketAddress(base_slice.p2p_ip_interface.GetAddress(1), sink_config.port).ConvertTo())
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