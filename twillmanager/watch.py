# encoding: utf-8

from __future__ import absolute_import
from __future__ import with_statement

import multiprocessing
from StringIO import StringIO
import Queue
import threading
import time

import twill
import twill.commands
import twill.parse

from twillmanager.db import get_db_connection, close_db_connection
import twillmanager.mail
from twillmanager.log import logger
import twillmanager.async

__all__ = ['STATUS_FAILED', 'STATUS_OK', 'STATUS_UNKNOWN', 'Watch', 'WorkerSet']

# Consts for statuses
STATUS_OK = 'OK'
STATUS_FAILED = 'FAILED'
STATUS_UNKNOWN = 'UNKNOWN'

class Watch(object):
    """ A simple data transfer object for describing watches (with data access methods
        for loading/storing watches into the database)
    """
    # Rows in database table
    COLUMNS = ['id',
               'name',
               'interval',
               'script',
               'emails',
               'status',
               'time',
               'reminder_interval',
               'last_alert',
              ]

    def __init__(self, name, interval, script,
            emails=None, status=STATUS_UNKNOWN, time=None,
            reminder_interval=600, last_alert=None, id=None):
        """ Create a new Watch

            :param name: Name of the watch
            :param interval: Interval (in seconds) between watch runs
            :param script: Twill script that should be executed by the watch
            :param emails: String containing all the e-mail addresses (comma-separated)
                of people who should receive failure notifications.
            :param status: Current status of the watch
            :param time: Last update time (as number of seconds since epoch - obtained by call to `time.time()`)
            :param reminder_interval: Interval (seconds) after which reminder that the watch is still down is sent
            :param last_alert: Time of last alert sent (as number of seconds since epoch - obtained by call to `time.time()`)
            :param id: Key in the database of the watch
        """
        self.name = name
        self.interval = interval
        self.script = script
        self.emails = emails
        self.status = status
        self.time = time
        self.reminder_interval = reminder_interval
        self.last_alert = last_alert
        self.id = id

    def formatted_time(self):
        if self.time:
            return time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(self.time));
        else:
            return None

    def dict(self):
        """ Watch status data as dictionary (not a complete watch) """
        data = {}
        data['id'] = self.id
        data['name'] = self.name
        data['status'] = self.status
        data['time'] = self.formatted_time();
        return data

    @classmethod
    def columns(cls):
        return ','.join(cls.COLUMNS)

    @classmethod
    def construct_from_row(cls, row):
        kwargs = dict()
        for name in cls.COLUMNS:
            try:
                kwargs[name] = row[name]
            except IndexError:
                pass
        return cls(**kwargs)

    def save(self, connection):
        """ Save the watch into the database (using given connection) """
        if self.id is None:
            self.insert(connection)
        else:
            self.update(connection)
        

    def insert(self, connection):
        """ Insert the watch into the database (using given connection) """
        c = connection.cursor()
        c.execute("INSERT INTO twills (name, interval, script, emails, status, time, reminder_interval, last_alert) VALUES (?,?,?,?,?,?,?,?)",
            (self.name, self.interval, self.script, self.emails, self.status, self.time, self.reminder_interval, self.last_alert))
        self.id = c.lastrowid
        c.close()
        connection.commit()

    def update(self, connection):
        """ Update the watch into the database (using given connection) """
        assert self.id is not None
        c = connection.cursor()
        c.execute("UPDATE twills SET name=?, interval=?, script=?, emails=?, status=?, time=?, reminder_interval=?, last_alert=? WHERE id = ?",
            (self.name, self.interval, self.script, self.emails, self.status, self.time, self.reminder_interval, self.last_alert, self.id))
        c.close()
        connection.commit()

    def update_status(self, connection):
        """ Updates only information related to status check
            (status, check time, messages).

            This avoids overwriting script definition by a worker.
        """
        assert self.id is not None
        c = connection.cursor()
        c.execute("UPDATE twills SET status=?, time=?, last_alert=? WHERE id = ?",
            (self.status, self.time, self.last_alert, self.id))
        c.close()
        connection.commit()

    def delete(self, connection):
        """ Deletes the watch from the database (using given connection) """
        c = connection.cursor()
        c.execute("DELETE FROM twills WHERE id = ?", (self.id,))
        c.close()
        connection.commit()

    @classmethod
    def load(cls, id, connection):
        """ Loads the watch with given id """
        watch = None
        c = connection.cursor()
        c.execute("SELECT " + cls.columns() + " FROM twills WHERE id = ?", (id,))
        for row in c:
            watch = cls.construct_from_row(row)
        c.close()
        return watch

    @classmethod
    def load_by_name(cls, name, connection):
        """ Loads the watch with given name """
        watch = None
        c = connection.cursor()
        c.execute("SELECT " + cls.columns() + " FROM twills WHERE name = ?", (name,))
        for row in c:
            watch = cls.construct_from_row(row)
        c.close()
        return watch

    @classmethod
    def load_all(cls, connection):
        """ Loads all watches """
        watches = []
        c = connection.cursor()
        c.execute("SELECT " + cls.columns() + " FROM twills ORDER BY name")
        for row in c:
            watches.append(cls.construct_from_row(row))
        c.close()
        return watches
    

