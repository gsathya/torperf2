import os

from datetime import datetime

from twisted.web.server import Site
from twisted.web.static import File
from twisted.web.resource import Resource
from twisted.internet.endpoints import TCP4ServerEndpoint

class StaticFile(File):
    def render_GET(self, request):
        timestamp = datetime.now()
        uniqueRequestId = timestamp.isoformat()

        # Log first byte time
        self.log("Starting request for %s" % (uniqueRequestId))

        # Give the client a unique identifier
        request.setHeader('X-Torperf-request-id', uniqueRequestId)

        # Log last byte time when the request finishes
        request.notifyFinish().addCallback(self.log,
                                           "Finished request for %s" % (uniqueRequestId))
        request.notifyFinish().addErrback(self.log)

        return File.render_GET(self, request)

    def log(self, message):
        print "%s" % message
