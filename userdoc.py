#!/usr/bin/env python

import ConfigParser
import os
from blessings import Terminal
from invoke import task, run, Collection
from path import path
import glob

t = Terminal()

INITIAL_PATH = path.getcwd()


@task
def install_requirements(requirement_file, upgrade=False):

    print 'Installing dependencies...'
    cmd = "pip install "
    if upgrade:
        cmd += " --upgrade "
    cmd += "-r %(requirement_file)s" % locals()
    run(cmd)


def create_symlinks(origin, destination, lang='es', remove=True):
    if remove:
        # Removing existing symlinks
        for link_file in path(destination).listdir():
            if link_file.islink():
                link_file.remove()

    for module_doc_dir in glob.glob('%s/*/doc/%s' % (origin, lang)):
        module_name = str(path(module_doc_dir).parent.parent.basename())
        symlink = path(destination).joinpath(module_name)
        if not symlink.exists():
            path(destination).relpathto(path(module_doc_dir)).symlink(symlink)


def update_modules(userdocpath='userdoc'):
    # TODO: all update_modules. copy utils/doc-update-modules.py
    # touch ./userdoc/modules.cfg
    # echo [modules] >> ./userdoc/modules.cfg
    pass


@task(default=True)
def make(builder='html', source='source-doc',
        destination="public_data/doc", clean=False):
    if clean:
        if path(destination).exists():
            path(destination).rmtree()

    if builder == 'pdf':
        run("sphinx-build  -b latex %s %s/latex" % (source, destination),
            echo=True)
        run("make -C %s/latex all-pdf" % (destination, ),
            echo=True)
        # Run two times to generate index correctly
        run("make -C %s/latex all-pdf" % (destination, ),
            echo=True)
        print "Documentation PDF generated in %s/latex" % (destination, )
    else:
        run("sphinx-build  -b %s %s %s" % (builder, source, destination),
            echo=True)


def make_link(origin, destination):
    directory = os.path.dirname(destination)
    if not os.path.exists(destination):
        path(directory).relpathto(path(origin)).symlink(destination)


@task()
def bootstrap(modules='modules', user_doc_path='tryton-doc',
        source_doc='source-doc', doc_path="public_data/doc", lang="es"):
    if not os.path.exists(source_doc):
        run("mkdir %(source_doc)s" % locals())
    if not os.path.exists(doc_path):
        run("mkdir %(doc_path)s" % locals())

    current_path = os.path.dirname(__file__)
    requirement_file = os.path.join(user_doc_path, 'requirements.txt')
    install_requirements(requirement_file, True)

    # create symlinks from modules.
    create_symlinks(modules, source_doc, lang, True)
    # create symlinks from core modeules.
    create_symlinks(user_doc_path, source_doc, lang, False)
    # create symlink for conf.py
    template = "%(current_path)s/templates/conf.py.template" % locals()
    conf_file = './conf.py'
    if not os.path.exists(conf_file):
        run("cp %(template)s %(conf_file)s" % locals(), echo=True)
    conf_file_link = os.path.join(source_doc, 'conf.py')
    make_link(conf_file, conf_file_link)

    # create symlink for index
    index = os.path.join(user_doc_path, 'index.rst')
    link = os.path.join(source_doc, 'index.rst')
    make_link(index, link)

DocCollection = Collection()
DocCollection.add_task(bootstrap)
DocCollection.add_task(make)
DocCollection.add_task(install_requirements)
