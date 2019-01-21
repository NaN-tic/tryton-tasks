#!/usr/bin/env python
import os
import sys
import ssl
from invoke import task, Collection, run
from .config import get_config
from .utils import read_config_file, NO_MODULE_REPOS, BASE_MODULES

import http.client
from urllib.parse import urlparse
from .scm import hg_clone
import tempfile

def check_url(url):
    p = urlparse(url)
    conn = http.client.HTTPConnection(p.netloc)
    conn.request('HEAD', p.path)
    resp = conn.getresponse()
    return resp.status < 400

def check_module(module):
    URLS = [
        'https://bitbucket.org/zikzakmedia/trytond-',
        'https://bitbucket.org/trytonspain/trytond-',
        'https://bitbucket.org/nantic/trytond-',
        ]
    for test in URLS:
        url = test + module
        if check_url(test + module):
            return url

try:
    from proteus import config as pconfig, Model
except ImportError as e:
    print("trytond importation error: ", e, file=sys.stderr)

os.environ['TZ'] = "Europe/Madrid"
settings = get_config()


def get_tryton_connection():
    if 'TRYTOND_TESTER_URI' in os.environ:
        url = os.environ['TRYTOND_TESTER_URI']
    else:
        tryton = settings['tryton']
        url = tryton['server']
    try:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        return pconfig.set_xmlrpc(url, context=ssl_context)
    except AttributeError:
        # If python is older than 2.7.9 it doesn't have
        # ssl.create_default_context() but it neither verify certificates
        return pconfig.set_xmlrpc(url)


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

    print("Fetching module list...")
    Module = Model.get('ir.module')
    modules = {}
    for module in Module.find([]):
        modules[module.name] = module

    print("Fetching component list...")
    components = {}
    for component in Component.find([]):
        components[component.name] = component

    print("Updating components...")
    Config = read_config_file(config, unstable=True)
    for section in Config.sections():
        if section in NO_MODULE_REPOS + BASE_MODULES:
            pass
        if filter and filter not in section:
            continue
        print("Updating %s..." % section, end=' ')
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
            print("No SLOC could be calculated.")
        else:
            print("%d SLOC" % c.sloc)
        c.save()

@task()
def upload_file():
    get_tryton_connection()
    Component = Model.get('project.work.component')

    print("Fetching component list...")
    components = {}
    for component in Component.find([]):
        components[component.name] = component

    with open('modules.txt', 'r') as f:
        modules = f.read().split()

    tempdir = tempfile.mkdtemp()

    print("Updating components:", modules)
    for module in modules:
        print("Updating %s..." % module)
        if module in components:
            c = components[module]
        else:
            c = Component()
            c.name = module
            c.url = check_module(module)
        c.sloc = None

        path = os.path.join(tempdir, module)
        hg_clone(c.url, path)

        if os.path.isdir(path):
            result = run('cd %s; sloccount *' % path, hide=True, warn=True)
            lines = [x for x in result.stdout.splitlines() if 'Total Physical Source Lines of Code (SLOC)' in x]
            if lines:
                value = lines[0]
                value = value.split('=')[1].strip()
                value = value.replace(',', '').replace('.', '')
                c.sloc = int(value)
        if c.sloc is None:
            print("No SLOC could be calculated.")
        else:
            print("%d SLOC" % c.sloc)
        c.save()

@task()
def sloccount():
    get_tryton_connection()
    Component = Model.get('project.work.component')

    print("Fetching component list...")
    tempdir = tempfile.mkdtemp()
    for component in Component.find([]):
        print("Updating %s..." % component.name)
        path = os.path.join(tempdir, component.name)
        hg_clone(component.url, path)
        if os.path.isdir(path):
            result = run('cd %s; sloccount *' % path, hide=True, warn=True)
            lines = [x for x in result.stdout.splitlines()
                if 'Total Physical Source Lines of Code (SLOC)' in x]
            if lines:
                value = lines[0]
                value = value.split('=')[1].strip()
                value = value.replace(',', '').replace('.', '')
                component.sloc = int(value)
                component.save()
                print('%d SLOC saved.' % component.sloc)
            else:
                print('No SLOC could be calculated.')



ComponentCollection = Collection()
ComponentCollection.add_task(push)
ComponentCollection.add_task(upload_file)
ComponentCollection.add_task(sloccount)
