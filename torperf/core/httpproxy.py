from twisted.web import http, proxy
from twisted.internet import reactor, interfaces, tcp
from twisted.internet.endpoints import TCP4ClientEndpoint
from torperf.core.socks import MeasuredSOCKS5ClientEndpoint
import urlparse

class WriteCountingTransport(tcp.Client):
    def __init__(self, wrapped):
        self.wrapped = wrapped
        self.sentBytes = 0

    def write(self, bytes):
        self.wrapped.write(bytes)
        self.sentBytes += len(bytes)

    def writeSequence(self, iovec):
        total = 0
        for s in iovec:
            total += len(s)
        self.wrapped.writeSequence(iovec)
        self.sentBytes += total

    def __getattr__(self, attr):
        return getattr(self.wrapped, attr)

class MeasuredHttpProxyClient(proxy.ProxyClient):
    def __init__(self, unique_id, *args):
        proxy.ProxyClient.__init__(self, *args)
        self.timer = interfaces.IReactorTime(reactor)
        self.timed_out = 0
        self.decileLogged = 0
        self.receivedBytes = 0
        # Modify outgoing headers here via self.father
        self.unique_id = unique_id
        # Send the request id to the server
        self.headers['X-TorPerfProxyId'] = self.unique_id
        self.setExpectedBytes()

    def setExpectedBytes(self):
        req_headers = dict(self.headers)
        # For some reason the header is lowercase
        if 'x-torperf-expected-bytes' in req_headers:
            self.expectedBytes = int(req_headers['x-torperf-expected-bytes'], 10)
        else:
            self.expectedBytes = 0

    def connectionMade(self):
        # Wrap the transport to record bytes sent
        self.transport = WriteCountingTransport(self.transport)

        self.father.times['DATAREQUEST'] = "%.02f" % self.timer.seconds()
        proxy.ProxyClient.connectionMade(self)
        # Add unique_id to response
        self.handleHeader('X-TorPerfProxyId', self.unique_id)

    """Mange returned header, content here.

    Use `self.father` methods to modify request directly.
    """
    def handleHeader(self, key, value):
        # change response header here
        # print "Header: %s: %s" % (key, value)
        proxy.ProxyClient.handleHeader(self, key, value)

    def handleResponsePart(self, buffer):
        # change response part here
        if self.receivedBytes == 0 and len(buffer) > 0:
            self.father.times['DATARESPONSE'] = "%.02f" % self.timer.seconds()
        self.receivedBytes += len(buffer)

        if self.expectedBytes > 0:
            while (self.decileLogged < 9 and
                  (self.receivedBytes * 10) / self.expectedBytes >
                   self.decileLogged):
                if self.decileLogged == 0:
                    self.father.times['DATAPERC'] = {}

                self.decileLogged += 1
                self.father.times['DATAPERC']['%d' % (self.decileLogged * 10, )] = \
                           "%.02f" % self.timer.seconds()

        # make all content upper case
        proxy.ProxyClient.handleResponsePart(self, buffer.upper())

    def handleStatus(self, version, code, message):
        if code != "200":
            print "Got status: %s for %s" % (code, self.father.uri)
            print "Message was: %s" % message
        proxy.ProxyClient.handleStatus(self, version, code, message)

    def handleResponseEnd(self):
        if not self._finished:
            self.father.times['WRITEBYTES'] = self.transport.sentBytes
            self.father.times['READBYTES'] = self.receivedBytes
            self.father.times['DATACOMPLETE'] = "%.02f" % self.timer.seconds()
            self.father.times['DIDTIMEOUT'] = self.timed_out
            self.father.times['FINALURI'] = self.father.uri
            proxy.ProxyClient.handleResponseEnd(self)

    def timeout(self):
        self.timed_out = 1
        self.handleResponseEnd()

class MeasuredHttpProxyClientFactory(proxy.ProxyClientFactory):
    protocol = MeasuredHttpProxyClient
    counter = 0
    init_time = None

    @classmethod
    def get_unique_id(cls, timer):
        cls.counter += 1
        if cls.init_time == None:
            cls.init_time = "%.02f" % timer.seconds()
        return cls.init_time + '_' + str(cls.counter)

    def __init__(self, *args, **kwargs):
        proxy.ProxyClientFactory.__init__(self, *args, **kwargs)
        timer = interfaces.IReactorTime(reactor)
        self.unique_id = MeasuredHttpProxyClientFactory.get_unique_id(timer)
        print "MeasuredHttpProxyClientFactory init called, counter is %s" % self.unique_id

    def buildProtocol(self, addr):
        #TODO: Add a timeout
        p = self.protocol(self.unique_id, self.command, self.rest, self.version,
                        self.headers, self.data, self.father)
        return p

    def clientConnectionFailed(self, connector, reason):
        """
        Report a connection failure in a response to the incoming request as
        an error.
        """
        self.father.setResponseCode(501, "Gateway error")
        self.father.responseHeaders.addRawHeader("Content-Type", "text/html")
        self.father.write("<H1>Could not connect</H1>")
        self.father.write(str(reason))

        print "Errored: %s" % str(reason)

        if hasattr(self.father, 'times'):
            print "Errored: %s" % self.father.times

        self.father.finish()

class MeasuredHttpProxyRequest(proxy.ProxyRequest):
    protocols = dict(http=MeasuredHttpProxyClientFactory)

    def __init__(self, channel, queued, reactor=reactor):
        proxy.ProxyRequest.__init__(self, channel, queued, reactor)
        # TODO: Take Tor socks port

    def process(self):
        print "Proxying request: %s" % self.uri
        parsed = urlparse.urlparse(self.uri)
        protocol = parsed[0]
        host = parsed[1]
        if protocol != "http":
            print "Skipping unimplemented protocol: %s" % protocol
            self.finish()
            return
        port = self.ports[protocol]
        if ':' in host:
            host, port = host.split(':')
            port = int(port)
        rest = urlparse.urlunparse(('', '') + parsed[2:])
        if not rest:
            rest = rest + '/'
        class_ = self.protocols[protocol]
        headers = self.getAllHeaders().copy()
        if 'host' not in headers:
            headers['host'] = host
        self.content.seek(0, 0)
        s = self.content.read()
        clientFactory = class_(self.method, rest, self.clientproto, headers,
                               s, self)

        self.times = {}
        self.channel.datastore[clientFactory.unique_id] = self.times

        torEndpoint = TCP4ClientEndpoint(self.reactor, '127.0.0.1', self.channel.socks_port)
        socksEndpoint = MeasuredSOCKS5ClientEndpoint(self.times, host, port, torEndpoint)

        socksReq = socksEndpoint.connect(clientFactory)
        def socks_error(reason):
            print "SOCKS ERROR: %s" % str(reason)
            # TODO: Log this error in times?
            self.finish()
        socksReq.addErrback(socks_error)

class MeasuredHttpProxy(proxy.Proxy):
    requestFactory = MeasuredHttpProxyRequest

class MeasuredHttpProxyFactory(http.HTTPFactory):
    #TODO TAKE A SOCKS PORT
    protocol = MeasuredHttpProxy

    def __init__(self, datastore, socks_port, **kwargs):
        self.protocol.datastore = datastore
        self.protocol.socks_port = socks_port
        http.HTTPFactory.__init__(self, **kwargs)