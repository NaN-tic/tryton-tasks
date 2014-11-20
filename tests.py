#!/usr/bin/env python
from invoke import task, run, Collection
import os
import sys
import tempfile
import scm
import utils
import project
from ConfigParser import NoOptionError
import logging
import time
from coverage import coverage

logging.basicConfig(filename='tests.log', level=logging.INFO,
    format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
logger = logging.getLogger(__name__)

#Ensure path is loaded correctly
sys.path.insert(0, os.path.abspath(os.path.normpath(os.path.join(
        os.path.dirname(__file__), '..', ''))))
for module_name in ('trytond', 'proteus'):
    DIR = os.path.abspath(os.path.normpath(os.path.join(
                os.path.dirname(__file__), '..', module_name)))
    if os.path.isdir(DIR):
        sys.path.insert(0, DIR)

#Now we should be able to import everything
import TrytonTestRunner
older_version = True
try:
    # TODO: Remove compatibility with older versions
    from trytond.config import CONFIG
except ImportError:
    from trytond.config import config as CONFIG
    older_version = False


def test(dbtype, name, modules, failfast, reviews):

    if older_version:
        CONFIG['db_type'] = dbtype
        if not CONFIG['admin_passwd']:
            CONFIG['admin_passwd'] = 'admin'
    elif dbtype != 'sqlite':
        CONFIG.set('database', 'uri', 'postgresql:///')

    if dbtype == 'sqlite':
        database_name = ':memory:'
    else:
        database_name = 'test_' + str(int(time.time()))

    if name is None:
        name = ''

    os.environ['DB_NAME'] = database_name
    cov = coverage()
    cov.start()
    from trytond.tests.test_tryton import modules_suite
    import proteus.tests

    if modules:
        suite = modules_suite(modules)
    else:
        suite = modules_suite()
        suite.addTests(proteus.tests.test_suite())

    runner = TrytonTestRunner.TrytonTestRunner(failfast=failfast, coverage=cov)
    runner.run(suite)
    if modules:
        name = name + " ["+modules+"]"

    logger.info('Upload results to tryton')
    runner.upload_tryton(dbtype, failfast, name, reviews)


@task()
def runall(test_file, dbtype='sqlite', branch='default', exclude_reviews=False,
        fail_fast=False):

    try:
        logger.info('Setting to branch: %s', branch)
        setup(branch)
        logger.info('Testing Branch %s with:'
            ' Include reviews: %s'
            ' Database Type: %s'
            ' Fail Fast: %s' % (branch, False, dbtype, fail_fast))
        runtests(test_file, branch, include_reviews=False,
            dbtype=dbtype, fail_fast=fail_fast)
        if not exclude_reviews:
            logger.info('Testing Branch %s with Reviews:'
            ' Include reviews: %s'
            ' Database Type: %s'
            ' Fail Fast: %s' % (branch, True, dbtype, fail_fast))
            runtests(test_file, branch, development=False,
                include_reviews=True, dbtype=dbtype, fail_fast=fail_fast)
    except:
        logger.critical(sys.exc_info()[1])
        logger.critical(sys.exc_info()[2])


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
    if include_reviews:
        name = '%s with reviews' % name

    logger.info('%s Testing...' % name)

    test(failfast=fail_fast, dbtype=dbtype, reviews=include_reviews, name=name,
        modules=None)

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
            project.fetch_reviews(branch, component=section)

        logger.info('%s Testing...' % name2)
        test(failfast=fail_fast, dbtype=dbtype, reviews=include_reviews,
            modules=section, name=name2)
        for to_remove in repos_to_remove:
            utils.remove_dir(to_remove, quiet=True)

    os.chdir(old_dir)
    run("rm -Rf %s" % directory)


@task()
def clean(force=True):
    scm.prefetch(force=force)


def setup(branch='default', force=True, fetch=True):
    scm.hg_update('config', 'config', force, branch=branch)
    scm.update(clean=force)
    if fetch:
        scm.fetch()
    scm.unknown(remove=True, quiet=force)


TestCollection = Collection()
TestCollection.add_task(clean)
TestCollection.add_task(runall)
