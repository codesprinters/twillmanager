# encoding: utf-8

from __future__ import absolute_import

import cherrypy

class ApplicationRoot(object):
    @cherrypy.expose
    def index(self):
        return "Hello world"