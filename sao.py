#!/usr/bin/env python
import os
from invoke import task, Collection
from blessings import Terminal

t = Terminal()

@task
def install(ctx):
    'Install SAO'
    os.chdir('./public_data/sao')
    os.system('npm install')
    os.system('bower install')

    # download TinyMCE
    os.system('bower install tinymce#4.9.3')
    os.system('bower install tinymce-i18n')
    os.system('ln -s ../tinymce-i18n/langs bower_components/tinymce/langs')

    print(t.bold('Done'))

@task
def grunt(ctx):
    'Grunt SAO'
    os.chdir('./public_data/sao')
    os.system('grunt')

    print(t.bold('Done'))

SaoCollection = Collection()
SaoCollection.add_task(install)
SaoCollection.add_task(grunt)
