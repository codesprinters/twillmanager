# encoding: utf-8

from __future__ import absolute_import

class Watcher(object):
    """ The class that actually performs monitoring via twill"""
    def __init__(self, script='', interval=10):
        """ Creates a new `Watcher`.

            :param script: The script text to execute
            :param interval: interval (in seconds between runs)
        """
        self.interval = interval
        self.script = script

    def start(self):
        """ Run monitoring thread. It is safe to call this method when the thread
            is already running.
        """
        pass

    def stop(self):
        """ Run monitoring thread. It is safe to call this method when the thread
            is already stopped.
        """
        pass