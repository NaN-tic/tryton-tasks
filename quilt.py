#!/usr/bin/env python
from invoke import task, Collection, run
from .utils import t


@task()
def applied(expect_empty=False):
    print t.bold('Patches Applied')
    res = run('quilt applied',  warn=True)
    patches = res.stdout.split('\n')
    for patch in patches:
        if expect_empty:
            print t.red(patch)
            return False
    return True


@task()
def unapplied():
    print t.bold('Patches Not Applied')
    res = run('quilt unapplied', hide='stdout', warn=True)
    patches = res.stdout.split('\n')
    for patch in patches:
        print t.red(patch)


def _pop():
    print t.bold('Reverting patches...')
    run('quilt pop -fa', warn=True)
    return applied(expect_empty=True)


@task()
def pop():
    _pop()


def _push():
    print t.bold('Applying patches...')
    run('quilt push -a', warn=True)
    res = applied()
    unapplied()
    return res


@task()
def push():
    _push()

QuiltCollection = Collection()
QuiltCollection.add_task(pop)
QuiltCollection.add_task(applied)
QuiltCollection.add_task(unapplied)
QuiltCollection.add_task(push)
