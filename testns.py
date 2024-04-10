"""
This script is a simple LTE simulation to test if your NS-3 environment is set correctly.
Make sure you have package ns3 installed.

Tested in NS-3 3.4.0
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


from ns import ns

dl_port = 1234

# Function used to make callback for Rx and Tx events of UDP
ns.cppyy.cppdef(
"""
#include<string>

using namespace ns3;
Callback<void, std::string, Ptr<const Packet>>
makeUdpTrace(void(*func)(std::string, Ptr<const Packet>)){
    return MakeCallback(func);
}
""")

def UdpTxCallback(contex, packet):
    print(f"At {ns.Simulator.Now().GetSeconds():.5f}s ,{contex}, Send {packet.__deref__().GetSize()} bytes data")

def UdpRxCallback(contex, packet):
    print(f"At {ns.Simulator.Now().GetSeconds():.5f}s ,{contex}, received {packet.__deref__().GetSize()} bytes data")

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
enb_nodes.Create(1)

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
enb_devices = lte_helper.InstallEnbDevice(enb_nodes)
ue_devices = lte_helper.InstallUeDevice(ue_nodes)

# Install network stack to UE and remote host
internet = ns.InternetStackHelper()
internet.Install(ue_nodes)
internet.Install(remote_nodes)
ue_ip_interface = epc_helper.AssignUeIpv4Address(ue_devices)

# Install p2p link between PGW and remote host
p2p_helper.SetDeviceAttribute("DataRate", ns.DataRateValue(ns.DataRate("100Gb/s")))
p2p_helper.SetDeviceAttribute("Mtu", ns.UintegerValue(1500))
p2p_helper.SetChannelAttribute("Delay", ns.TimeValue(ns.MilliSeconds(10)))
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

# ---------- Install UDP server ---------- #

# Install UDP server to remote host
udp_server = ns.UdpEchoServerHelper(dl_port)
udp_server_apps = udp_server.Install(remote_nodes.Get(0))
udp_server_apps.Start(ns.Seconds(0))
udp_server_apps.Stop(ns.Seconds(5.0))

# ---------- Install UDP clients ---------- #

# Install UDP client to UEs
udp_client = ns.UdpEchoClientHelper(p2p_ip_interface.GetAddress(1).ConvertTo(), dl_port)
udp_client.SetAttribute("MaxPackets", ns.UintegerValue(100))
udp_client.SetAttribute("Interval", ns.TimeValue(ns.Seconds(0.2)))
udp_client.SetAttribute("PacketSize", ns.UintegerValue(1024))
udp_client_apps = udp_client.Install(ue_nodes)
udp_client_apps.Start(ns.Seconds(0.3))
udp_client_apps.Stop(ns.Seconds(4.8))

# ---------- Enable UDP Traces ---------- #

# Enable UDP Tx Traces
UdpTxCallback_cpp = ns.cppyy.gbl.makeUdpTrace(UdpTxCallback)
ns.Config.Connect("/NodeList/*/ApplicationList/*/$ns3::UdpEchoClient/Tx", UdpTxCallback_cpp)

# Enable UDP Rx Traces
UdpRxCallback_cpp = ns.cppyy.gbl.makeUdpTrace(UdpRxCallback)
ns.Config.Connect("/NodeList/*/ApplicationList/*/$ns3::UdpEchoServer/Rx", UdpRxCallback_cpp)

# Enable UDP log
# ns.LogComponentEnable("UdpEchoClientApplication", ns.LOG_LEVEL_INFO)
# ns.LogComponentEnable("UdpEchoServerApplication", ns.LOG_LEVEL_INFO)

# Enable eNodeB Traces
# lte_helper.EnableTraces()

# ---------- Run Simulation ---------- #

# Simulate RL Gym environment, so set two steps here

# Run simulation for 2.5s
print("\n-------------------- Step1 0s-2.5s --------------------\n")
ns.Simulator.Stop(ns.Seconds(2.5))
ns.Simulator.Run()
# Run simulation for 2.5s
print("\n-------------------- Step2 2.5s-5s --------------------\n")
ns.Simulator.Stop(ns.Seconds(5))
ns.Simulator.Run()

ns.Simulator.Destroy()