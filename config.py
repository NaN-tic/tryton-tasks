import os
import ConfigParser
from invoke import task, run
from .utils import read_config_file, get_config_files

from collections import OrderedDict


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


@task
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


@task
def add_module(config, path, url=None):
    """ Add module to specified config file """
    Config = read_config_file(config, type='all', unstable=True)
    module = os.path.basename(path)
    url = run('cd %s; hg paths default' % (path)).stdout.split('\n')[0]
    if 'http' in url:
        url = 'ssh://hg@bitbucket.org/nantic/trytond-%s' % module
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
