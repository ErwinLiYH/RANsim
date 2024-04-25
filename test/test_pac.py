import ransim
from ransim import Slice
from ransim import utils
from ns import ns


# ns.LogComponentEnable("OnOffApplication", ns.LOG_LEVEL_DEBUG)
# ns.LogComponentEnable("PacketSink", ns.LOG_LEVEL_DEBUG)

log_helper = utils.logging_helper()
log1 = log_helper.get_simple_print_logger("test_pac1")
log2 = log_helper.get_simple_print_logger("test_pac2")

onoff_config1 = utils.OnOffAppConfig(0.1, 4.9, data_rate="35Mb/s")
onoff_config2 = utils.OnOffAppConfig(0.1, 4.9, data_rate="0.1Mb/s")
sink_config = utils.SinkAppConfig(0, 5)

Slice.InitRemoteSinkApp(sink_config)

testslice1 = Slice.OnOffSlice(2, 25, onoff_config1, sink_config, logger=log1, unlim_RB=False)
testslice2 = Slice.OnOffSlice(5, 25, onoff_config2, sink_config, logger=log2, unlim_RB=False)

testslice1.set_enb_location(0)
testslice1.set_ue_location(0, 100)

testslice2.set_enb_location(5000)
testslice2.set_ue_location(5000, 100)

print(testslice1)
print(testslice2)

ns.Config.Connect("/NodeList/*/ApplicationList/*/$ns3::OnOffApplication/TxWithSeqTsSize", Slice.TxWithSeqTsSize_callback_cpp)
ns.Config.Connect("/NodeList/*/ApplicationList/*/$ns3::PacketSink/RxWithSeqTsSize", Slice.RxWithSeqTsSize_callback_cpp)

ns.Simulator.Stop(ns.Seconds(0.5))
ns.Simulator.Run()
Slice.merge_records()
testslice1.stat_report(0.5)
testslice2.stat_report(0.5)
Slice.step_records()

testslice1.handoverTo(100)

ns.Simulator.Stop(ns.Seconds(0.5))
ns.Simulator.Run()
Slice.merge_records()
testslice1.stat_report(0.5)
testslice2.stat_report(0.5)
Slice.step_records()
ns.Simulator.Destroy()
