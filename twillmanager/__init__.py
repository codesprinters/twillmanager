# encoding: utf-8

from __future__ import absolute_import

import sqlite3
from threading import local

from twillmanager.mail import create_mailer

_thread_local = local()

__all__ = ['create_mailer', 'get_db_connection', 'create_db_connection', 'create_tables']

def create_db_connection(config):
    return sqlite3.connect(config['sqlite.file'])

def get_db_connection(config):
    if not hasattr(_thread_local, 'connection'):
        _thread_local.connection = create_db_connection(config)
    return _thread_local.connection


def create_tables(connection):
    c = connection.cursor()
    try:
        c.execute("SELECT * FROM twills LIMIT 1");
    except sqlite3.OperationalError:
        c.execute("""CREATE TABLE twills(
            id INTEGER PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            interval INTEGER NOT NULL,
            script TEXT,
            emails TEXT,
            status VARCHAR(100) NOT NULL,
            time INTEGER)""")
    connection.commit()
