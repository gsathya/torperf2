import os
import time

from twisted.web.server import Site
from twisted.web.static import File
from twisted.web import resource
from twisted.internet.endpoints import TCP4ServerEndpoint

class TimedFile(File):
    counter = 0
    processStartTime = time.time()
    @classmethod
    def getUniqueId(cls):
        # This should be safe as twisted is single threaded?
        # It's also using the process start time so there's no
        # collisions if the service gets rebooted
        cls.counter += 1
        return "%s-%s" % (cls.processStartTime, cls.counter)

    def render_GET(self, request):
        uniqueRequestId = TimedFile.getUniqueId()
        
        # Log first byte time
        self.logFirstByte(uniqueRequestId)

        # Give the client a unique identifier
        request.setHeader('X-Torperf-request-id', uniqueRequestId)

        # Log last byte time when the request finishes
        request.notifyFinish().addCallback(self.logLastByte, uniqueRequestId)
        return File.render_GET(self, request)

    def logFirstByte(self, uniqueRequestId):
        print "Starting request for %s at %s" % (uniqueRequestId, time.time())

    def logLastByte(self, error, uniqueRequestId):
        if error:
            # Request closed early, should log the error
            pass

        # Log last byte time
        print "Finished request for %s at %s" % (uniqueRequestId, time.time())

class FileDispatcher(resource.Resource):
    children = {}
    def __init__(self, server_config):
        self._experiments_dir = server_config['experiments_dir']
        
        for dir in os.listdir(self._experiments_dir):
            if dir[0] != ".":
                self.addExperiment(dir)

    def addExperiment(self, name):
        servePath = self._experiments_dir + name + "/public"
        self.putChild(name, TimedFile(servePath))
        print "Added static files for: %s" % name

class TorPerfFileServer(object):
    def __init__(self, reactor, server_config):
        self._reactor = reactor
        self._config = server_config
        self._dispatcher = FileDispatcher(self._config)

    def startServer(self):
        self.web_endpoint = TCP4ServerEndpoint(self._reactor,
                                                self._config['http_port'])
        root = resource.Resource()
        root.putChild("static", self._dispatcher)
        self.web_endpoint.listen(Site(root))
        print "Http Server started."