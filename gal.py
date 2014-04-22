#!/usr/bin/env python
import os
import sys
import logging
import time
import subprocess
import hgapi
from invoke import task, run, Task

from .utils import t, read_config_file, NO_MODULE_REPOS

directory = os.path.abspath(os.path.normpath(os.path.join(os.getcwd(),
                    'trytond')))
proteus_directory = os.path.abspath(os.path.normpath(os.path.join(os.getcwd(),
                    'proteus')))

if os.path.isdir(directory):
    sys.path.insert(0, directory)
if os.path.isdir(proteus_directory):
    sys.path.insert(0, proteus_directory)

from proteus import config as pconfig, Model, Wizard

#def gal_action2(action, kwargs):
    #msg = ', '.join(['%s=%s' % (k, v) for k, v in kwargs.iteritems()])
    #msg = '%s(%s)' % (action, msg)
    #gal_repo().hg_commit(msg)
#
#def gal(function):
    #def inner(*args, **kwargs):
        #res = function((args, kwargs), *args, **kwargs)
        #gal_action(function.func_name, kwargs)
        #return res
    #return inner
#
#class GalTask(Task):
#
    #def __init__(self, args, **kwargs):
        #super(GalTask, self).__init__(args, kwargs)
#
    #def __call__(self, *args, **kwargs):
        #tmp = self.body
        #self.body = self.gal
        #super(GalTask, self).__call__(args, kwargs)
        #self.body = tmp
#
#def gal_task(function):
    #def inner(*args, **kwargs):
        ##res = function((args, kwargs), *args, **kwargs)
        #print "GAL: ", kwargs
        #res = function(*args, **kwargs)
        #gal_action(function.func_name, kwargs)
        #return res
    #task = GalTask(function)
    #task.gal = inner
    #return task


def check_output(*args):
    process = subprocess.Popen(args, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    process.wait()
    data = process.stdout.read()
    return data

def connect_database(database=None, password='admin',
        database_type='postgresql'):
    if database is None:
        database = 'gal'
    global config 
    config = pconfig.set_trytond(database, database_type=database_type,
        password=password, config_file='trytond.conf')

def dump(dbname=None):
    if dbname is None:
        dbname = 'gal'
    from trytond import backend
    Database = backend.get('Database')
    Database(dbname).close()
    # Sleep to let connections close
    time.sleep(1)
    dump_file = 'gal.sql'
    check_output('pg_dump', '-f', gal_path(dump_file), dbname)
    gal_repo().hg_add(dump_file)

def restore(dbname=None):
    if dbname is None:
        dbname = 'gal'
    dump_file = 'gal.sql'
    check_output('dropdb', dbname)
    check_output('psql', '-f', gal_path(dump_file), dbname)

def gal_path(path=None):
    res = 'gal'
    if path:
        res = os.path.join(res, path)
    return res

def gal_repo():
    path = gal_path()
    if os.path.exists(path) and not os.path.isdir(path):
        t.red('Error: gal file exists')
        sys.exit(1)
    if os.path.isdir(path) and not os.path.isdir(os.path.join(path, '.hg')):
        t.red('Invalid gal repository')
        sys.exit(1)
    repo = hgapi.Repo(path)
    if not os.path.exists(path):
        os.mkdir(path)
        repo.hg_init()
    return repo

def gal_action(action, **kwargs):
    global commit_msg
    commit_msg = ', '.join(["%s='%s'" % (k, v) for k, v in kwargs.iteritems()])
    commit_msg = '%s(%s)' % (action, commit_msg)

def gal_commit():
    dump()
    gal_repo().hg_commit(commit_msg)

@task
def create(language=None, password=None):
    gal_action('create', language=language, password=password)
    connect_database()
    gal_commit()

@task
def replay(commit=None):
    repo = gal_repo()
    for revision in repo.revisions(slice(0, 'tip')):
        # TODO: This is not safe. Run with care.
        eval(revision.desc)

@task
def set_active_languages(lang_codes=None):
    gal_action('set_active_languages', lang_codes=lang_codes)
    restore()
    connect_database()
    if lang_codes:
        lang_codes = lang_codes.split(',')

    Lang = Model.get('ir.lang')
    User = Model.get('res.user')

    if not lang_codes:
        lang_codes = ['ca_ES', 'es_ES']
    langs = Lang.find([
            ('code', 'in', lang_codes),
            ])
    assert len(langs) > 0

    Lang.write([l.id for l in langs], {
            'translatable': True,
            }, config.context)

    default_langs = [l for l in langs if l.code == lang_codes[0]]
    if not default_langs:
        default_langs = langs
    users = User.find([])
    if users:
        User.write([u.id for u in users], {
                'language': default_langs[0].id,
                }, config.context)

    # Reload context
    User = Model.get('res.user')
    config._context = User.get_preferences(True, config.context)

    if not all(l.translatable for l in langs):
        # langs is fetched before wet all translatable
        print "Upgrading all because new translatable languages has been added"
        upgrade_modules(config, all=True)
    gal_commit()

@task
def install_modules(modules):
    '''
    Function taken from tryton_demo.py in tryton-tools repo:
    http://hg.tryton.org/tryton-tools
    '''
    gal_action('install_modules', modules=modules)
    restore()
    connect_database()
    modules = modules.split(',')

    Module = Model.get('ir.module.module')
    modules = Module.find([
            ('name', 'in', modules),
            #('state', '!=', 'installed'),
            ])
    Module.install([x.id for x in modules], config.context)
    modules = [x.name for x in Module.find([
                ('state', 'in', ('to install', 'to_upgrade')),
                ])]
    Wizard('ir.module.module.install_upgrade').execute('upgrade')

    ConfigWizardItem = Model.get('ir.module.module.config_wizard.item')
    for item in ConfigWizardItem.find([('state', '!=', 'done')]):
        item.state = 'done'
        item.save()

    installed_modules = [m.name
        for m in Module.find([('state', '=', 'installed')])]

    gal_commit()
    return modules, installed_modules
