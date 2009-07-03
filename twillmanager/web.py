# encoding: utf-8

from __future__ import absolute_import

import cherrypy
from mako.lookup import TemplateLookup
import os.path

from twillmanager.db import get_db_connection, create_tables
from twillmanager.watch import WorkerSet, Watch

class ApplicationRoot(object):
    """ Web application interface """
    def __init__(self):
        self.worker_set = None
        self.config = None

        tpl_directory = os.path.normpath(os.path.join(os.path.dirname(__file__), 'templates'))

        self.tpl_lookup = TemplateLookup(directories=[tpl_directory], default_filters=['unicode', 'h'])

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

    def render(self, file, **kwargs):
        tpl = self.tpl_lookup.get_template(file)
        cherrypy.response.headers['Content-Type'] = "text/html; charset=UTF-8"
        return tpl.render_unicode(**kwargs).encode('utf-8')

    def validate_twill(self, data, watch=None):
        """ Checks if data (dictionary) contains valid watch definition.
            Returns a tuple (valid_dict, list of errors),
            where valid_dict contains the successfully validated values
        """
        # no need for any fancy form handling library for this
        # single form
        valid_dict = {}
        errors = []

        name = data.get('name', '')
        if not name:
            errors.append(u"Watch name is missing")
        else:
            other_watch = Watch.load_by_name(name, get_db_connection(self.config))
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
                errors.append(u"Invalid number")

        script = data.get('script', None)
        if not script or script.isspace():
            errors.append(u"Script is missing")
        else:
            valid_dict['script'] = script

        valid_dict['emails'] = data.get('emails', '')

        return valid_dict, errors
        

    @cherrypy.expose
    def index(self):
        watches = Watch.load_all(get_db_connection(self.config))
        return self.render('index.html', watches=watches, worker_set=self.worker_set)

    @cherrypy.expose
    def restart_worker(self, id=None):
        watch = None
        if id is not None:
            id = int(id)
            watch = Watch.load(id, get_db_connection(self.config))

        if not watch:
            raise cherrypy.NotFound()

        self.worker_set.restart(id)
        raise cherrypy.HTTPRedirect(cherrypy.url('/'), status=303)

    @cherrypy.expose
    def stop_worker(self, id=None):
        if id is not None:
            id = int(id)
            self.worker_set.remove(id)
        raise cherrypy.HTTPRedirect(cherrypy.url('/'), status=303)

    @cherrypy.expose
    def check_now(self, id=None):
        """ Force a check immediately """
        watch = None
        if id is not None:
            id = int(id)
            watch = Watch.load(id, get_db_connection(self.config))

        if not watch:
            raise cherrypy.NotFound()

        self.worker_set.check_now(id)
        raise cherrypy.HTTPRedirect(cherrypy.url('/'), status=303)

    @cherrypy.expose
    def new(self, **kwargs):
        watch = None
        if cherrypy.request.method == 'POST':
            c = get_db_connection(self.config)
            try:
                valid_dict, errors = self.validate_twill(kwargs)
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

    @cherrypy.expose
    def edit(self, id=None, **kwargs):
        c = get_db_connection(self.config)

        try:
            watch = None
            if id is not None:
                id = int(id)
                watch = Watch.load(id, c)
                
            if not watch:
                raise cherrypy.NotFound()

            if cherrypy.request.method == 'POST':
                valid_dict, errors = self.validate_twill(kwargs, watch)
                if len(errors):
                    c.rollback()
                else:
                    for k,v in valid_dict.iteritems():
                        setattr(watch, k, v)
                    watch.update(c)
                    c.commit()
                    self.worker_set.restart(id)
                    raise cherrypy.HTTPRedirect(cherrypy.url('/'), status=303)
            else:
                errors = []

            return self.render('edit.html', watch=watch, data=kwargs, errors=errors)
        except Exception:
            c.rollback()
            raise

    @cherrypy.expose
    def delete(self, id=None):
        c = get_db_connection(self.config)
        watch = None

        try:
            if id is not None:
                id = int(id)
                watch = Watch.load(id, c)
            if not watch:
                raise cherrypy.NotFound()

            if cherrypy.request.method == 'POST':
                watch.delete(c)
                self.worker_set.remove(id)
                c.commit()
                raise cherrypy.HTTPRedirect(cherrypy.url('/'), status=303)

            return self.render('delete.html', watch=watch)
        except Exception:
            c.rollback()
            raise
