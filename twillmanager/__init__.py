# encoding: utf-8

from __future__ import absolute_import

import cherrypy

from twillmanager.watcher import WatcherPool, Watcher

class ApplicationRoot(object):
    def __init__(self):
        self._pool = WatcherPool()

        
    @cherrypy.expose
    def index(self):
        return "Hello world"