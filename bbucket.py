#!/usr/bin/env python

from invoke import task, run, Collection
import hgapi
from blessings import Terminal
import os
import ConfigParser
import bitbucket as bb
from scm import Config, read_config_file, t

"Library: https://bitbucket.org/DavidVilla/python-bitbucket-api/wiki/Home"


@task(
    help={
        'name': 'Repository name',
        'owner': 'Repository Owner',
        })
def create(name, owner='', public=True):
    """ Create repository on BitBucket """
    if not public:
        run('bucket create %s/%s'%(owner,name))
    else:
        run('bucket create --public %s/%s'%(owner,name))

@task
def mirror(name, verbose=False):

    read_config_file(None)
    if not Config.has_section(name):
        print ("Repo {t.red}%s{t.normal} has {t.red}NOT{t.normal} been "
            "configured yet"%name).format(t=t)
        return

    if not Config.has_option(name, 'mirror-url'):
        print ("Repo {t.red}%s hasn't{t.normal} got mirror-url"%name).format(
            t=t)
        return

    repo_type = Config.get(name, 'repo')
    repo_url = Config.get(name, 'url')
    repo_branch = Config.get(name, 'branch')

    mirror_url = Config.get(name, 'mirror-url')
    mirror_branch = Config.get(name, 'mirror-branch')

    path = Config.get(name, 'path')
    path_repo = os.path.join(path, name)
    owner = Config.get(name, 'owner')

    hide = 'stdout'
    if verbose:
        hide = None

    def hg_mirror():
        out = run('cd %s; hg branches'%(path_repo), hide=hide)
        if not mirror_branch in out.stdout:
            out = run('cd %s; hg branch %s'%(path_repo, mirror_branch),
                hide=hide)
            if out.failed:
                print ("{t.red}Failed {t.normal} to create branch %s on"
                    " %s" % (mirror_branch,name)).format(t=t)
                print t.red(out.stdout)
                return
            out = run('cd %s; hg push --new-branch'%(path_repo), hide=hide)
            if out.failed:
                print ("{t.red}Failed {t.normal} to push new branch %s on"
                    " %s" % (mirror_branch,name)).format(t=t)
                print t.red(out.stdout)
                return
        else:
            out = run('cd %s; hg update %s'%(path_repo, mirror_branch),
                hide=hide)
            if out.failed:
                print ("{t.red}Failed {t.normal} to change to branch %s on"
                    " %s" % (mirror_branch,name)).format(t=t)
                print t.red(out.stdout)
                return

        out = run('cd %s; hg pull -u %s'%(path_repo, mirror_url), hide=hide)
        if out.failed:
            print ("{t.red}Failed {t.normal} to change to pull %s on"
                " %s" % (mirror_url,name)).format(t=t)
            print t.red(out.stdout)
            return

        out = run('cd %s; hg push'%(path_repo), hide=hide)
        if out.failed:
            print ("{t.red}Failed {t.normal} to push changes to %s on"
                " %s" % (url,name)).format(t=t)
            print t.red(out.stdout)
            return

    if repo_type != 'hg':
        print "not supported yet"


    repo_name = repo_url.split('/')[-1]
    repos = run('bucket ls %s'%owner, hide=hide)
    if not repo_name in repos.stdout:
        create(repo_name, owner)
    hg_mirror()





