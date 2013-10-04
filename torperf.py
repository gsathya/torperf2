#!/usr/bin/env python
#
# Copyright (c) 2013, Sathyanarayanan Gunasekaran, The Tor Project, Inc.
# See LICENSE for licensing information

import perfconf

from torperf.core.experimentScheduler import ExperimentScheduler

from twisted.internet import reactor, task
from twisted.python import log
import sys

log.startLogging(sys.stdout)

experimenTor = ExperimentScheduler(reactor, perfconf.tor_config)
experimenTor.start_experiments()

# SUPER HANDY DEBUG YEAH!
def setup_heartbeat():
    def beat():
        print "The reactor is still alive!"
    lc = task.LoopingCall(beat)
    lc.start(10.0)

setup_heartbeat()

reactor.run()