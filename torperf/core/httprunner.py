import time

from urlparse import urlparse
from twisted.web import client
from twisted.internet import defer, endpoints, reactor, interfaces, protocol
from twisted.internet.protocol import Protocol
from twisted.internet.endpoints import TCP4ClientEndpoint
from txsocksx.http import SOCKS5Agent, SOCKS5ClientEndpoint
from twisted.web._newclient import ResponseDone

from twisted.python.log import err
from twisted.web.client import ProxyAgent, RedirectAgent
from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ClientEndpoint

from twisted.web.http_headers import Headers

class DebugPrinter(Protocol):
    def __init__(self, finished, times):
        self.finished = finished
        self.remaining = 500
        self.times = times
        self.data = []

    def dataReceived(self, bytes):
        if self.remaining:
            self.data.append(bytes[:self.remaining])
            self.remaining -= len(bytes[:self.remaining])

    def connectionLost(self, reason):
        #print 'Finished receiving body:', reason.getErrorMessage()
        self.times['DATA'] = self.data
        self.finished.callback(self.times)

class HTTPRunner(object):

    def __init__(self, reactor, proxy_host, proxy_port):
        self._reactor = reactor
        self._proxy_host = proxy_host
        self._proxy_port = proxy_port

    def requestFinished(self, response, times, d):
        if hasattr(response, 'code'):
            times['HTTPSTATUS'] = response.code
        else:
            times['HTTPERROR'] = str(response)
            d.callback(times)
            return
        # if data.code == 200
        #    Non 200 results?
        if hasattr(response, 'headers'):
            times['headers'] = list(response.headers.getAllRawHeaders())

        if hasattr(response, 'deliverBody'):
            response.deliverBody(DebugPrinter(d, times))
        else:
            d.callback(times)

    def get(self, url):
        d = defer.Deferred()
        url = bytes(url) # Fails on unicode
        times = { 'URL': url }

        endpoint = TCP4ClientEndpoint(reactor, self._proxy_host, self._proxy_port)
        agent = RedirectAgent(ProxyAgent(endpoint))
        d2 = agent.request(
            'GET',
            url,
            Headers({'User-Agent': ['Mozilla/5.0 (Macintosh; Intel Mac OS X 10.8; rv:24.0) Gecko/20100101 Firefox/24.0']}),
            None
        )

        d2.addBoth(self.requestFinished, times, d)
        return d

    def post(self, url, data):
        pass