import pandas as pd
import random
import logging
from collections import deque
from ns import ns
from ransim_utils.utils import SinkAppConfig, OnOffAppConfig, logging_helper, list_to_abbr_str
import random

import matplotlib.pyplot as plt

import pickle


# Current time
current_time = 0

# Set random seed
r = random.Random()
randint = r.randint(0,100000)
ns.RngSeedManager.SetSeed(randint)

# -------------------- DataFrames for recording Tx and Rx events --------------------

step=0

tx_record_df = pd.DataFrame(columns=["uid", "seq_num", "size", "time", "step", "src_ip", "src_port", "dest_ip", "dest_port"])
rx_record_df = pd.DataFrame(columns=["uid", "seq_num", "size", "time", "step", "src_ip", "src_port", "dest_ip", "dest_port"])

merged_df = None

# -------------------- Callbacks for Tx and Rx events --------------------

CALLBACK_LOGGER = logging_helper(level = logging.INFO).get_simple_print_logger("Slices callback")

def TxWithSeqTsSize_callback(contex, packet, address_src, address_dest, SeqTsSizeHeader):
    address_src = ns.InetSocketAddress.ConvertFrom(address_src)
    address_dest = ns.InetSocketAddress.ConvertFrom(address_dest)
    CALLBACK_LOGGER.debug(f"At {ns.Simulator.Now().GetSeconds():.5f}s ,{contex}, sent {packet.__deref__().GetSize()} bytes data")
    tx_record_df.loc[len(tx_record_df)] = [packet.__deref__().GetUid(), SeqTsSizeHeader.GetSeq(), SeqTsSizeHeader.GetSize(), ns.Simulator.Now().GetSeconds(), step, str(address_src.GetIpv4()), str(address_src.GetPort()), str(address_dest.GetIpv4()), str(address_dest.GetPort())]


def RxWithSeqTsSize_callback(contex, packet, address_src, address_dest, SeqTsSizeHeader):
    address_src = ns.InetSocketAddress.ConvertFrom(address_src)
    address_dest = ns.InetSocketAddress.ConvertFrom(address_dest)
    CALLBACK_LOGGER.debug(f"At {ns.Simulator.Now().GetSeconds():.5f}s ,{contex}, received {packet.__deref__().GetSize()} bytes data")
    rx_record_df.loc[len(rx_record_df)] = [packet.__deref__().GetUid(), SeqTsSizeHeader.GetSeq(), SeqTsSizeHeader.GetSize(), ns.Simulator.Now().GetSeconds(), step, str(address_src.GetIpv4()), str(address_src.GetPort()), str(address_dest.GetIpv4()), str(address_dest.GetPort())]

TxWithSeqTsSize_callback_cpp = ns.cppyy.gbl.make_SeqTsSizeCallback_with_context(TxWithSeqTsSize_callback)
RxWithSeqTsSize_callback_cpp = ns.cppyy.gbl.make_SeqTsSizeCallback_with_context(RxWithSeqTsSize_callback)

# -------------------- Callbacks of buffer recording --------------------

cellId2nodeId_map = {}

connected_cell_id = []

buffer_record_df = pd.DataFrame(columns=["pdcp_rx", "pdcp_tx", "rlc_rx", "rlc_tx", "rlc_drop"])

def init_cellId_map(*maps:dict):
    for i in maps:
        cellId2nodeId_map.update(i)

def insert_data(node_id:any, col:str, data:int):
    if node_id in buffer_record_df.index:
            buffer_record_df.loc[node_id, col] += data
    else:
        buffer_record_df.loc[node_id] = 0
        buffer_record_df.loc[node_id, col] = data

def clean_all_buffer_record():
    buffer_record_df.drop(buffer_record_df.index, inplace=True)
    buffer_record_df.reset_index(drop=True, inplace=True)
    global connected_cell_id
    connected_cell_id = []

