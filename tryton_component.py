#!/usr/bin/env python
import os
import sys
import ssl
from invoke import task, Collection, run
from .config import get_config
from .utils import read_config_file, NO_MODULE_REPOS, BASE_MODULES

try:
    from proteus import config as pconfig, Model
except ImportError, e:
    print >> sys.stderr, "trytond importation error: ", e

os.environ['TZ'] = "Europe/Madrid"
settings = get_config()


def get_tryton_connection():
    tryton = settings['tryton']
    try:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return pconfig.set_xmlrpc(tryton['server'], context=ssl_context)
    except AttributeError:
        # If python is older than 2.7.9 it doesn't have
        # ssl.create_default_context() but it neither verify certificates
        return pconfig.set_xmlrpc(tryton['server'])


def _pull():
    get_tryton_connection()
    Component = Model.get('project.work.component')
    components = {}
    for component in Component.find([]):
        components[component.name] = component
    return components

@task()
def push(config=None, filter=None):
    get_tryton_connection()
    Component = Model.get('project.work.component')

    print "Fetching module list..."
    Module = Model.get('ir.module')
    modules = {}
    for module in Module.find([]):
        modules[module.name] = module

    print "Fetching component list..."
    components = {}
    for component in Component.find([]):
        components[component.name] = component

    print "Updating components..."
    Config = read_config_file(config, unstable=True)
    for section in Config.sections():
        if section in NO_MODULE_REPOS + BASE_MODULES:
            pass
        if filter and filter not in section:
            continue
        print "Updating %s..." % section,
        c = Component()
        if section in components:
            c = components[section]
        c.name = section
        c.url = Config.get(section, 'url')
        c.module = modules.get(section, None)
        c.sloc = None
        path = os.path.join(Config.get(section, 'path'), section)
        if os.path.isdir(path):
            result = run('cd %s; sloccount *' % path, hide=True, warn=True)
            lines = [x for x in result.stdout.splitlines() if 'Total Physical Source Lines of Code (SLOC)' in x]
            if lines:
                value = lines[0]
                value = value.split('=')[1].strip()
                value = value.replace(',', '').replace('.', '')
                c.sloc = int(value)
        if c.sloc is None:
            print "No SLOC could be calculated."
        else:
            print "%d SLOC" % c.sloc
        c.save()

ComponentCollection = Collection()
ComponentCollection.add_task(push)
