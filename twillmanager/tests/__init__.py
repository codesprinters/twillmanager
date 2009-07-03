# encoding: utf-8

from __future__ import absolute_import

import sqlite3
from nose.tools import *

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
    