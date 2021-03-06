#!/usr/bin/env python
from invoke import task, Collection
import os
import subprocess
import sys
from . import scm
import logging
import time
from coverage import coverage
from .utils import read_config_file, NO_MODULE_REPOS
from multiprocessing import Pool
import hgapi
from .tryton_component import get_tryton_connection

MAX_PROCESSES = 4
TEST_FILE = 'tests.log'

logging.basicConfig(filename=TEST_FILE, level=logging.INFO,
    format='[%(asctime)s] %(name)s: %(message)s',
    datefmt='%m/%d/%Y %I:%M:%S %p')
logger = logging.getLogger("nan-tasks")

# Ensure path is loaded correctly
sys.path.insert(0, os.path.abspath(os.path.normpath(os.path.join(
        os.path.dirname(__file__), '..', ''))))
for module_name in ('trytond', 'proteus'):
    DIR = os.path.abspath(os.path.normpath(os.path.join(
                os.path.dirname(__file__), '..', module_name)))
    if os.path.isdir(DIR):
        sys.path.insert(0, DIR)

# Now we should be able to import everything
from . import TrytonTestRunner

older_version = True
try:
    # TODO: Remove compatibility with older versions
    from trytond.config import CONFIG
except ImportError:
    try:
        from trytond.config import config as CONFIG
        older_version = False
    except:
        pass

try:
    from proteus import Model
except ImportError as e:
    print("trytond importation error: ", e, file=sys.stderr)


def check_output(*args):
    process = subprocess.Popen(args, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    process.wait()
    data = process.stdout.read()
    return data


def get_fqdn():
    data = check_output('hostname', '--fqdn')
    data = data.strip('\n').strip('\r').strip()
    if not data:
        # In some hosts we may get an error message on stderr with
        # 'No such host'.
        # if using --fqdn parameter. In this case, try to run hostname
        # without parameters.
        data = check_output('hostname')
        data = data.strip('\n').strip('\r').strip()
    return data


def test(dbtype, name, modules, failfast, upload=True):

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

    suite = None
    if modules:
        suite = modules_suite(modules)
    else:
        suite = modules_suite()
        suite.addTests(proteus.tests.test_suite())

    runner = TrytonTestRunner.TrytonTestRunner(failfast=failfast, coverage=cov)
    runner.run(suite)
    if modules:
        name = name + " ["+','.join(modules)+"]"

    logger.info('Upload results to tryton')
    if upload:
        print(("Uploading to Tryton '%s'" % name))
        runner.upload_tryton(dbtype, failfast, name)
        print(("'%s' uploaded." % name))
    else:
        runner.print_report(dbtype, failfast, name)


@task()
def module(ctx, module, work=None,  dbtype='sqlite', fail_fast=False, upload=True,
        force=False):
    open(TEST_FILE, 'w').close()
    _module(module, dbtype, fail_fast, upload, force)


def _module(module, dbtype='sqlite', fail_fast=False, upload=True, force=False):

    if upload:
        get_tryton_connection()
        Build = Model.get('project.test.build')
        Config = read_config_file()

        repo = scm.get_repo(module, Config, 'revision')
        repo = hgapi.Repo(repo['path'])
        build = None
        try:
            rev = repo.hg_rev()
            revision = repo.revision(rev)
            build = Build.find([
                ('component.name', '=', module),
                ('revision', '=', revision.node)],
                order=[('execution', 'Desc')],
                limit=1)

        except hgapi.HgException as e:
            print("Error running %s: %s" % (e.exit_code, str(e)))

        if build and not force:
            return

    logger.info("Testing module:" + module)
    test(failfast=fail_fast, dbtype=dbtype, modules=[module], name=module,
        upload=upload)


@task()
def modules(ctx, dbtype='sqlite', force=False, processes=MAX_PROCESSES):
    open(TEST_FILE, 'w').close()

    Config = read_config_file()
    p = Pool(processes)
    repos = [x for x in Config.sections() if x not in NO_MODULE_REPOS]
    p.map(_module, repos)



TestCollection = Collection()
TestCollection.add_task(module)
TestCollection.add_task(modules)
