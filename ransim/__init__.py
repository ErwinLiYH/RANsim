from ns import ns


# Function used to make callback for Rx and Tx events of UDP
ns.cppyy.cppdef(
"""
#include<string>
using namespace ns3;

Callback<void, std::string, Ptr< const Packet >, const Address &, const Address &, const SeqTsSizeHeader &>
make_SeqTsSizeCallback_with_context(void(*func)(std::string, Ptr< const Packet >, const Address &, const Address &, const SeqTsSizeHeader &)){
    return MakeCallback(func);
}
""")

ns.Config.SetDefault("ns3::LteSpectrumPhy::CtrlErrorModelEnabled", ns.BooleanValue(0))
ns.Config.SetDefault("ns3::LteSpectrumPhy::DataErrorModelEnabled", ns.BooleanValue(0))

TCP = "ns3::TcpSocketFactory"
UDP = "ns3::UdpSocketFactory"