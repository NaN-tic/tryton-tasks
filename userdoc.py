#!/usr/bin/env python

import ConfigParser
import os
from blessings import Terminal
from invoke import task, run
from path import path

from .utils import _exit, _check_required_file


t = Terminal()
Config = ConfigParser.ConfigParser()
# TODO: l'us que faig del config potser correspon a context
# http://docs.pyinvoke.org/en/latest/getting_started.html#handling-configuration-state

INITIAL_PATH = path.getcwd()


# TODO: put clone_config and activate_virtualenv in 'common' or call
# bootstrap.clone_config?
#@task(['clone_config', 'activate_virtualenv'])
@task
def install_requirements(upgrade=False):
    if not Config.requirements:
        return
    if not Config.virtualenv_active and os.geteuid() != 0:
        resp = raw_input('It can\'t install requirements because you aren\'t '
            'the Root user and you aren\'t in a Virtualenv. You will have to '
            'install requirements manually as root with command:\n'
            '  $ pip install [--upgrade] -r requirements.txt\n'
            'What do you want to do now: skip requirements install or abort '
            'bootstrap? [Skip/abort] ')
        if resp.lower() not in ('', 's', 'skip', 'a', 'abort'):
            _exit(INITIAL_PATH, 'Invalid answer.')
        if resp.lower() in ('a', 'abort'):
            _exit(INITIAL_PATH)
        if resp.lower() in ('', 's', 'skip'):
            return

    print 'Installing dependencies.'
    _check_required_file('requirements-userdoc.txt',
        Config.config_path.basename(), Config.config_path)
    if upgrade:
        run('pip install --upgrade -r %s/requirements-userdoc.txt'
            % Config.config_path)
        #    _out=options.output, _err=sys.stderr)
    else:
        run('pip install -r %s/requirements-userdoc.txt' % Config.config_path)
        #    _out=options.output, _err=sys.stderr)
    print ""


@task
def prepare_dir(userdocpath='userdoc'):
    userdocpath = path(userdocpath)
    Config.userdoc_path = path(userdocpath).abspath()

    if not userdocpath.exists():
        os.makedirs(userdocpath)

    makefile_path = userdocpath.joinpath('Makefile')
    if not makefile_path.exists():
        # TODO: copy from ¿get from mercurial? Makefile file
        pass


@task('prepare_dir')
def symlinks(userdocpath='userdoc'):
    Config.userdoc_path = Config.project_path.joinpath('userdoc')
    if not Config.userdoc_path.exists():
        _exit(INITIAL_PATH, '"userdoc" directory doesn\'t exits in project\'s '
            'root directory. Please, execute buildout with userdoc.cfg file.')
    # TODO: convert to python
    run('create-doc-symlinks.sh')  # _out=Config.output, _err=sys.stderr)


@task('prepare_dir')
def prepare_config(userdocpath='userdoc'):
    # TODO: all prepare_config() task
    # recipe = collective.recipe.template
    # input = ${buildout:trytond-doc-dir}/trytond_doc/userdoc/conf.py.template
    # output = ${buildout:userdoc-dir}/conf.py
    # # Redefine variables you want to customize in the local.cfg file
    # project_title = u'Tryton'
    # author = u'Tryton Spain'
    # copyright = u'2013, Tryton Spain'
    # htmlhelp_basename = 'TrytonDoc'
    # texhelp_filename = 'tryton.tex'
    # # documentclass could be 'manual' or 'howto'
    # documentclass = 'manual'
    pass


@task('prepare_dir')
def update_modules(userdocpath='userdoc'):
    # TODO: all update_modules. copy utils/doc-update-modules.py
    # touch ./userdoc/modules.cfg
    # echo [modules] >> ./userdoc/modules.cfg
    pass


@task(['prepare_dir', 'symlinks', 'prepare_config', 'update_modules'])
def compile(userdocpath='userdoc'):
    # TODO: get userdoc from config or from param?
    # os.chdir(Config.userdoc_path)
    if path.getcwd().abspath() != path(userdocpath).abspath():
        os.chdir(userdocpath)

    run('make')  # out=options.output, _err=sys.stderr)

    os.chdir(INITIAL_PATH)


@task(default=True)
def bootstrap(projectpath='', projectname='',
        userdocpath='userdoc',
        #taskspath='tasks',
        configpath='config',
        virtualenv=True,
        upgradereqs=True):

    if projectpath:
        projectpath = path(projectpath)
        os.chdir(projectpath)
    elif INITIAL_PATH.basename() == 'tasks':
        projectpath = INITIAL_PATH.parent()
        os.chdir(projectpath)
    else:
        projectpath = INITIAL_PATH

    if not projectname:
        projectname = str(projectpath.basename())
    Config.project_name = projectname

    Config.virtualenv = virtualenv

    # TODO: parse local.cfg to Config if exists?
    Config.clone_tasks = True
    Config.clone_config = True
    Config.requirements = True  # Install?

    #clone_config(configpath)
    #activate_virtualenv(projectname)
    install_requirements(upgrade=upgradereqs)
    prepare_dir(userdocpath)
    symlinks(userdocpath)
    prepare_config(userdocpath)
    update_modules(userdocpath)
    compile(userdocpath)

    if path.getcwd() != INITIAL_PATH:
        os.chdir(INITIAL_PATH)
