#!/usr/bin/env python
import os
import sys
from utils import t, read_config_file
from pyactiveresource.activeresource import ActiveResource
from key import site, headers
from invoke import Collection, task, run

class Issue(ActiveResource):
    _site = site
    _headers = headers


@task
def apply(issue, fdir='features'):
    Config = read_config_file(None,  type='patches')
    for section in Config.sections():
        if section[1:] == issue:
            url = Config.get(section, 'url')
            path = Config.get(section, 'path')
            aux_path = path.replace('/', '\/')
            diff_file = url.split('/')[-1]
            run('patch -p0 -i %s'%(fdir+"/"+diff_file), echo=True)
            break


@task
def list(patch=None, unstable=True, verbose=False):
    Config = read_config_file(None, type='patches', unstable=unstable)
    for section in Config.sections():
        issue_id = section[1:]
        if patch and patch != issue_id:
            continue
        issue = Issue.find(issue_id)
        print issue_id, ("{t.bold}%s{t.normal}"%issue.subject).format(t=t)
        if verbose:
            print ("{t.yellow}%s{t.normal}"%issue.description).format(t=t)


@task
def update(config=None, unstable=True, module=None, fdir='features'):
    if not os.path.exists(fdir):
        os.makedirs(fdir)

    Config = read_config_file(config, type='patches', unstable=True)
    for section in Config.sections():
        if not Config.has_option(section, 'patch'):
            continue

        if not module is None and module != section:
            continue

        url = Config.get(section, 'url')
        path = Config.get(section, 'path')

        run('cd %s; wget -N -q %s' % (fdir, url))

        aux_path = path.replace('/', '\/')
        diff_file = url.split('/')[-1]
        run('cd %s; sed -i "s/a\//%s/g" %s' % (fdir, aux_path, diff_file),
            echo=True)
        run('cd %s; sed -i "s/b\//%s/g" %s' % (fdir, aux_path, diff_file),
            echo=True)
        #run('patch -p0 %s'%(fdir+"/"+diff_file), echo=True)
