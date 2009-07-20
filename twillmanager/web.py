# encoding: utf-8

from __future__ import absolute_import

import cherrypy
from mako.lookup import TemplateLookup
import os.path
import simplejson

from twillmanager.db import get_db_connection, create_tables
from twillmanager.watch import WorkerSet, Watch

def validate_twill_form(connection, data, watch=None):
    """ Checks if data (dictionary) contains valid watch definition.
        Returns a tuple (valid_dict, list of errors),
        where valid_dict contains the successfully validated values
    """
    # no need for any fancy form handling library for this single form
    valid_dict = {}
    errors = []

    name = data.get('name', '')
    if not name:
        errors.append(u"Watch name is missing")
    else:
        other_watch = Watch.load_by_name(name, connection)
        if other_watch is not None and other_watch.id != watch.id:
            errors.append(u"Watch with this name already exists")
        else:
            valid_dict['name'] = name

    interval = data.get('interval', None)
    if not interval:
        errors.append(u"Interval is missing")
    else:
        try:
            valid_dict['interval'] = int(interval)
        except ValueError:
            errors.append(u"Invalid number (interval)")

    reminder_interval = data.get('reminder_interval', '').strip()
    if reminder_interval:
        try:
            valid_dict['reminder_interval'] = int(reminder_interval)
        except ValueError:
            errors.append(u"Invalid number (reminder interval)")
    else:
        valid_dict['reminder_interval'] = None

    script = data.get('script', None)
    if not script or script.isspace():
        errors.append(u"Script is missing")
    else:
        valid_dict['script'] = script

    valid_dict['emails'] = data.get('emails', '')

    return valid_dict, errors

class Controller(object):
    template_directory = os.path.normpath(os.path.join(os.path.dirname(__file__), 'templates'))
    template_lookup = TemplateLookup(directories=[template_directory], default_filters=['unicode', 'h'])

    def render(self, file, **kwargs):
        template = self.template_lookup.get_template(file)
        cherrypy.response.headers['Content-Type'] = "text/html; charset=UTF-8"
        return template.render_unicode(**kwargs).encode('utf-8')


class DashboardController(Controller):
    """ Web application interface """
    def __init__(self):
        self.worker_set = None
        self.config = None

    def finish(self):
        """ Call this to clean up when the application is shut down """
        if self.worker_set:
            self.worker_set.finish()

    def configure(self, cfg):
        """ Configuration and initialization is delayed to allow working
            with CherryPy configuration API
        """
        self.config = cfg
        create_tables(get_db_connection(self.config))

        self.worker_set = WorkerSet(cfg)
        for w in Watch.load_all(get_db_connection(self.config)):
            self.worker_set.add(w.id)

    @cherrypy.expose
    def index(self):
        watches = Watch.load_all(get_db_connection(self.config))
        return self.render('index.html', watches=watches, worker_set=self.worker_set)

    @cherrypy.expose
    def status(self):
        watches = Watch.load_all(get_db_connection(self.config))

        data = {}
        for watch in watches:
            data[str(watch.id)] = watch.dict(self.worker_set.get(watch.id))

        cherrypy.response.headers['Content-Type'] = "application/json"
        return simplejson.dumps(data)

    @cherrypy.expose
    def new(self, **kwargs):
        watch = None
        if cherrypy.request.method == 'POST':
            c = get_db_connection(self.config)
            try:
                valid_dict, errors = validate_twill_form(c, kwargs)
                if len(errors):
                    c.rollback()
                else:
                    watch = Watch(**valid_dict)
                    watch.save(c)
                    c.commit()
                    self.worker_set.add(watch.id)
            except Exception:
                c.rollback()
                raise
        else:
            errors = []

        if watch:
            raise cherrypy.HTTPRedirect(cherrypy.url('/'), status=303)
        else:
            return self.render('new.html', data=kwargs, errors=errors)


    def __getattr__(self, name):
        try:
            id = int(name)
        except ValueError:
            raise AttributeError

        return WatchController(id, self.config, self.worker_set)

class WatchController(Controller):
    def __init__(self, id, config, worker_set):
        self.config = config
        self.id = int(id)
        self.worker_set = worker_set

    @cherrypy.expose
    def index(self):
        raise cherrypy.HTTPRedirect(cherrypy.url('/'), status=303)

    @cherrypy.expose
    def status(self):
        watch = Watch.load(self.id, get_db_connection(self.config))
        if not watch:
            raise cherrypy.NotFound()

        data = watch.dict(self.worker_set.get(self.id))

        cherrypy.response.headers['Content-Type'] = "application/json"
        return simplejson.dumps(data)

    @cherrypy.expose
    def restart(self):
        watch = Watch.load(self.id, get_db_connection(self.config))
        if not watch:
            raise cherrypy.NotFound()
        
        self.worker_set.restart(self.id)
        raise cherrypy.HTTPRedirect(cherrypy.url('/'), status=303)

    @cherrypy.expose
    def stop(self):
        self.worker_set.remove(self.id)
        raise cherrypy.HTTPRedirect(cherrypy.url('/'), status=303)

    @cherrypy.expose
    def check_now(self):
        """ Force a check immediately """
        watch = Watch.load(self.id, get_db_connection(self.config))
        if not watch:
            raise cherrypy.NotFound()

        self.worker_set.check_now(self.id)
        raise cherrypy.HTTPRedirect(cherrypy.url('/'), status=303)

    @cherrypy.expose
    def edit(self, **kwargs):
        connection = get_db_connection(self.config)

        try:
            watch = Watch.load(self.id, connection)
                
            if not watch:
                raise cherrypy.NotFound()

            if cherrypy.request.method == 'POST':
                valid_dict, errors = validate_twill_form(connection, kwargs, watch)
                if len(errors):
                    connection.rollback()
                else:
                    for k,v in valid_dict.iteritems():
                        setattr(watch, k, v)
                    watch.update(connection)
                    connection.commit()
                    self.worker_set.restart(self.id)
                    raise cherrypy.HTTPRedirect(cherrypy.url('/'), status=303)
            else:
                errors = []

            return self.render('edit.html', watch=watch, data=kwargs, errors=errors)
        except Exception:
            connection.rollback()
            raise

    @cherrypy.expose
    def delete(self):
        connection = get_db_connection(self.config)

        try:
            watch = Watch.load(self.id, connection)
            if not watch:
                raise cherrypy.NotFound()

            if cherrypy.request.method == 'POST':
                watch.delete(connection)
                self.worker_set.remove(self.id)
                connection.commit()
                raise cherrypy.HTTPRedirect(cherrypy.url('/'), status=303)

            return self.render('delete.html', watch=watch)
        except Exception:
            connection.rollback()
            raise
