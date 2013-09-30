from txsocksx import client, grammar
from parsley import makeProtocol, stack
from twisted.internet import reactor, interfaces

class MeasuredSOCKS5Receiver(client.SOCKS5Receiver):
    def __init__(self, sender):
        client.SOCKS5Receiver.__init__(self, sender)
        self.timer = interfaces.IReactorTime(reactor)
        # Don't have a parent factory yet
        self.init_time = "%0.2f" % self.timer.seconds()

    def prepareParsing(self, parser):
        client.SOCKS5Receiver.prepareParsing(self, parser)
        self.factory.times['SOCKET'] = self.init_time
        self.factory.times['CONNECT'] = "%0.2f" % self.timer.seconds()

    def auth_anonymous(self):
        self.factory.times['NEGOTIATE'] = "%0.2f" % self.timer.seconds()
        client.SOCKS5Receiver.auth_anonymous(self)

    def loginResponse(self, success):
        self.factory.times['NEGOTIATE'] = "%0.2f" % self.timer.seconds()
        client.SOCKS5Receiver.loginResponse(self, success)

    def _sendRequest(self):
        self.factory.times['REQUEST'] = "%0.2f" % self.timer.seconds()
        client.SOCKS5Receiver._sendRequest(self)

    def serverResponse(self, status, address, port):
        self.factory.times['RESPONSE'] = "%0.2f" % self.timer.seconds()
        client.SOCKS5Receiver.serverResponse(self, status, address, port)

MeasuredSOCKS5Client = makeProtocol(
    grammar.grammarSource,
    client.SOCKS5Sender,
    stack(client.SOCKS5AuthDispatcher, MeasuredSOCKS5Receiver),
    grammar.bindings)

class MeasuredSOCKS5ClientFactory(client.SOCKS5ClientFactory):
    protocol = MeasuredSOCKS5Client

    def __init__(self, times, *args, **kwargs):
        client.SOCKS5ClientFactory.__init__(self, *args, **kwargs)
        self.times = times

class MeasuredSOCKS5ClientEndpoint(client.SOCKS5ClientEndpoint):
    def __init__(self, times, *args, **kwargs):
        client.SOCKS5ClientEndpoint.__init__(self, *args, **kwargs)           
        self.times = times

    def connect(self, fac):
        proxyFac = MeasuredSOCKS5ClientFactory(self.times, self.host, self.port, fac, self.methods)
        d = self.proxyEndpoint.connect(proxyFac)
        d.addCallback(lambda proto: proxyFac.deferred)
        return d