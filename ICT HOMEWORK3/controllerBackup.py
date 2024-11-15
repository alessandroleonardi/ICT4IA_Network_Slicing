from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.lib.packet import udp
from ryu.lib.packet import tcp
from ryu.lib.packet import icmp

import random


class TrafficSlicing(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(TrafficSlicing, self).__init__(*args, **kwargs)

        # out_port = slice_to_port[dpid][in_port]
        self.mac_to_port = {
            1: {
                "00:00:00:00:00:01": 3, # host 1 port 3
                "00:00:00:00:00:05": 1, # host 5 port 5
                "00:00:00:00:00:06": 2, # host 6 port 6
                "00:00:00:00:00:02": 4, # host 2 port 4
            },
            2: {
                "00:00:00:00:00:03": 3, # host 6 port 1
                "00:00:00:00:00:04": 4, # host 7 port 2
                "00:00:00:00:00:07": 1, # host 7 port 2
                "00:00:00:00:00:08": 2, # host 7 port 2
            },
            3: {
                "00:00:00:00:00:01": 1, # host 1 port 1
                "00:00:00:00:00:02": 1, # host 2 port 2
                "00:00:00:00:00:05": 2, # host 3 port 3
                "00:00:00:00:00:06": 2, # host 4 port 1
            },
            4: {
                "00:00:00:00:00:01": 1, # host 1 port 1
                "00:00:00:00:00:02": 1, # host 2 port 2
                "00:00:00:00:00:05": 3, # host 2 port 2
                "00:00:00:00:00:06": 3, # host 2 port 2
                "00:00:00:00:00:03": 2, # host 3 port 3
                "00:00:00:00:00:04": 2, # host 4 port 1
                "00:00:00:00:00:07": 4, # host 2 port 2
                "00:00:00:00:00:08": 4, # host 2 port 2
            },
            5: {
                "00:00:00:00:00:03": 1, # host 3 port 3
                "00:00:00:00:00:04": 1, # host 4 port 1
                "00:00:00:00:00:07": 2, # host 2 port 2
                "00:00:00:00:00:08": 2, # host 2 port 2
            },
            6: {
                "00:00:00:00:00:01": 1, # host 1 port 1
                "00:00:00:00:00:02": 2, # host 2 port 2
                "00:00:00:00:00:05": 3, # host 2 port 2
                "00:00:00:00:00:06": 4, # host 2 port 2
            },
            7: {
                "00:00:00:00:00:03": 1, # host 3 port 3
                "00:00:00:00:00:04": 2, # host 4 port 1
                "00:00:00:00:00:07": 3, # host 2 port 2
                "00:00:00:00:00:08": 4, # host 2 port 2
            },
        }
        # outport = slice_to_port[dpid][in_port]
        self.slice_to_port = {
            4: {1: 3, 3: 1, 2: 4, 4: 2}
        }
        self.slice_HTTPdata = 80
        self.slice_Videodata = 9999
        # outport = self.slice_ports[dpid][slicenumber]
        self.slice_ports = {1: {1: 2, 2: 1}, 6: {1: 2, 2: 1}}
        self.end_swtiches = [1, 6]


    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # install the table-miss flow entry.
        match = parser.OFPMatch()
        actions = [
            parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)
        ]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # construct flow_mod message and send it.
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(
            datapath=datapath, priority=priority, match=match, instructions=inst
        )
        datapath.send_msg(mod)

    def _send_package(self, msg, datapath, in_port, actions):
        data = None
        ofproto = datapath.ofproto
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = datapath.ofproto_parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data,
        )
        datapath.send_msg(out)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
         # reads some useful data
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            # ignore lldp packet
            return
        dst = eth.dst
        src = eth.src
        ip=pkt.protocols[1]
        ip_dst=ip.dst
        ip_src=ip.src

        dpid = datapath.id

        # Applies topology slicing
        if dpid in self.slice_to_port and in_port in self.slice_to_port[dpid]:
            out_port = self.slice_to_port[dpid][in_port]
            actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
            match = datapath.ofproto_parser.OFPMatch(in_port=in_port)
            self.add_flow(datapath, 1, match, actions)
            self._send_package(msg, datapath, in_port, actions)

        elif dpid in self.mac_to_port:
            if dst in self.mac_to_port[dpid]:
                out_port = self.mac_to_port[dpid][dst]
                actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
                match = datapath.ofproto_parser.OFPMatch(eth_dst=dst)
                self.add_flow(datapath, 1, match, actions)
                self._send_package(msg, datapath, in_port, actions)

            elif (pkt.get_protocol(udp.udp) and pkt.get_protocol(udp.udp).dst_port == self.slice_Videodata):
                slice_number = 1
                out_port = self.slice_ports[dpid][slice_number]
                match = datapath.ofproto_parser.OFPMatch(
                    in_port=in_port,
                    eth_dst=dst,
                    eth_type=ether_types.ETH_TYPE_IP,
                    ip_proto=0x11,  # udp
                    udp_dst=self.slice_Videodata,
                )

                actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
                self.add_flow(datapath, 2, match, actions)
                self._send_package(msg, datapath, in_port, actions)

            elif (pkt.get_protocol(udp.udp) and pkt.get_protocol(udp.udp).dst_port != self.slice_Videodata):
                slice_number = 2
                out_port = self.slice_ports[dpid][slice_number]
                match = datapath.ofproto_parser.OFPMatch(
                    in_port=in_port,
                    eth_dst=dst,
                    eth_src=src,
                    eth_type=ether_types.ETH_TYPE_IP,
                    ip_proto=0x11,  # udp
                    udp_dst=pkt.get_protocol(udp.udp).dst_port,
                )
                actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
                self.add_flow(datapath, 1, match, actions)
                self._send_package(msg, datapath, in_port, actions)

            elif pkt.get_protocol(tcp.tcp):
                slice_number = 2
                out_port = self.slice_ports[dpid][slice_number]
                match = datapath.ofproto_parser.OFPMatch(
                    in_port=in_port,
                    eth_dst=dst,
                    eth_src=src,
                    eth_type=ether_types.ETH_TYPE_IP,
                    ip_proto=0x06,  # tcp
                )
                actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
                self.add_flow(datapath, 1, match, actions)
                self._send_package(msg, datapath, in_port, actions)

            elif pkt.get_protocol(icmp.icmp):
                slice_number = 2
                out_port = self.slice_ports[dpid][slice_number]
                match = datapath.ofproto_parser.OFPMatch(
                    in_port=in_port,
                    eth_dst=dst,
                    eth_src=src,
                    eth_type=ether_types.ETH_TYPE_IP,
                    ip_proto=0x01,  # icmp
                )
                actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
                self.add_flow(datapath, 1, match, actions)
                self._send_package(msg, datapath, in_port, actions)

        elif dpid not in self.end_swtiches:
            out_port = ofproto.OFPP_FLOOD
            actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]
            match = datapath.ofproto_parser.OFPMatch(in_port=in_port)
            self.add_flow(datapath, 1, match, actions)
            self._send_package(msg, datapath, in_port, actions)