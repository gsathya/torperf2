import time

from twisted.web import client
from twisted.internet import defer, endpoints, reactor, interfaces
from twisted.internet.protocol import Protocol
from twisted.internet.endpoints import TCP4ClientEndpoint
from txsocksx.http import SOCKS5Agent
from twisted.web._newclient import ResponseDone

class HTTPRunner(object):

    def __init__(self, reactor, socks_host, socks_port, ):
        torServerEndpoint = TCP4ClientEndpoint(reactor, socks_host, socks_port)
        self.socks_agent = SOCKS5Agent(reactor, proxyEndpoint=torServerEndpoint)
        pass

    def handleSocksResponse(self, response, times, d):
        protocol = MeasuringHTTPPageGetter(times)
        response.deliverBody(protocol)
        # TODO: This is pretty broken until we do a timed socks agent
        # need to also handle the response headers to get any unique ids
        # we've set from our hosted server
        protocol.finished.addCallback(d.callback)

    def get(self, url):
        d = defer.Deferred()
        times = {}
        # TODO: This is incorrect, need to handle the http vs socks
        # timings at the socks layer really
        times['DATAREQUEST'] = "%.02f" % time.time()
        sd = self.socks_agent.request('GET', bytes(url))
        sd.addCallback(self.handleSocksResponse, times, d)
        #TODO:  Handle error
        return d

    def post(self, url, data):
        pass

class MeasuringHTTPPageGetter(Protocol):

    def __init__(self, times):
        self.timer = interfaces.IReactorTime(reactor)
        self.sentBytes = 0
        self.receivedBytes = 0
        self.times = times
        # self.expectedBytes = 0
        self.decileLogged = 0
        self.finished = defer.Deferred()

    def connectionMade(self):
        # This is not accurate due to agent?
        #self.times['DATAREQUEST'] = "%.02f" % self.timer.seconds()
        pass

    def sendCommand(self, command, path):
        self.sentBytes += len('%s %s HTTP/1.0\r\n' % (command, path))
        #self.expectedBytes = int(path.split('/')[-1])

    def sendHeader(self, name, value):
        self.sentBytes += len('%s: %s\r\n' % (name, value))

    def endHeaders(self):
        self.sentBytes += len('\r\n')

    def dataReceived(self, data):
        if self.receivedBytes == 0 and len(data) > 0:
            self.times['DATARESPONSE'] = "%.02f" % self.timer.seconds()
        # Should probably dump data to a file for debug in the short term
        self.receivedBytes += len(data)
        # while (self.decileLogged < 9 and
        #       (self.receivedBytes * 10) / self.expectedBytes >
        #        self.decileLogged):
        #     self.decileLogged += 1
        #     self.times['DATAPERC%d' % (self.decileLogged * 10, )] = \
        #                "%.02f" % self.timer.seconds()

    def handleResponse(self, response):
        self.times['WRITEBYTES'] = self.sentBytes
        self.times['READBYTES'] = self.receivedBytes
        self.times['DATACOMPLETE'] = "%.02f" % self.timer.seconds()
        self.times['DIDTIMEOUT'] = 0

    def timeout(self):
        self.times['WRITEBYTES'] = self.sentBytes
        self.times['READBYTES'] = self.receivedBytes
        self.times['DIDTIMEOUT'] = 1

    def connectionLost(self, reason):
        # TODO: Fix this
        if reason.getErrorMessage() == "Response body fully received":
            self.times['WRITEBYTES'] = self.sentBytes
            self.times['READBYTES'] = self.receivedBytes
            self.times['DATACOMPLETE'] = "%.02f" % self.timer.seconds()
            self.times['DIDTIMEOUT'] = 0
        else:
            self.times['FAILREASON'] = reason.getErrorMessage()
            self.times['DEBUG'] = reason
        self.finished.callback(self.times)