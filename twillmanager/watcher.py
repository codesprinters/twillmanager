# encoding: utf-8

from __future__ import absolute_import

import time
from Queue import Empty
from multiprocessing import Process, Queue, current_process

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
        self.status = STATUS_UNKNOWN # status
        self.time = None# execution timestamp

class AsyncProcess(object):
    """ A simple abstract class for asynchronously responding server processes """
    def __init__(self):
        self.queue = Queue(0)
        self.process = current_process()
        self._running = False # this variable is not shared between processes
        
    def spawn(self, daemon=False):
        """ Start in another process """
        self.process = Process(target=self.start)
        self.process.daemon = daemon
        self.process.start()

    def start(self):
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
        """ Execute a command queued by `_queue_command` """
        name, arguments = cmd
        func = getattr(self, '_' + name)
        return func(*arguments)

class WorkerManager(AsyncProcess):
    """ Object managing spawning of other workers."""
    def __init__(self):
        AsyncProcess.__init__(self)
        self.watches = {}
        self.workers = {}

    def add(self, watch):
        """ Asynchronously add a watch.

            :param watch: A `Watch` object
        """
        self.queue_command('add', watch)
        
    def _add(self, watch):
        name = watch.name
        if name in self.watches:
            raise KeyError("Watch `%s` already defined" % name)
        print "Adding watch %s" % name
        worker = Worker(watch, self)
        worker.spawn(True)
        self.watches[name] = watch
        self.workers[name] = worker

    def remove(self, watch):
        """ Asynchronously remove a watch.

            :param watch: A `Watch` object or watch name (string)
        """
        self.queue_command('remove', watch)

    def _remove(self, watch):
        # support both strings and watch objects
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

    def quit(self):
        self.queue_command('quit')

    def _quit(self):
        print "Stopping manager"
        self._running = False
        for worker in self.workers.itervalues():
            worker.quit()
        self.workers = {}
        self.watches = {}

    def update_status(self, name, status):
        self.queue_command('update_status', name, status)

    def _update_status(self, name, status):
        if name not in self.watches:
            return

        old_status = self.watches[name].status
        self.watches[name].status = status
        self.watches[name].time = time.time()
        if old_status != STATUS_UNKNOWN and old_status != status:
            print "STATUS CHANGED: %s -> %s" % (old_status, status)

    def list(self):
        back_queue = Queue()
        self.queue_command('list', back_queue)

        try:
            return back_queue.get(True, 120)
        except Empty:
            return None
    
    def _list(self, back_queue):
        back_queue.put(self.watches)
            

class Worker(AsyncProcess):
    """ Object managing spawning of other workers."""
    def __init__(self, watch, manager):
        AsyncProcess.__init__(self)
        self.watch = watch
        self.manager = manager

    def start(self):
        try:
            self._running = True
            while self._running:
                try:
                    print self.queue
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
