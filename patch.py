#!/usr/bin/env python
import os
import ConfigParser
from utils import t, read_config_file
from pyactiveresource.activeresource import ActiveResource
from invoke import task, run
from .config import get_config


config = get_config()
site = None
headers = None
if 'redmine' in config:
    site = config['redmine'].get('site')
    headers = eval(config['redmine'].get('headers'))

class Issue(ActiveResource):
    _site = site
    _headers = headers


@task
def unapply(issue, fdir='features'):
    Config = read_config_file(None, type='patches')
    for section in Config.sections():
        if section[1:] == issue:
            url = Config.get(section, 'url')
            diff_file = url.split('/')[-1]
            run('patch -p0 -R -i %s' % (fdir + "/" + diff_file), echo=True)
            break


@task
def apply(issue, fdir='features'):
    Config = read_config_file(None, type='patches')
    for section in Config.sections():
        if section[1:] == issue:
            url = Config.get(section, 'url')
            diff_file = url.split('/')[-1]
            run('patch -p0 -i %s' % (fdir + "/" + diff_file), echo=True)
            break


@task
def list(patch=None, unstable=True, verbose=False):
    Config = read_config_file(None, type='patches', unstable=unstable)
    for section in Config.sections():
        issue_id = section[1:]
        if patch and patch != issue_id:
            continue
        issue = Issue.find(issue_id)
        print issue_id, ("{t.bold}%s{t.normal}" % issue.subject).format(t=t)
        if verbose:
            print ("{t.yellow}%s{t.normal}" % issue.description).format(t=t)


@task
def update(config=None, unstable=True, module=None, fdir='features',
        verbose=False):
    if not os.path.exists(fdir):
        os.makedirs(fdir)

    Config = read_config_file(config, type='patches', unstable=True)
    for section in Config.sections():
        if not Config.has_option(section, 'patch'):
            continue

        if not module is None and module != section:
            continue

        print t.bold("patch.update: ") + section

        url = Config.get(section, 'url')
        path = Config.get(section, 'path')

        run('cd %s; wget -N -q %s' % (fdir, url), echo=verbose)

        aux_path = path.replace('/', '\/')
        diff_file = url.split('/')[-1]
        run('cd %s; sed -i "s/a\//%s/g" %s' % (fdir, aux_path, diff_file),
            echo=verbose)
        run('cd %s; sed -i "s/b\//%s/g" %s' % (fdir, aux_path, diff_file),
            echo=verbose)
        #run('patch -p0 %s'%(fdir+"/"+diff_file), echo=True)


@task
def push(patch=None, force=False):
    cmd = ['quilt', 'push']
    if force:
        cmd.append('-f')
    if patch:
        cmd.append(patch)
    else:
        cmd.append('-a')
    run(' '.join(cmd), echo=True)


@task
def pop(patch=None, force=True):
    cmd = ['quilt', 'pop']
    if force:
        cmd.append('-f')
    if patch:
        cmd.append(patch)
    else:
        cmd.append('-a')
    run(' '.join(cmd), echo=True)
