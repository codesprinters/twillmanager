# encoding: utf-8

from __future__ import absolute_import
from __future__ import with_statement

from StringIO import StringIO
from threading import Thread, RLock, Event as threadEvent
from time import time
from multiprocessing import active_children

import twill
import twill.commands
import twill.parse

from twillmanager.db import get_db_connection, close_db_connection
from twillmanager.mail import create_mailer
from twillmanager.async import AsyncProcess

__all__ = ['STATUS_FAILED', 'STATUS_OK', 'STATUS_UNKNOWN', 'Watch', 'WorkerSet']

# Consts for statuses
STATUS_OK = 'OK'
STATUS_FAILED = 'FAILED'
STATUS_UNKNOWN = 'UNKNOWN'

class Watch(object):
    """ A simple data transfer object for describing watches (with data access methods
        for loading/storing watches into the database)
    """
    def __init__(self, name, interval, script, emails = None, status=STATUS_UNKNOWN, time=None, id=None):
        """ Create a new Watch

            :param name: Name of the watch
            :param interval: Interval (in seconds) between watch runs
            :param script: Twill script that should be executed by the watch
            :param emails: String containing all the e-mail addresses (comma-separated)
                of people who should receive failure notifications.
            :param status: Current status of the watch
            :param time: Last update time (as number of seconds since epoch - obtained by call to `time.time()`)
            :param id: Key in the database of the watch
        """
        self.name = name
        self.interval = interval
        self.script = script
        self.emails = emails
        self.status = status
        self.time = time
        self.id = id

    def save(self, connection):
        """ Save the watch into the database (using given connection) """
        if self.id is None:
            self.insert(connection)
        else:
            self.update(connection)
        

    def insert(self, connection):
        """ Insert the watch into the database (using given connection) """
        c = connection.cursor()
        c.execute("INSERT INTO twills (name, interval, script, emails, status, time) VALUES (?,?,?,?,?,?)",
            (self.name, self.interval, self.script, self.emails, self.status, self.time))
        self.id = c.lastrowid
        c.close()
        connection.commit()

    def update(self, connection):
        """ Update the watch into the database (using given connection) """
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
        assert self.id is not None
        c = connection.cursor()
        c.execute("UPDATE twills SET status=?, time=? WHERE id = ?",
            (self.status, self.time, self.id))
        c.close()
        connection.commit()

    def delete(self, connection):
        """ Deletes the watch from the database (using given connection) """
        c = connection.cursor()
        c.execute("DELETE FROM twills WHERE id = ?", (self.id,))
        c.close()
        connection.commit()

    @classmethod
    def load(cls, id, connection):
        """ Loads the watch with given id """
        watch = None
        c = connection.cursor()
        c.execute("SELECT name, interval, script, emails, status, time, id FROM twills WHERE id = ?", (id,))
        for row in c:
            watch = cls(*row)
        c.close()
        return watch

    @classmethod
    def load_by_name(cls, name, connection):
        """ Loads the watch with given name """
        watch = None
        c = connection.cursor()
        c.execute("SELECT name, interval, script, emails, status, time, id FROM twills WHERE name = ?", (name,))
        for row in c:
            watch = cls(*row)
        c.close()
        return watch

    @classmethod
    def load_all(cls, connection):
        """ Loads all watches """
        watches = []
        c = connection.cursor()
        c.execute("SELECT name, interval, script, emails, status, time,id FROM twills ORDER BY name")
        for row in c:
            watches.append(cls(*row))
        c.close()
        return watches


class Worker(AsyncProcess):
    """ Worker - a process that monitors if given twill script executes properly"""
    def __init__(self, id, config):
        """ Creates a new `Worker`
            :param id: Id (database primary key) of the watch to use
            :param config: Configuration dict to be used (needed for e-mail addresses etc)
        """
        AsyncProcess.__init__(self)
        self.id = id
        self.config = config
        
        self.watch = None
        self.connection = None

    def main(self):
        """ Process main function """
        # to make sure we do not use inherited descriptor
        # from the parent process
        close_db_connection()
        self.connection = get_db_connection(self.config)
        self.watch = Watch.load(self.id, self.connection)
        if self.watch:
            self.tick_interval = self.watch.interval
            AsyncProcess.main(self)

    def tick(self):
        """ Executed every self.watch.interval seconds """
        self._execute()

    def quit(self):
        """ Send 'quit' signal to the process """
        self.queue_command('quit')

    def _quit(self):
        self._running = False


    def execute(self):
        """ Send 'execute the script now' signal to the process """
        self.queue_command('execute')

    def _execute(self):
        """ Called by `tick` and when `execute` schedules immediate script execution."""
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
        """ Sends out notifications about watch status change """
        recipients = self.watch.emails

        if not recipients:
            return

        # strip
        recipients = [r.strip() for r in recipients.split(',')]
        # remove empty addresses
        recipients = [r for r in recipients if r]

        if len(recipients) == 0:
            return

        sender = self.config['mail.from']

        subject = "Watch %s status change %s -> %s" % (self.watch.name, old_status, new_status)

        body = "Script:\n%s\n\nResult:\n%s" % (self.watch.script, message)

        mailer = create_mailer(self.config)
        mailer.send_mail(sender, recipients, subject, body)
        

class WorkerSet(object):
    """ Object managing spawning of workers."""
    def __init__(self, config):
        """ Create a new `WorkerSet`.

            :param config: Configuration dict to be passed to spawned workers
        """
        # synchronization between threads (WorkerSet is used from CherryPy)
        self._lock = RLock()
        self.workers = {}
        self.config = config

        # thread that checks for workers that died unexpectedly
        # and it's control event (to notify that thread it is no longer needed)
        self.checking_thread_control_event = threadEvent()
        self.checking_thread = Thread(target=self.check_for_dead_workers)
        self.checking_thread.daemon = True
        self.checking_thread.start()


    def finish(self):
        """ Call this to clean up when the application is shut down """
        self.checking_thread_control_event.set()
        self.checking_thread.join()

    def is_alive(self, id):
        """ Check if worker with given id is alive """
        with self._lock:
            return id in self.workers and self.workers[id].is_alive()

    def check_now(self, id):
        """ Tell the worker with given id to check immediately.
            This also restarts the worker if it died.
        """
        with self._lock:
            self.restart(id)
            self.workers[id].execute()

    def restart(self, id):
        """ Restarts given worker. """
        with self._lock:
            self.remove(id)
            self.add(id)

    def add(self, id):
        """ Adds worker for watch with given id.
            
            It is safe to call this method even if the worker is already running.
        """
        with self._lock:
            if id in self.workers:
                return
            worker = Worker(id, self.config)
            self.workers[id] = worker
            worker.start(True)

    def remove(self, id):
        """ Removes worker for watch with given id.

            It is safe to call this method even if the worker is not running.
        """
        with self._lock:
            if id in self.workers:
                worker = self.workers[id]
                worker.quit()
                del self.workers[id]
                if worker.process:
                    worker.process.join()

    def check_for_dead_workers(self):
        """ Checks for workers that are dead but shouldn't and restarts them.

            This is main method of ``self.checking_thread``,
            so it loops indefinitely.
        """
        while True:
            self.checking_thread_control_event.wait(60)
            if self.checking_thread_control_event.isSet():
                break
            # this one is to remove zombie processes
            active_children()

            with self._lock:
                ids_to_restart = []
                for id, worker in self.workers.items():
                    if not worker.is_alive():
                        ids_to_restart.append(id)

                for id in ids_to_restart:
                    self.restart(id)
