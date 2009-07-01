# encoding: utf-8

from __future__ import absolute_import

from nose.tools import *

from twillmanager.watcher import Watcher


class Test_Watcher(object):
    def test_watcher_can_be_created(self):
        w = Watcher("Code Sprinters", "go http://www.codesprinters.com/", 120)
        assert_equal(120, w.interval)
        assert_equal("go http://www.codesprinters.com/", w.script)
        assert_equal("Code Sprinters", w.name)
