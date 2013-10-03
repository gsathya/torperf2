import os
import txtorcon
import time
import signal

from twisted.internet.defer import Deferred
from torperf.core.httprunner import HTTPRunner
from pprint import pprint
from urlparse import urlparse
from twisted.internet import interfaces

class Experiment(object):
    def __init__(self, name, config):
        self.set_config(config)
        self.set_name(name)
        self.set_interval()
        self.set_tor_version()
        self.last_run = 0

    def set_tor_version(self):
        if 'tor_version' in self._config.keys():
            self.tor_version = self._config['tor_version']
        else:
            self.tor_version = None

    def set_name(self, name):
        if isinstance(name, str) and len(name) > 0:
            self.name = name
        else:
            raise ValueError("An experiment must have a name.")

    def set_config(self, config):
        if config is not None:
            self._config = config
        else:
            raise ValueError("An experiment must have a config.")

    def set_interval(self):
        if not 'interval' in self._config.keys():
            raise KeyError("An experiment's config must have an interval.")
        self.interval = self._config['interval']
        if self.interval < 60:
            raise ValueError("Interval is too low, must be >= 60 seconds.")

    def next_runtime(self):
        return self.last_run + self.interval

    def run(self, reactor, http_port, server_config):
        raise NotImplementedError()

class SimpleHttpExperiment(Experiment):
    def __init__(self, name, config):
        Experiment.__init__(self, name, config)
        self.set_requests()

    def set_requests(self):
        r = self._config['requests']
        
        if isinstance(r, list):
            if len(r) < 1:
                raise ValueError("No requests urls specified.")
            else:
                for url in r:
                    if not self.check_valid_url(url):
                        raise ValueError("'%s' is not a valid url" % url)
                self.requests = r
        else:
            # Handle a single url
            if isinstance(r, str) and self.check_valid_url(r):
                self.requests = [r]
            else:
                raise ValueError("No requests urls specified.")

    def check_valid_url(self, url):
        return urlparse(url).hostname != None

    def run(self, reactor, http_port, server_config):
        self.finished = Deferred()

        runner = HTTPRunner(reactor, '127.0.0.1', http_port)
        self.start_time = time.time()

        for url in self.requests:
            # TODO: Reset identity
            # Fetch url
            d = runner.get(url)
            d.addCallback(self.save_results, url)

        return self.finished

    def save_results(self, results, url):
        results['START'] = self.start_time
        # results['SOCKET'] = self.socket_time
        #results['SOCKS'] = self.socks_port
        #results['TOR_VERSION'] = self.tor_instance.version

        # The results could be an error
        self.results.append(results)
        if len(self.results) == len(self.requests):
            # Cleanup our tor instance
            # try:
            #     self.tor_protoprocess.transport.signalProcess('KILL')
            # except Exception as ex:
            #     print "Caught exception:", ex
            self.return_results()

    def return_results(self):
        self.finished.callback(self.results)

class StaticFileExperiment(Experiment):
    def __init__(self, *args):
        Experiment.__init__(self, *args)
        self.set_files()

    def set_files(self):
        files = self._config['files']

        if isinstance(files, dict):
            if len(files) < 1:
                raise ValueError("No files specified.")
            else:
                for fn in files.keys():
                    sz = files[fn]
                    # Ensure we have a valid size for each filename
                    # TODO: Validate valid filenames
                    try:
                        x = sz
                        if not isinstance(sz, int):
                            x = int(sz, 10)
                        if x <= 0:
                            raise ValueError("'%d' is too small." % sz)
                        files[fn] = sz
                    except Exception as ex:
                        raise ValueError("'%s' is not a valid number" % sz)
                self.files = files
        else:
            raise ValueError("Files not specified in proper format.\nExpected: { 'filename': 'expected_size' }")

    def run(self, reactor, http_port, server_config):
        self.finished = Deferred()

        base_url = server_config['http_host'] + '/static/' + self.name + '/'
        public_folder = server_config['experiments_dir'] + self.name + '/public/'

        # Generate new files inside /experiments_dir/self/
        for fn in self.files.keys():
            sz = self.files[fn]
            full_path = public_folder + fn
            with open(full_path, 'w') as data_file:
                print "Writing %d bytes to %s" % (sz, full_path)
                data_file.write(os.urandom(sz))

        # Reset the start time
        timer = interfaces.IReactorTime(reactor)
        self.start_time = "%0.2f" % timer.seconds()
        runner = HTTPRunner(reactor, '127.0.0.1', http_port)

        for fn in self.files.keys():
            # TODO: Reset identity
            url = bytes(base_url + fn)
            sz = self.files[fn]

            # Send header X-Torperf-Expected-Bytes
            headers = { 'X-Torperf-Expected-Bytes': [sz] }
            # Fetch url
            d = runner.get(url, headers)
            d.addCallback(self.save_results, url)

        return self.finished

    def save_results(self, results, url):
        results['START'] = self.start_time

        # Remove the data results since it's random garbage
        # TODO: Verify received data is same as local file
        del results['DATA']

        # The results could be an error
        self.results.append(results)
        if len(self.results) == len(self.files):
            self.finished.callback(self.results)
