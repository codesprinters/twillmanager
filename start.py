#!/usr/bin/env python
# encoding: utf-8

import sys
import twillmanager
import twillmanager.web
import cherrypy

def usage():
    """ Prints the start script usage """
    print "Usage: start.py config_file_name"

def start(config):
    """ Starts the application with given config (filename or dict)"""
    cherrypy.config.update(config)

    app = twillmanager.web.ApplicationRoot()
    cp_app = cherrypy.tree.mount(app, '/', config)
    app.configure(cp_app.config['twillmanager'])
    cherrypy.engine.start()
    cherrypy.engine.block()
    

if __name__ == "__main__":
    if len(sys.argv) != 2:
        usage()
    else:
        start(sys.argv[1])
