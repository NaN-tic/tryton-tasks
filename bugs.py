#!/usr/bin/env python
from invoke import task, Collection
import os
import yaml
import subprocess

patches_dir = "./bugs"
series_file = 'series'


def read_series():
    return yaml.load(open(os.path.join(patches_dir, series_file)).read())


class Patch(object):
    def __init__(self, yaml_obj, conflict=False):
        self.name, = yaml_obj.keys()
        self.patchfile = os.path.join(patches_dir, yaml_obj[self.name]['file'])
        self.task = yaml_obj[self.name]['task']
        self.conflict = conflict

    def __repr__(self):
        applied = 'applied' if self.applied() else 'Not applied'
        conflict = '' if not self.conflict else 'Conflict'
        return "[%s] - file: %s ,  %s , %s" % (self.name, self.patchfile,
            applied, conflict)

    def applied(self):
        command = ["patch", "-N", "-p1", "--silent", "--dry-run", "-i", self.patchfile]
        process = subprocess.Popen(command, stdout=subprocess.PIPE)
        output, err = process.communicate()
        self.conflict = 'FAILED' in output
        if not output or self.conflict:
            return False
        return True

    def push(self):
        command = ["patch", "-N", "-p1", "-i", self.patchfile]
        process = subprocess.Popen(command, stdout=subprocess.PIPE)
        output, err = process.communicate()
        return True if not err else False

    def pop(self):
        command = ["patch", "-R", "-p1", "-i", self.patchfile]
        process = subprocess.Popen(command, stdout=subprocess.PIPE)
        output, err = process.communicate()
        return True if not err else False


@task()
def applied():
    series = read_series()
    if not series:
        print("Series is empty")
        return
    applied = []
    for patch_yml in series:
        patch = Patch(patch_yml)
        if patch.applied():
            applied.append(str(patch))

    if applied:
        print("Patch applied:")
        for p in applied:
            print(p)
    return True


@task()
def unnapplied():
    series = read_series()
    if not series:
        print("Series is empty")
        return
    unnapplied = []
    for patch_yml in series:
        patch = Patch(patch_yml)
        if not patch.applied():
            unnapplied.append(str(patch))

    if unnapplied:
        print("Patch Not applied:")
        for p in unnapplied:
            print(p)
    return True


def _pop():
    series = read_series()
    if not series:
        print("Series is empty")
        return
    for patch_yml in series:
        patch = Patch(patch_yml)
        if patch.applied():
            patch.pop()
            print(patch)


@task()
def pop():
    _pop()


def _push():
    series = read_series()
    if not series:
        print("Series is empty")
        return
    for patch_yml in series:
        patch = Patch(patch_yml)
        if not patch.applied():
            if not patch.conflict:
                patch.push()
            print(patch)


@task()
def push():
    _push()


BugCollection = Collection()
BugCollection.add_task(pop)
BugCollection.add_task(applied)
BugCollection.add_task(unnapplied)
BugCollection.add_task(push)
