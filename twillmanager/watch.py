# encoding: utf-8

from __future__ import absolute_import
from __future__ import with_statement

from StringIO import StringIO
from threading import Thread, RLock
from time import time, sleep
from multiprocessing import active_children

import twill
import twill.commands
import twill.parse

from twillmanager import get_db_connection, create_mailer, close_db_connection
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
        c = connection.cursor()
        c.execute("INSERT INTO twills (name, interval, script, emails, status, time) VALUES (?,?,?,?,?,?)",
            (self.name, self.interval, self.script, self.emails, self.status, self.time))
        self.id = c.lastrowid
        c.close()
        connection.commit()

    def update(self, connection):
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
        c = connection.cursor()
        c.execute("DELETE FROM twills WHERE id = ?", (self.id,))
        c.close()
        connection.commit()

    @classmethod
    def load(self, id, connection):
        watch = None
        c = connection.cursor()
        c.execute("SELECT name, interval, script, emails, status, time, id FROM twills WHERE id = ?", (id,))
        for row in c:
            watch = Watch(*row)
        c.close()
        return watch

    @classmethod
    def load_by_name(self, name, connection):
        watch = None
        c = connection.cursor()
        c.execute("SELECT name, interval, script, emails, status, time, id FROM twills WHERE name = ?", (name,))
        for row in c:
            watch = Watch(*row)
        c.close()
        return watch

    @classmethod
    def load_all(self, connection):
        watches = []
        c = connection.cursor()
        c.execute("SELECT name, interval, script, emails, status, time,id FROM twills ORDER BY name")
        for row in c:
            watches.append(Watch(*row))
        c.close()
        return watches


class Worker(AsyncProcess):
    def __init__(self, id, config):
        AsyncProcess.__init__(self)
        self.id = id
        self.config = config
        
        self.watch = None
        self.connection = None

    def main(self):
        close_db_connection() # to make sure we do not use inherited descriptor from the parent
        self.connection = get_db_connection(self.config)
        self.watch = Watch.load(self.id, self.connection)
        if self.watch is None:
            return
        self.tick_interval = self.watch.interval
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
    """ Object managing spawning of other workers."""
    def __init__(self, config):
        self._lock = RLock()
        self.workers = {}
        self.config = config
        
        self.checking_thread = Thread(target=self.check_for_dead_workers)
        self.checking_thread_running = True
        self.checking_thread.daemon = True
        self.checking_thread.start()


    def finish(self):
        """ Call this to clean up when the application is shut down """
        self.checking_thread_running = False
        self.checking_thread.join()

    def is_alive(self, id):
        with self._lock:
            return id in self.workers and self.workers[id].is_alive()

    def check_now(self, id):
        with self._lock:
            self.restart(id)
            self.workers[id].execute()

    def restart(self, id):
        with self._lock:
            self.remove(id)
            self.add(id)

    def add(self, id):
        with self._lock:
            if id in self.workers:
                return
            worker = Worker(id, self.config)
            self.workers[id] = worker
            worker.start(True)

    def remove(self, id):
        with self._lock:
            if id in self.workers:
                worker = self.workers[id]
                worker.quit()
                del self.workers[id]

    def check_for_dead_workers(self):
        """ Checks for workers that are dead but shouldn't and restarts them """

        while self.checking_thread_running:
            sleep(60)
            # this one is to remove zombie processes
            active_children()

            with self._lock:
                ids_to_restart = []
                for id, worker in self.workers.items():
                    if not worker.is_alive():
                        ids_to_restart.append(id)

                for id in ids_to_restart:
                    self.restart(id)
