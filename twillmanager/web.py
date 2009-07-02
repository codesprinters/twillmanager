# encoding: utf-8

from __future__ import absolute_import

import cherrypy
from twillmanager import create_db_connection, create_tables
from twillmanager.watcher import WorkerSet, Watch
from threading import RLock

class ApplicationRoot(object):
    """ Web application interface """
    def __init__(self):
        self.worker_set = WorkerSet()
        self.database_lock = RLock() # to ensure exclusive access to sqlite connection
        self.config = None
        self.connection = None

    def configure(self, cfg):
        """ Configuration and initialization is delayed to allow working
            with CherryPy configuration API
        """
        self.config = cfg
        self.connection = create_db_connection(cfg)
        create_tables(self.connection)

        for w in Watch.load_all(self.connection):
            self.worker_set.add(w, self.config)

    @cherrypy.expose
    def index(self):
        return "Hello world"
    