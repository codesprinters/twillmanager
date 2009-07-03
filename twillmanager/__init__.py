# encoding: utf-8

from __future__ import absolute_import

import os.path
import sys

import cherrypy

import twillmanager.web

__all__ = ['start']

def usage():
    """ Prints the start script usage """
    print "Usage: %s config_file_name"  % sys.argv[0]

def start():
    """ Starts the application """

    if len(sys.argv) != 2:
        usage()
        return

    config_file = sys.argv[1]

    static_directory = os.path.normpath(os.path.join(os.path.dirname(__file__), 'static'))
    local_config = {'/static': {'tools.staticdir.on': True,
            'tools.staticdir.dir': static_directory}}

    cherrypy.config.update(config_file)
    cherrypy.config.update(local_config)

    app = twillmanager.web.ApplicationRoot()
    cp_app = cherrypy.tree.mount(app, '/', config_file)
    cp_app.config.update(local_config)
    app.configure(cp_app.config['twillmanager'])

    cherrypy.engine.start()
    cherrypy.engine.block()
    app.finish()
