#!/usr/bin/env python
# encoding: utf-8

import os.path
import sys

import cherrypy

import twillmanager
import twillmanager.web



def start(config):
    """ Starts the application with given config (filename or dict)"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    local_config = {'/static': {'tools.staticdir.on': True,
            'tools.staticdir.dir': os.path.join(current_dir, 'static')}}

    cherrypy.config.update(config)
    cherrypy.config.update(local_config)

    app = twillmanager.web.ApplicationRoot()
    cp_app = cherrypy.tree.mount(app, '/', config)
    cp_app.config.update(local_config)
    app.configure(cp_app.config['twillmanager'])


    cherrypy.engine.start()
    cherrypy.engine.block()
    app.finish()
    

if __name__ == "__main__":
    if len(sys.argv) != 2:
        usage()
    else:
        start(sys.argv[1])