class WorkerProxy(twillmanager.async.WorkerProxy):
    """ A proxy for controlling `Worker` processes """
    def __init__(self, id, config):
        twillmanager.async.WorkerProxy.__init__(self)
        self.id = id
        self.config = config
        self.on_twill_start = None # executed when twill check starts
        self.on_twill_end = None # executed when twill check starts

    def set_twill_callbacks(self, on_start, on_end):
        """ Sets callbacks to be executed when twill check starts and ends.
            Must be set before starting the worker

            :param on_start: Executed when twill starts. A zero-argument callable
            :param on_start: Executed when twill end. A zero-argument callable
        """
        assert not self.already_started(), "Can't call set_twill_callbacks on worker that is already started"
        self.on_twill_start = on_start
        self.on_twill_end = on_end

    def make_worker(self, queue):
        return Worker(queue, self.id, self.config, self.on_twill_start, self.on_twill_end)

    def quit(self):
        """ Send 'quit' signal to the worker """
        self.queue_command('quit')

    def execute(self):
        """ Send 'execute the script now' signal to the worker """
        self.queue_command('execute')

class Worker(twillmanager.async.Worker):
    """ Worker - a process that monitors if given twill script executes properly"""
    def __init__(self, queue, id, config, on_start=None, on_end=None):
        """ Creates a new `Worker`
            :param queue: The command queue, as needed by `twillmanager.async.Worker`
            :param id: Id (database primary key) of the watch to use
            :param config: Configuration dict to be used (needed for e-mail addresses etc)
            :param on_start: Callable (zero-argument) to be invoked when
                twill script starts execution
            :param on_end: Callable (zero-argument) to be invoked when twill
                script finishes execution (disregarding status)
        """
        twillmanager.async.Worker.__init__(self, queue)
        self.id = id
        self.config = config
        self.watch = None
        self.connection = None
        self.on_start = on_start
        self.on_end = on_end

    def main(self):
        """ Process main function """
        # to make sure we do not use inherited descriptor
        # from the parent process
        close_db_connection()
        self.connection = get_db_connection(self.config)
        self.watch = Watch.load(self.id, self.connection)


        if self.watch:
            logger.info("Starting worker for watch `%s` (id: %s)" % (self.watch.name, self.id))
            self.tick_interval = self.watch.interval
            twillmanager.async.Worker.main(self)
        else:
            logger.warn("Failed to start worker for watch (id: %s) - no such watch" % self.id)

    def tick(self):
        """ Executed every self.watch.interval seconds """
        self.execute()

    def quit(self):
        self.running = False


    def execute(self):
        """ Called by `tick` and when `execute` schedules immediate script execution."""
        try: # large try block to ensure on_end is called
            if self.on_start:
                self.on_start()

            new_status, output = self.execute_script()

            old_status = self.watch.status
            self.watch.status = new_status
            self.watch.time = time.time()
            self.watch.update_status(self.connection)

            msg = "Status for watch `%s` (id: %s): %s" % (self.watch.name, self.id, new_status)

            if new_status != STATUS_OK:
                logger.warn(msg)
            else:
                logger.info(msg)

            # when was last e-mail alert sent
            if self.watch.last_alert is None:
                time_since_last_alert = None
            else:
                time_since_last_alert = self.watch.time - self.watch.last_alert

            status_has_changed = (old_status != new_status)

            # whether last alert was sent long ago enough to send a failure reminder
            # (normally e-mails are sent only on change, but a reminder is sent
            # if the watch keeps failing)
            if self.watch.reminder_interval:
                last_alert_was_long_ago = time_since_last_alert is None or time_since_last_alert > self.watch.reminder_interval
            else:
                last_alert_was_long_ago = False


            if status_has_changed or (last_alert_was_long_ago and new_status == STATUS_FAILED):
                logger.info("Sending notification for watch `%s` (id: %s)" % (self.watch.name, self.id))
                self.status_notify(old_status, new_status, output)
                self.watch.last_alert = time.time()
                self.watch.update_status(self.connection)
        except Exception, e:
            logger.error("Worker `%s` (id: %s) failed with exception: %s" % (self.watch.name, self.id, e.message))
            raise
        finally:
            if self.on_end:
                self.on_end()

    def execute_script(self):
        """ Executes twill script. Returns a tuple status, output """
        out = StringIO()
        # execute the twill, catching any exceptions
        try:
            twill.set_errout(out)
            twill.set_output(out)
            twill.parse._execute_script(self.watch.script.split("\n"))
            status = STATUS_OK
        except Exception, e:
            status = STATUS_FAILED
        finally:
            twill.commands.reset_error()
            twill.commands.reset_output()
        return status, out.getvalue()

    def status_notify(self, old_status, new_status, message):
        """ Sends out notifications about watch status change """
        recipients = self.watch.emails

        if not recipients:
            return

        # strip
        recipients = [r.strip() for r in recipients.split(',')]
        # remove empty addresses
        recipients = [r for r in recipients if r]

        if len(recipients) == 0:
            return

        sender = self.config['mail.from']

        if old_status != new_status:
            subject = "Watch %s status change %s -> %s" % (self.watch.name, old_status, new_status)
        else:
            subject = "Watch %s status is still %s" % (self.watch.name, new_status)

        body = "Script:\n%s\n\nResult:\n%s" % (self.watch.script, message)

        mailer = twillmanager.mail.create_mailer(self.config)
        mailer.send_mail(sender, recipients, subject, body)
        

