from twisted.internet import defer
from collections import deque
from torperf.core.httpproxy import MeasuredHttpProxyFactory

import txtorcon

class TorManager:
    # TODO: Pre-setup a normal instance for every version of tor listed in the config
    def __init__(self, reactor, config):
        self.instances = {}
        self.queued = {}
        self._reactor = reactor
        self._config = config
        self.port_offset = 0

    # TODO: Handle specialized configs
    def get_version(self, tor_version):
        if tor_version == None:
            tor_version = "latest"

        d = defer.Deferred()

        if tor_version in self.instances:
            i = self.instances[tor_version]
            if i.available:
                i.available = False
                return i.refresh_identity()
            else:
                if tor_version in self.queued:
                    self.queued[tor_version].append(d)
                else:
                    self.queued[tor_version] = deque([d])
        else:
            newTor = TorHttpProxy(tor_version, self.port_offset,
                                  self._reactor, self._config)
            newTor.ready.addCallback(self.startup_complete, d)
            newTor.ready.addErrback(self.startup_failed, d)
            self.port_offset += 1

        return d

    def startup_complete(self, instance, d):
        self.instances[instance.tor_version] = instance
        d.callback(instance)

    def startup_failed(self, error, d):
        d.errback(error)

    def free(self, instance):
        if instance.tor_version in self.queued:
            q = self.queued[instance.tor_version]
            next = q.popleft()
            if next:
                instance.available = False
                next.callback(instance)
            else:
                instance.available = True
        else:
            instance.available = True

class TorHttpProxy:
    def __init__(self, tor_version, port_offset, reactor, config):
        self.available = False
        self.ready = defer.Deferred()
        
        self.timings = {}

        self.socks_port = 9050 + port_offset
        self.http_port = 10050 + port_offset
        self.or_port = 11050 + port_offset
        self.control_port = 12050 + port_offset

        self.tor_version = tor_version

        # TODO: Choose random (free) port for both of these
        torcfg = txtorcon.TorConfig()
        torcfg.OrPort = self.or_port
        torcfg.ControlPort = self.control_port
        torcfg.SocksPort = self.socks_port

        d = txtorcon.launch_tor(torcfg, reactor,
                                timeout=60,
                                progress_updates=self.tor_progress)
        d.addCallback(self.tor_setup_complete, reactor)
        d.addErrback(self.ready.errback)

    def get_timings(self, identifier):
        if identifier in self.timings:
            result = self.timings[identifier]
            # Remove from results set
            del self.timings[identifier]

            # Add tor_version and socks port
            if hasattr(self.tor_instance, 'version'):
                result['TORVERSION'] = self.tor_instance.version

            result['SOCKS'] = self.socks_port

            return result
        else:
            print "No timings found for %s" % identifier
            return None

    def refresh_identity(self):
        def handle_response(response, d):
            if response != "OK":
                d.errback(response)
            else:
                print "Got a new identity!"
                d.callback(self)

        d = defer.Deferred()
        # Should probably clear cached DNS also
        # CLEARDNSCACHE -- Forget the client-side cached IPs for all hostnames.
        sig = self.tor_instance.signal("NEWNYM")
        sig.addBoth(handle_response, d)
        return d

    def tor_progress(self, progress, tag, summary):
        # TODO: Log whatever is valuable
        print "%d%%: %s" % (progress, summary)

    def tor_setup_complete(self, proto, reactor):
        print "Tor setup complete: ", proto
        self.tor_protoprocess = proto
        self.tor_instance = proto.tor_protocol

        f = MeasuredHttpProxyFactory(self.timings, self.socks_port)
        reactor.listenTCP(self.http_port, f)

        state = txtorcon.TorState(proto.tor_protocol)
        state.post_bootstrap.addCallback(lambda ignore: self.ready.callback(self))
        state.post_bootstrap.addErrback(self.ready.errback)

    def reset_identity(self, config):
        pass

    def quit(self, config):
        pass
