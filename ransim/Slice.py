import pandas as pd
import logging
from ns import ns
from .utils import OnOffAppConfig, SinkAppConfig, logging_helper


# -------------------- DataFrames for recording Tx and Rx events --------------------

step=0

tx_record_df = pd.DataFrame(columns=["uid", "seq_num", "size", "time", "step", "src_ip", "src_port", "dest"])
rx_record_df = pd.DataFrame(columns=["uid", "seq_num", "size", "time", "step", "src_ip", "src_port", "dest"])

merged_df = None

# -------------------- Callbacks for Tx and Rx events --------------------

CALLBACK_LOGGER = logging_helper(level = logging.INFO).get_simple_print_logger("Slices callback")

def TxWithSeqTsSize_callback(contex, packet, address_src, address_dest, SeqTsSizeHeader):
    address_src = ns.InetSocketAddress.ConvertFrom(address_src)
    address_dest = ns.InetSocketAddress.ConvertFrom(address_dest)
    CALLBACK_LOGGER.debug(f"At {ns.Simulator.Now().GetSeconds():.5f}s ,{contex}, sent {packet.__deref__().GetSize()} bytes data")
    tx_record_df.loc[len(tx_record_df)] = [packet.__deref__().GetUid(), SeqTsSizeHeader.GetSeq(), SeqTsSizeHeader.GetSize(), ns.Simulator.Now().GetSeconds(), step, str(address_src.GetIpv4()), str(address_src.GetPort()), f"{address_dest.GetIpv4()}:{address_dest.GetPort()}"]


def RxWithSeqTsSize_callback(contex, packet, address_src, address_dest, SeqTsSizeHeader):
    address_src = ns.InetSocketAddress.ConvertFrom(address_src)
    address_dest = ns.InetSocketAddress.ConvertFrom(address_dest)
    CALLBACK_LOGGER.debug(f"At {ns.Simulator.Now().GetSeconds():.5f}s ,{contex}, received {packet.__deref__().GetSize()} bytes data")
    rx_record_df.loc[len(rx_record_df)] = [packet.__deref__().GetUid(), SeqTsSizeHeader.GetSeq(), SeqTsSizeHeader.GetSize(), ns.Simulator.Now().GetSeconds(), step, str(address_src.GetIpv4()), str(address_src.GetPort()), f"{address_dest.GetIpv4()}:{address_dest.GetPort()}"]

TxWithSeqTsSize_callback_cpp = ns.cppyy.gbl.make_SeqTsSizeCallback_with_context(TxWithSeqTsSize_callback)
RxWithSeqTsSize_callback_cpp = ns.cppyy.gbl.make_SeqTsSizeCallback_with_context(RxWithSeqTsSize_callback)

# -------------------- Function to merge and clean records --------------------

def merge_records():
    global merged_df
    merged_df = pd.merge(tx_record_df, rx_record_df, on=['seq_num', 'src_ip', 'src_port'], suffixes=('_tx', '_rx'), how='left', indicator=True)

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
    tcp_sink = ns.PacketSinkHelper(sink_config.socket_type, ns.InetSocketAddress(ns.Ipv4Address.GetAny(), sink_config.port).ConvertTo())
    tcp_sink.SetAttribute("EnableSeqTsSizeHeader", ns.BooleanValue(1))
    sink_apps = tcp_sink.Install(remote_nodes.Get(0))
    sink_apps.Start(sink_config.start_time)
    sink_apps.Stop(sink_config.stop_time)

# -------------------- Basic Slice class --------------------

