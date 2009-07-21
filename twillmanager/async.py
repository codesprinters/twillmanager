# encoding: utf-8

""" This module contains a class for creating asynchronously responding workers"""

from __future__ import absolute_import

from Queue import Empty
from multiprocessing import Process, Queue

__all__ = ['Worker', 'WorkerProxy']

class WorkerProxy(object):
    """ Proxy for controlling worker from another process """
    def __init__(self):
        self.queue = Queue(0)
        self.process = None

    def is_alive(self):
        """ Whether the worker process is alive """
        return self.process is not None and self.process.is_alive()

    def already_started(self):
        return self.process

    def queue_command(self, name, *arguments):
        """ Queue a command to be executed by the worker
            
            :param name: Name of the method to be called on the Worker object
            :param arguments: Arguments to that method
        """
        self.queue.put((name, arguments))

    def start(self, daemon=False):
        """ Start the worker

            :param daemon: Whether to make the process daemonic
        """
        assert not self.already_started(), "The worker is already started"

        worker = self.make_worker(self.queue)

        self.process = Process(target=worker.main)
        self.process.daemon = daemon
        self.process.start()

    def make_worker(self, queue):
        """ Construct instance of the `Worker` to be used by the worker process
        
            :param queue: Queue to be used by the worker
        """
        raise NotImplementedError("make_worker not implemented")

class Worker(object):
    """ A simple abstract class for asynchronously responding worker processes

        `main` is the process main event loop. It just keeps running indefinitely
        processing events (the loop can be broken by setting ``running``
        attribute to False from within the process).

        Events are read from the `Queue` passed to the `__init__`

        Additionally, if ``tick_interval`` is set to non None value
        then every tick_interval seconds (approximately),
        if there are no events queued, the tick() method is executed.
    """
    
    def __init__(self, queue):
        """ Create a process """
        self.queue = queue
        self.tick_interval = None
        self.running = False # this variable is not shared between processes

    def main(self):
        """ Main function of the process (the event loop) """
        try:
            self.running = True
            while self.running:
                try:
                    self.execute_command(self.queue.get(True, self.tick_interval))
                except Empty:
                    self.tick()
        finally:
            self.running = False

    def tick(self):
        """ Executed by the event loop every ``tick_interval`` seconds.

            Note that the frequency of ticks is only approximate -
            processing events in the loop as well as the `tick` method itself
            take some time which makes the loop a bit off.
        """
        pass

    def execute_command(self, cmd):
        """ Execute a command queued by `queue_command` """
        name, arguments = cmd
        func = getattr(self, name)
        return func(*arguments)
