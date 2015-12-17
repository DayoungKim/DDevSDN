#!/usr/bin/python

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.cli import CLI
from mininet.log import setLogLevel, info, debug
from mininet.node import Host, RemoteController
import json, sys
QUAGGA_DIR = '/usr/lib/quagga'
# Must exist and be owned by quagga user (quagga:quagga by default on Ubuntu)
QUAGGA_RUN_DIR = '/var/run/quagga'
CONFIG_DIR = 'configs'
zebraConf = '%s/zebra.conf' % CONFIG_DIR

class SdnIpHost(Host):
    def __init__(self, name, ip, route, *args, **kwargs):
        Host.__init__(self, name, ip=ip, *args, **kwargs)

        self.route = route

    def config(self, **kwargs):
        Host.config(self, **kwargs)

        debug("configuring route %s" % self.route)

        self.cmd('ip route add default via %s' % self.route)

class Router(Host):
    def __init__(self, name, quaggaConfFile, zebraConfFile, intfDict, *args, **kwargs):
        Host.__init__(self, name, *args, **kwargs)

        self.quaggaConfFile = quaggaConfFile
        self.zebraConfFile = zebraConfFile
        self.intfDict = intfDict

    def config(self, **kwargs):
        Host.config(self, **kwargs)
        self.cmd('sysctl net.ipv4.ip_forward=1')

        for intf, attrs in self.intfDict.items():
            self.cmd('ip addr flush dev %s' % intf)
            if 'mac' in attrs:
                self.cmd('ip link set %s down' % intf)
                self.cmd('ip link set %s address %s' % (intf, attrs['mac']))
                self.cmd('ip link set %s up ' % intf)
            for addr in attrs['ipAddrs']:
                self.cmd('ip addr add %s dev %s' % (addr, intf))

        self.cmd('/usr/lib/quagga/zebra -d -f %s -z %s/zebra%s.api -i %s/zebra%s.pid' % (self.zebraConfFile, QUAGGA_RUN_DIR, self.name, QUAGGA_RUN_DIR, self.name))
        self.cmd('/usr/lib/quagga/bgpd -d -f %s -z %s/zebra%s.api -i %s/bgpd%s.pid' % (self.quaggaConfFile, QUAGGA_RUN_DIR, self.name, QUAGGA_RUN_DIR, self.name))


    def terminate(self):
        self.cmd("ps ax | egrep 'bgpd%s.pid|zebra%s.pid' | awk '{print $1}' | xargs kill" % (self.name, self.name))

        Host.terminate(self)