class RanSlice:
    """
    RanSlice is the basic class for creating a slice in RAN simulation. It sets up all the UEs' and eNodeBs' nodes and devices.
    """
    def __init__(self, N_UEs:int, initial_RB:int, RB_resolution:int = 1, min_RB:int = 1, max_RB:int = 100, logger:None|logging.Logger = None, unlim_RB=True):
        self.N_UEs = N_UEs
        self.current_RB = initial_RB
        self.changed_RB = False
        self.min_RB = min_RB
        self.max_RB = max_RB
        self.RB_resolution = RB_resolution
        self.ids = {
            "UEs": [],
            "eNodeBs": []
        }
        self.ue_ips = []
        self.stat_df = pd.DataFrame(columns=["step", "nSend", "nRecv", "nRecvStep", "minDelay", "maxDelay", "avgDelay", "delivRate", "throughput", "rate"])
        self.logger = logger

        # Create eNodeB nodes
        self.enb_nodes = ns.NodeContainer()
        if unlim_RB:
            self.enb_nodes.Create(len(list(range(min_RB, max_RB+1, RB_resolution))))
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
        self.enb_divices = {}

        if unlim_RB:
            index = 0
            for i in range(min_RB, max_RB+1, RB_resolution):
                lte_helper.SetEnbDeviceAttribute("UlBandwidth", ns.UintegerValue(i))
                lte_helper.SetEnbDeviceAttribute("DlBandwidth", ns.UintegerValue(i))
                self.enb_divices[i] = lte_helper.InstallEnbDevice(self.enb_nodes.Get(index))
                index+=1
        else:
            index = 0
            for i in [6, 15, 25, 50, 75, 100]:
                lte_helper.SetEnbDeviceAttribute("UlBandwidth", ns.UintegerValue(i))
                lte_helper.SetEnbDeviceAttribute("DlBandwidth", ns.UintegerValue(i))
                self.enb_divices[i] = lte_helper.InstallEnbDevice(self.enb_nodes.Get(index))
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

    def stat_report(self, step_time) -> pd.Series:
        """
        Analyze the permformance of the slice in this step.
        """
        # Filter to analyze
        sub_merged_df = merged_df[merged_df["src_ip"].isin(self.ue_ips)]

        # Get sending and receiving information
        sent_number = len(sub_merged_df[sub_merged_df["step_tx"]==step])
        recv_number_in_step = len(sub_merged_df[(sub_merged_df['_merge'] == 'both') & (sub_merged_df['step_tx'] == step)])
        recv_number_total = len(sub_merged_df[sub_merged_df["_merge"] == 'both'])
        receive_info = sub_merged_df[sub_merged_df['_merge'] == 'both']['step_tx'].value_counts()
        # receive_info_str = ''
        # for i in receive_info.index:
        #     receive_info_str+=f"{i}:{receive_info[i]}|"

        # Delivery rate : number of received packets sent in this step / number of sent packets
        try:
            delivery_rate = recv_number_in_step/sent_number
        except ZeroDivisionError:
            delivery_rate = 1    # sending number could be zero

        # Delay: receiving time of packets received in this step - sending time
        temp = sub_merged_df[sub_merged_df['_merge'] == 'both']["time_rx"]-sub_merged_df[sub_merged_df['_merge'] == 'both']["time_tx"]
        average_delay = temp.mean()
        max_delay = temp.max()
        min_delay = temp.min()

        # Rate (Mb/s): avg(packet size / (receiving time - sending time))
        rate = (sub_merged_df[sub_merged_df['_merge'] == 'both']["size_rx"] / temp).mean()
        rate = rate*8/1024/1024

        # Throughput (Mb/s): total received size / step time
        throughput = sub_merged_df["size_rx"].sum() / step_time
        throughput = throughput*8/1024/1024

        # Log report
        if self.logger:
            self.logger.info(f"-------------------- step {step} report --------------------")
            self.logger.info(f"Sent {sent_number} packet in step {step}.")
            self.logger.info(f"Received {recv_number_total} packet in total.")
            for i in receive_info.index:
                self.logger.info(f"Received {receive_info[i]} packet from step {i}.")
            self.logger.info(f"Min delay: {min_delay} s")
            self.logger.info(f"Max delay: {max_delay} s")
            self.logger.info(f"Avg delay: {average_delay} s")
            self.logger.info(f"Delivery rate: {delivery_rate}")
            self.logger.info(f"Throughput: {throughput} Mb/s")
            self.logger.info(f"Rate: {rate} Mb/s")

        # record report
        self.stat_df.loc[len(self.stat_df)] = [step, sent_number, recv_number_total, receive_info[step], min_delay, max_delay, average_delay, delivery_rate, throughput, rate]

        return self.stat_df.loc[len(self.stat_df)-1]
    
    def handoverTo(self, N_RAB:int):
        if N_RAB != self.current_RB:
            for i in range(self.N_UEs):
                self.logger.info(f"UE {self.ids['UEs'][i]} handover to eNodeB with RB {N_RAB}")
                lte_helper.HandoverRequest(ns.Seconds(0), self.ue_devices.Get(i), self.enb_divices[self.current_RB].Get(0).GetObject["LteEnbNetDevice"](), self.enb_divices[N_RAB].Get(0).GetObject["LteEnbNetDevice"]())
            self.current_RB = N_RAB
            self.changed_RB = True
        else:
            self.logger.info(f"Retain in eNodeB with RB {N_RAB}")
            self.changed_RB = False

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}[{self.N_UEs} UEs & {self.min_RB}:{self.RB_resolution}:{self.max_RB} eNodeBs]>"
    
    def __str__(self) -> str:
        res = f"{self.__class__.__name__}:\n\n"
        for i in range(self.N_UEs):
            res += f"UE {self.ids['UEs'][i]}: {self.ue_ips[i]}\n"
        res += "\n"
        res += f"eNodeBs {self.ids['eNodeBs']}\n"
        res += f"RB from {self.min_RB} to {self.max_RB} with resolution {self.RB_resolution}\n"
        res += f"Current RB: {self.current_RB}\n"
        res += "\n"
        res += f"PGW {pgw.GetId()}: {pgw_addr}\n"
        res += "\n"
        res += f"RemoteHost {remote_nodes.Get(0).GetId()}: {p2p_ip_interface.GetAddress(1)}\n"
        return res


