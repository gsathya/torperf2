from twisted.trial import unittest
from twisted.internet import defer, task
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet.interfaces import IProtocolFactory
from zope.interface import implements
from twisted.internet.interfaces import IReactorCore

import sys
from StringIO import StringIO

import os
import tempfile
import shutil

from torperf.core.experimentScheduler import ExperimentScheduler

class FakeReactor(task.Clock):
    implements(IReactorCore)

    def __init__(self):
        super(FakeReactor, self).__init__()

reactor = FakeReactor()

class clean_tmp_dir(object):
    def __enter__(self):
        self.tmp_dir = tempfile.mkdtemp()
        return self.tmp_dir

    def __exit__(self, type, value, traceback):
        try:
            shutil.rmtree(self.tmp_dir)
        except OSError as ex:
            if ex.errno != 2: # File doesn't exist
                raise

class muted_std_out(object):
    def __enter__(self):
        self.old_stdout = sys.stdout
        out = StringIO()
        sys.stdout = out
        return out

    def __exit__(self, type, value, traceback):
        sys.stdout = self.old_stdout

class TestExperimentFactory(unittest.TestCase):

    def test_no_experiments(self):
        with clean_tmp_dir() as tmp_dir:
            config = {
                'experiments_dir': tmp_dir,

            }
            with muted_std_out() as out:
                sched = ExperimentScheduler(reactor, config)
                self.assertEqual(0, len(sched.experiments))

    def test_no_experiment_dir(self):
        with clean_tmp_dir() as tmp_dir:
            config = {
                'experiments_dir': tmp_dir + "/non_existent_folder/",
            }

            # This is a pretty bad config bug, maybe we should expect
            # the reactor to get shut down and a good error message
            # written to output
            try:
                with muted_std_out() as out:
                    sched = ExperimentScheduler(reactor, config)
            except Exception as ex:
                self.assertTrue(isinstance(ex, OSError))

    def test_experiment_no_config(self):
        with clean_tmp_dir() as tmp_dir:
            path = tmp_dir + '/experiment1/'
            os.makedirs(path)
            config = {
                'experiments_dir': tmp_dir,
            }
            # TODO: Check error message was written to console

            with muted_std_out() as out:
                sched = ExperimentScheduler(reactor, config)
                self.assertEqual(0, len(sched.experiments))

    def test_experiment_with_bad_configs(self):
        with clean_tmp_dir() as tmp_dir:
            path = tmp_dir + '/experiment1/'
            os.makedirs(path)
            config = {
                'experiments_dir': tmp_dir + "/",
            }

            bad_configs = [
                # No data
                "{}",
                # Bad JSON
                """
                {
                    requests: [
                        "http://www.torproject.org/"
                    ]
                }
                """,
                # Bad JSON
                """
                {
                    "interval",
                    "requests": [
                        "http://www.torproject.org/"
                    ]
                }
                """,
                # Missing interval
                """
                {
                    "requests": [
                        "http://www.torproject.org/"
                    ]
                }
                """,
                # Negative interval
                """
                {
                    "interval": -7,
                    "requests": [
                        "http://www.torproject.org/"
                    ]
                }
                """,
                # Interval too short (lower limit to be decided, currently 60)
                """
                {
                    "interval": 59,
                    "requests": [
                        "http://www.torproject.org/"
                    ]
                }
                """,
                # Missing request urls
                """
                {
                    "interval": 60,
                }
                """,
                # Empty url list
                """
                {
                    "interval": 60,
                    "requests": []
                }
                """,
            ]

            for bad_cfg in bad_configs:
                with open(path + "/config.json", "w") as f:
                    f.write(bad_cfg)

                # TODO: Check error message was written to console
                with muted_std_out() as out:
                    sched = ExperimentScheduler(reactor, config)
                    self.assertEqual(0, len(sched.experiments))

    def test_experiment_with_OK_config(self):
        with clean_tmp_dir() as tmp_dir:
            path = tmp_dir + '/experiment1/'
            os.makedirs(path)

            config = {
                'experiments_dir': tmp_dir + "/",
            }

            with open(path + "/config.json", "w") as f:
                f.write("""
                    {
                        "interval": 60,
                        "requests": [
                            "http://www.torproject.org/"
                        ]
                    }
                    """
                )

            # TODO: Check error message was written to console
            with muted_std_out() as out:
                sched = ExperimentScheduler(reactor, config)
                self.assertEqual(1, len(sched.experiments))

    def test_many_experiments_some_bad(self):
        with clean_tmp_dir() as tmp_dir:
            config = {
                'experiments_dir': tmp_dir + "/",
            }

            def write_configs(names, json):
                for x in names:
                    path = tmp_dir + '/' + x + '/'
                    os.makedirs(path)

                    with open(path + "/config.json", "w") as f:
                        f.write(json)

            good_exps = ['experiment1', 'xp2', '2314asdaSCIENCE']

            write_configs(good_exps, """
                {
                    "interval": 60,
                    "requests": [
                        "http://www.torproject.org/"
                    ]
                }
                """
            )

            bad_exps = ['bad', 'nichtgud', 'error gehaben']
            write_configs(bad_exps, "{}")

            # TODO: Check error message was written to console
            with muted_std_out() as out:
                sched = ExperimentScheduler(reactor, config)
                self.assertEqual(len(good_exps), len(sched.experiments))

    def test_many_experiments_with_OK_configs(self):
        with clean_tmp_dir() as tmp_dir:
            config = {
                'experiments_dir': tmp_dir + "/",
            }

            exps = ['experiment1', 'xp2', '2314asdaSCIENCE']

            for x in exps:
                path = tmp_dir + '/' + x + '/'
                os.makedirs(path)

                with open(path + "/config.json", "w") as f:
                    f.write("""
                        {
                            "interval": 60,
                            "requests": [
                                "http://www.torproject.org/"
                            ]
                        }
                        """
                    )

            # TODO: Check error message was written to console
            with muted_std_out() as out:
                sched = ExperimentScheduler(reactor, config)
                self.assertEqual(len(exps), len(sched.experiments))