import os
import time

from twisted.web.server import Site
from twisted.web.static import File
from twisted.web import resource
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet import interfaces

class TimedFile(File):
    def __init__(self, server, path, defaultType="text/html", ignoredExts=(), registry=None, allowExt=0):
        File.__init__(self, path, defaultType, ignoredExts, registry, allowExt)
        self.server = server

    def render_GET(self, request):
        req_headers = dict(request.getAllHeaders())

        # Didn't come from our client
        if not 'x-torperfproxyid' in req_headers:
            return File.render_GET(self, request)

        unique_id = req_headers['x-torperfproxyid']

        # Create an entry in our datastore
        times = {}
        self.server.datastore[unique_id] = times
        self.timer = interfaces.IReactorTime(self.server.reactor)

        # Log first byte time
        times['SERVER_FIRSTBYTE'] = "%0.2f" % self.timer.seconds()

        # Log last byte time when the request finishes
        request.notifyFinish().addCallback(self.logLastByte, times)
        return File.render_GET(self, request)

    def logLastByte(self, error, times):
        if error:
            # Request closed early, should log the error
            times['SERVER_ERROR'] = str(error)

        times['SERVER_LASTBYTE'] = "%0.2f" % self.timer.seconds()

    # Probably better ways to handle this
    def createSimilarFile(self, path):
        f = self.__class__(self.server, path, self.defaultType, self.ignoredExts, self.registry)
        # refactoring by steps, here - constructor should almost certainly take these
        f.processors = self.processors
        f.indexNames = self.indexNames[:]
        f.childNotFound = self.childNotFound
        return f

class FileDispatcher(resource.Resource):
    children = {}
    def __init__(self, server, server_config):
        self.server = server
        self._experiments_dir = server_config['experiments_dir']
        
        for dir in os.listdir(self._experiments_dir):
            if dir[0] != ".":
                self.addExperiment(dir)

    def addExperiment(self, name):
        servePath = self._experiments_dir + name + "/public"
        self.putChild(name, TimedFile(self.server, servePath))
        print "Added static files for: %s" % name

class TorPerfFileServer(object):
    def __init__(self, reactor, server_config):
        self.reactor = reactor
        self.datastore = {}
        self._config = server_config
        self._dispatcher = FileDispatcher(self, self._config)

    def startServer(self):
        self.web_endpoint = TCP4ServerEndpoint(self.reactor,
                                                self._config['http_port'])
        root = resource.Resource()
        root.putChild("static", self._dispatcher)

        self.web_endpoint.listen(Site(root))
        print "Http Server started."

    def get_timings(self, identifier):
        if identifier in self._datastore:
            result = self.datastore[identifier]
            # Remove from results set
            del self.datastore[identifier]
            return result
        else:
            print "No timings found for %s" % identifier
            return None