class OnOffSlice(RanSlice):
    """
    When creating a OnOffSlice, it will install a OnOff client for each UE, and do all action in RanSlice.
    """
    def __init__(self, N_UEs:int, initial_RB:int, onoff_config:OnOffAppConfig, sink_config:SinkAppConfig, RB_resolution: int = 1, min_RB: int = 1, max_RB: int = 100, logger:None|logging.Logger = None, unlim_RB=True):
        super().__init__(N_UEs, initial_RB, RB_resolution, min_RB, max_RB, logger, unlim_RB)

        # Install onoff client to UEs
        for i in range(self.N_UEs):
            tcp_client = ns.OnOffHelper(onoff_config.socket_type, ns.InetSocketAddress(p2p_ip_interface.GetAddress(1), sink_config.port).ConvertTo())
            tcp_client.SetAttribute("OnTime", onoff_config.on_time)
            tcp_client.SetAttribute("OffTime", onoff_config.off_time)
            tcp_client.SetAttribute("DataRate", onoff_config.data_rate)
            tcp_client.SetAttribute("PacketSize", onoff_config.packet_size)
            tcp_client.SetAttribute("EnableSeqTsSizeHeader", ns.BooleanValue(1))
            # if not set Local attr, the source ip when using UDP will be 0.0.0.0
            ue_adress = ns.InetSocketAddress(self.ue_ip_interface.GetAddress(i), onoff_config.port)
            tcp_client.SetAttribute("Local", ns.AddressValue(ue_adress.ConvertTo()))
            self.tcp_client_apps = tcp_client.Install(self.ue_nodes.Get(i))
            self.tcp_client_apps.Start(onoff_config.start_time)
            self.tcp_client_apps.Stop(onoff_config.stop_time)

    def reward(self, step_time):
        """
        An example of reward function. It just returns the rate of the slice in this step.
        """
        stat = self.stat_report(step_time)
        return stat["rate"]

class EmbbSlice(RanSlice):
    pass