# encoding: utf-8

from __future__ import absolute_import
from __future__ import with_statement


import threading


class Watcher(object):
    """ The class that actually performs monitoring via twill"""
    def __init__(self, script='', interval=10):
        """ Creates a new `Watcher`.

            :param script: The script text to execute
            :param interval: interval (in seconds between runs)
        """
        self.interval = interval
        self.script = script
        
        self._thread = None # the thread that performs watching

        self._lock = threading.Lock()  # lock for watcher data
        self._event = threading.Event() # event for sleeping and waking up the thread

    def start(self):
        """ Run monitoring thread. It is safe to call this method when the thread
            is already running.
        """
        with self._lock:
            if self._thread is not None:
                return

            self._thread = threading.Thread(target=self._watcher_thread)
            self._thread.setDaemon(True)
            self._thread.start()
            self._event.clear()

    def stop(self):
        """ Run monitoring thread. It is safe to call this method when the thread
            is already stopped.
        """
        with self._lock:
            self._thread = None # this will cause the thread to stop on the first check
            self._event.set()

    def _watcher_thread(self):
        print "Watcher script start"
        while True:
            # get the control variables in a thread-safe way
            with self._lock:
                if self._thread is None: break
                interval = self.interval
                assert interval is not None

            # sleep interval seconds
            self._event.wait(interval)

            with self._lock:
                if self._thread is None: break
                script = self.script
            
            print script
        print "Watcher script done"
