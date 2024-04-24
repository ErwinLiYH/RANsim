"""
This script is a simple LTE simulation to test if your NS-3 environment is set correctly.
Make sure you have package ns3 installed.

Tested in NS-3 3.4.0

Contain delay and rate statistics.
"""

#                        Network Structure
#
#            +-------+       +----+       +------------------+
#            |       |       |PGW |-------| Remote Host      |
#            | eNodeB|-------|SGW |       | [UDP Server]     |
#            |       |       |    |       +------------------+
#            +---+---+       +----+            |
#                |             |               |
#                |             |               |
#          +-----+-------+     |     +---------+----+
#          |     UE1     |     +-----| P2P Internet |
#          | [UDP Client]|           +--------------+
#          +-------------+
#          
#          +-------------+
#          |     UE2     |            
#          | [UDP Client]|          
#          +-------------+
#          
#          +-------------+
#          |     UE3     |
#          | [UDP Client]|
#          +-------------+


# Add temp PYTHONPATH
import os
import sys
ns_build_root = "/home/yl1118/Desktop/ns-allinone-3.41/ns-3.41/build"
binding_path = os.path.join(ns_build_root, "bindings/python")
lib_path = os.path.join(ns_build_root, "lib")
include_path = os.path.join(ns_build_root, "include")
if binding_path not in sys.path:
    sys.path.append(binding_path)
current_PATH = os.environ.get('PATH', '')
current_LD_LIBRARY_PATH = os.environ.get('LD_LIBRARY_PATH', '')
os.environ["PATH"] = lib_path + os.pathsep+ current_PATH
os.environ["LD_LIBRARY_PATH"] = include_path + os.pathsep + current_LD_LIBRARY_PATH
# export LD_PRELOAD="/lib/x86_64-linux-gnu/libffi.so.7"

from ns import ns
import pandas as pd

# Log setting
# logLevel = ns.LOG_INFO
# ns.LogComponentEnable("LteEnbMac", logLevel)
# ns.LogComponentEnable("LteEnbRrc", logLevel)
# ns.LogComponentEnable("EpcEnbApplication", logLevel)
# ns.LogComponentEnable("LtePhy", logLevel)
# ns.LogComponentEnable("LteEnbPhy", logLevel)
# ns.LogComponentEnable("LteUePhy", logLevel)
# ns.LogComponentEnable("LteRlc", logLevel)
# ns.LogComponentEnable("LtePdcp", logLevel)

# Pandas setting
pd.set_option('display.max_rows', None)
pd.set_option('display.expand_frame_repr', False) 

port = 1234
send_port = 49153

tx_record_df = pd.DataFrame(columns=["uid", "size", "time", "step", "src", "dest", "seq_num"])
rx_record_df = pd.DataFrame(columns=["uid", "size", "time", "step", "src", "dest", "seq_num"])

def statistic_report(df1, df2):
    """
    df1 for tx
    df2 for rx
    """
    # print(df1)
    # print(df2)
    sent_number = len(df1[df1["step"]==step])
    print(f"sent {sent_number} packet in step {step}")
    merged_df = pd.merge(df1, df2, on=['seq_num', 'src'], suffixes=('_tx', '_rx'), how='left', indicator=True)
    # print(merged_df)
    recv_number_in_step = len(merged_df[(merged_df['_merge'] == 'both') & (merged_df['step_tx'] == step)])
    recv_number_total = len(df2)
    receive_info = merged_df[merged_df['_merge'] == 'both']['step_tx'].value_counts()
    for i in receive_info.index:
        print(f"received {receive_info[i]} packet from step {i}")
    # print(f"received {recv_number_in_step} packet sent in step {step}")
    print(f"received {recv_number_total} packet in total")
    try:
        delivery_rate = recv_number_in_step/sent_number
    except:
        delivery_rate = 1
    average_delay = (merged_df[merged_df['_merge'] == 'both']["time_rx"]-merged_df[merged_df['_merge'] == 'both']["time_tx"]).mean()
    rate = merged_df["size_rx"].sum() / (merged_df["time_rx"].max()-merged_df["time_rx"].min())
    print(f"delay: {average_delay} s\ndelivery rate: {delivery_rate}\nrate: {rate*8/1024/1024} Mbps")
    df1.drop(merged_df[merged_df['_merge'] == 'both'].index, inplace=True)
    df1.reset_index(drop=True, inplace=True)
    df2.drop(df2.index, inplace=True)

