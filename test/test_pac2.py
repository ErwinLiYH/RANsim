import ransim
from ransim import FuncSlices
from ransim import Slice
from ransim_utils import utils
from ransim import Station
from ns import ns

log_helper = utils.logging_helper()
log1 = log_helper.get_simple_print_logger("test_pac1")
log2 = log_helper.get_simple_print_logger("test_pac2")
log3 = log_helper.get_simple_print_logger("station")

onoff_config1 = utils.OnOffAppConfig(0.1, 4.9, data_rate="35Mb/s")
onoff_config2 = utils.OnOffAppConfig(0.1, 4.9, data_rate="0.1Mb/s")

sink_config = utils.SinkAppConfig(0, 5)

Slice.InitRemoteSinkApp(sink_config)

testslice1 = FuncSlices.OnOffSlice(2, 25, onoff_config1, sink_config, logger=log1, unlim_RB=False)
testslice2 = FuncSlices.OnOffSlice(5, 25, onoff_config2, sink_config, logger=log2, unlim_RB=False)

station = Station.Station([testslice1, testslice2], logger=log3, warmup_times=10)

station.step([50,25])
station.step([50,25])
station.step([50,25])
station.step([25,50])
station.step([25,50])
station.step([25,50])