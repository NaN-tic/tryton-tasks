#!/usr/bin/env python

import ConfigParser
import hgapi
import os
import sys
from blessings import Terminal
from invoke import task, run
from path import path

from .scm import clone


t = Terminal()
Config = ConfigParser.ConfigParser()
# TODO: l'us que faig del config potser correspon a context
# http://docs.pyinvoke.org/en/latest/getting_started.html#handling-configuration-state

INITIAL_PATH = path.getcwd()


def _exit(message=None):
    if path.getcwd() != INITIAL_PATH:
        os.chdir(INITIAL_PATH)
    if not message:
        return sys.exit(0)
    sys.exit(message)


def _ask_ok(prompt, default_answer=None):
    ok = raw_input(prompt) or default_answer
    if ok.lower() in ('y', 'ye', 'yes'):
        return True
    if ok.lower() in ('n', 'no', 'nop', 'nope'):
        return False
    _exit("Yes or no, please")


def _check_required_file(filename, directory_name, directory_path):
    if not directory_path.joinpath(filename).exists():
        _exit('%s file not found in %s directory: %s' % (filename,
                directory_name, directory_path))


@task
def get_tasks(taskpath='tasks'):
    # TODO: add option to update repository
    Config.tasks_path = taskpath
    if path(taskpath).exists():
        print ('Updating tasks repo')
        repo = hgapi.Repo(taskpath)
        print repo.hg_command(*['pull', '-u'])
        return

    if not Config.get_tasks:
        if not _ask_ok('Are you in the customer project directory? '
                'Answer "yes" to clone the "tryton-utils" repository '
                'in "%s" directory. [Y/n] ' % taskpath, 'y'):
            return

    print ('Cloning ssh://hg@hg.bitbucket.org/nantic/tryton-utils '
        'repository in "tasks" directory.')
    run('hg clone ssh://hg@hg.bitbucket.org/nantic/tryton-utils %s'
            % str(taskpath))
    #_out=options.output, _err=sys.stderr)
    print ""


@task
def get_config(configpath='config'):
    # TODO: add option to update repository
    Config.config_path = path(configpath).abspath()
    if path(configpath).exists():
        print ('Updating config repo')
        repo = hgapi.Repo(configpath)
        print repo.hg_command(*['pull', '-u'])
        return

    if not Config.get_config:
        if not _ask_ok('Are you in the customer project directory? '
                'Answer "yes" to clone the "tryton-config" repository '
                'in "%s" directory. [Y/n] ' % configpath, 'y'):
            return

    print ('Cloning ssh://hg@hg.bitbucket.org/nantic/tryton-config '
        'repository in "config" directory.')
    run('hg clone ssh://hg@hg.bitbucket.org/nantic/tryton-config %s'
            % str(configpath))
    #_out=options.output, _err=sys.stderr)
    print ""


@task
def activate_virtualenv(projectname):
    '''
    Config.virtualenv indicates virtualenv must to be activated
    Config.virtualenv_active informs virtualenv is activated

    To ensure you doesn't forgotten to activate virtualenv,
        if not Config.virtualenv but environment variable 'VIRTUAL_ENV' exists,
        it asks you if you want to activate it.
    '''
    if os.environ.get('VIRTUAL_ENV'):
        # Virtualenv already activated
        Config.virtualenv = True
        Config.virtualenv_active = True
        return

    if not Config.virtualenv and 'WORKON_HOME' in os.environ:
        # virtualenvwrapper avilable. confirm don't activate virtualenv
        if _ask_ok('You have available the "virtualenvwrapper". Are you '
                'sure you don\'t whant to prepare project in a virtualenv? '
                'Answer "yes" to continue without activate a virtualenv. '
                '[Yes/no (activate)] ', 'y'):
            Config.virtualenv_active = False
            return
        Config.virtualenv = True

    if not Config.virtualenv:
        Config.virtualenv_active = False
        return

    if 'WORKON_HOME' not in os.environ:
        _exit('ERROR: To could activate a virtualenv it\'s required the '
            '"virtualenvwrapper" installed and configured.')

    virtualenv_path = path(os.environ['WORKON_HOME']).joinpath(
        projectname)
    if not virtualenv_path.exists() or not virtualenv_path.isdir():
        _exit('ERROR: Do not exists a virtualenv for project "%s" in '
            'workon directory: %s. Create it with "mkvirtualenv" tool.'
            % (projectname, virtualenv_path))

    activate_this_path = virtualenv_path.joinpath('bin/activate_this.py')
    print "Activating virtualenv %s" % projectname
    #execfile(activate_this_path, dict(__file__=activate_this_path))
    run(activate_this_path)


@task(['get_config', 'activate_virtualenv'])
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
            _exit('Invalid answer.')
        if resp.lower() in ('a', 'abort'):
            _exit()
        if resp.lower() in ('', 's', 'skip'):
            return

    print 'Installing dependencies.'
    _check_required_file('requirements.txt', Config.config_path.basename(),
        Config.config_path)
    if upgrade:
        run('pip install --upgrade -r %s/requirements.txt'
            % Config.config_path)
        #    _out=options.output, _err=sys.stderr)
    else:
        run('pip install -r %s/requirements.txt' % Config.config_path)
        #    _out=options.output, _err=sys.stderr)
    print ""


# TODO: prepare_local() => set configuration options for future bootstrap based
# on Config values

@task(default=True)
def bootstrap(projectpath='', projectname='',
        taskspath='tasks',
        configpath='config',
        virtualenv=True,
        upgradereqs=False):

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
    Config.get_tasks = True
    Config.get_config = True
    Config.requirements = True  # Install?

    get_tasks(taskspath)
    get_config(configpath)
    activate_virtualenv(projectname)
    install_requirements(upgrade=upgradereqs)

    clone('config/base.cfg')
    clone()

    if path.getcwd() != INITIAL_PATH:
        os.chdir(INITIAL_PATH)
