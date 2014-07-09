#!/usr/bin/env python
from invoke import task
from .utils import t, execBashCommand


@task
def pop():
    print t.bold('Reverting patches...')
    command = ['quilt', 'pop', '-fa']
    success = "patch(es) removed correctly"
    failure = "It's not possible to remove patch(es)"
    return execBashCommand(command, success, failure)


@task
def push():
    print t.bold('Applying patches...')
    command = ['quilt', 'push', '-a']
    success = "patch(es) applied correctly"
    failure = "It's not possible to apply patch(es)"
    return execBashCommand(command, success, failure)
