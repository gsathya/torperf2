import os
import errno
import json
import time

from torperf.core.experiments import SimpleHttpExperiment, StaticFileExperiment
from torperf.core.tormanager import TorManager
from twisted.internet import defer, interfaces
from pprint import pprint

class ExperimentFactory(object):
    def get_experiment(self, name, experiments_dir):
        base_folder = experiments_dir + name + '/'
        exp = self.parse_config(name, base_folder)
        return exp

    def parse_config(self, name, experiment_dir):
        # Raises error if config doesn't exist
        config_path = experiment_dir + "config.json"
        with open(config_path) as config_file:
            config = json.load(config_file)

        if 'skip' in config.keys():
            if config['skip'] == True:
                raise Exception("Skipping.")

        if 'requests' in config.keys():
            return self.init_simple_experiment(name, experiment_dir, config)

        if 'files' in config.keys():
            return StaticFileExperiment(name, config)

        raise ValueError("Config is not setup in an expected manner.")

    def init_simple_experiment(self, name, experiment_dir, config):
        return SimpleHttpExperiment(name, config)

class ExperimentRunner(object):
    def __init__(self, reactor, config):
        self.reactor = reactor
        self.defers = {}
        self.timer = interfaces.IReactorTime(reactor)
        self.torManager = TorManager(reactor, config)
        self._server_config = config
        # TODO: take datastore param

    def run(self, experiment):
        self.defers[experiment.name] = defer.Deferred()

        # Setup new results set
        experiment.results = []
        experiment.start_time = "%.02f" % self.timer.seconds()

        p = self.torManager.get_version(experiment.tor_version)
        p.addCallback(self.got_tor_http_proxy, experiment)
        p.addErrback(self.errored, experiment, None)
        return self.defers[experiment.name] # Just use experiment.finished

    def got_tor_http_proxy(self, proxy, experiment):
        d = experiment.run(self.reactor, proxy.http_port, self._server_config)
        # TODO: Timeout based on experiment timeout
        d.addCallback(self.finished, experiment, proxy)
        d.addErrback(self.errored, experiment, proxy)

    # This should only really be called if there's an error
    # during setup and no results could be gained at all
    def errored(self, error, experiment, proxy):
        print "Experiment %s failed with error %s at %s" % (experiment.name, error, time.time())
        # TODO: ensure the error has a nested results set and try postprocess
        experiment.last_run = time.time()
        experiment.results.append({'ERROR': str(error)})
        self.save_results(experiment)
        if proxy is not None:
            self.torManager.free(proxy)
        self.defers[experiment.name].callback(None)

    def finished(self, ignore, experiment, proxy):
        print "Experiment %s finished at %s" % (experiment.name, time.time())
        experiment.last_run = time.time()
        self.postprocess_results(experiment, proxy)
        self.save_results(experiment)
        self.torManager.free(proxy)
        self.defers[experiment.name].callback(None)

    def postprocess_results(self, experiment, proxy):
        for r in experiment.results:
            if 'headers' in r.keys():
                if 'X-Torperfproxyid' in r['headers']:
                    # get the server data from the proxy
                    id = r['headers']['X-Torperfproxyid'][0]
                    proxy_timings = proxy.get_timings(id)
                    for key in proxy_timings.keys():
                        # Only overwrite it if the experiment hasn't chosen their own value
                        if key not in r:
                            r[key] = proxy_timings[key]

    def save_results(self, experiment):
        def make_sure_dirs_exist(path):
            try:
                os.makedirs(path)
            except OSError as err:
                if err.errno != errno.EEXIST:
                    raise

        results = experiment.results
        pprint(results)
        try:
            dirname = "results/" + experiment.name + "/"
            make_sure_dirs_exist(dirname)

            for r in results:
                if not 'START' in r.keys():
                    r['START'] = experiment.start_time
                filename = dirname + str(r['START']) + '.json'
                with open(filename, "w") as results_file:
                    results_file.write(json.dumps(r) + "\n")
        except Exception as e:
            print "Error: "
            print e

class ExperimentScheduler(object):
    def __init__(self, reactor, config):
        self._reactor = reactor
        self._config = config
        self._experiments_dir = config['experiments_dir']
        self._factory = ExperimentFactory()
        self._runner = ExperimentRunner(reactor, config)
        self.setup_experiments()

    def setup_experiments(self):
        # TODO: Cancel scheduled experiments?
        self.experiments = []

        for dir in os.listdir(self._experiments_dir):
            if dir[0] != ".":
                try:
                    self.experiments.append(self._factory.get_experiment(dir, self._experiments_dir))
                    # TODO: Update last_run time to the last result file's timestamp
                except Exception as err:
                    print "Error loading experiment %s:\n\t%s" % (dir, err)
                    continue

        print "Loaded %d experiments successfully." % len(self.experiments)

    def start_experiments(self):
        # Should probably just batch run all the valid experiments,
        # but one at a time might be better for accuracy?... test!
        self.run_next_experiment()

    def run_next_experiment(self):
        next_exp = None
        now = time.time()
        for exp in self.experiments:
            if not next_exp or next_exp.next_runtime() > exp.next_runtime():
                next_exp = exp

        # Check if the next_experiment is in the past or the future
        diff = next_exp.next_runtime() - now
        if diff < 0:
            def finishCb(ignore):
                # Wait for old tor client to shutdown.... -_-
                #self._reactor.callLater(15.0, self.run_next_experiment)
                self.run_next_experiment()
            # In the past, run it
            print "Running experiment %s at %s" % (next_exp.name, now)
            d = self._runner.run(next_exp)
            d.addBoth(finishCb)
        else:
            # Schedule for the future
            print "Scheduling experiment %s to run in %ss" % (next_exp.name, diff)
            self._reactor.callLater(diff, self.run_next_experiment)