step = 0

# Function used to make callback for Rx and Tx events of UDP
ns.cppyy.cppdef(
"""
#include<string>
using namespace ns3;

Callback<void, std::string, Ptr< const Packet >, const Address &, const Address &, const SeqTsSizeHeader &>
make_SeqTsSizeCallback(void(*func)(std::string, Ptr< const Packet >, const Address &, const Address &, const SeqTsSizeHeader &)){
    return MakeCallback(func);
}

Callback<void, std::string, Ptr< const Packet >, const Address &, const Address &>
make_TwoAddressTracedCallback(void(*func)(std::string, Ptr< const Packet >, const Address &, const Address &)){
    return MakeCallback(func);
}
""")

def RxWithSeqTsSize_callback(contex, packet, address_src, address_dest, SeqTsSizeHeader):
    address_src = ns.InetSocketAddress.ConvertFrom(address_src)
    address_dest = ns.InetSocketAddress.ConvertFrom(address_dest)
    # print(f"At {ns.Simulator.Now().GetSeconds():.5f}s ,{contex}, received {packet.__deref__().GetSize()} bytes data")
    # print(f"Packet ID: {packet.__deref__().GetUid()}")
    # print(f"Packet Size: {packet.__deref__().GetSize()}")
    # print(f"Sequence Number: {SeqTsSizeHeader.GetSeq()}")
    # print(f"Time Stamp: {SeqTsSizeHeader.GetTs()}")
    # print(f"Size: {SeqTsSizeHeader.GetSize()}")
    rx_record_df.loc[len(rx_record_df)] = [packet.GetUid(), SeqTsSizeHeader.GetSize(), ns.Simulator.Now().GetSeconds(), step, f"{address_src.GetIpv4()}:{address_src.GetPort()}", f"{address_dest.GetIpv4()}:{address_dest.GetPort()}", SeqTsSizeHeader.GetSeq()]

def RxWithAddresses_callback(contex, packet, address_src, address_dest):
    address_src = ns.InetSocketAddress.ConvertFrom(address_src)
    address_dest = ns.InetSocketAddress.ConvertFrom(address_dest)
    print(f"At {ns.Simulator.Now().GetSeconds():.5f}s, received {packet.__deref__().GetSize()} bytes data")
    print(f"Context: {contex}, from {address_src.GetIpv4()}:{address_src.GetPort()} to {address_dest.GetIpv4()}:{address_dest.GetPort()}")
    rx_record_df.loc[len(rx_record_df)] = [packet.__deref__().GetUid(), packet.__deref__().GetSize(), ns.Simulator.Now().GetSeconds(), step, f"{address_src.GetIpv4()}:{address_src.GetPort()}", f"{address_dest.GetIpv4()}:{address_dest.GetPort()}"]

def TxWithSeqTsSize_callback(contex, packet, address_src, address_dest, SeqTsSizeHeader):
    address_src = ns.InetSocketAddress.ConvertFrom(address_src)
    address_dest = ns.InetSocketAddress.ConvertFrom(address_dest)
    # print(f"At {ns.Simulator.Now().GetSeconds():.5f}s ,{contex}, sent {packet.__deref__().GetSize()} bytes data")
    # print(f"Packet ID: {packet.__deref__().GetUid()}")
    # print(f"Packet Size: {packet.__deref__().GetSize()}")
    # print(f"Sequence Number: {SeqTsSizeHeader.GetSeq()}")
    # print(f"Time Stamp: {SeqTsSizeHeader.GetTs()}")
    # print(f"Size: {SeqTsSizeHeader.GetSize()}")
    tx_record_df.loc[len(tx_record_df)] = [packet.__deref__().GetUid(), SeqTsSizeHeader.GetSize(), ns.Simulator.Now().GetSeconds(), step, f"{address_src.GetIpv4()}:{address_src.GetPort()}", f"{address_dest.GetIpv4()}:{address_dest.GetPort()}", SeqTsSizeHeader.GetSeq()]
    