def RxPdu_callback_Rlc(context, rnti, lcid, bytes, delay):
    node_id = int(context.split("/")[2])
    insert_data(node_id, "rlc_rx", bytes)
    
def TxPdu_callback_Rlc(context, rnti, lcid, bytes):
    node_id = int(context.split("/")[2])
    insert_data(node_id, "rlc_tx", bytes)

def RxPdu_callback_Pdcp(context, rnti, lcid, bytes, delay):
    node_id = int(context.split("/")[2])
    insert_data(node_id, "pdcp_rx", bytes)
    
def TxPdu_callback_Pdcp(context, rnti, lcid, bytes):
    node_id = int(context.split("/")[2])
    insert_data(node_id, "pdcp_tx", bytes)

def DropPac_callback(context, packet):
    node_id = int(context.split("/")[2])
    insert_data(node_id, "rlc_drop", packet.GetSize())

RxPdu_Rlc_callback_cpp = ns.cppyy.gbl.make_RxPduCallback(RxPdu_callback_Rlc)
RxPdu_Pdcp_callback_cpp = ns.cppyy.gbl.make_RxPduCallback(RxPdu_callback_Pdcp)
TxPdu_Rlc_callback_cpp = ns.cppyy.gbl.make_TxPduCallback(TxPdu_callback_Rlc)
TxPdu_Pdcp_callback_cpp = ns.cppyy.gbl.make_TxPduCallback(TxPdu_callback_Pdcp)
DropPac_callback_cpp = ns.cppyy.gbl.make_DropPacCallback(DropPac_callback)

def connect_buffer_record_callbacks(cellId, c):
    if cellId not in connected_cell_id:
        ns.Config.Connect(f"NodeList/{cellId2nodeId_map[cellId]}/DeviceList/*/$ns3::LteEnbNetDevice/LteEnbRrc/UeMap/*/DataRadioBearerMap/*/LtePdcp/RxPDU", RxPdu_Pdcp_callback_cpp)
        ns.Config.Connect(f"NodeList/{cellId2nodeId_map[cellId]}/DeviceList/*/$ns3::LteEnbNetDevice/LteEnbRrc/UeMap/*/DataRadioBearerMap/*/LtePdcp/TxPDU", TxPdu_Pdcp_callback_cpp)

        ns.Config.Connect(f"NodeList/{cellId2nodeId_map[cellId]}/DeviceList/*/$ns3::LteEnbNetDevice/LteEnbRrc/UeMap/*/DataRadioBearerMap/*/LteRlc/RxPDU", RxPdu_Rlc_callback_cpp)
        ns.Config.Connect(f"NodeList/{cellId2nodeId_map[cellId]}/DeviceList/*/$ns3::LteEnbNetDevice/LteEnbRrc/UeMap/*/DataRadioBearerMap/*/LteRlc/TxPDU", TxPdu_Rlc_callback_cpp)
        ns.Config.Connect(f"NodeList/{cellId2nodeId_map[cellId]}/DeviceList/*/$ns3::LteEnbNetDevice/LteEnbRrc/UeMap/*/DataRadioBearerMap/*/LteRlc/TxDrop", DropPac_callback_cpp)
        connected_cell_id.append(cellId)

# -------------------- Callbacks of handover events --------------------

def NotifyHandoverEndOkUe_callback(contex, imis, cellId, rnti):
    CALLBACK_LOGGER.debug(f"At {ns.Simulator.Now().GetSeconds():.5f}s ,{contex}, RNTI {rnti} handover to cell {cellId} is successful")
    connect_buffer_record_callbacks(cellId, contex)

def NotifyHandoverStartUe_callback(contex, imis, cellId, rnti, targetCellId):
    CALLBACK_LOGGER.debug(f"At {ns.Simulator.Now().GetSeconds():.5f}s ,{contex}, RNTI {rnti} start handover to cell {targetCellId}")

