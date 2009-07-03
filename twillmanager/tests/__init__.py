# encoding: utf-8

from __future__ import absolute_import

import sqlite3
from time import sleep

from mock import Mock
import multiprocessing
from Queue import Empty
from nose.tools import *

from twillmanager.async import AsyncProcess
from twillmanager.db import create_tables
from twillmanager.watch import Watch

class Test_Watch(object):
    def setUp(self):
        self.connection = sqlite3.connect(':memory:')
        create_tables(self.connection)

    def test_saving(self):
        w1 = Watch('codesprinters', 10, "go codesprinters")
        w1.save(self.connection)
        w2 = Watch('google', 10, "go google")
        w2.save(self.connection)

        w1loaded = Watch.load(w1.id, self.connection)
        w2loaded = Watch.load(w2.id, self.connection)

        self.compare_watches(w1, w1loaded)
        self.compare_watches(w2, w2loaded)

    def test_updating(self):
        w1 = Watch('codesprinters', 10, "go codesprinters")
        w1.save(self.connection)
        w2 = Watch('google', 10, "go google")
        w2.save(self.connection)

        w1loaded = Watch.load(w1.id, self.connection)
        w2loaded = Watch.load(w2.id, self.connection)

        self.compare_watches(w1, w1loaded)
        self.compare_watches(w2, w2loaded)

        w1.script = "go http://codesprinters.com"
        w1.update(self.connection)
        w1loaded = Watch.load(w1.id, self.connection)
        w2loaded = Watch.load(w2.id, self.connection)

        self.compare_watches(w1, w1loaded)
        self.compare_watches(w2, w2loaded)
        
    def test_deleting(self):
        w1 = Watch('codesprinters', 10, "go codesprinters")
        w1.save(self.connection)
        w2 = Watch('google', 10, "go google")
        w2.save(self.connection)

        w2.delete(self.connection)

        w1loaded = Watch.load(w1.id, self.connection)
        w2loaded = Watch.load(w2.id, self.connection)

        self.compare_watches(w1, w1loaded)
        assert w2loaded is None

    def test_load_by_name(self):
        w1 = Watch('codesprinters', 10, "go codesprinters")
        w1.save(self.connection)
        w2 = Watch('google', 10, "go google")
        w2.save(self.connection)

        w2loaded = Watch.load_by_name('google', self.connection)
        self.compare_watches(w2, w2loaded)

        w1loaded = Watch.load_by_name('codesprinters', self.connection)
        self.compare_watches(w1, w1loaded)

    def test_load_by_id(self):
        w1 = Watch('codesprinters', 10, "go codesprinters")
        w1.save(self.connection)
        w2 = Watch('google', 10, "go google")
        w2.save(self.connection)


        w2loaded = Watch.load(w2.id, self.connection)
        self.compare_watches(w2, w2loaded)

        w1loaded = Watch.load(w1.id, self.connection)
        self.compare_watches(w1, w1loaded)

        w3loaded = Watch.load(w1.id + w2.id, self.connection)
        assert w3loaded is None

    def test_load_all(self):
        w1 = Watch('www.google.com', 10, "go google")
        w1.save(self.connection)
        w2 = Watch('www.codesprinters.com', 10, "go codesprinters")
        w2.save(self.connection)
        w3 = Watch('www.squarewheel.pl', 10, "go google")
        w3.save(self.connection)

        watches = Watch.load_all(self.connection)

        assert_equal(3, len(watches))

        self.compare_watches(w2, watches[0])
        self.compare_watches(w1, watches[1])
        self.compare_watches(w3, watches[2])


    def compare_watches(self, w1, w2):
        assert_equal(w1.name, w2.name)
        assert_equal(w1.script, w2.script)
        assert_equal(w1.interval, w2.interval)


class Test_Async(object):
    """ Tests for AsyncProcess"""
    def test_messages_are_executed(self):
        def term(process):
            process._running = False

        ap = AsyncProcess()
        ap._first = Mock()
        ap._second = Mock()
        ap._third = Mock()
        ap._fourth = lambda: term(ap)

        ap.queue_command('first')
        ap.queue_command('second', 1)
        ap.queue_command('third',1,2)
        ap.queue_command('fourth')

        # force immediate execution (in the same process)
        ap.main()

        ap._first.assert_called_with()
        ap._second.assert_called_with(1)
        ap._third.assert_called_with(1,2)
        assert not ap._running
        
    def test_inter_process_communication(self):
        def term(process):
            process._running = False

        ap = AsyncProcess()
        ap._quit = lambda: term(ap)

        ap.start(True)
        sleep(1) # give the process some time to run

        assert ap.is_alive()

        ap.queue_command('quit')

        ap.process.join()
        assert not ap.is_alive()
        assert not ap._running

    def test_process_ticks(self):
        def term(process):
            process._running = False
        def tick():
            q.put(123)

        q = multiprocessing.Queue()

        ap = AsyncProcess()
        ap._quit = lambda: term(ap)
        ap.tick = tick
        ap.tick_interval = 1
        ap.start(True)
        sleep(6) # this should give us some ticks

        ap.queue_command('quit')

        ap.process.join()
        assert not ap.is_alive()
        assert not ap._running

        received_ticks = []

        while True:
            try:
                received_ticks.append(q.get_nowait())
            except Empty:
                break

        # the it might be a bit off
        assert 5 <= len(received_ticks) <= 7
