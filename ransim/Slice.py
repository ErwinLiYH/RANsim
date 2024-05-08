import pandas as pd
import random
import logging
from ns import ns
from .utils import SinkAppConfig, OnOffAppConfig, logging_helper, list_to_abbr_str


# Current time
current_time = 0

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
    def __init__(self, N_UEs:int, initial_RB:int, RB_resolution:int = 1, min_RB:int = 6, max_RB:int = 100, logger:None|logging.Logger = None, unlim_RB=True):
        self.N_UEs = N_UEs
        self.last_RB = initial_RB
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
        self.stat_df = pd.DataFrame(columns=["step", "nSend", "nRecv", "nRecvStep", "minDelay", "maxDelay", "avgDelay", "minRate", "maxRate", "avgRate", "delivRate", "throughput"])
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

        # Set Tx power to 0 for all eNodeBs except the initial one
        self.open_enb(initial_RB)

    def stat_report(self, step_time, rxtx = "tx") -> pd.Series:
        """
        Analyze the permformance of the slice in this step.
        """
        # Dataframe to store the performance per UE
        res = pd.DataFrame(columns=["UEIP", "step", "nSend", "nRecv", "nRecvStep", "minDelay", "maxDelay", "avgDelay", "minRate", "maxRate", "avgRate", "delivRate", "throughput", "tx_throughput", "pacSizeSum"])

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
            average_rate = rates.mean()*8/1024/1024
            max_rate = rates.max()*8/1024/1024
            min_rate = rates.min()*8/1024/1024

            # Throughput (Mb/s): total received size / step time
            throughput = sub_merged_df["size_rx"].sum() / step_time
            throughput = throughput*8/1024/1024
            
            # Tx throughput (Mb/s): total sent size / step time
            tx_throughput = sub_merged_df[sub_merged_df["step_tx"]==step]["size_tx"].sum() / step_time
            tx_throughput = tx_throughput*8/1024/1024

            # Average packet size
            pac_size_sum = sub_merged_df[sub_merged_df['_merge'] == 'both']["size_rx"].sum()

            res.loc[len(res)] = [i, step, sent_number, recv_number_total, recv_number_in_step, min_delay, max_delay, average_delay, min_rate, max_rate, average_rate, delivery_rate, throughput, tx_throughput, pac_size_sum]

        # Log report
        if self.logger:
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
                delivery_rate = recv_number_in_step/sent_number
            except ZeroDivisionError:
                delivery_rate = 1    # sending number could be zero

            delays = sub_merged_df[sub_merged_df['_merge'] == 'both']["time_rx"]-sub_merged_df[sub_merged_df['_merge'] == 'both']["time_tx"]
            average_delay = delays.mean()

            rates = sub_merged_df[sub_merged_df['_merge'] == 'both']["size_rx"] / delays
            average_rate = rates.mean()*8/1024/1024

            throughput = sub_merged_df["size_rx"].sum() / step_time
            throughput = throughput*8/1024/1024

            tx_throughput = sub_merged_df[sub_merged_df["step_tx"]==step]["size_tx"].sum() / step_time
            tx_throughput = tx_throughput*8/1024/1024

            self.logger.info(f"-------------------- step {step} report <{current_time:.3f}s - {current_time+step_time:.3f}s> --------------------")
            self.logger.info(f"Sent {sent_number} packet in step {step}.")
            self.logger.info(f"Received {recv_number_total} packet in total.")
            for i in receive_info.index:
                self.logger.info(f"Received {receive_info[i]} packet from step {i}.")
            self.logger.info(f"Avg delay: {average_delay} s")
            self.logger.info(f"Delivery rate: {delivery_rate}")
            self.logger.info(f"Throughput: {throughput} Mb/s")
            self.logger.info(f"Tx Throughput: {tx_throughput} Mb/s")
            self.logger.info(f"Avg Rate: {average_rate} Mb/s")

        return res
    
    def open_enb(self, RB, power=30):
        for i, d in self.enb_divices.items():
            phy = d.Get(0).GetPhy()
            if i != RB:
                phy.SetTxPower(0)
            else:
                phy.SetTxPower(power)

    def handoverTo(self, N_RAB:int):
        self.logger.info(f"-------------------- step {step} handover --------------------")
        self.open_enb(N_RAB)
        if N_RAB != self.current_RB:
            for i in range(self.N_UEs):
                self.logger.info(f"UE {self.ids['UEs'][i]} handover to eNodeB with RB {N_RAB}")
                lte_helper.HandoverRequest(ns.Seconds(0), self.ue_devices.Get(i), self.enb_divices[self.current_RB].Get(0).GetObject["LteEnbNetDevice"](), self.enb_divices[N_RAB].Get(0).GetObject["LteEnbNetDevice"]())
            self.last_RB = self.current_RB
            self.current_RB = N_RAB
            self.changed_RB = True
        else:
            self.logger.info(f"Retain in eNodeB with RB {N_RAB}")
            self.changed_RB = False

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
    
    def clean_stat(self):
        self.stat_df.drop(self.stat_df.index, inplace=True)
        self.stat_df.reset_index(drop=True, inplace=True)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}[{self.N_UEs} UEs & {self.min_RB}:{self.RB_resolution}:{self.max_RB} eNodeBs]>"
    
    def get_info(self, max_display_nodes:int = 3) -> str:
        ue_location = self.get_ue_location()
        enb_location = self.get_enb_location()
        res = f"{self.__class__.__name__}:\n\n"
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
