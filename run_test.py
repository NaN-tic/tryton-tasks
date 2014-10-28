import optparse
import os
import sys
import time

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
from trytond.config import CONFIG


def run(dbtype='sqlite', name=None, modules=None, failfast=True,
        reviews=False):
    CONFIG['db_type'] = dbtype
    if not CONFIG['admin_passwd']:
        CONFIG['admin_passwd'] = 'admin'

    if dbtype == 'sqlite':
        database_name = ':memory:'
    else:
        database_name = 'test_' + str(int(time.time()))

    if name is None:
        name = ''

    name += "(" + str(int(time.time())) + ")"
    os.environ['DB_NAME'] = database_name
    from trytond.tests.test_tryton import modules_suite
    import proteus.tests

    if modules:
        suite = modules_suite(modules)
    else:
        suite = modules_suite()
        suite.addTests(proteus.tests.test_suite())

    runner = TrytonTestRunner.TrytonTestRunner(failfast=failfast)
    runner.run(suite)
    if modules:
        name = name + " ["+modules+"]"

    runner.upload_tryton(dbtype, failfast, name, reviews)

parser = optparse.OptionParser()
parser.add_option("", "--name", dest="name",
    help="specify name of execution")
parser.add_option("", "--db-type", dest="db_type", help="specify db type")
parser.add_option('', '--reviews', action="store_true", dest='reviews',
    help='Includes reviews', default=False)
parser.add_option('', '--fail-fast', action="store_true", dest='failfast',
    help='Fail on first error', default=False)
parser.add_option("-m", "--modules", dest="modules", default=None)
(opt, _) = parser.parse_args()


if __name__ != '__main__':
    raise ImportError('%s can not be imported' % __name__)

run(opt.db_type, opt.name, opt.modules, opt.failfast, opt.reviews)