def TxWithAddresses_callback(contex, packet, address_src, address_dest):
    address_src = ns.InetSocketAddress.ConvertFrom(address_src)
    address_dest = ns.InetSocketAddress.ConvertFrom(address_dest)
    print(f"At {ns.Simulator.Now().GetSeconds():.5f}s, sent {packet.__deref__().GetSize()} bytes data")
    print(f"Context: {contex}, from {address_src.GetIpv4()}:{address_src.GetPort()} to {address_dest.GetIpv4()}:{address_dest.GetPort()}")
    tx_record_df.loc[len(tx_record_df)] = [packet.__deref__().GetUid(), packet.__deref__().GetSize(), ns.Simulator.Now().GetSeconds(), step, f"{address_src.GetIpv4()}:{address_src.GetPort()}", f"{address_dest.GetIpv4()}:{address_dest.GetPort()}"]

ns.Config.SetDefault("ns3::LteSpectrumPhy::CtrlErrorModelEnabled", ns.BooleanValue(0))
ns.Config.SetDefault("ns3::LteSpectrumPhy::DataErrorModelEnabled", ns.BooleanValue(0))

# Initialise LTE Helper
lte_helper = ns.CreateObject("LteHelper")
# Some bugs in LteHelper, must use CreateObject, cannot use constructor
# like `lte_helper = ns.LteHelper()`.
# ref: https://gitlab.com/nsnam/ns-3-dev/-/issues/1062#note_1853771087

# Initialise EPC Helper and install it to LTE Help
epc_helper = ns.PointToPointEpcHelper()
lte_helper.SetEpcHelper(epc_helper)

# Initialise P2P link Helper
p2p_helper = ns.PointToPointHelper()

# Get PGW
pgw = epc_helper.GetPgwNode()

# ---------- initialise nodes ---------- #

# Set container for eNodeB
enb_nodes = ns.NodeContainer()
enb_nodes.Create(2)

# Set container for UE
ue_nodes = ns.NodeContainer()
ue_nodes.Create(3)

# Set remote host
remote_nodes = ns.NodeContainer()
remote_nodes.Create(1)

# ---------- Set mobility ---------- #

# Set mobility
mobilityhelper = ns.MobilityHelper()
mobilityhelper.SetMobilityModel("ns3::ConstantPositionMobilityModel")
mobilityhelper.Install(enb_nodes)
mobilityhelper.Install(ue_nodes)

# ---------- Initialise network ---------- #

# Install device to Node
lte_helper.SetEnbDeviceAttribute("UlBandwidth", ns.UintegerValue(50))
# lte_helper.SetEpcHelper(epc_helper)
enb_devices1 = lte_helper.InstallEnbDevice(enb_nodes.Get(0))
lte_helper.SetEnbDeviceAttribute("UlBandwidth", ns.UintegerValue(100))
# lte_helper.SetEpcHelper(epc_helper)
enb_devices2 = lte_helper.InstallEnbDevice(enb_nodes.Get(1))
ue_devices = lte_helper.InstallUeDevice(ue_nodes)

# Get devices from devices container
LteEnbNetDevices_list = []
LteEnbNetDevices_list.append(enb_devices1.Get(0).GetObject["LteEnbNetDevice"]())
LteEnbNetDevices_list.append(enb_devices2.Get(0).GetObject["LteEnbNetDevice"]())

# Install network stack to UE and remote host
internet = ns.InternetStackHelper()
internet.Install(ue_nodes)
internet.Install(remote_nodes)
ue_ip_interface = epc_helper.AssignUeIpv4Address(ue_devices)

# Install network stack and X2 interface to eNodeBs
internet.Install(enb_nodes)
lte_helper.AddX2Interface(enb_nodes)

# Install p2p link between PGW and remote host
p2p_helper.SetDeviceAttribute("DataRate", ns.DataRateValue(ns.DataRate("100Gb/s")))
p2p_helper.SetDeviceAttribute("Mtu", ns.UintegerValue(1500))
# p2p_helper.SetChannelAttribute("Delay", ns.TimeValue(ns.MilliSeconds(10)))
p2p_link_device = p2p_helper.Install(pgw, remote_nodes.Get(0))

