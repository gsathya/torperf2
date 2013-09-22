import os
import txtorcon
import time
import signal

from twisted.internet.defer import Deferred
from httprunner import HTTPRunner
from pprint import pprint

class Experiment(object):
    def __init__(self, name, config):
        self._config = config
        self.name = name
        self.interval = self._config['interval']
        self.last_run = 0

    def next_runtime(self):
        return self.last_run + self.interval

    def run(self, reactor):
        raise NotImplementedError()

class SimpleHttpExperiment(Experiment):
    def __init__(self, name, config):
        Experiment.__init__(self, name, config)
        self.requests = self._config['requests']

    def run(self, reactor):
        self.results = []
        self.finished = Deferred()

        # Setup a tor client on a unique port
        torcfg = txtorcon.TorConfig()
        self.start_time = time.time()

        # TODO: Choose random (free) port for both of these
        self.socks_port = 9050
        torcfg.OrPort = 1234 
        torcfg.SocksPort = self.socks_port

        d = txtorcon.launch_tor(torcfg, reactor,
            progress_updates=self.tor_progress,
            timeout=60.0)
        self.socket_time = time.time()
        # Wait a small time?

        d.addCallback(self.tor_setup_complete, reactor)
        d.addErrback(self.handle_failure)

        return self.finished

    def tor_progress(self, progress, tag, summary):
        # TODO: Log whatever is valuable
        print "%d%%: %s" % (progress, summary)

    def tor_setup_complete(self, proto, reactor):
        print "Tor setup complete: ", proto
        self.tor_protoprocess = proto
        self.tor_instance = proto.tor_protocol
        
        state = txtorcon.TorState(proto.tor_protocol)
        state.post_bootstrap.addCallback(self.do_requests, reactor)
        state.post_bootstrap.addErrback(self.handle_failure)

    def handle_failure(self, arg):
        self.finished.errback(arg)

    def do_requests(self, state, reactor):
        runner = HTTPRunner(reactor, '127.0.0.1', self.socks_port)
        self.tor_instance.pid = state.tor_pid

        for url in self.requests:
            # TODO: Reset identity
            # Fetch url
            d = runner.get(url)
            d.addCallback(self.save_results, url)

    def save_results(self, results, url):
        results['START'] = self.start_time
        results['SOCKET'] = self.socket_time
        results['SOCKS'] = self.socks_port
        results['TOR_VERSION'] = self.tor_instance.version

        # The results could be an error
        self.results.append(results)
        if len(self.results) == len(self.requests):
            # Cleanup our tor instance
            #d = self.tor_instance.quit()
            # This callback seems to return before tor has actually quit
            #d.addCallback(self.return_results)
            # I don't want to do this, but the above doesn't seem to work.
            #os.kill(self.tor_instance.pid, signal.SIGKILL)
            try:
                self.tor_protoprocess.transport.signalProcess('KILL')
            except Exception:
                # Ignore the typeerror for no exit code (txtorcon bug?)
                print "Ignoring typeerror"
            self.return_results(None)

    def return_results(self, cbval):
        self.finished.callback(self.results)