class WorkerSet(object):
    """ Object managing spawning of workers."""
    def __init__(self, config):
        """ Create a new `WorkerSet`.

            :param config: Configuration dict to be passed to spawned workers
        """
        # synchronization between threads (WorkerSet is used from CherryPy)
        self._lock = threading.RLock()
        self.workers = {}
        self.now_building = {}
        self.config = config

        # thread that checks for workers that died unexpectedly
        # and listens to their status update messages
        # only tuples (command, argument) should be put into that queue.
        self.manager_thread_queue = multiprocessing.Queue(0)
        self.manager_thread = threading.Thread(target=self.manager_thread_main)
        self.manager_thread.daemon = True
        self.manager_thread.start()

    def worker_status_dict(self, id):
        with self._lock:
            return {'alive': self.is_alive(id), 'building': self.is_building(id)}

    def get(self, id):
        return self.workers.get(id, None)

    def finish(self):
        """ Call this to clean up when the application is shut down """
        self.manager_thread_queue.put(('quit', None))
        self.manager_thread.join()

    def is_alive(self, id):
        """ Check if worker with given id is alive """
        with self._lock:
            return id in self.workers and self.workers[id].is_alive()

    def is_building(self, id):
        """ Check if worker with given id is currently building"""
        with self._lock:
            return self.now_building.get(id, False)

    def check_now(self, id):
        """ Tell the worker with given id to check immediately.
            This also restarts the worker if it died.
        """
        with self._lock:
            self.restart(id)
            self.now_building[id] = True
            self.workers[id].execute()

    def restart(self, id):
        """ Restarts given worker. """
        with self._lock:
            self.remove(id)
            self.add(id)

    def add(self, id):
        """ Adds worker for watch with given id.
            
            It is safe to call this method even if the worker is already running.
        """
        with self._lock:
            if id in self.workers:
                return

            def on_start():
                self.manager_thread_queue.put(('start', id))

            def on_end():
                self.manager_thread_queue.put(('end', id))

            worker = WorkerProxy(id, self.config)
            worker.set_twill_callbacks(on_start, on_end)
            
            self.workers[id] = worker
            self.now_building[id] = False
            worker.start(True)

    def remove(self, id):
        """ Removes worker for watch with given id.

            It is safe to call this method even if the worker is not running.
        """
        with self._lock:
            if id in self.workers:
                worker = self.workers[id]
                worker.quit()
                del self.workers[id]
                del self.now_building[id]
                if worker.process:
                    worker.process.join()

    def manager_thread_main(self):
        """ Checks for workers that died unexpectedly and listens to their
            status update messages.
        """
        while True:
            # wait up to 60 seconds
            try:
                command, argument = self.manager_thread_queue.get(True, 60)

                if command == 'quit':
                    break
                elif command == 'start':
                    with self._lock:
                        self.now_building[argument] = True
                elif command == 'end':
                    with self._lock:
                        self.now_building[argument] = False
                else:
                    logger.warn("Unknown command to manager thread: %s" % command)

            except Queue.Empty:
                pass

            # this one is to remove zombie processes
            multiprocessing.active_children()

            with self._lock:
                ids_to_restart = []
                for id, worker in self.workers.items():
                    if not worker.is_alive():
                        ids_to_restart.append(id)

                for id in ids_to_restart:
                    self.restart(id)
