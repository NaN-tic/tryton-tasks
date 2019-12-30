import os
import sys

DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', 'trytond', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

from trytond.config import config


class Application(object):
    '''
    This class wraps trytond's WSGI app in order to be able to setup
    the configuration file on the first call.

    mod_wsgi does not allow passing environment variables (those obtained via
    os.environ) for several reasons explained in its documentation. So we had
    to workaround that limitation somehow and this class allows administrators
    to add 'Set Env trytond.config /etc/trytond/whatever.conf' to Apache's
    virtual host.
    '''
    def __init__(self):
        self.loaded = False
        self.app = None

    def __call__(self, environ, start_response):
        if not self.loaded:
            config.update_etc(environ.get('trytond.config'))
            logconf = config.get('optional', 'logconf')
            if logconf:
                os.environ['TRYTOND_LOGGING_CONFIG'] = logconf

            from trytond.application import app
            self.app = app
            self.loaded = True
        return self.app.wsgi_app(environ, start_response)


# WSGI standard requires the variable to be named 'application' and mod_wsgi
# does not allow that value to be overriden.
application = Application()
