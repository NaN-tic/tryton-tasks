#!/usr/bin/env python
from invoke import task, run, Collection
from .scm import prefetch, fetch



@task()
def test(coverage=False, flakes=False, failfast=True,
        sqlite=True, postgres=False, mail=False, Module=None):
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
    prefetch()


@task()
def setup(defevelopment=False):
    clean()
    fetch()




TestCollection = Collection()
TestCollection.add_task(test)
TestCollection.add_task(clean)
TestCollection.add_task(setup)
