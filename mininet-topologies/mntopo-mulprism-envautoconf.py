from mininet.clean import cleanup
from mininet.net import Mininet
from mininet.topo import Topo
from mininet.cli import CLI
from mininet.node import RemoteController

from subprocess import call, check_output
from time import sleep
import re, os, sys

###CLI
from subprocess import call
from cmd import Cmd
from os import isatty
from select import poll, POLLIN
import sys
import time

from mininet.log import info, output, error
from mininet.term import makeTerms, runX11
from mininet.util import quietRun, isShellBuiltin, dumpNodeConnections
###
#import pdb; pdb.set_trace()
class LeafspineTopo( Topo ):
    def __init__(self, leaf=2):
        Topo.__init__(self)
        leaves=[]
        spines=[]
        hostIdx=1
        for sw in range(leaf):
            switch = self.addSwitch('s%d' % (sw+1))
            leaves.append(switch)
            host = self.addHost('h%d' %hostIdx)
            hostIdx+=1
            self.addLink(host, switch)
        for spine_sw in range(2):
            switch = self.addSwitch('s%d' % (leaf+spine_sw+1))
            for leaf_sw in leaves:
                self.addLink(switch, leaf_sw)



def configure_prism( net ):
    #configure hosts's ip and default gateway
    try:
        os.remove('/etc/mul/prism/vif.conf')
    except: pass
    prismconf = open('/etc/mul/prism/vif.conf','w+')
    for h in net.hosts:
    #    import pdb; pdb.set_trace()
        r = re.compile("([a-zA-Z]+)([0-9]+)")
        m = r.match(h.name)
        idx = m.group(2)
        ip_str='%s.%s.%s.2/24' % (idx,idx,idx)
        dfl_route='%s.%s.%s.1' % (idx,idx,idx)
        h.config(ip='%s' % ip_str, defaultRoute=dfl_route)
        h.setDefaultRoute(intf='dev %s via %s' % (h.intf().name,dfl_route))
        for port, (peer_name, peer_port)  in net.topo.ports[h.name].iteritems():
            if peer_name.startswith('s'):
                prismconf.write("0x%s|%d|pr-%s-eth%d\n" 
                                %(net.getNodeByName(peer_name).dpid,
                                  peer_port,peer_name,peer_port))
    prismconf.close()

    call(['bash','./mul.sh','start','prism'])
    sleep(3)

def configure_prism_intf( net ):
    for h in net.hosts:
        for port, (peer_name, peer_port) in net.topo.ports[h.name].iteritems():
            idx = h.IP().split(".")
            dfl_route = "%s.%s.%s.1/24" % (idx[0], idx[1], idx[2])
            call(['ifconfig',"pr-%s-eth%d"%(peer_name,peer_port),dfl_route,'up'])

def ping( node ):
    nodePoller = poll()
    nodPoller.register( node.stdout )
    bothPoller = poll()
    bothPoller.register(0)


topo = LeafspineTopo(3)
net = Mininet(topo=topo, controller=RemoteController, cleanup=True)
configure_prism(net)
net.start()
configure_prism_intf(net)
while True:
    ploss = net.ping()
    if ploss == 0: break
CLI(net)
net.stop()
cleanup()
