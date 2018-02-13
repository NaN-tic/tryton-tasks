import os
import ConfigParser
from invoke import Collection, task, run
from .utils import read_config_file, get_config_files
from .scm import get_repo
from collections import OrderedDict
import hgapi


def get_config():
    """ Get config file for tasks module """
    parser = ConfigParser.ConfigParser()
    config_path = '%s/.tryton-tasks.cfg' % os.getenv('HOME')
    parser.read(config_path)
    settings = {}
    for section in parser.sections():
        usection = unicode(section, 'utf-8')
        settings[usection] = {}
        for name, value, in parser.items(section):
            settings[usection][name] = value
    return settings


@task()
def set_revision(config=None):
    """ Set branch on repository config files """

    if config is None:
        config_files = get_config_files()
    else:
        config_files = [config]

    for config_file in config_files:
        Config = read_config_file(config_file, type='all', unstable=True)
        f_d = open(config_file, 'w+')
        for section in Config.sections():
            if Config.has_option(section, 'patch'):
                continue
            repo = get_repo(section, Config, 'revision')
            revision = repo['function'](section, repo['path'], verbose=False)
            Config.set(section, 'revision', revision)

        Config.write(f_d)
        f_d.close()


@task()
def set_branch(branch, config=None):
    """ Set branch on repository config files """

    if config is None:
        config_files = get_config_files()
    else:
        config_files = [config]

    for config_file in config_files:
        Config = read_config_file(config_file, type='all', unstable=True)
        f_d = open(config_file, 'w+')
        for section in Config.sections():
            if Config.has_option(section, 'patch'):
                continue
            Config.set(section, 'branch', branch)

        Config.write(f_d)
        f_d.close()

@task()
def add_modules(config, version, owner, modules="./modules"):
    Config = read_config_file(config, type='all', unstable=True)

    for d in [x for x in os.listdir(modules) if os.path.isdir(
            os.path.join(modules, x))]:
        path = os.path.join(modules, d)
        cfg_file = os.path.join(path, 'tryton.cfg')
        if not os.path.exists(cfg_file):
            continue
        Config = ConfigParser.ConfigParser()
        Config.readfp(open(cfg_file))
        v = Config.get('tryton', 'version')
        if v != version:
            continue

        repo = hgapi.Repo(path)
        url = repo.config('paths', 'default')

        if owner and "/%s/" % owner not in url:
            continue

        add_module(config, path, url)




@task()
def add_module(config, path, url=None):
    """ Add module to specified config file """
    Config = read_config_file(config, type='all', unstable=True)
    module = os.path.basename(path)
    url = run('cd %s; hg paths default' % (path)).stdout.split('\n')[0]
    branch = run('cd %s;hg branch' % (path)).stdout.split('\n')[0]
    cfile = open(config, 'w+')
    if not Config.has_section(module):
        Config.add_section(module)
        Config.set(module, 'branch', branch)
        Config.set(module, 'repo', 'hg')
        Config.set(module, 'url', url)
        Config.set(module, 'path', './trytond/trytond/modules')

    Config._sections = OrderedDict(sorted(Config._sections.iteritems(),
        key=lambda x: x[0]))
    Config.write(cfile)
    cfile.close()

ConfigCollection = Collection()
ConfigCollection.add_task(add_module)
ConfigCollection.add_task(set_branch)
ConfigCollection.add_task(set_revision)
ConfigCollection.add_task(add_modules)
