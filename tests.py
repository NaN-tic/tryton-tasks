#!/usr/bin/env python
from invoke import task, run, Collection
from scm import unknown
from bootstrap import bootstrap


@task()
def test(coverage=False, flakes=False, failfast=True,
        sqlite=True, postgres=False, mail=False):
    cmd = ['./test.py']
    if coverage:
        cmd.append('--coverage')
    if flakes:
        cmd.append('--flakes')
    if failfast:
        cmd.append('--fail-fast')
    if sqlite:
        cmd.append('--db-type sqlite')
    if postgres:
        cmd.append('--db-type postgres')
    if mail:
        cmd.append('--mail')

    run(" ".join(cmd), echo=True)


@task()
def clean():
    without_repo, not_config = unknown(show=False)


@task()
def setup(development=False):
    pass


TestCollection = Collection()
TestCollection.add_task(test)
TestCollection.add_task(clean)
TestCollection.add_task(setup)
