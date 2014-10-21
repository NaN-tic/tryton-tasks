#!/usr/bin/env python
import os
from invoke import task, Collection, run
from .scm import get_repo
from .utils import read_config_file



README_MSG = "\nNotes\n"
README_MSG+= "=====\n\n"
README_MSG+= "This packages includes some backports and bugfixes from original.\n"
README_MSG+= "Find it at: http://bitbucket.org/nantic/trytond-patches\n"

@task()
def prepare(config, unstable=True):
    Config = read_config_file(config, unstable=unstable)

    for section in Config.sections():
        repo = get_repo(section, Config)
        revision = repo['revision']
        path = repo['path']
        setup_file = os.path.join(path, 'setup.py')
        run('sed -i "s/trytond_/nantic_/g" %s' % setup_file)
        run('sed -i "s/=version,/=version+\'.%s\',/g" %s'%
            (revision, setup_file))
        run('sed -i "/download_url=/d" %s' % setup_file)
        readme_file = os.path.join(path, 'README')
        run('echo "%s" >> %s' % (README_MSG, readme_file))


@task()
def dist(pypi, config, unstable=True):
    Config = read_config_file(config, unstable=unstable)

    for section in Config.sections():
        repo = get_repo(section, Config)
        pypi = repo['pypi'] or 'nantic'
        path = repo['path']
        run('cd %s; python setup.py sdist upload -r %s' % (path, pypi))




PypiCollection = Collection()
PypiCollection.add_task(prepare)
PypiCollection.add_task(dist)
