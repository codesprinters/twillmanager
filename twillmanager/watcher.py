# encoding: utf-8

from __future__ import absolute_import
from __future__ import with_statement

from StringIO import StringIO
from threading import Lock
from time import time

import twill
import twill.commands
import twill.parse

from twillmanager import create_db_connection
from twillmanager.async import AsyncProcess

__all__ = ['STATUS_FAILED', 'STATUS_OK', 'STATUS_UNKNOWN', 'Watch', 'WorkerSet']

# Consts for statuses
STATUS_OK = 'OK'
STATUS_FAILED = 'FAILED'
STATUS_UNKNOWN = 'UNKNOWN'

class Watch(object):
    """ A simple data transfer object for describing watches """
    def __init__(self, name, interval, script, emails = None, status=STATUS_UNKNOWN, time=None, id=None):
        self.name = name
        self.interval = interval
        self.script = script
        self.emails = emails
        self.status = status
        self.time = time
        self.id = id

    def save(self, connection):
        if self.id is None:
            self.insert(connection)
        else:
            self.update(connection)
        

    def insert(self, connection):
        # FIXME: thread-safety
        c = connection.cursor()
        c.execute("INSERT INTO twills (name, interval, script, emails, status, time) VALUES (?,?,?,?,?,?)",
            (self.name, self.interval, self.script, self.emails, self.status, self.time))
        self.id = c.lastrowid
        c.close()
        connection.commit()

    def update(self, connection):
        # FIXME: thread-safety
        assert self.id is not None
        c = connection.cursor()
        c.execute("UPDATE twills SET name=?, interval=?, script=?, emails=?, status=?, time=? WHERE id = ?",
            (self.name, self.interval, self.script, self.emails, self.status, self.time, self.id))
        c.close()
        connection.commit()

    def update_status(self, connection):
        """ Updates only information related to status check
            (status, check time, messages).

            This avoids overwriting script definition by a worker.
        """
        # FIXME: thread-safety
        assert self.id is not None
        c = connection.cursor()
        c.execute("UPDATE twills SET status=?, time=? WHERE id = ?",
            (self.status, self.time, self.id))
        c.close()
        connection.commit()

    def delete(self, connection):
        # FIXME: thread-safety
        c = connection.cursor()
        c.execute("DELETE FROM twills WHERE name = ?", (self.name,))
        c.close()
        connection.commit()

    @classmethod
    def load(self, name, connection):
        # FIXME: thread-safety
        watch = None
        c = connection.cursor()
        c.execute("SELECT interval, script, emails, status, time, id FROM twills WHERE name = ?", (name,))
        for row in c:
            watch = Watch(name, *row)
        c.close()
        return watch

    @classmethod
    def load_all(self, connection):
        # FIXME: thread-safety
        watches = []
        c = connection.cursor()
        c.execute("SELECT name, interval, script, emails, status, time, id FROM twills")
        for row in c:
            watches.append(Watch(*row))
        c.close()
        return watches


class Worker(AsyncProcess):
    def __init__(self, watch, config, manager):
        AsyncProcess.__init__(self, watch.interval)
        self.watch = watch
        self.manager = manager
        self.connection = None
        self.config = config

    def main(self):
        self.connection = create_db_connection(self.config)
        AsyncProcess.main(self)

    def tick(self):
        self._execute()

    def quit(self):
        self.queue_command('quit')

    def _quit(self):
        self._running = False


    def execute(self):
        self.queue_command('execute')

    def _execute(self):
        out = StringIO()

        try:
            twill.set_errout(out)
            twill.set_output(out)
            twill.parse._execute_script(self.watch.script.split("\n"))
            status = STATUS_OK
        except Exception, e:
            status = STATUS_FAILED
        finally:
            twill.commands.reset_error()
            twill.commands.reset_output()


        old_status = self.watch.status
        self.watch.status = status
        self.watch.time = time()
        self.watch.update_status(self.connection)
        if old_status != status:
            self.status_notify(old_status, status, out.getvalue())
            


    def status_notify(self, old_status, new_status, message):
        """ Sends out notifications about watch status change"""
        mailer = create_mailer(self.config)
        print "STATUS CHANGED: %s -> %s" % (old_status, new_status)
        print message
        

class WorkerSet(object):
    """ Object managing spawning of other workers."""
    def __init__(self):
        self._lock = Lock()
        self.watches = {}
        self.workers = {}
        
    def add(self, watch, config):
        with self._lock:
            name = watch.name
            if name in self.watches:
                raise KeyError("Watch `%s` already defined" % name)
            print "Adding watch %s" % name
            worker = Worker(watch, config, self)
            worker.start(True)
            self.watches[name] = watch
            self.workers[name] = worker

    def remove(self, watch):
        # support both strings and watch objects
        with self._lock:
            if hasattr(watch, 'name'):
                name = watch.name
            else:
                name = watch

            print "Removing worker %s" % name
            if name in self.workers:
                worker = self.workers[name]
                worker.quit()
            del self.workers[name]
            del self.watches[name]
