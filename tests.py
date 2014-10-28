#!/usr/bin/env python
from invoke import task, run, Collection
import os
import sys
import tempfile
import scm
import utils
import project
from ConfigParser import NoOptionError

# from .scm import prefetch, fetch, get_repo, remove_dir,
#      hg_clone, git_clone
# from .utils import read_config_file


@task()
def test(failfast=True, dbtype='sqlite', reviews=False, modules=None,
        name=None, directory=None):

    test_file = 'run_test.py'
    if directory is None:
        directory = os.path.dirname(__file__)
    test_file = os.path.join(directory, test_file)
    cmd = ['/usr/bin/env', 'python', test_file]
    if reviews:
        cmd.append('--reviews')
    if failfast:
        cmd.append('--fail-fast')
    cmd.append('--db-type %s' % dbtype)
    if name:
        cmd.append('--name %s' % name)
    if modules:
        cmd.append('-m %s' % modules)

    run(" ".join(cmd), echo=True)


@task()
def runall(test_file, dbtype='sqlite', branch='default', exclude_stable=False,
        exclude_development=False, exclude_reviews=False, fail_fast=False):
    setup(branch)
    if not exclude_stable:
        print "Setup & testing stable revision of branch: %s " % branch
        runtests(test_file, branch, development=False, include_reviews=False,
            dbtype=dbtype, fail_fast=fail_fast)
        if not exclude_reviews:
            runtests(test_file, branch, development=False,
                include_reviews=True, dbtype=dbtype, fail_fast=fail_fast)
    if not exclude_development:
        print "Setup & testing development revision of branch: %s " % branch
        runtests(test_file, branch, development=True,
            include_reviews=False, dbtype=dbtype, fail_fast=fail_fast)
        if not exclude_reviews:
            runtests(test_file, branch, development=True,
                include_reviews=True, dbtype=dbtype, fail_fast=fail_fast)


@task()
def runtests(test_file=None, branch='default', development=False,
        include_reviews=False, dbtype='sqlite', fail_fast=False):

    directory = tempfile.mkdtemp()
    run("cp . %s -R" % directory)
    old_dir = os.getcwd()
    os.chdir(directory)
    setup(branch, development, fetch=False)
    sections = []
    if test_file:
        config = utils.read_config_file(test_file)
        sections = config.sections()

    if test_file and include_reviews:
        project.fetch_reviews(branch, exclude_components=config.sections() +
            ['OpenERP'])

    name = 'Generic Modules'
    if development:
            name = '%s - Development' % name

    test(failfast=fail_fast, dbtype=dbtype, reviews=include_reviews, name=name,
        directory=os.path.join(directory, 'tasks'))

    for section in sections:
        name2 = name + "/" + section
        repos_to_clone = [section]
        try:
            repos_to_clone += config.get(section, 'requires').split(',')
        except NoOptionError:
            pass

        repos_to_remove = []
        for to_clone in repos_to_clone:
            repo = scm.get_repo(to_clone, config, 'clone', development)
            if repo['branch'] != branch:
                continue
            func = repo['function']
            func(repo['url'], repo['path'], repo['branch'], repo['revision'])
            repos_to_remove.append(repo['path'])
        if include_reviews:
            name2 = '%s (with reviews)' % name2
            project.fetch_reviews(branch, component=section)

        test(failfast=fail_fast, dbtype=dbtype, reviews=True, modules=section,
            name=name2, directory=os.path.join(directory, 'tasks'))
        for to_remove in repos_to_remove:
            utils.remove_dir(to_remove, quiet=True)

    os.chdir(old_dir)
    run("rm -Rf %s" % directory)


@task()
def clean(force=True):
    scm.prefetch(force=force)


@task()
def setup(branch='default', development=False, force=True, fetch=True):
    scm.hg_update('config', 'config', force, branch=branch)
    scm.update(clean=force)
    if fetch:
        scm.fetch()
    scm.unknown(remove=True, quiet=force)


TestCollection = Collection()
TestCollection.add_task(test)
TestCollection.add_task(clean)
TestCollection.add_task(setup)
TestCollection.add_task(runtests)
TestCollection.add_task(runall)
