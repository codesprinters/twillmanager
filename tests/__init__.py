# encoding: utf-8

from __future__ import absolute_import

from nose.tools import *

from twillmanager.watcher import Watcher, WatcherPool


class Test_Watcher(object):
    def test_watcher_can_be_created(self):
        w = Watcher("Code Sprinters", "go http://www.codesprinters.com/", 120)
        assert_equal(120, w.interval)
        assert_equal("go http://www.codesprinters.com/", w.script)
        assert_equal("Code Sprinters", w.name)


class Test_WatcherPool(object):
    def test_watchers_can_be_added(self):
        w1 = Watcher("Google", "go http://www.google.com/", 120)
        w2 = Watcher("Code Sprinters", "go http://www.codesprinters.com/", 120)

        pool = WatcherPool()
        assert w1 not in pool
        assert w2 not in pool

        pool.add(w1)
        assert w1 in pool
        assert w2 not in pool
        
        pool.add(w2)
        assert w1 in pool
        assert w2 in pool

