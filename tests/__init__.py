# encoding: utf-8

from __future__ import absolute_import

import sqlite3
from nose.tools import *

from twillmanager import create_tables
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

        w1loaded = Watch.load('codesprinters', self.connection)
        w2loaded = Watch.load('google', self.connection)

        assert_equal(w1.name, w1loaded.name)
        assert_equal(w1.script, w1loaded.script)
        assert_equal(w1.interval, w1loaded.interval)

        assert_equal(w2.name, w2loaded.name)
        assert_equal(w2.script, w2loaded.script)
        assert_equal(w2.interval, w2loaded.interval)

    def test_updating(self):
        w1 = Watch('codesprinters', 10, "go codesprinters")
        w1.save(self.connection)
        w2 = Watch('google', 10, "go google")
        w2.save(self.connection)

        w1loaded = Watch.load('codesprinters', self.connection)
        w2loaded = Watch.load('google', self.connection)

        assert_equal(w1.name, w1loaded.name)
        assert_equal(w1.script, w1loaded.script)
        assert_equal(w1.interval, w1loaded.interval)

        assert_equal(w2.name, w2loaded.name)
        assert_equal(w2.script, w2loaded.script)
        assert_equal(w2.interval, w2loaded.interval)

        w1.script = "go http://codesprinters.com"
        w1.update(self.connection)
        w1loaded = Watch.load('codesprinters', self.connection)
        w2loaded = Watch.load('google', self.connection)

        assert_equal(w1.name, w1loaded.name)
        assert_equal(w1.script, w1loaded.script)
        assert_equal(w1.interval, w1loaded.interval)

        assert_equal(w2.name, w2loaded.name)
        assert_equal(w2.script, w2loaded.script)
        assert_equal(w2.interval, w2loaded.interval)

    def test_deleting(self):
        w1 = Watch('codesprinters', 10, "go codesprinters")
        w1.save(self.connection)
        w2 = Watch('google', 10, "go google")
        w2.save(self.connection)

        w2.delete(self.connection)

        w1loaded = Watch.load('codesprinters', self.connection)
        w2loaded = Watch.load('google', self.connection)

        assert_equal(w1.name, w1loaded.name)
        assert_equal(w1.script, w1loaded.script)
        assert_equal(w1.interval, w1loaded.interval)

        assert w2loaded is None
        