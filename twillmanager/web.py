# encoding: utf-8

from __future__ import absolute_import

import cherrypy
from mako.lookup import TemplateLookup
import os.path


from twillmanager import get_db_connection, create_tables
from twillmanager.watch import WorkerSet, Watch

class ApplicationRoot(object):
    """ Web application interface """
    def __init__(self):
        self.worker_set = WorkerSet()
        self.config = None

        tpl_directory = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'templates'))

        self.tpl_lookup = TemplateLookup(directories=[tpl_directory], default_filters=['unicode', 'h'])

    def configure(self, cfg):
        """ Configuration and initialization is delayed to allow working
            with CherryPy configuration API
        """
        self.config = cfg
        create_tables(get_db_connection(self.config))

        for w in Watch.load_all(get_db_connection(self.config)):
            self.worker_set.add(w, self.config)

    def render(self, file, **kwargs):
        tpl = self.tpl_lookup.get_template(file)
        return tpl.render_unicode(**kwargs)

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
            other_watch = Watch.load(name, get_db_connection(self.config))
            if other_watch is not None and other_watch is not watch:
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
        workers = self.worker_set.workers
        return self.render('index.html', watches=watches, workers=workers)

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
            except Exception:
                c.rollback()
                raise
        else:
            errors = []


        if watch:
            raise cherrypy.HTTPRedirect(cherrypy.url('/'), status=302)
        else:
            return self.render('new.html', data=kwargs, errors=errors)
