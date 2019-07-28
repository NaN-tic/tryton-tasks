#!/usr/bin/env python
from invoke import task, Collection
import os
import yaml

patches_dir = "./features"
series_file = 'series'
import subprocess

def read_series():
    return yaml.load(open(os.path.join(patches_dir, series_file)).read())

class Patch(object):
    def __init__(self, yaml_obj, conflict=False):
        self.name, = yaml_obj.keys()
        self.patchfile = os.path.join(patches_dir, yaml_obj[self.name]['file'])
        self.milestone = yaml_obj[self.name]['milestone']
        self.task = yaml_obj[self.name]['task']
        self.conflict = conflict

    def __repr__(self):
        applied = 'applied' if self.applied() else 'Not applied'
        conflict = '' if not self.conflict else 'Conflict'
        return "[%s] - file: %s ,  %s , %s" % (self.name, self.patchfile,
            applied, conflict)

    def applied(self):
        command = ["patch", "-N", "-p1", "--silent",  "--dry-run", "-i", self.patchfile ]
        process = subprocess.Popen(command, stdout=subprocess.PIPE)
        output, err = process.communicate()
        if not output:
            return False
        return True

    def push(self):
        command = ["patch", "-N", "-p1", "-i", self.patchfile ]
        process = subprocess.Popen(command, stdout=subprocess.PIPE)
        output, err = process.communicate()
        return True if not err else False

    def pop(self):
        command = ["patch", "-R", "-p1", "-i", self.patchfile ]
        process = subprocess.Popen(command, stdout=subprocess.PIPE)
        output, err = process.communicate()
        return True if not err else False

@task()
def applied(ctx):
    series = read_series()
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
def unnapplied(ctx):
    series = read_series()
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
    for patch_yml in series:
        patch = Patch(patch_yml)
        if patch.applied():
            patch.pop()
            print(patch)


@task()
def pop(ctx):
    _pop()


def _push():
    series = read_series()
    for patch_yml in series:
        patch = Patch(patch_yml)
        if not patch.applied():
            patch.push()
            print(patch)


@task()
def push(ctx):
    _push()

FeatureCollection = Collection()
FeatureCollection.add_task(pop)
FeatureCollection.add_task(applied)
FeatureCollection.add_task(unnapplied)
FeatureCollection.add_task(push)
