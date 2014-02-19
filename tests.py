#!/usr/bin/env python
from invoke import task, run


@task()
def test(coverage=False, flakes=False, unittest=False, failfast=True,
    sqlite=False, psql=False):
    cmd = ['./tryton-tests/runtests.py']
    if coverage:
        cmd.append('--coverage')
    if flakes:
        cmd.append('--flakes-only')
    if unittest:
        cmd.append('--unittest-only')
    if failfast:
        cmd.append('--failfast')
    if sqlite:
        cmd.append('--sqlite-only')
    if psql:
        cmd.append('--psql-only')

    run(" ".join(cmd), echo=True)


