# encoding: utf-8

from __future__ import absolute_import

import sqlite3

from twillmanager.mail import create_mailer

def create_db_connection(config):
    return sqlite3.connect(config['sqlite.file'])

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