# Assign IP to PGW and remote host
ipv4_helper = ns.Ipv4AddressHelper()
ipv4_helper.SetBase("1.0.0.0", "255.0.0.0")
p2p_ip_interface = ipv4_helper.Assign(p2p_link_device)

# Create Routing
ipv4_routing_helper = ns.Ipv4StaticRoutingHelper()
remote_routing = ipv4_routing_helper.GetStaticRouting(remote_nodes.Get(0).GetObject["Ipv4"]())
remote_routing.AddNetworkRouteTo(ns.Ipv4Address("7.0.0.0"), ns.Ipv4Mask("255.0.0.0"), 1)

for i in range(ue_nodes.GetN()):
    ue_node = ue_nodes.Get(i)
    ue_routing = ipv4_routing_helper.GetStaticRouting(ue_node.GetObject["Ipv4"]())
    ue_routing.SetDefaultRoute(epc_helper.GetUeDefaultGatewayAddress(), 1)

# Attach UEs to eNodeB
lte_helper.Attach(ue_devices)

# ---------- Install TCP server ---------- #

# Install Sink app to remote host
tcp_sink = ns.PacketSinkHelper("ns3::TcpSocketFactory", ns.InetSocketAddress(ns.Ipv4Address.GetAny(), port).ConvertTo())
tcp_sink.SetAttribute("EnableSeqTsSizeHeader", ns.BooleanValue(1))
tcp_sink_apps = tcp_sink.Install(remote_nodes.Get(0))
tcp_sink_apps.Start(ns.Seconds(0.1))
tcp_sink_apps.Stop(ns.Seconds(5.0))

# ---------- Install TCP clients ---------- #

# Install TCP client to UEs
for i in range(ue_nodes.GetN()):
    tcp_client = ns.OnOffHelper("ns3::TcpSocketFactory", ns.InetSocketAddress(p2p_ip_interface.GetAddress(1), port).ConvertTo())
    tcp_client.SetAttribute("OnTime", ns.StringValue("ns3::ConstantRandomVariable[Constant=1]"))
    tcp_client.SetAttribute("OffTime", ns.StringValue("ns3::ConstantRandomVariable[Constant=0]"))
    tcp_client.SetAttribute("DataRate", ns.StringValue("30Mbps"));
    tcp_client.SetAttribute("PacketSize", ns.UintegerValue(512))
    tcp_client.SetAttribute("EnableSeqTsSizeHeader", ns.BooleanValue(1))
    # if not set Local attr, the source ip when using UDP will be 0.0.0.0
    ue_adress = ns.InetSocketAddress(ue_ip_interface.GetAddress(i), send_port)
    tcp_client.SetAttribute("Local", ns.AddressValue(ue_adress.ConvertTo()))
    tcp_client_apps = tcp_client.Install(ue_nodes.Get(i))
    tcp_client_apps.Start(ns.Seconds(2))
    tcp_client_apps.Stop(ns.Seconds(2.5))

# ---------- Enable UDP Traces ---------- #

# Enable OnOff Tx Traces
TxWithSeqTsSize_callback_cpp = ns.cppyy.gbl.make_SeqTsSizeCallback(TxWithSeqTsSize_callback)
ns.Config.Connect("/NodeList/*/ApplicationList/*/$ns3::OnOffApplication/TxWithSeqTsSize", TxWithSeqTsSize_callback_cpp)
# TxWithAddresses_callback_cpp = ns.cppyy.gbl.make_TwoAddressTracedCallback(TxWithAddresses_callback)
# ns.Config.Connect("/NodeList/*/ApplicationList/*/$ns3::OnOffApplication/TxWithAddresses", TxWithAddresses_callback_cpp)

# Enable Sink Rx Traces
RxWithSeqTsSize_callback_cpp = ns.cppyy.gbl.make_SeqTsSizeCallback(RxWithSeqTsSize_callback)
ns.Config.Connect("/NodeList/*/ApplicationList/*/$ns3::PacketSink/RxWithSeqTsSize", RxWithSeqTsSize_callback_cpp)
# RxWithAddresses_callback_cpp = ns.cppyy.gbl.make_TwoAddressTracedCallback(RxWithAddresses_callback)
# ns.Config.Connect("/NodeList/*/ApplicationList/*/$ns3::PacketSink/RxWithAddresses", RxWithAddresses_callback_cpp)

