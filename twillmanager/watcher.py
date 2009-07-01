# encoding: utf-8

from __future__ import absolute_import

import time
from Queue import Empty
from multiprocessing import Process, Queue

# Consts for statuses
STATUS_OK = 'OK'
STATUS_FAILED = 'FAILED'
STATUS_UNKNOWN = 'UNKNOWN'

class Watch(object):
    """ A simple data transfer object for describing watches """
    def __init__(self, name, interval, script):
        self.name = name
        self.interval = interval
        self.script = script

class WatchStatus(object):
    """ A simple data transfer object for describing watch statuses"""
    def __init__(self, name, status = STATUS_UNKNOWN, time = None):
        self.name = name
        self.status = status # status
        self.time = time # execution timestamp

class AsyncProcess(object):
    def __init__(self, daemon):
        self.queue = Queue(0)
        self.process = Process(target=self.main)
        self.process.daemon = daemon
        self._running = False # this variable is not shared between processes
        
    def start(self):
        self.process.start()

    def is_alive(self):
        return self.process.is_alive()

    def main(self):
        try:
            self._running = True
            while self._running:
                item = self.queue.get()
                self.execute_command(item)
        finally:
            self._running = False

    def queue_command(self, name, *arguments):
        """ Queue a command to be executed by the process"""
        self.queue.put((name, arguments))

    def execute_command(self, cmd):
        """ Execute a command queued by _queue_command """
        name, arguments = cmd
        func = getattr(self, '_' + name)
        return func(*arguments)

class WorkerManager(AsyncProcess):
    """ Object managing spawning of other workers."""
    def __init__(self):
        AsyncProcess.__init__(self, False)
        self.workers = {}
        self.statuses = {}

    def add(self, watch):
        self.queue_command('add', watch)
        
    def _add(self, watch):
        name = watch.name
        if name in self.workers:
            raise KeyError("Worker `%s` already defined" % name)
        print "Adding worker %s" % name

    def remove(self, watch):
        self.queue_command('remove', watch)

    def _remove(self, watch):
        name = watch.name
        if name in self.workers:
            print "Removing worker %s" % name
            worker = self.workers[name]
            worker.quit()
            del self.workers[name]
            del self.statuses[name]

    def quit(self):
        self.queue_command('quit')

    def _quit(self):
        print "Stopping manager"
        self._running = False

    def update_status(self, name, status):
        self.queue_command('update_status', name, status)

    def _update_status(self, name, status):
        if name not in self.statuses:
            return
        assert self.statuses[name].name == name
        self.statuses[name].status = status
        self.statuses[name].time = time.time()


class Worker(AsyncProcess):
    """ Object managing spawning of other workers."""
    def __init__(self, watch, manager):
        AsyncProcess.__init__(self, True)
        self.watch = watch
        self.manager = manager

    def main(self):
        try:
            self._running = True
            while self._running:
                try:
                    item = self.queue.get(True, self.watch.interval)
                    self.execute_command(item)
                except Empty:
                    self._execute()
        finally:
            self._running = False

    def quit(self):
        self.queue_command('quit')

    def _quit(self):
        print "Stopping manager"
        self._running = False

    def execute(self):
        self.queue_command('execute')

    def _execute(self):
        print self.watch.script

if __name__ == '__main__':
    manager = WorkerManager()
    manager.start()