NotifyHandoverEndOkUe_callback_cpp = ns.cppyy.gbl.make_NotifyHandoverEndOkUeCallback(NotifyHandoverEndOkUe_callback)
NotifyHandoverStartUe_callback_cpp = ns.cppyy.gbl.make_NotifyHandoverStartUeCallback(NotifyHandoverStartUe_callback)

# -------------------- Function to merge and clean records --------------------

def merge_records():
    global merged_df
    merged_df = pd.merge(tx_record_df, rx_record_df, on=['seq_num', 'src_ip', 'src_port', 'dest_ip', 'dest_port'], suffixes=('_tx', '_rx'), how='left', indicator=True)

def step_records():
    # Clean all receiving records
    rx_record_df.drop(rx_record_df.index, inplace=True)
    rx_record_df.reset_index(drop=True, inplace=True)
    # Clean all sending records which be received
    tx_record_df.drop(merged_df[merged_df['_merge'] == 'both'].index, inplace=True)
    tx_record_df.reset_index(drop=True, inplace=True)
    global step
    step += 1

def clean_all_records():
    # Clean all receiving records
    rx_record_df.drop(rx_record_df.index, inplace=True)
    rx_record_df.reset_index(drop=True, inplace=True)
    # Clean all sending records
    tx_record_df.drop(tx_record_df.index, inplace=True)
    tx_record_df.reset_index(drop=True)
    global step
    step = 0

# -------------------- Initialise all helpers --------------------

lte_helper = ns.CreateObject("LteHelper")
epc_helper = ns.PointToPointEpcHelper()
lte_helper.SetEpcHelper(epc_helper)

internet = ns.InternetStackHelper()

p2p_helper = ns.PointToPointHelper()

pgw = epc_helper.GetPgwNode()
pgw_addr = epc_helper.GetUeDefaultGatewayAddress()

mobilityhelper = ns.MobilityHelper()
mobilityhelper.SetMobilityModel("ns3::ConstantPositionMobilityModel")

# -------------------- Create the shared RemoteHost --------------------

remote_nodes = ns.NodeContainer()
remote_nodes.Create(1)

# install internet stack to remote host
internet.Install(remote_nodes)

# Link PWG and remotehost
p2p_helper.SetDeviceAttribute("DataRate", ns.DataRateValue(ns.DataRate("100Gb/s")))
p2p_helper.SetDeviceAttribute("Mtu", ns.UintegerValue(1500))
p2p_link_device = p2p_helper.Install(pgw, remote_nodes.Get(0))

# Assign IP to PGW and remote host
ipv4_helper = ns.Ipv4AddressHelper()
ipv4_helper.SetBase("1.0.0.0", "255.0.0.0")
p2p_ip_interface = ipv4_helper.Assign(p2p_link_device)

# Initialise routing for remote host
ipv4_routing_helper = ns.Ipv4StaticRoutingHelper()
remote_routing = ipv4_routing_helper.GetStaticRouting(remote_nodes.Get(0).GetObject["Ipv4"]())
remote_routing.AddNetworkRouteTo(ns.Ipv4Address("7.0.0.0"), ns.Ipv4Mask("255.0.0.0"), 1)

def InitRemoteSinkApp(sink_config:SinkAppConfig):
    # Install Sink app to remote host
    sink = ns.PacketSinkHelper(sink_config.socket_type, ns.InetSocketAddress(ns.Ipv4Address.GetAny(), sink_config.port).ConvertTo())
    sink.SetAttribute("EnableSeqTsSizeHeader", ns.BooleanValue(1))
    sink_apps = sink.Install(remote_nodes.Get(0))
    sink_apps.Start(sink_config.start_time)
    sink_apps.Stop(sink_config.stop_time)

