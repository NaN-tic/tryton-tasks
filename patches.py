#!/usr/bin/env python
from invoke import task, Collection, run
from .utils import t
import os

from quilt.push import Push
from quilt.pop import Pop
from quilt.error import AllPatchesApplied, QuiltError, UnknownPatch

patches_dir = "patches"
pc_dir = ".pc"
series_file = 'series'


@task()
def applied(ctx, expect_empty=False):
    print(t.bold('Patches Applied'))
    res = run('quilt applied',  warn=True)
    patches = res.stdout.split('\n')
    for patch in patches:
        if expect_empty:
            print(t.red(patch))
            return False
    return True


@task()
def unapplied(ctx,):
    print(t.bold('Patches Not Applied'))
    res = run('quilt unapplied', hide='stdout', warn=True)
    patches = res.stdout.split('\n')
    for patch in patches:
        print(t.red(patch))


def _pop(force=False):
    pop = Pop(os.getcwd(), pc_dir)
    try:
        pop.unapply_all(force)
    except QuiltError as e:
        print(t.red('KO: Error applying patch:' + str(e)))
        return -1
    except UnknownPatch as e:
        print(t.red('KO: Error applying patch:' + str(e)))
        return -1
    print(t.green('OK: All Patches removed'))
    return 0


@task()
def pop(ctx, force=False):
    _pop(force)


def _push(force=False, quiet=True):
    push = Push(os.getcwd(), pc_dir, patches_dir)
    try:
        push.apply_all(force, quiet)
    except AllPatchesApplied:
        print(t.green('OK: Patches already Applied'))
        return 0
    except QuiltError as e:
        print(t.red('KO: Error applying patch:' + str(e)))
        return -1
    except UnknownPatch as e:
        print(t.red('KO: Error applying patch:' + str(e)))
        return -1
    print(t.green('OK: All Patches Applied'))
    return 0


@task()
def push(ctx, force=False, quiet=True):
    _push(force=False, quiet=True)

QuiltCollection = Collection()
QuiltCollection.add_task(pop)
QuiltCollection.add_task(applied)
QuiltCollection.add_task(unapplied)
QuiltCollection.add_task(push)
