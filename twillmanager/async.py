# encoding: utf-8

""" This module contains a class for creating asynchronously responding server processes"""

from __future__ import absolute_import
from __future__ import with_statement

from Queue import Empty
from multiprocessing import Process, Queue

__all__ = ['AsyncProcess']

class AsyncProcess(object):
    """ A simple abstract class for asynchronously responding server processes

        `main` is the process main event loop. It just keeps running indefinitely
        and processing events (the loop can be broken by setting ``running``
        attribute to False from within the process).

        `queue_message` can be used to queue method calls. Those methods are
        then processed by the event loop (name of the method gets an underscore
        prepended, so ``queue_command('abc',1,2,3)`` causes a call to ``self._abc(1,2,3)``)

        Additionally, if ``tick_interval`` is set to non None value
        then every tick_interval seconds (approximately), if there are no events queued,
        the tick() method is executed.
    """
    
    def __init__(self):
        """ Create a process """
        self.queue = Queue(0)
        self.process = Process(target=self.main)
        self.tick_interval = None
        self.running = False # this variable is not shared between processes

    def start(self, daemon=False):
        """ Start the process
            
            :param daemon: Whether to make the process daemonic
        """
        self.process.daemon = daemon
        self.process.start()

    def is_alive(self):
        """ Whether the process is alive """
        return self.process.is_alive()

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


    def queue_command(self, name, *arguments):
        """ Queue a command to be executed by the process"""
        self.queue.put((name, arguments))

    def execute_command(self, cmd):
        """ Execute a command queued by `queue_command` """
        name, arguments = cmd
        func = getattr(self, '_' + name)
        return func(*arguments)
