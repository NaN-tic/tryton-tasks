#!/usr/bin/env python

from invoke import task, run
import os
from utils import t, read_config_file
from multiprocessing import Process

"Library: https://bitbucket.org/DavidVilla/python-bitbucket-api/wiki/Home"


@task(
    help={
        'name': 'Repository name',
        'owner': 'Repository Owner',
        })
def create(name, owner='', public=True):
    """ Create repository on BitBucket """
    if not public:
        run('bucket create %s/%s' % (owner, name))
    else:
        run('bucket create --public %s/%s' % (owner, name))


@task
def mirror_module(name, verbose=False):
    def print_msg(msg):
        print ("\n".join(msg)).format(t=t)

    hide = 'stdout'
    if verbose:
        hide = None
    config = read_config_file()
    if not config.has_section(name):
        print ("Repo {t.red}%s{t.normal} has {t.red}NOT{t.normal} been "
            "configured yet" % name).format(t=t)
        return

    if not config.has_option(name, 'mirror-url'):
        print ("Repo {t.red}%s{t.normal} hasn't got mirror-url" %
            name).format(t=t)
        return

    msg = []

    repo_type = config.get(name, 'repo')
    repo_url = config.get(name, 'url')

    mirror_url = config.get(name, 'mirror-url')
    mirror_branch = config.get(name, 'mirror-branch')

    path = config.get(name, 'path')
    path_repo = os.path.join(path, name)
    owner = config.get(name, 'owner')

    if repo_type != 'hg':
        print "not supported yet"
        return

    repo_name = repo_url.split('/')[-1]
    repos = run('bucket ls %s' % owner, hide='stdout')
    existing_repos = repos.stdout.split('\n')
    if not repo_name in existing_repos:
        create(repo_name, owner)

    out = run('cd %s; hg branches' % (path_repo), hide='stdout')
    if not mirror_branch in out.stdout:
        out = run('cd %s; hg branch %s' % (path_repo, mirror_branch),
            hide=hide)
        if out.failed:
            msg.append("{t.red}Failed {t.normal} to create branch %s on"
                " %s" % (mirror_branch, name))
            print_msg(msg)
            return
        out = run('cd %s; hg ci -m "start %s branch"' % (
                path_repo, mirror_branch), hide=hide)
        if out.failed:
            msg.append("{t.red}Failed {t.normal} to commit new branch %s on"
                " %s" % (mirror_branch, name))
            msg.append(t.red(out.stdout))
            print_msg(msg)
            return

        out = run('cd %s; hg push --new-branch' % (path_repo), hide=hide)
        if out.failed:
            msg.append("{t.red}Failed {t.normal} to push new branch %s on"
                " %s" % (mirror_branch, name))
            msg.append(t.red(out.stdout))
            print_msg(msg)
            return
    else:
        out = run('cd %s; hg update %s' % (path_repo, mirror_branch),
            hide=hide)
        if out.failed:
            msg.append("{t.red}Failed {t.normal} to change to branch %s on"
                " %s" % (mirror_branch, name))
            msg.append(t.red(out.stdout))
            print_msg(msg)
            return

    out = run('cd %s; hg pull -u %s' % (path_repo, mirror_url), hide=hide)
    if out.failed:
        msg.append("{t.red}Failed {t.normal} to change to pull %s on"
            " %s" % (mirror_url, name))
        msg.append(t.red(out.stdout))
        print_msg(msg)
        return

    #TODO: check why run function fail
    os.system('cd %s; hg push --quiet' % (path_repo))

    if not msg:
        msg.append("Mirror {t.bold}%s{t.normal} {t.green}Ok{t.normal}" % name)
    #out = run('cd %s; hg push' % (path_repo), echo=True)
    #if out.failed:
    #    msg.append("{t.red}Failed {t.normal} to push changes to %s on"
    #        " %s" % (repo_url, name))
    #    msg.append(t.red(out.stdout))

    print_msg(msg)


@task
def mirror(config=None, verbose=False):
    config = read_config_file(config)
    repos = config.sections()
    processes = []

    for repo in repos:
        p = Process(target=mirror_module, args=(repo, verbose))
        p.start()
        processes.append(p)
