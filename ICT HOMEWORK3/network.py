#!/usr/bin/python3

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import OVSKernelSwitch, RemoteController
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import info


class NetworkSlicingTopo(Topo):
    def __init__(self):
        # Initialize topology
        Topo.__init__(self)

        # Create template host, switch and link
        host_config = dict(inNamespace=True)
        http_link_config = dict(bw=1)
        video_link_config = dict (bw=10)
        host_link_config = dict()

        # Create switch nodes
        for i in range(7):
            sconfig = {"dpid": "%016x" % (i+1)}
            self.addSwitch("s%d" % (i + 1), **sconfig)

        # Create host nodes
        for i in range (8):
            self.addHost("h%d" % (i + 1), **host_config)
        info(" Adding switch and links \n")
        # add Switch links
        self.addLink("s1","s3", **video_link_config)
        self.addLink("s1","s4", **http_link_config)
        self.addLink("s2","s4", **http_link_config)
        self.addLink("s2","s5", **http_link_config)
        self.addLink("s3","s6", **video_link_config)
        self.addLink("s4","s6", **http_link_config)
        self.addLink("s4","s7", **http_link_config)
        self.addLink("s5","s7", **http_link_config)

        # add host links
        self.addLink("h1","s1", **host_link_config)
        self.addLink("h2","s1", **host_link_config)
        self.addLink("h3","s2", **host_link_config)
        self.addLink("h4","s2", **host_link_config)
        self.addLink("h5","s6", **host_link_config)
        self.addLink("h6","s6", **host_link_config)
        self.addLink("h7","s7", **host_link_config)
        self.addLink("h8","s7", **host_link_config)

topos = {"networkslicingtopo": (lambda: NetworkSlicingTopo())}

if __name__ == "__main__":
    topo = NetworkSlicingTopo()
    net = Mininet(
            topo=topo,
            switch=OVSKernelSwitch,
            build=False,
            autoSetMacs=True,
            autoStaticArp=True,
            link=TCLink,
    )
    info("Adding the controller\n")
    controller = RemoteController("c1", ip="127.0.0.1", port=6633)
    net.addController(controller)
    net.build()
    info("\n Starting the network\n")
    net.start()
    CLI(net)
    net.stop()
