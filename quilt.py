#!/usr/bin/env python
from invoke import task, Collection, run
from .utils import t, execBashCommand



@task()
def applied(expect_empty=False):
    print t.bold('Patches Applied')
    res = run('quilt applied',  warn=True)
    patches = res.stdout.split('\n')
    for patch in patches:
        if expect_empty:
            print t.green(patch)
        else:
            print t.red(patch)


@task
def unapplied():
    print t.bold('Patches Not Applied')
    res = run('quilt unapplied', hide='stdout', warn=True)
    patches = res.stdout.split('\n')
    for patch in patches:
        print t.red(patch)

@task()
def pop():
    print t.bold('Reverting patches...')
    res = run('quilt pop -fa', warn=True)
    applied(expect_empty=True)


@task()
def push():
    print t.bold('Applying patches...')
    res = run('quilt push -a', warn=True)
    applied()
    unapplied()


QuiltCollection = Collection()
QuiltCollection.add_task(pop)
QuiltCollection.add_task(applied)
QuiltCollection.add_task(unapplied)
QuiltCollection.add_task(push)
