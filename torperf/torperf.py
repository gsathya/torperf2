#!/usr/bin/env python


import txtorcon
import perfconf

from pprint import pformat

from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.internet.protocol import Protocol
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.web.client import Agent
from twisted.web.http_headers import Headers

from txsocksx.http import SOCKS5Agent


class BeginningPrinter(Protocol):
    def __init__(self, finished):
        self.finished = finished
        self.data = []

    def dataReceived(self, data):
        self.data.append(data)

    def connectionLost(self, reason):
        print 'Finished receiving body:', reason.getErrorMessage()
        print 'Body:', ''.join(self.data)
        self.finished.callback(None)

def cbRequest(response):
    print 'Response received'
    print 'Response headers:'
    print pformat(list(response.headers.getAllRawHeaders()))

    finished = Deferred()
    response.deliverBody(BeginningPrinter(finished))
    return finished

def cbShutdown(ignored):
    reactor.stop()

def do_request(state):
    torServerEndpoint = TCP4ClientEndpoint(reactor, '127.0.0.1', 9050)
    agent = SOCKS5Agent(reactor, proxyEndpoint=torServerEndpoint)
    d = agent.request('GET', 'http://www.google.com/')
    d.addCallback(cbRequest)
    d.addBoth(cbShutdown)

def setup_complete(proto):
    print "setup complete:", proto
    state = txtorcon.TorState(proto.tor_protocol)

    state.post_bootstrap.addCallback(do_request)
    state.post_bootstrap.addErrback(setup_failed)

def setup_failed(arg):
    print "Setup Failed", arg
    reactor.stop()

def updates(prog, tag, summary):
    print "%d%%: %s" % (prog, summary)

config = txtorcon.TorConfig()
config.OrPort = 1234
config.SocksPort = perfconf.tor_config['socks_port']

# Launch tor.
d = txtorcon.launch_tor(config, reactor, progress_updates=updates)
d.addCallback(setup_complete)
d.addErrback(setup_failed)
reactor.run()
