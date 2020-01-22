#!/usr/bin/env python

import configparser
import os
from blessings import Terminal
from invoke import Collection, task, run
from path import Path

from .utils import _ask_ok, _check_required_file, _exit
from .scm import git_clone, git_pull, clone, fetch
from .sao import install as sao_install, grunt as sao_grunt


t = Terminal()
Config = configparser.ConfigParser()

# TODO: l'us que faig del config potser correspon a context
# http://docs.pyinvoke.org/en/latest/getting_started.html#handling-configuration-state

INITIAL_PATH = Path.getcwd()


@task()
def get_tasks(ctx, taskpath='tasks'):
    # TODO: add option to update repository
    Config.tasks_path = taskpath
    if Path(taskpath).exists():
        print('Updating tasks repo')
        git_pull(taskpath, taskpath, True)
        return

    if not getattr(Config, 'get_tasks', False):
        if not _ask_ok('Are you in the customer project directory? '
                'Answer "yes" to clone the "tryton-tasks" repository '
                'in "%s" directory. [Y/n] ' % taskpath, 'y'):
            return

    print ('Cloning git@github.com:NaN-tic/tryton-tasks '
        'repository in "tasks" directory.')
    git_clone('git@github.com:NaN-tic/tryton-tasks', taskpath)
    print("")


@task()
def get_config(ctx, configpath='config', branch='default'):
    # TODO: add option to update repository
    Config.config_path = Path(configpath).abspath()
    if Path(configpath).exists():
        print ('Updating config repo')
        git_pull(configpath, configpath, True, branch=branch)
        return

    if not getattr(Config, 'get_config', False):
        if not _ask_ok('Are you in the customer project directory? '
                'Answer "yes" to clone the "tryton-config" repository '
                'in "%s" directory. [Y/n] ' % configpath, 'y'):
            return

    print ('Cloning git@github.com:NaN-tic/tryton-config '
        'repository in "config" directory.')
    git_clone('git@github.com:NaN-tic/tryton-config', configpath, branch)
    print("")


@task()
def activate_virtualenv(ctx, projectname):
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

    if 'WORKON_HOME' in os.environ:
        virtualenv_path = Path(os.environ['WORKON_HOME']).joinpath(
            projectname)
        if virtualenv_path.exists() and virtualenv_path.isdir():
            activate_this_path = virtualenv_path.joinpath('bin/activate_this.py')
            print("Activating virtualenv %s" % projectname)
            run(activate_this_path)


@task(['get_config', 'activate_virtualenv'])
def install_requirements(ctx, upgrade=False):
    if not Config.requirements:
        return
    if not hasattr(Config, 'virtualenv_active') and os.geteuid() != 0:
        resp = input('It can\'t install requirements because you aren\'t '
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

    print('Installing dependencies.')
    _check_required_file('requirements.txt', Config.config_path.basename(),
        Config.config_path)
    if upgrade:
        run('pip install --upgrade -r %s/requirements.txt'
            % Config.config_path)
        #    _out=options.output, _err=sys.stderr)
    else:
        run('pip install -r %s/requirements.txt' % Config.config_path)
        #    _out=options.output, _err=sys.stderr)
    print("")


# TODO: prepare_local() => set configuration options for future bootstrap based
# on Config values


@task()
def install_proteus(ctx, proteuspath=None, upgrade=False):
    print("Installing proteus.")
    if proteuspath is None:
        cmd = ['pip', 'install', 'proteus']
        if upgrade:
            cmd.insert(2, '-u')
        run(' '.join(cmd))
    else:
        if not Path(proteuspath).exists():
            _exit(INITIAL_PATH, "ERROR: Proteus path '%s' doesn't exists."
                % proteuspath)
        cwd = Path.getcwd()
        os.chdir(proteuspath)
        run('python setup.py install')
        os.chdir(cwd)
    print("")


@task(default=True)
def bootstrap(ctx, branch, projectpath='', projectname='',
        taskspath='tasks',
        configpath='config',
        utilspath='utils',
        virtualenv=True,
        upgradereqs=False):

    cwd = Path.getcwd()

    if projectpath:
        projectpath = Path(projectpath)
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

    get_tasks(ctx, taskspath)
    get_config(ctx, configpath, branch=branch)
    activate_virtualenv(ctx, projectname)
    install_requirements(ctx, upgrade=upgradereqs)

    clone(ctx, 'config/base.cfg')
    fetch(ctx)

    # SAO
    sao_install(ctx)
    os.chdir(cwd)
    sao_grunt(ctx)

    if Path.getcwd() != INITIAL_PATH:
        os.chdir(INITIAL_PATH)


__all__ = ['get_tasks', 'get_config', 'activate_virtualenv',
    'install_requirements', 'install_proteus', 'bootstrap']

BootstrapCollection = Collection()
BootstrapCollection.add_task(bootstrap)
BootstrapCollection.add_task(get_config)
BootstrapCollection.add_task(get_tasks)
BootstrapCollection.add_task(activate_virtualenv)
BootstrapCollection.add_task(install_requirements)
BootstrapCollection.add_task(install_proteus)
