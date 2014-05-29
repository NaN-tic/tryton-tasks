#!/usr/bin/env python

from invoke import task, run


@task()
def create(name, description='', owner='nantic', private=False, scm='hg'):
    cmd = 'bitbucket repo create -r "%(name)s" '
    cmd += '--owner=%(owner)s '
    cmd += '-d %(description)s -s %(scm)s -i true'
    if private:
        cmd += '-p true'
    run(cmd % locals())


@task()
def delete(account, repo):
    cmd = 'bitbucket repo delete -a %(account)s '
    cmd += ' -r %(repo)s'
    run(cmd % locals())


@task()
def list():
    cmd = 'bitbucket repo list'
    run(cmd)


@task()
def detail(repo):
    cmd = 'bitbucket repo detail -r %(repo)s'
    run(cmd % locals())
