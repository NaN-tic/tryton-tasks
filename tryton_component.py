#!/usr/bin/env python
import os
import sys
from invoke import task
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
    return pconfig.set_xmlrpc(tryton['server'])


@task
def push(config=None):
    get_tryton_connection()
    Component = Model.get('project.work.component')

    Module = Model.get('ir.module.module')
    modules = {}
    for module in Module.find([]):
        modules[module.name] = module

    components = {}
    for component in Component.find([]):
        components[component.name] = component

    Config = read_config_file(config, unstable=True)
    for section in Config.sections():
        if section in NO_MODULE_REPOS + BASE_MODULES:
            pass
        c = Component()
        if section in components:
            c = components[section]
        c.name = section
        c.url = Config.get(section, 'url')
        c.module = modules.get(section, None)
        c.save()
