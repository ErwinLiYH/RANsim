from . import Slice
from .utils import OnOffAppConfig, SinkAppConfig
import logging
from ns import ns


class OnOffSlice(Slice.BasicRanSlice):
    """
    An example for functional slice. When creating a OnOffSlice, it will install a OnOff client for each UE, and do all action in BasicRanSlice.
    """
    def __init__(self, N_UEs:int, initial_RB:int, onoff_config:OnOffAppConfig, sink_config:SinkAppConfig, RB_resolution: int = 1, min_RB: int = 1, max_RB: int = 100, logger:None|logging.Logger = None, unlim_RB=True):
        super().__init__(N_UEs, initial_RB, RB_resolution, min_RB, max_RB, logger, unlim_RB)

        # Install onoff client to UEs
        for i in range(self.N_UEs):
            tcp_client = ns.OnOffHelper(onoff_config.socket_type, ns.InetSocketAddress(Slice.p2p_ip_interface.GetAddress(1), sink_config.port).ConvertTo())
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
    