# Eable log
# ns.LogComponentEnable("OnOffApplication", ns.LOG_LEVEL_INFO)
# ns.LogComponentEnable("PacketSink", ns.LOG_LEVEL_INFO)

# Enable eNodeB Traces
# lte_helper.EnableTraces()

# ---------- Get configurations ---------- #

print("\n-------------------- eNodeB configurations --------------------\n")
enb_node = enb_nodes.Get(0)
enb_node_id = enb_node.GetId()
print(f"eNodeB Node ID: {enb_node_id}")

print(f"eNodeB downlink Bandwidth:{LteEnbNetDevices_list[0].GetDlBandwidth()}")
print(f"eNodeB downlink Earfcn:{LteEnbNetDevices_list[0].GetDlEarfcn()}")
print(f"eNodeB uplink Bandwidth:{LteEnbNetDevices_list[0].GetUlBandwidth()}")
print(f"eNodeB uplink Earfcn:{LteEnbNetDevices_list[0].GetUlEarfcn()}")

# ---------- Run Simulation ---------- #

# Simulate RL Gym environment, so set two steps here

# Run simulation for 0.05s
print("\n-------------------- Step0 2.0s-2.0.5s --------------------\n")
ns.Simulator.Stop(ns.Seconds(2.05))
ns.Simulator.Run()

# Calculate delay
statistic_report(tx_record_df,rx_record_df)
step+=1

# Dynamically adjust bandwidth
# ns.Config.Set(f"/NodeList/{enb_node_id}/DeviceList/*/$ns3::LteNetDevice/$ns3::LteEnbNetDevice/UlBandwidth", ns.UintegerValue(6))
# ns.Config.Set(f"/NodeList/{enb_node_id}/DeviceList/*/$ns3::LteNetDevice/$ns3::LteEnbNetDevice/DlBandwidth", ns.UintegerValue(6))
lte_helper.HandoverRequest(ns.Seconds(0), ue_devices.Get(0), LteEnbNetDevices_list[0], LteEnbNetDevices_list[1])
lte_helper.HandoverRequest(ns.Seconds(0), ue_devices.Get(1), LteEnbNetDevices_list[0], LteEnbNetDevices_list[1])
lte_helper.HandoverRequest(ns.Seconds(0), ue_devices.Get(2), LteEnbNetDevices_list[0], LteEnbNetDevices_list[1])


print("\n-------------------- configuration changed --------------------\n")
print("Configuration changed!")
print(f"eNodeB downlink Bandwidth:{LteEnbNetDevices_list[1].GetDlBandwidth()}")
print(f"eNodeB downlink Earfcn:{LteEnbNetDevices_list[1].GetDlEarfcn()}")
print(f"eNodeB uplink Bandwidth:{LteEnbNetDevices_list[1].GetUlBandwidth()}")
print(f"eNodeB uplink Earfcn:{LteEnbNetDevices_list[1].GetUlEarfcn()}")

# Run simulation for 0.05s
print("\n-------------------- Step1 2.05s-2.1s --------------------\n")
ns.Simulator.Stop(ns.Seconds(0.05))
ns.Simulator.Run()

# Calculate delay
statistic_report(tx_record_df,rx_record_df)
step+=1

# Run simulation for 0.05s
print("\n-------------------- Step2 2.1s-2.15s --------------------\n")
ns.Simulator.Stop(ns.Seconds(0.05))
ns.Simulator.Run()

# Calculate delay
statistic_report(tx_record_df,rx_record_df)
step+=1

for i in range(10):
    print(f"\n-------------------- Step{step} {2+(step)*0.05}s-{2+(step+1)*0.05}s --------------------\n")
    ns.Simulator.Stop(ns.Seconds(0.05))
    ns.Simulator.Run()

    # Calculate delay
    statistic_report(tx_record_df,rx_record_df)
    step+=1

ns.Simulator.Destroy()