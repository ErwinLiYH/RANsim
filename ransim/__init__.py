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

Callback<void, std::string, uint64_t, uint16_t, uint16_t>
make_NotifyHandoverEndOkUeCallback(void(*func)(std::string, uint64_t, uint16_t, uint16_t)){
    return MakeCallback(func);
}

Callback<void, std::string, uint64_t, uint16_t, uint16_t, uint16_t>
make_NotifyHandoverStartUeCallback(void(*func)(std::string, uint64_t, uint16_t, uint16_t, uint16_t)){
    return MakeCallback(func);
}

Callback<void, std::string, uint16_t, uint8_t, uint32_t, uint64_t>
make_RxPduCallback(void(*func)(std::string, uint16_t, uint8_t, uint32_t, uint64_t)){
    return MakeCallback(func);
}

Callback<void, std::string, uint16_t, uint8_t, uint32_t>
make_TxPduCallback(void(*func)(std::string, uint16_t, uint8_t, uint32_t)){
    return MakeCallback(func);
}

Callback<void, std::string, Ptr< const Packet >>
make_DropPacCallback(void(*func)(std::string, Ptr< const Packet >)){
    return MakeCallback(func);
}
""")

ns.Config.SetDefault("ns3::LteEnbRrc::DefaultTransmissionMode", ns.UintegerValue(2))
# MIMO Spatial Multiplexity Open Loop
ns.Config.SetDefault ("ns3::LteRlcUm::MaxTxBufferSize", ns.UintegerValue (10 * 1024))
# ref: https://groups.google.com/g/ns-3-users/c/qbSu3pR9H5M, to improve throughput

# Close error models
ns.Config.SetDefault("ns3::LteSpectrumPhy::CtrlErrorModelEnabled", ns.BooleanValue(0))
ns.Config.SetDefault("ns3::LteSpectrumPhy::DataErrorModelEnabled", ns.BooleanValue(0))

TCP = "ns3::TcpSocketFactory"
UDP = "ns3::UdpSocketFactory"