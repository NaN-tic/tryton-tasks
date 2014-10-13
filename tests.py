#!/usr/bin/env python
from invoke import task, run, Collection
import os
import tempfile
import scm
import utils
import project
from ConfigParser import NoOptionError
import TrytonTestRunner
import time

# from .scm import prefetch, fetch, get_repo, remove_dir,
#      hg_clone, git_clone
# from .utils import read_config_file


@task()
def test(failfast=True, dbtype='sqlite', reviews =False, modules=None,
        name=None):

    from trytond.config import CONFIG

    CONFIG['db_type'] = dbtype
    if not CONFIG['admin_passwd']:
        CONFIG['admin_passwd'] = 'admin'

    if dbtype == 'sqlite':
        database_name = ':memory:'
    else:
        database_name = 'test_' + str(int(time.time()))

    name += "("+str(int(time.time()))+")"
    os.environ['DB_NAME'] = database_name

    from trytond.tests.test_tryton import modules_suite
    import proteus.tests

    if modules:
        suite = modules_suite(modules)
    else:
        suite = modules_suite()
        suite.addTests(proteus.tests.test_suite())


    runner = TrytonTestRunner.TrytonTestRunner(failfast=failfast)
    result = runner.run(suite)
    if modules:
        name = name + " ["+modules+"]"

    runner.upload_tryton(dbtype, failfast, name, reviews)


@task
def runall(test_file, dbtype='sqlite', branch='default', exclude_stable=False,
        exclude_development=False, exclude_reviews=False):
    if not exclude_stable:
        print "Setup & testing stable revision of branch: %s " % branch
        runtests(test_file, branch, development=False, include_reviews=False,
            dbtype=dbtype)
        if not exclude_reviews:
            runtests(test_file, branch, development=False,
                include_reviews=True, dbtype=dbtype)
    if not exclude_development:
        print "Setup & testing development revision of branch: %s " % branch
        runtests(test_file, branch, development=True,
            include_reviews=False, dbtype=dbtype)
        if not exclude_reviews:
            runtests(test_file, branch, development=True,
                include_reviews=True, dbtype=dbtype)

@task()
def runtests(test_file=None, branch='default', development=False,
        include_reviews=False, dbtype='sqlite'):

    directory = tempfile.mkdtemp()
    run("cp . %s -R" % directory)
    old_dir = os.getcwd()
    os.chdir(directory)
    setup(branch, development)
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

    failfast=False
    test(failfast=failfast, dbtype=dbtype, reviews=include_reviews, name=name)

    for section in sections:
        name +=  "/" + section
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
            name = '%s (with reviews)' % name
            project.fetch_reviews(component=section)

        test(failfast=failfast, dbtype=dbtype, reviews=True, modules=section,
            name=name)
        for to_remove in repos_to_remove:
            utils.remove_dir(to_remove, quiet=True)

    os.chdir(old_dir)
    run("rm -Rf %s" % directory)


@task()
def clean(force=True):
    scm.prefetch(force=force)


@task()
def setup(branch='default', development=False, force=True):
    scm.hg_update('config', 'config', force, branch=branch)
    scm.update(clean=force)
    scm.fetch()
    scm.unknown(remove=True, quiet=force)


TestCollection = Collection()
TestCollection.add_task(test)
TestCollection.add_task(clean)
TestCollection.add_task(setup)
TestCollection.add_task(runtests)
TestCollection.add_task(runall)
