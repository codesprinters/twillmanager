# encoding: utf-8

from __future__ import absolute_import

import sqlite3
import cherrypy
from twillmanager.watcher import WorkerSet, Watch

class ApplicationRoot(object):
    def __init__(self):
        self.worker_set = WorkerSet()
        self.connection_string = None
        self.connection = None

    def configure(self, cfg):
        """ Configuration and initialization is delayed to allow working
            with CherryPy configuration API
        """
        self.connection_string = cfg['sqlite_file']
        self.connection = sqlite3.connect(cfg['sqlite_file'])
        self.create_tables()

        for w in Watch.load_all(self.connection):
            print w.name
            self.worker_set.add(w, self.connection_string)

    def create_tables(self):
        c = self.connection.cursor()
        try:
            c.execute("SELECT * FROM twills LIMIT 1");
        except sqlite3.OperationalError:
            c.execute("""CREATE TABLE twills(
                id INTEGER PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL,
                interval INTEGER NOT NULL,
                script TEXT,
                status VARCHAR(100) NOT NULL,
                time INTEGER)""")
        self.connection.commit()


    @cherrypy.expose
    def index(self):
        return "Hello world"
    