import time

from urlparse import urlparse
from twisted.web import client
from twisted.internet import defer, endpoints, reactor, interfaces, protocol
from twisted.internet.protocol import Protocol
from twisted.internet.endpoints import TCP4ClientEndpoint
from txsocksx.http import SOCKS5Agent, SOCKS5ClientEndpoint
from twisted.web._newclient import ResponseDone

class HTTPRunner(object):

    def __init__(self, reactor, socks_host, socks_port):
        self._reactor = reactor
        self._socks_host = socks_host
        self._socks_port = socks_port

    def requestFinished(self, data, times, d):
        if data is not None:
            data = str(data)
            times['DATA'] = (data[:200] + '..') if len(data) > 200 else data
        d.callback(times)

    def get(self, url):
        d = defer.Deferred()
        times = {}
        url = bytes(url) # Fails on unicode

        factory = MeasuringHTTPClientFactory(url, times, 15.0)
        torServerEndpoint = TCP4ClientEndpoint(self._reactor, self._socks_host, self._socks_port)

        hostname = urlparse(url).hostname
        exampleEndpoint = SOCKS5ClientEndpoint(hostname, 80, torServerEndpoint)

        times['URL'] = url
        times['HOSTNAME'] = hostname

        reqd = exampleEndpoint.connect(factory)
        reqd.addErrback(self.requestFinished, times, d)

        http = factory.deferred
        http.addBoth(self.requestFinished, times, d)

        return d

    def post(self, url, data):
        pass

class MeasuringHTTPPageGetter(client.HTTPPageGetter):

    def __init__(self):
        self.timer = interfaces.IReactorTime(reactor)
        self.sentBytes = 0
        self.receivedBytes = 0
        # self.expectedBytes = 0
        self.decileLogged = 0

    def connectionMade(self):
        client.HTTPPageGetter.connectionMade(self)
        self.times['DATAREQUEST'] = "%.02f" % self.timer.seconds()
        pass

    def sendCommand(self, command, path):
        self.sentBytes += len('%s %s HTTP/1.0\r\n' % (command, path))
        #self.expectedBytes = int(path.split('/')[-1])
        client.HTTPPageGetter.sendCommand(self, command, path)

    def sendHeader(self, name, value):
        self.sentBytes += len('%s: %s\r\n' % (name, value))
        client.HTTPPageGetter.sendHeader(self, name, value)

    def endHeaders(self):
        self.sentBytes += len('\r\n')
        client.HTTPPageGetter.endHeaders(self)

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
        client.HTTPPageGetter.dataReceived(self, data)

    def handleResponse(self, response):
        self.times['WRITEBYTES'] = self.sentBytes
        self.times['READBYTES'] = self.receivedBytes
        self.times['DATACOMPLETE'] = "%.02f" % self.timer.seconds()
        self.times['DIDTIMEOUT'] = 0
        client.HTTPPageGetter.handleResponse(self, response)

    def timeout(self):
        self.times['WRITEBYTES'] = self.sentBytes
        self.times['READBYTES'] = self.receivedBytes
        self.times['DIDTIMEOUT'] = 1
        client.HTTPPageGetter.timeout(self)

class MeasuringHTTPClientFactory(client.HTTPClientFactory):

    def __init__(self, url, times, timeout):
        self.times = times
        client.HTTPClientFactory.__init__(self, url, timeout=timeout)
        self.protocol = MeasuringHTTPPageGetter

    def buildProtocol(self, addr):
        p = protocol.ClientFactory.buildProtocol(self, addr)
        p.followRedirect = self.followRedirect
        p.afterFoundGet = self.afterFoundGet
        if self.timeout:
            timeoutCall = reactor.callLater(self.timeout, p.timeout)
            self.deferred.addBoth(self._cancelTimeout, timeoutCall)
        p.times = self.times
        return p

