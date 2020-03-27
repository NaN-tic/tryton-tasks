#!/usr/bin/env python
import os
from invoke import task, Collection
from blessings import Terminal

t = Terminal()

@task
def install(context):
    'Install SAO'
    os.chdir('public_data/sao')
    os.system('npm install')
    os.system('bower install')

    print t.bold('Done')

@task
def grunt(context):
    'Grunt SAO'
    os.chdir('public_data/sao')
    os.system('grunt')

    print t.bold('Done')

SaoCollection = Collection()
SaoCollection.add_task(install)
SaoCollection.add_task(grunt)