def InitRemoteOnOffApp(sink_config:SinkAppConfig, onoff_config: OnOffAppConfig, dest_ip):
    # Install OnOff app to remote host
    client = ns.OnOffHelper(onoff_config.socket_type, ns.InetSocketAddress(dest_ip, sink_config.port).ConvertTo())
    client.SetAttribute("OnTime", onoff_config.on_time)
    client.SetAttribute("OffTime", onoff_config.off_time)
    client.SetAttribute("DataRate", onoff_config.data_rate)
    client.SetAttribute("PacketSize", onoff_config.packet_size)
    client.SetAttribute("EnableSeqTsSizeHeader", ns.BooleanValue(1))
    # if not set Local attr, the source ip when using UDP will be 0.0.0.0
    local_adress = ns.InetSocketAddress(p2p_ip_interface.GetAddress(1), onoff_config.port)
    client.SetAttribute("Local", ns.AddressValue(local_adress.ConvertTo()))
    client_apps = client.Install(remote_nodes.Get(0))
    client_apps.Start(onoff_config.start_time)
    client_apps.Stop(onoff_config.stop_time)

# -------------------- Basic Slice class --------------------

class BasicRanSlice:
    """
    RanSlice is the basic class for creating a slice in RAN simulation. It sets up all the UEs' and eNodeBs' nodes and devices.
    """
    def __init__(self, N_UEs:int, initial_RB:int, RB_resolution:int = 1, min_RB:int = 6, max_RB:int = 100, logger:None|logging.Logger = None, unlim_RB=True, unchange_terminate:int=0, action_process_fn = None):
        self.N_UEs = N_UEs
        self.last_RB = initial_RB
        self.current_RB = initial_RB
        self.changed_RB = False
        self.RB_variation = 0
        self.change_RB_queue = deque(maxlen=unchange_terminate)
        self.unchange_terminate = unchange_terminate
        self.min_RB = min_RB
        self.max_RB = max_RB
        self.RB_resolution = RB_resolution
        self.candidate_RBs = list(range(min_RB, max_RB+1, RB_resolution))
        self.plot_data = []
        self.buffer_increase = None
        self.droped_size = None
        self.ids = {
            "UEs": [],
            "eNodeBs": []
        }
        self.ue_ips = []
        self.stat_df = pd.DataFrame(columns=["step", "nSend", "nRecv", "nRecvStep", "minDelay", "maxDelay", "avgDelay", "minRate", "maxRate", "avgRate", "delivRate", "throughput"])
        self.logger = logger
        self.name = None
        self.action_process_fn = action_process_fn
        self.accumulated_reward = 0
        self.accumulated_SLA_violation = 0
        self.accumulated_reconfig_times = 0

        # Create eNodeB nodes
        self.enb_nodes = ns.NodeContainer()
        if unlim_RB:
            self.enb_nodes.Create(len(self.candidate_RBs))
        else:
            self.enb_nodes.Create(6)
        mobilityhelper.Install(self.enb_nodes)

        # Get eNodeB nodes' ids
        for i in range(self.enb_nodes.GetN()):
            self.ids["eNodeBs"].append(self.enb_nodes.Get(i).GetId())

        # Create UE nodes
        self.ue_nodes = ns.NodeContainer()
        self.ue_nodes.Create(N_UEs)
        mobilityhelper.Install(self.ue_nodes)

        # Install eNodeB devices
        self.enb_divices = {}  # key: RB, val: NetDeviceContainer
        self.cellId2nodeId = {}

        if unlim_RB:
            index = 0
            for i in self.candidate_RBs:
                lte_helper.SetEnbDeviceAttribute("UlBandwidth", ns.UintegerValue(i))
                lte_helper.SetEnbDeviceAttribute("DlBandwidth", ns.UintegerValue(i))
                self.enb_divices[i] = lte_helper.InstallEnbDevice(self.enb_nodes.Get(index))
                self.cellId2nodeId[self.enb_divices[i].Get(0).GetObject["LteEnbNetDevice"]().GetCellIds()[0]] = self.enb_nodes.Get(index).GetId()
                index+=1
        else:
            index = 0
            for i in [6, 15, 25, 50, 75, 100]:
                lte_helper.SetEnbDeviceAttribute("UlBandwidth", ns.UintegerValue(i))
                lte_helper.SetEnbDeviceAttribute("DlBandwidth", ns.UintegerValue(i))
                self.enb_divices[i] = lte_helper.InstallEnbDevice(self.enb_nodes.Get(index))
                self.cellId2nodeId[self.enb_divices[i].Get(0).GetObject["LteEnbNetDevice"]().GetCellIds()[0]] = self.enb_nodes.Get(index).GetId()
                index+=1

        # Install UE devices
        self.ue_devices = lte_helper.InstallUeDevice(self.ue_nodes)

        # Install network stack and X2 interface to eNodeBs
        internet.Install(self.enb_nodes)
        lte_helper.AddX2Interface(self.enb_nodes)

        # Install internet stack to UEs
        internet.Install(self.ue_nodes)

        # Assign IP to UE
        self.ue_ip_interface = epc_helper.AssignUeIpv4Address(self.ue_devices)

        # Initialise routing for UEs
        for i in range(self.N_UEs):
            ue_node = self.ue_nodes.Get(i)
            ue_node_ipv4 = ue_node.GetObject["Ipv4"]()
            self.ue_routing = ipv4_routing_helper.GetStaticRouting(ue_node_ipv4)
            self.ue_routing.SetDefaultRoute(pgw_addr, 1)
            self.ids["UEs"].append(ue_node.GetId())  # Get UEs' ids
            self.ue_ips.append(str(self.ue_ip_interface.GetAddress(i)))   # Get UEs' IPs

        # Attach UEs to initial eNodeB
        lte_helper.Attach(self.ue_devices, self.enb_divices[initial_RB].Get(0))

        # Set Tx power to 0 for all eNodeBs except the initial one
        self.open_enb(initial_RB)

    def stat_report(self, step_time, rxtx = "tx", if_log=True) -> pd.Series:
        """
        Analyze the permformance of the slice in this step.
        """
        # Analyze packets transmission
        # Dataframe to store the performance per UE
        res = pd.DataFrame(columns=["UEIP", "step", "nSend", "nRecv", "nRecvStep", "minDelay", "maxDelay", "avgDelay", "minRate", "maxRate", "avgRate", "delivRate", "throughput", "tx_throughput", "pacSizeSum", "tx_pacSizeSum"])

        plot_data = {"step": step, "UE_data": {}, "RB": self.current_RB}

        # Analyze per UE
        for i in self.ue_ips:
            # Filter to analyze
            if rxtx == "tx":
                sub_merged_df = merged_df[merged_df["src_ip"]==i]
            elif rxtx == "rx":
                sub_merged_df = merged_df[merged_df["dest_ip"]==i]
            else:
                raise ValueError("'rxtx' should be 'tx' or 'rx'")

            # Get sending and receiving information
            sent_number = len(sub_merged_df[sub_merged_df["step_tx"]==step])
            recv_number_in_step = len(sub_merged_df[(sub_merged_df['_merge'] == 'both') & (sub_merged_df['step_tx'] == step)])
            recv_number_total = len(sub_merged_df[sub_merged_df["_merge"] == 'both'])

            # Delivery rate : number of received packets sent in this step / number of sent packets
            try:
                delivery_rate = recv_number_in_step/sent_number
            except ZeroDivisionError:
                delivery_rate = 1    # sending number could be zero

            # Delay: receiving time of packets received in this step - sending time
            delays = sub_merged_df[sub_merged_df['_merge'] == 'both']["time_rx"]-sub_merged_df[sub_merged_df['_merge'] == 'both']["time_tx"]
            average_delay = delays.mean()
            max_delay = delays.max()
            min_delay = delays.min()

            # Rate (Mb/s): avg(packet size / (receiving time - sending time))
            rates = sub_merged_df[sub_merged_df['_merge'] == 'both']["size_rx"] / delays
            average_rate = rates.mean()*8/1000/1000
            max_rate = rates.max()*8/1000/1000
            min_rate = rates.min()*8/1000/1000

            # Throughput (Mb/s): total received size / step time
            throughput = sub_merged_df["size_rx"].sum() / step_time
            throughput = throughput*8/1000/1000
            
            # Tx throughput (Mb/s): total sent size / step time
            tx_throughput = sub_merged_df[sub_merged_df["step_tx"]==step]["size_tx"].sum() / step_time
            tx_throughput = tx_throughput*8/1000/1000

            # Average packet size
            pac_size_sum = sub_merged_df[sub_merged_df['_merge'] == 'both']["size_rx"].sum()
            tx_pac_size_sum = sub_merged_df[sub_merged_df["step_tx"]==step]["size_tx"].sum()

            res.loc[len(res)] = [i, step, sent_number, recv_number_total, recv_number_in_step, min_delay, max_delay, average_delay, min_rate, max_rate, average_rate, delivery_rate, throughput, tx_throughput, pac_size_sum, tx_pac_size_sum]

            plot_data["UE_data"][i] = {"tx": tx_throughput, "rx": throughput}

        self.plot_data.append(plot_data)

        # Log report
        if self.logger and if_log:
            # Calculate performance per slice
            if rxtx == "tx":
                sub_merged_df = merged_df[merged_df["src_ip"].isin(self.ue_ips)]
            elif rxtx == "rx":
                sub_merged_df = merged_df[merged_df["dest_ip"].isin(self.ue_ips)]
            else:
                raise ValueError("'rxtx' should be 'tx' or 'rx'")
            sent_number = len(sub_merged_df[sub_merged_df["step_tx"]==step])
            recv_number_total = len(sub_merged_df[sub_merged_df["_merge"] == 'both'])
            receive_info = sub_merged_df[sub_merged_df['_merge'] == 'both']['step_tx'].value_counts()

            try:
                # recv_number_in_step error
                delivery_rate = recv_number_in_step/sent_number
            except ZeroDivisionError:
                delivery_rate = 1    # sending number could be zero

            delays = sub_merged_df[sub_merged_df['_merge'] == 'both']["time_rx"]-sub_merged_df[sub_merged_df['_merge'] == 'both']["time_tx"]
            average_delay = delays.mean()
            max_delay = delays.max()

            rates = sub_merged_df[sub_merged_df['_merge'] == 'both']["size_rx"] / delays
            average_rate = rates.mean()*8/1000/1000

            throughput = sub_merged_df["size_rx"].sum() / step_time
            throughput = throughput*8/1000/1000

            tx_throughput = sub_merged_df[sub_merged_df["step_tx"]==step]["size_tx"].sum() / step_time
            tx_throughput = tx_throughput*8/1000/1000

            log_title = f"-------------------- slice {self.name} step {step} report <{current_time:.3f}s - {current_time+step_time:.3f}s> --------------------" if self.name else \
                f"-------------------- step {step} report <{current_time:.3f}s - {current_time+step_time:.3f}s> --------------------"
            self.logger.info(log_title)
            self.logger.info(f"Sent {sent_number} packet in step {step}.")
            self.logger.info(f"Received {recv_number_total} packet in total.")
            for i in receive_info.index:
                self.logger.info(f"Received {receive_info[i]} packet from step {i}.")
            self.logger.info(f"Avg delay: {average_delay} s")
            self.logger.info(f"Max delay: {max_delay} s")
            self.logger.info(f"Delivery rate: {delivery_rate}")
            self.logger.info(f"Throughput: {throughput} Mb/s")
            self.logger.info(f"Tx Throughput: {tx_throughput} Mb/s")
            self.logger.info(f"Avg Rate: {average_rate} Mb/s")

        # Analyze RLC layer
        self.sub_buffer_record_df = buffer_record_df.loc[buffer_record_df.index.intersection(self.ids["eNodeBs"])]
        if self.sub_buffer_record_df.empty == False:
            sum_record = self.sub_buffer_record_df.sum()
            self.buffer_increase = (sum_record['pdcp_tx']-sum_record['rlc_tx']-sum_record['rlc_drop'])*8/1000 # kb
            self.droped_size = sum_record['rlc_drop']*8/1000 # kb
            if self.logger and if_log:
                self.logger.info(f"Buffer increase: {self.buffer_increase} kb")
                self.logger.info(f"RLC drop packet size: {self.droped_size} kb")
        else:
            self.buffer_increase = None
            self.droped_size = None

        return res
    
    def open_enb(self, RB, power=30):
        for i, d in self.enb_divices.items():
            phy = d.Get(0).GetPhy()
            if i != RB:
                phy.SetTxPower(0)
            else:
                phy.SetTxPower(power)

    def handoverTo(self, N_RAB:int):
        log_title = f"-------------------- slice {self.name} step {step} handover --------------------" if self.name else \
            f"-------------------- step {step} handover --------------------"
        self.logger.info(log_title)
        self.open_enb(N_RAB)
        if N_RAB != self.current_RB:
            for i in range(self.N_UEs):
                self.logger.info(f"UE {self.ids['UEs'][i]} handover to eNodeB with RB {N_RAB}")
                lte_helper.HandoverRequest(ns.Seconds(0), self.ue_devices.Get(i), self.enb_divices[self.current_RB].Get(0), self.enb_divices[N_RAB].Get(0))
            self.changed_RB = True
            self.RB_variation = abs(N_RAB - self.current_RB)
            self.accumulated_reconfig_times += 1
        else:
            self.logger.info(f"Retain in eNodeB with RB {N_RAB}")
            self.changed_RB = False
            self.RB_variation = 0
        self.last_RB = self.current_RB
        self.current_RB = N_RAB
        self.change_RB_queue.append(self.changed_RB)

    def set_enb_location(self, x):
        # Set location of eNodeBs to (x, 0, 0)
        for i in range(self.enb_nodes.GetN()):
            self.enb_nodes.Get(i).GetObject["ConstantPositionMobilityModel"]().SetPosition(ns.Vector(x, 0, 0))

    def get_enb_location(self):
        # Get location of eNodeBs
        res = set()
        for i in range(self.enb_nodes.GetN()):
            nsVector3D = self.enb_nodes.Get(i).GetObject["ConstantPositionMobilityModel"]().GetPosition()
            res.add((nsVector3D.x, nsVector3D.y, nsVector3D.z))
        if len(res) == 1:
            return res.pop()
        else:
            raise ValueError("Virtual eNodeBs are not in the same location")

    def set_ue_location(self, x, ue_range):
        # Set location of UEs to (x, 0, 0) with random x, y in range (-ue_range, ue_range)
        for i in range(self.N_UEs):
            self.ue_nodes.Get(i).GetObject["ConstantPositionMobilityModel"]().SetPosition(ns.Vector(random.uniform(x-ue_range, x+ue_range), random.uniform(-ue_range, ue_range), 0))

    def get_ue_location(self):
        # Get location of UEs
        res = []
        for i in range(self.N_UEs):
            nsVector3D = self.ue_nodes.Get(i).GetObject["ConstantPositionMobilityModel"]().GetPosition()
            res.append((nsVector3D.x, nsVector3D.y, nsVector3D.z))
        return res
    
    def get_terminated(self):
        return self.get_unchange_terminated()
        
    def get_unchange_terminated(self):
        if self.unchange_terminate:
            if len(self.change_RB_queue) < self.unchange_terminate:
                return False
            else:
                return not any(self.change_RB_queue)
        else:
            return False
    
    def clean_stat(self):
        self.stat_df.drop(self.stat_df.index, inplace=True)
        self.stat_df.reset_index(drop=True, inplace=True)

    def clean_RB_record(self, initial_RB):
        self.last_RB = initial_RB
        self.current_RB = initial_RB
        self.change_RB_queue.clear()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}[{self.N_UEs} UEs & {self.min_RB}:{self.RB_resolution}:{self.max_RB} eNodeBs]>"
    
    def get_info(self, max_display_nodes:int = 3) -> str:
        ue_location = self.get_ue_location()
        enb_location = self.get_enb_location()
        name = f"{self.name} ({self.__class__.__name__})" if self.name else self.__class__.__name__
        res = f"{name}:\n\n"
        res += f"Num of UEs: {self.N_UEs}\n"
        for i in range(self.N_UEs):
            if (i<max_display_nodes) or (i==self.N_UEs-1):
                res += f"UE {self.ids['UEs'][i]}: {self.ue_ips[i]} in {ue_location[i]}\n"
            if i == max_display_nodes:
                res += f"......\n"
        res += "\n"
        res += f"Num of candidate eNodeBs: {len(self.enb_divices)}\n"
        res += f"Virtual eNodeB location: {enb_location}\n"
        res += f"eNodeBs ids: {list_to_abbr_str(self.ids['eNodeBs'])}\n"
        res += f"RB from {self.min_RB} to {self.max_RB} with resolution {self.RB_resolution}\n"
        res += f"Current RB: {self.current_RB}\n"
        res += "\n"
        res += f"PGW {pgw.GetId()}: {pgw_addr}\n"
        res += "\n"
        res += f"RemoteHost {remote_nodes.Get(0).GetId()}: {p2p_ip_interface.GetAddress(1)}\n"
        return res
    
    def __str__(self) -> str:
        return self.get_info()

    def plot(self, save_path:str):
        # plot the sum of tx and rx throughput of each UE, and the RB in each step
        fig, ax = plt.subplots()

        # prepare data
        steps = [i["step"] for i in self.plot_data if i["step"]!=0]
        tx_throughputs = [sum([j["tx"] for j in i["UE_data"].values()]) for i in self.plot_data if i["step"]!=0]
        rx_throughputs = [sum([j["rx"] for j in i["UE_data"].values()]) for i in self.plot_data if i["step"]!=0]
        RBs = [i["RB"] for i in self.plot_data if i["step"]!=0]

        # plot ax1
        ax.plot(steps, tx_throughputs, label="Tx Throughput")
        ax.plot(steps, rx_throughputs, label="Rx Throughput")
        ax.set_xlabel('Steps')
        ax.set_ylabel('Throughput (Mb/s)')

        # plot ax2
        ax2 = ax.twinx()
        ax2.plot(steps, RBs, label="RB", color="yellow")
        ax2.set_ylabel('number of RBs')

        # add title
        fig.suptitle(f"Rew {self.accumulated_reward}, SLA_vio {self.accumulated_SLA_violation}, reconfig {self.accumulated_reconfig_times}")

        # show legend
        ax.legend()
        ax2.legend()

        # save figure
        fig.savefig(save_path)

        return {"steps": steps, "tx_throughputs": tx_throughputs, "rx_throughputs": rx_throughputs, "RBs": RBs}
    
    def clean_plot_data(self, save_path:str = None):
        if save_path:
            # save the plot data to a archive path
            save_data = {
                "plot_data": self.plot_data,
                "acc_SLA_vio": self.accumulated_SLA_violation,
                "acc_rew": self.accumulated_reward,
                "acc_reconfig": self.accumulated_reconfig_times
            }
            pickle.dump(save_data, open(save_path, "wb"))
        self.plot_data = []
        self.accumulated_SLA_violation = 0
        self.accumulated_reward = 0
        self.accumulated_reconfig_times = 0