BGP_MAC = '00:00:00:00:00:01'
class SdnIpTopo( Topo ):
    "SDN-IP tutorial topology"

    def i2strdpid(self, dpid):
        return '%s:%s:%s:%s:%s:%s:%s:%s'%(dpid[0:2],dpid[2:4],dpid[4:6],dpid[6:8],
                                          dpid[8:10],dpid[10:12],dpid[12:14],dpid[14:16])

    def addSwRouterHost(self, i):
        dpid = "a%015x" % i
        switch = self.addSwitch('s%d'%i, dpid=dpid)
        name = 'r%s' % i
        eth0 = { 'mac' : '00:00:00:00:%02x:01' % i,
                 'ipAddrs' : ['10.0.%s.1/24' % i] }#ip of r-eth0:switch-eth1
        eth1 = { 'ipAddrs' : ['192.168.%s.254/24' % i] }#ip of r-eth1:host-eth0
        intfs = { '%s-eth0' % name : eth0,
                      '%s-eth1' % name : eth1 }

        quaggaConf = '%s/quagga%s.conf' % (CONFIG_DIR, i)

        router = self.addHost(name, cls=Router, quaggaConfFile=quaggaConf,
                              zebraConfFile=zebraConf, intfDict=intfs)

        host = self.addHost('h%s' % i, cls=SdnIpHost,
                            ip='192.168.%s.1/24' % i,
                            route='192.168.%s.254' % i)
        self.addLink(router, switch)
        self.addLink(router, host)
        #return switch, dpid , ip
        return switch, self.i2strdpid(dpid), '10.0.%s'%i
    
    def addBGPSwSpeakerRoot(self, i, ipAddrs):
        dpid = 'a%015x' % i
        switch = self.addSwitch('s%d'%i, dpid=dpid)
        bgpEth0 = { 'mac': BGP_MAC ,
                    'ipAddrs' : [ip+'.101/24' for ip in ipAddrs]}
        bgpEth1 = { 'ipAddrs' : ['10.10.10.1/24'] }
        bgpIntfs = { 'bgp-eth0' : bgpEth0,
                     'bgp-eth1' : bgpEth1 }

        bgp = self.addHost( "bgp", cls=Router,
                             quaggaConfFile = '%s/quagga-sdn%d.conf' %( CONFIG_DIR, i-1),
                             zebraConfFile = zebraConf,
                             intfDict=bgpIntfs )
        root = self.addHost( 'root', inNamespace=False, ip='10.10.10.2/24')
        self.addLink( bgp , switch )
        self.addLink( root, bgp )

        return switch, self.i2strdpid(dpid)

    def makeConfigFiles(self, dpid_ip, bgpswdpid):
        addresses = []
        bgpPeers = []
        interfaceAddresses = []
        for dpid, ip in dpid_ip.iteritems():
            addresses.append({'dpid':dpid, 'port':'1','ips':[ip+'.101/24'],'mac':BGP_MAC})
            bgpPeers.append({'attachmentDpid':dpid,'attachmentPort':'1','ipAddress':ip+'.1'})
            interfaceAddresses.append({
                'interfaceDpid':dpid,'interfacePort':'1','ipAddress':ip+'.101'
            })
        bgpSpeaker=[{
            'name':'bgp','attachmentDpid':bgpswdpid,'attachmentPort':'1',
            'macAddress':BGP_MAC,'interfaceAddresses':interfaceAddresses
        }]
        addressesjson = open('/home/mininet/onos/tools/package/config/addresses.json','w+')
        json.dump({'addresses': addresses},addressesjson, indent=4)
        addressesjson.close()

        sdnipjson = open('/home/mininet/onos/tools/package/config/sdnip.json','w+')
        json.dump({'bgpPeers':bgpPeers,'bgpSpeakers':bgpSpeaker},sdnipjson, indent=4)
        sdnipjson.close()

        addressesjson = open('configs/addresses.json','w+')
        json.dump({'addresses': addresses},addressesjson, indent=4)
        addressesjson.close()

        sdnipjson = open('configs/sdnip.json','w+')
        json.dump({'bgpPeers':bgpPeers,'bgpSpeakers':bgpSpeaker},sdnipjson, indent=4)
        sdnipjson.close()


    def linear( self, n ):
        lastSwitch = None
        dpid_ip = {}
        for i in range(1, n+1):
            switch , dpid, ip = self.addSwRouterHost(i)
            dpid_ip.update({dpid:ip})
            if lastSwitch:
                self.addLink(switch, lastSwitch)
            lastSwitch=switch

        bgpAttachedSwitch , bgpswdpid = self.addBGPSwSpeakerRoot(n+1, ipAddrs=dpid_ip.values())
        self.addLink(bgpAttachedSwitch, lastSwitch)
        self.makeConfigFiles(dpid_ip, bgpswdpid)

    def leafspine( self, n ):
        leaves = []
        dpid_ip = {}
        for i in range(1, n+1):
            switch, dpid, ip = self.addSwRouterHost(i)
            dpid_ip.update({dpid:ip})
            leaves.append(switch)

        bgpAttachedSwitch , bgpswdpid = self.addBGPSwSpeakerRoot(n+1, ipAddrs=dpid_ip.values())
        spine_switch1 = self.addSwitch('s%d'%(n+2), dpid='a%015x' %(n+2))
        spine_switch2 = self.addSwitch('s%d'%(n+3), dpid='a%015x' %(n+3))
        spines = [spine_switch1, spine_switch2]

        self.addLink(bgpAttachedSwitch,spine_switch1)
        for spine in spines:
            for leaf in leaves:
                self.addLink(spine, leaf)
        self.makeConfigFiles(dpid_ip, bgpswdpid)

    def tree( self, n ):
        self.switchNum = 1000
        self.routerNum = 1
        self.dpid_ip = {}
        sw1 = self.addTree( n-1 )
        sw2 = self.addTree( n-1 )
        bgpAttachedSwitch , bgpswdpid = self.addBGPSwSpeakerRoot(self.routerNum, ipAddrs=self.dpid_ip.values())
        self.addLink(bgpAttachedSwitch, sw1)
        self.addLink(bgpAttachedSwitch, sw2)
        self.makeConfigFiles(self.dpid_ip, bgpswdpid)


    def addTree( self , depth ):
        isSwitch = depth > 1
        if isSwitch:
            node = self.addSwitch('s%d'%( self.switchNum))
            self.switchNum += 1
            for _ in range(2):
                child = self.addTree(depth - 1 )
                self.addLink(node, child)
        else:
            node, dpid, ip = self.addSwRouterHost(self.routerNum)
            self.routerNum += 1
            self.dpid_ip.update({dpid:ip})
        return node

    def  __init__(self, Type, n):
        super(SdnIpTopo, self).__init__()
        if Type == 'linear':
            self.linear(n)
        if Type == 'leafspine':
            self.leafspine(n)
        if Type == 'tree':
            self.tree(n)

if __name__ == '__main__':
    setLogLevel('debug')
    topo = SdnIpTopo(Type=sys.argv[1],n=int(sys.argv[2]))

    net = Mininet(topo=topo, controller=RemoteController(name='c0',ip='10.0.3.11'), listenPort=None)
    #net = Mininet(topo=topo, controller=RemoteController, listenPort=None)

    net.start()

    CLI(net)

    net.stop()

    info("done\n")
