# encoding: utf-8

from __future__ import absolute_import
from __future__ import with_statement

from Queue import Empty
from multiprocessing import Process, Queue
from threading import Lock

from sqlite3 import connect

# Consts for statuses
STATUS_OK = 'OK'
STATUS_FAILED = 'FAILED'
STATUS_UNKNOWN = 'UNKNOWN'

class Watch(object):
    """ A simple data transfer object for describing watches """
    def __init__(self, name, interval, script, status=STATUS_UNKNOWN, time=None):
        self.name = name
        self.interval = interval
        self.script = script
        self.status = status
        self.time = time

    def save(self, connection):
        # FIXME: thread-safety
        c = connection.cursor()
        c.execute("INSERT INTO twills (name, interval, script, status, time) VALUES (?,?,?,?,?)",
            (self.name, self.interval, self.script, self.status, self.time))
        c.close()
        connection.commit()

    def update(self, connection):
        # FIXME: thread-safety
        c = connection.cursor()
        c.execute("UPDATE twills SET interval=?, script=?, status=?, time=? WHERE name = ?",
            (self.interval, self.script, self.status, self.time, self.name))
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
        c.execute("SELECT interval, script, status, time FROM twills WHERE name = ?", (name,))
        for row in c:
            watch = Watch(name, *row)
        c.close()
        return watch

    @classmethod
    def load_all(self, connection):
        # FIXME: thread-safety
        watches = []
        c = connection.cursor()
        c.execute("SELECT name, interval, script, status, time FROM twills")
        for row in c:
            watches.append(Watch(*row))
        c.close()
        return watches

class AsyncProcess(object):
    """ A simple abstract class for asynchronously responding server processes """
    def __init__(self, tick_interval=None):
        self.queue = Queue(0)
        self.process = Process(target=self.main)
        self.tick_interval = tick_interval
        self._running = False # this variable is not shared between processes
        
    def spawn(self, daemon=False):
        """ Start in another process """
        self.process.daemon = daemon
        self.process.start()

    def is_alive(self):
        return self.process.is_alive()

    def main(self):
        try:
            self._running = True
            while self._running:
                try:
                    self.execute_command(self.queue.get(True, self.tick_interval))
                except Empty:
                    self.tick()
        finally:
            self._running = False

    def tick(self):
        pass
        

    def queue_command(self, name, *arguments):
        """ Queue a command to be executed by the process"""
        self.queue.put((name, arguments))

    def execute_command(self, cmd):
        """ Execute a command queued by `_queue_command` """
        name, arguments = cmd
        func = getattr(self, '_' + name)
        return func(*arguments)

class WatchWorker(AsyncProcess):
    """ Object managing spawning of other workers."""
    def __init__(self, watch, connstring, manager):
        AsyncProcess.__init__(self, watch.interval)
        self.watch = watch
        self.manager = manager
        self.connection = None
        self.connstring = connstring

    def main(self):
        self.connection = connect(self.connstring)
        AsyncProcess.main(self)

    def tick(self):
        self._execute()

    def quit(self):
        self.queue_command('quit')

    def _quit(self):
        print "Stopping worker"
        self._running = False


    def execute(self):
        self.queue_command('execute')

    def _execute(self):
        print self.watch.script
        status = STATUS_OK
        old_status = self.watch.status

        if old_status != status and old_status != STATUS_UNKNOWN:
            print "STATUS CHANGED: %s -> %s" % (old_status, status)
            

class WorkerSet(object):
    """ Object managing spawning of other workers."""
    def __init__(self):
        self._lock = Lock()
        self.watches = {}
        self.workers = {}
        
    def add(self, watch, connstring):
        with self._lock:
            name = watch.name
            if name in self.watches:
                raise KeyError("Watch `%s` already defined" % name)
            print "Adding watch %s" % name
            worker = WatchWorker(watch, connstring, self)
            worker.spawn(True)
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
