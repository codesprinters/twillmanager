# encoding: utf-8

from __future__ import absolute_import

from mock import Mock, patch
import multiprocessing
from nose.tools import *

import twillmanager.mail
from twillmanager.async import Worker, WorkerProxy
from twillmanager.db import create_tables, create_db_connection
from twillmanager.watch import Watch

class Test_Watch(object):
    def setUp(self):
        self.connection = create_db_connection({'sqlite.file':':memory:'})
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


class Test_AsyncWorkerProxy(object):
    """ Tests for async.WorkerProxy"""
    def test_messages_are_queued(self):
        worker_proxy = WorkerProxy()
        worker_proxy.queue_command('zero')
        worker_proxy.queue_command('one',1)
        worker_proxy.queue_command('two',1,None)
        worker_proxy.queue_command('three','a','b','c')

        calls = []
        for i in xrange(4):
            calls.append(worker_proxy.queue.get())


        assert_equal(('zero',()), calls[0])
        assert_equal(('one',(1,)), calls[1])
        assert_equal(('two',(1,None)), calls[2])
        assert_equal(('three',('a','b','c')), calls[3])


class Test_AsyncWorker(object):
    """ Tests for async.Worker"""
    def test_messages_are_executed(self):
        def term(worker):
            worker.running = False

        q = multiprocessing.Queue(0)

        worker = Worker(q)
        worker.first = Mock()
        worker.second = Mock()
        worker.third = Mock()
        worker.fourth = lambda: term(worker)

        q.put(('first',()))
        q.put(('second',(1,)))
        q.put(('third',(1,2)))
        q.put(('fourth',()))

        # force immediate execution (in the same process)
        worker.main()

        worker.first.assert_called_with()
        worker.second.assert_called_with(1)
        worker.third.assert_called_with(1,2)
        assert not worker.running
        
class Test_WatchWorker(object):
    """ Tests for watch.Worker """

    @patch('twillmanager.mail.create_mailer')
    def test_status_notify_change(self, create_mailer_mock):
        """ Test sending e-mails"""
        mailer = Mock()
        mailer.send_mail = Mock()
        create_mailer_mock.return_value = mailer


        watch = Mock()
        watch.name = 'codesprinters.com'
        watch.script = 'go "http://codesprinters.com"'
        watch.emails = 'jobs@codesprinters.com, pstradomski@codesprinters.com'

        config = {'mail.from': 'test@codesprinters.com'}

        worker = twillmanager.watch.Worker(multiprocessing.Queue(0), id=1, config=config)
        worker.watch = watch
        worker.status_notify('FAILED', "OK", "Is ok now")

        assert_true(mailer.send_mail.called)
        args = mailer.send_mail.call_args[0]
        assert_equals(4, len(args))
        assert_equals('test@codesprinters.com', args[0])
        assert_equals(['jobs@codesprinters.com', 'pstradomski@codesprinters.com'], args[1])
        assert_equals('Watch codesprinters.com status change FAILED -> OK', args[2])
        assert_equals('Script:\ngo "http://codesprinters.com"\n\nResult:\nIs ok now', args[3])

    @patch('twillmanager.mail.create_mailer')
    def test_status_notify_still(self, create_mailer_mock):
        """ Test sending e-mails"""
        mailer = Mock()
        mailer.send_mail = Mock()
        create_mailer_mock.return_value = mailer

        
        watch = Mock()
        watch.name = 'codesprinters.com'
        watch.script = 'go "http://codesprinters.com"'
        watch.emails = 'jobs@codesprinters.com, pstradomski@codesprinters.com'

        config = {'mail.from': 'test@codesprinters.com'}

        worker = twillmanager.watch.Worker(multiprocessing.Queue(0), id=1, config=config)
        worker.watch = watch
        worker.status_notify('FAILED', "FAILED", "Kick it")

        assert_true(mailer.send_mail.called)
        args = mailer.send_mail.call_args[0]
        assert_equals(4, len(args))
        assert_equals('test@codesprinters.com', args[0])
        assert_equals(['jobs@codesprinters.com', 'pstradomski@codesprinters.com'], args[1])
        assert_equals('Watch codesprinters.com status is still FAILED', args[2])
        assert_equals('Script:\ngo "http://codesprinters.com"\n\nResult:\nKick it', args[3])

