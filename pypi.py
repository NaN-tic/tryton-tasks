#!/usr/bin/env python
import os
from invoke import task, Collection, run
from .scm import get_repo
from .utils import read_config_file


@task
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

PypiCollection = Collection()
PypiCollection.add_task(prepare)
