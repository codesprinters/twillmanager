# encoding: utf-8

from __future__ import absolute_import

import os.path
import sys
from optparse import OptionParser

import cherrypy

import twillmanager.web
from twillmanager.osutil import daemonize

__all__ = ['start']

def start():
    """ Starts the application """

    p = OptionParser(usage='Usage: %prog [options] config_file')
    p.add_option('-d', '--daemonize', action='store_true', dest='daemonize',
                 help='Start twillmanager in daemon mode')
    opts, args = p.parse_args()


    if len(args) != 1:
        print p.get_usage()
        sys.exit(1)
    config_file = args[0]

    static_directory = os.path.normpath(os.path.join(os.path.dirname(__file__), 'static'))
    local_config = {'/static': {'tools.staticdir.on': True,
            'tools.staticdir.dir': static_directory}}

    cherrypy.config.update(config_file)
    cherrypy.config.update(local_config)

    if opts.daemonize:
        cherrypy.config.update({'log.screen': False})
        daemonize()

    app = twillmanager.web.DashboardController()
    cp_app = cherrypy.tree.mount(app, '/', config_file)
    cp_app.config.update(local_config)
    app.configure(cp_app.config['twillmanager'])

    cherrypy.engine.start()
    cherrypy.engine.block()
    app.finish()
