import os
import configparser
from invoke import Collection, task, run
from .scm import get_repo, hg_status, git_status
from collections import OrderedDict
import hgapi
from pick import pick
from path import Path
from .utils import (t, get_config_files, read_config_file, remove_dir,
    NO_MODULE_REPOS)


def get_config():
    """ Get config file for tasks module """
    parser = configparser.ConfigParser()
    config_path = '%s/.tryton-tasks.cfg' % os.getenv('HOME')
    parser.read(config_path)
    settings = {}
    for section in parser.sections():
        usection = str(section)
        settings[usection] = {}
        for name, value, in parser.items(section):
            settings[usection][name] = value
    return settings


@task()
def set_revision(ctx, config=None):
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
def set_branch(ctx, branch, config=None):
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
def add_modules(ctx, config, version, owner, modules="./modules"):
    Config = read_config_file(config, type='all', unstable=True)

    for d in [x for x in os.listdir(modules) if os.path.isdir(
            os.path.join(modules, x))]:
        path = os.path.join(modules, d)
        cfg_file = os.path.join(path, 'tryton.cfg')
        if not os.path.exists(cfg_file):
            continue
        Config = configparser.ConfigParser()
        Config.readfp(open(cfg_file))
        v = Config.get('tryton', 'version')
        # if v != version:
        #     continue

        repo = hgapi.Repo(path)
        url = repo.config('paths', 'default')

        if owner and "/%s/" % owner not in url:
            continue
        print("module:", path)
        add_module(config, path, url)




@task()
def add_module(ctx, config, path, url=None):
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

    Config._sections = OrderedDict(sorted(iter(Config._sections.items()),
        key=lambda x: x[0]))
    Config.write(cfile)
    cfile.close()

@task()
def unknown(ctx, unstable=True, status=False, show=True, remove=False, quiet=False,
        add=False):
    """
    Return a list of modules/repositories that exists in filesystem but not in
    config files
    ;param status: show status for unknown repositories.
    """
    Config = read_config_file(unstable=unstable)
    configs_module_list = [section for section in Config.sections()
        if section not in NO_MODULE_REPOS]

    modules_wo_repo = []
    repo_not_in_cfg = []
    for module_path in Path('./modules').dirs():
        module_name = module_path.basename()
        if module_name in configs_module_list:
            continue

        if (module_path.joinpath('.hg').isdir() or
                module_path.joinpath('.git').isdir()):
            repo_not_in_cfg.append(module_name)
            if status and module_path.joinpath('.hg').isdir():
                hg_status(module_name, module_path.parent, False, None)
            elif status and module_path.joinpath('.git').isdir():
                git_status(module_name, module_path.parent, False, None)
        else:
            modules_wo_repo.append(module_name)

    if show:
        if modules_wo_repo:
            print(t.bold("Unknown module (without repository):"))
            print("  - " + "\n  - ".join(modules_wo_repo))
            print("")
        if not status and repo_not_in_cfg:
            print(t.bold("Unknown repository:"))
            print("  - " + "\n  - ".join(repo_not_in_cfg))
            print("")

    if add:
        config_files = get_config_files()
        for repo in modules_wo_repo + repo_not_in_cfg:
            title = 'Add "%s" to Config Fille:' % repo
            option, index = pick(config_files, title, default_index=1)
            path = os.path.join('./modules', repo)
            add_module(option, path)

    if remove:
        for repo in modules_wo_repo + repo_not_in_cfg:
            path = os.path.join('./modules', repo)
            remove_dir(path, quiet)

    return modules_wo_repo, repo_not_in_cfg


ConfigCollection = Collection()
ConfigCollection.add_task(add_module)
ConfigCollection.add_task(set_branch)
ConfigCollection.add_task(set_revision)
ConfigCollection.add_task(add_modules)
ConfigCollection.add_task(unknown)
