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
from torperf.core.experiments import SimpleHttpExperiment

class TestExperimentBase(unittest.TestCase):
    # [Name, config, expected error type]
    bad_combos = [
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
    def test_bad_inputs(self):
        for c in TestExperimentBase.bad_combos:
            try:
                xp = Experiment(c[0], c[1])
                self.fail("Expected %s for inputs name:%s config:%s\nBut no exception was thrown." % (c[2], c[0], c[1]))
            except Exception as ex:
                self.assertTrue(isinstance(ex, c[2]), "Expected %s for inputs name:%s config:%s\nBut got %s" % (c[2], c[0], c[1], ex))

    def test_init(self):
        xp = Experiment("name", {'interval': 600})

        self.assertEqual("name", xp.name)
        self.assertEqual(600, xp.interval)
        self.assertEqual(0, xp.last_run)

class TestSimpleHttpExperiment(unittest.TestCase):

    def test_init(self):
        xp = SimpleHttpExperiment("name", {
            'interval':600,
            'requests': [
                'http://www.torproject.org/',
            ]
        })

        self.assertTrue(isinstance(xp, Experiment))
        self.assertEqual(1, len(xp.requests))
        
    def test_bad_inputs(self):
        bad_combos = [
            # No requests
            [None, ValueError],
            # Empty requests array
            [[], ValueError],
            # Blank requests in array
            [[''], ValueError],
            # Non-urls in array
            [['not.a.url.com'], ValueError],
            # Bad urls and valid urls
            [['http://www.example.com', 'not.a.url.com'], ValueError],
            # Blank request string
            ['', ValueError],
            # Not a url
            ['not.a.url.com', ValueError],
        ]
        for c in bad_combos:
            try:
                cfg = { 'interval': 600 }
                cfg['requests'] = c[0]
                xp = SimpleHttpExperiment("name", cfg)
                self.fail("Expected %s for urls:%s\nBut no exception was thrown." % (c[1], c[0]))
            except Exception as ex:
                self.assertTrue(isinstance(ex, c[1]), "Expected %s for urls:'%s'\nBut got '%s'\n" % (c[1], c[0], ex))

        # Should still fail all bad combos for base class, even with a valid url
        for c in TestExperimentBase.bad_combos:
            try:
                if c[1]:
                    c[1]['requests'] = ['http://www.example.com']
                xp = SimpleHttpExperiment(c[0], c[1])
                self.fail("Expected %s for inputs name:%s config:%s\nBut no exception was thrown." % (c[2], c[0], c[1]))
            except Exception as ex:
                self.assertTrue(isinstance(ex, c[2]), "Expected %s for inputs name:%s config:%s\nBut got %s" % (c[2], c[0], c[1], ex))
        