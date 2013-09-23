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
from torperf.core.experiments import Experiment

class TestExperimentBase(unittest.TestCase):

    def test_bad_inputs(self):
        # [Name, config, expected error type]
        combos = [
            # No name
            [None, {}, ValueError],
            # Empty name
            ['', {}, ValueError],
            # No config
            ['name', None, ValueError],
            # Empty config
            ['name', {}, KeyError],
            # Interval not defined
            ['name', { 'key': 'value' }, KeyError],
            # Interval too short
            ['name', { 'interval': 59 }, ValueError],
        ]
        
        for c in combos:
            try:
                xp = Experiment(c[0], c[1])
            except Exception as ex:
                self.assertTrue(isinstance(ex, c[2]), "Expected %s for inputs name:%s config:%s\nBut got %s" % (c[2], c[0], c[1], ex))
            except:
                self.fail(isinstance(ex, c[2]), "Expected %s for inputs name:%s config:%s\nBut no exception was thrown." % (c[2], c[0], c[1]))

    def test_init(self):
        xp = Experiment("name", {'interval': 600})

        self.assertEqual("name", xp.name)
        self.assertEqual(600, xp.interval)
        self.assertEqual(0, xp.last_run)