#!/usr/bin/env python

from invoke import task, run
from .utils import t, read_config_file
import os
import sys
from blessings import Terminal

@task
def features(config=None, module=None, fdir='features'):
    Config = read_config_file(config)
    for section in Config.sections():
        if not Config.has_option(section, 'patch'):
            continue

        if not module is None and module != section:
            continue

        repo = Config.get(section, 'repo')
        url = Config.get(section, 'url')
        path = Config.get(section, 'path')
        run('cd %s; wget %s'%(fdir, url))
        aux_path = path.replace('/','\/')
        diff_file = url.split('/')[-1]
        run('cd %s; sed -i "s/a\//%s/g" %s'%(fdir, aux_path,diff_file), echo=True)
        run('cd %s; sed -i "s/b\//%s/g" %s'%(fdir, aux_path,diff_file), echo=True)
        #run('patch -p0 %s'%(fdir+"/"+diff_file), echo=True)

