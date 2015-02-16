import datetime
import subprocess
import StringIO
import sys
import unittest
import os
from tasks.config import get_config
from tasks.scm import hg_revision, get_branch
from coverage import coverage
import re
import logging


try:
    from proteus import config as pconfig, Model
except ImportError, e:
    print >> sys.stderr, "trytond importation error: ", e

os.environ['TZ'] = "Europe/Madrid"
settings = get_config()


logging.basicConfig(filename='tests.log', level=logging.INFO,
    format='[%(asctime)s] %(name)s: %(message)s',
    datefmt='%m/%d/%Y %I:%M:%S %p')
logger = logging.getLogger("TrytonTest")


def get_tryton_connection():
    tryton = settings['tryton']
    return pconfig.set_xmlrpc(tryton['server'])


def get_module_key(filename):
    uppath = lambda _path, n: os.sep.join(_path.split(os.sep)[:-n])
    directory = os.path.dirname(filename)
    i = 0
    while not os.path.exists(os.path.join(directory, 'tryton.cfg')):
        if directory.split(os.sep)[-1] == 'trytond':
            return False
        i += 1
        if i > 5:
            return False
        directory = uppath(directory, i)

    return directory.split('/')[-1]


def check_output(args, env=None, errors=False):
    try:
        process = subprocess.Popen(args, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        data, stderr = process.communicate()
        if errors:
            data += '-' * 50 + '\n' + stderr
        if stderr:
            raise Exception("Exception executing %s" % args)
    except:
        logger.exception("Exception executing %s:" % args, exc_info=1)
        return "Exception executing %s:" % args
    return data


# ------------------------------------------------------------------------
# The redirectors below is used to capture output during testing. Output
# sent to sys.stdout and sys.stderr are automatically captured. However
# in some cases sys.stdout is already cached before HTMLTestRunner is
# invoked (e.g. calling logging.basicConfig). In order to capture those
# output, use the redirectors for the cached stream.
#
# e.g.
#   >>> logging.basicConfig(stream=HTMLTestRunner.stdout_redirector)
#   >>>
class OutputRedirector(object):
    """ Wrapper to redirect stdout or stderr """
    def __init__(self, fp):
        self.fp = fp

    def write(self, s):
        self.fp.write(s)

    def writelines(self, lines):
        self.fp.writelines(lines)

    def flush(self):
        self.fp.flush()

stdout_redirector = OutputRedirector(sys.stdout)
stderr_redirector = OutputRedirector(sys.stderr)


TestResult = unittest.TestResult


class _TestResult(TestResult):
    # note: _TestResult is a pure representation of results.
    # It lacks the output and reporting ability compares to unittest._
    # TextTestResult.

    def __init__(self, verbosity=1, failfast=False):
        TestResult.__init__(self)
        self.stdout0 = None
        self.stderr0 = None
        self.success_count = 0
        self.failure_count = 0
        self.error_count = 0
        self.verbosity = verbosity
        self.failfast = failfast

        # result is a list of result in 4 tuple
        # (
        #   result code (0: success; 1: fail; 2: error),
        #   TestCase object,
        #   Test output (byte string),
        #   stack trace,
        # )
        self.result = []

    def startTest(self, test):
        TestResult.startTest(self, test)
        # just one buffer for both stdout and stderr
        self.outputBuffer = StringIO.StringIO()
        stdout_redirector.fp = self.outputBuffer
        stderr_redirector.fp = self.outputBuffer
        self.stdout0 = sys.stdout
        self.stderr0 = sys.stderr
        sys.stdout = stdout_redirector
        sys.stderr = stderr_redirector

    def complete_output(self):
        """
        Disconnect output redirection and return buffer.
        Safe to call multiple times.
        """
        if self.stdout0:
            sys.stdout = self.stdout0
            sys.stderr = self.stderr0
            self.stdout0 = None
            self.stderr0 = None
        return self.outputBuffer.getvalue()

    def stopTest(self, test):
        # Usually one of addSuccess, addError or addFailure would have been
        # called. But there are some path in unittest that would bypass this.
        # We must disconnect stdout in stopTest(), which is guaranteed to be
        #called.
        self.complete_output()

    def addSuccess(self, test):
        self.success_count += 1
        TestResult.addSuccess(self, test)
        output = self.complete_output()
        self.result.append((0, test, output, ''))
        if self.verbosity > 1:
            sys.stderr.write('ok ')
            sys.stderr.write(str(test))
            sys.stderr.write('\n')
        else:
            sys.stderr.write('.')

    def addError(self, test, err):
        self.error_count += 1
        TestResult.addError(self, test, err)
        _, _exc_str = self.errors[-1]
        output = self.complete_output()
        self.result.append((2, test, output, _exc_str))
        if self.verbosity > 1:
            sys.stderr.write('E  ')
            sys.stderr.write(str(test))
            sys.stderr.write('\n')
        else:
            sys.stderr.write('E')
        if self.failfast:
            self.stop()

    def addFailure(self, test, err):
        self.failure_count += 1
        TestResult.addFailure(self, test, err)
        _, _exc_str = self.failures[-1]
        output = self.complete_output()
        self.result.append((1, test, output, _exc_str))
        if self.verbosity > 1:
            sys.stderr.write('F  ')
            sys.stderr.write(str(test))
            sys.stderr.write('\n')
        else:
            sys.stderr.write('F')
        if self.failfast:
            self.stop()


class TrytonTestRunner(object):

    STATUS = {
        0: 'pass',
        1: 'fail',
        2: 'error',
    }

    def __init__(self, stream=sys.stdout, verbosity=1, failfast=False,
            coverage=None):
        self.verbosity = verbosity
        self.failfast = failfast
        self.startTime = datetime.datetime.now()
        self.result = None
        self.coverage_result = {}
        self._coverage = coverage
        self.pyflakes_result = {}

    def upload_tryton(self, db_type, failfast, name, reviews, work):
        logger.info("Generating report for execution %s" % name)
        report = self._generate_report(self.result)
        logger.info("Report for execution %s" % name)
        get_tryton_connection()
        Test = Model.get('project.test.build')
        TestGroup = Model.get('project.test.build.group')
        Component = Model.get('project.work.component')
        TestResult = Model.get('project.test.build.result')
        ProjectWork = Model.get('project.work')

        group = TestGroup()
        group.name = name
        group.failfast = failfast
        group.reviews = reviews
        group.start = self.startTime
        group.end = self.stopTime
        group.db_type = db_type

        if work:
            work, = ProjectWork.find([('code', '=', work)])
            group.work = work
        for module in report:
            logger.info("Create Test Report for Module: %s" % module)
            result = report[module]
            component = Component.find([('name', '=', module)])
            component = component and component[0]
            if not component:
                component = Component(name=module)
                component.save()
            path = result['path']
            try:
                revision = hg_revision(module, path) or 0
                branch = get_branch(path) or 'default'
            except:
                revision = 'unknown'
                branch = 'default'
            test = Test()
            test.coverage = round(self.coverage_result.get(module,
                    (0, 0, 0))[2], 2)
            test.lines = self.coverage_result.get(module, (0, 0, 0))[0]
            test.covered_lines = self.coverage_result.get(module, (0, 0, 0))[1]
            test.component = component
            test.branch = branch
            test.revision = revision
            test.execution = datetime.datetime.now()

            for test_result in result['test']:
                tr = TestResult()
                tr.name = test_result['desc']
                tr.type = test_result['type']
                tr.description = test_result['output']
                tr.state = test_result['status']
                test.test.append(tr)

            for test_result in self.pyflakes_result.get(module, []):
                tr = TestResult()
                tr.name = test_result['name']
                tr.type = test_result['type']
                tr.description = test_result['output']
                tr.state = test_result['status']
                test.test.append(tr)
            group.builds.append(test)
        logger.info("Saving Test group: %s" % name)
        group.save()
        logger.info("Saved Test group: %s" % name)

    def coverage_report(self):
        f = StringIO.StringIO()
        self._coverage.load()
        self._coverage.report(file=f, show_missing=False)
        output = f.getvalue()

        module_name = None
        for line in output.splitlines():
            if ('trytond' in line and
                    (not module_name or 'modules/'+module_name+'/' in line)):
                item = re.split(' +', line)
                filename = item[0]
                try:
                    lines = int(item[1])
                    uncovered = int(item[2])
                except ValueError:
                    continue

                covered = lines - uncovered
                key = get_module_key(filename)
                if not key:
                    continue

                if not key in self.coverage_result:
                    self.coverage_result[key] = (0, 0)
                lines += self.coverage_result[key][0]
                covered += self.coverage_result[key][1]
                if lines == 0.0:
                    percentage = 100.0
                else:
                    percentage = 100.0 * float(covered) / float(lines)
                self.coverage_result[key] = (lines, covered, percentage)

    def runflakes(self, checker, tests=None):
        """
        Possible values for checker: pyflakes, flake8
        """
        assert checker in ('pyflakes', 'flake8')
        args = []
        type_ = 'flake'
        if checker == 'flake8':
            args = ['--ignore="E120,E121,E123,E124,E126,E127,E128,E711,W0232,'
                'R0903"']
            type_ = 'pep8'

        path = os.path.abspath(os.path.normpath(os.path.join(
                    os.path.dirname(__file__), '..', 'modules')))

        dirs = []
        modules = set()
        if tests is not None:
            modules = set([t.__module__.split('modules.')[1].split('.')[0]
                    for t in tests if 'modules.' in t.__module__])

        for f in sorted(os.listdir(path)):
            if modules and not f in modules:
                continue
            p = '%s/%s' % (path, f)
            if not os.path.isdir(p):
                continue
            dirs.append(p)
        for d in dirs:
            parameters = [checker, d] + args
            output = check_output(parameters)
            module = os.path.basename(d)
            self.pyflakes_result.setdefault(module, [])
            for error in output.split('\n'):
                if not error:
                    continue
                # Don't report import * errors on __init__ files as it is a
                # common pattern on tryton.
                if "import *' used;" in error and '__init__.py' in error:
                    continue
                # Don't report 'suite' imported but unused as it is a common
                # pattern used on tryton tests.
                if ("'suite' imported but unused" in error and
                        'tests/__init__.py' in error):
                    continue
                self.pyflakes_result[module].append({
                        'name': checker,
                        'type': type_,
                        'output': error,
                        'status': 'fail',
                        })

    def run(self, test):
        "Run the given test case or test suite."
        if self._coverage is None:
            self._coverage = coverage()
        #Start only coverage when not started
        if not self._coverage._started:
            self._coverage.start()
        result = _TestResult(self.verbosity, failfast=self.failfast)
        test(result)
        self.stopTime = datetime.datetime.now()
        self._coverage.stop()
        self._coverage.save()
        print >> sys.stderr, '\nTime Elapsed: %s' % (self.stopTime -
            self.startTime)
        self.generateReport(test, result)
        self.coverage_report()
        self.runflakes('flake8', test)
        self.runflakes('pyflakes', test)
        self.result = result
        return result

    def sortResult(self, result_list):
        # unittest does not seems to run in any particular order.
        # Here at least we want to group them together by class.
        rmap = {}
        classes = []
        for n, t, o, e in result_list:
            cls = t.__class__
            if not rmap.has_key(cls):
                rmap[cls] = []
                classes.append(cls)
            rmap[cls].append((n, t, o, e))
        r = [(cls, rmap[cls]) for cls in classes]
        return r

    def getReportAttributes(self, result):
        """
        Return report attributes as a list of (name, value).
        Override this to add custom attributes.
        """
        startTime = str(self.startTime)[:19]
        duration = str(self.stopTime - self.startTime)
        status = []
        if result.success_count: status.append('Pass %s' % result.success_count)
        if result.failure_count: status.append('Failure %s' % result.failure_count)
        if result.error_count:   status.append('Error %s'% result.error_count)
        if status:
            status = ' '.join(status)
        else:
            status = 'none'
        return [
            ('Start Time', startTime),
            ('Duration', duration),
            ('Status', status),
        ]

    def generateReport(self, test, result):
        report = self._generate_report(result)


    def _generate_report(self, result):

        report = {}
        sortedResult = self.sortResult(result.result)
        for cid, (cls, cls_results) in enumerate(sortedResult):
            # subtotal for a class
            np = nf = ne = 0
            for n,t,o,e in cls_results:
                if n == 0: np += 1
                elif n == 1: nf += 1
                else: ne += 1

            # format class description
            if cls.__module__ == "__main__":
                name = cls.__name__
            else:
                name = "%s.%s" % (cls.__module__, cls.__name__)

            if name != 'doctest.DocFileCase':
                if not 'trytond' in name:
                    continue

                module = name.split('.tests')[0]
                path = os.path.join(os.getcwd(), module.replace('.', '/'))

                if 'modules' in module:
                    module = module.split('.')[-1]
                    path = path.replace('trytond/', '')

                if not module in report:
                    report[module] = {
                        'test': [],
                        'path': path
                    }

            for tid, (n, t, o, e) in enumerate(cls_results):
                record = self._generate_report_test(report, cid, tid, n, t, o,
                    e)
                record['type'] = 'unittest'
                new_module = module
                if 'doctest.' in name:
                    new_module = str(t).split('modules/')[1].split('/')[0]
                    if not new_module in report:
                        path = str(t).split('tests/scenario')[0]
                        report[new_module] = {
                            'test': [],
                            'path': path,
                        }
                    record['type'] = 'scenario'
                    record['desc'] = record['desc']
                else:
                    record['desc'] = name + ":" + record['desc']
                report[new_module]['test'].append(record)
        return report


    def _generate_report_test(self, rows, cid, tid, n, t, o, e):
        # e.g. 'pt1.1', 'ft1.1', etc
        has_output = bool(o or e)
        tid = (n == 0 and 'p' or 'f') + 't%s.%s' % (cid+1,tid+1)
        name = t.id().split('.')[-1]
        doc = t.shortDescription() or ""
        desc = doc and ('%s: %s' % (name, doc)) or name
        # tmpl = has_output and self.REPORT_TEST_WITH_OUTPUT_TMPL or self.REPORT_TEST_NO_OUTPUT_TMPL

        # o and e should be byte string because they are collected from stdout and stderr?
        if isinstance(o,str):
            # TODO: some problem with 'string_escape': it escape \n and mess up formating
            # uo = unicode(o.encode('string_escape'))
            uo = o.decode('latin-1')
        else:
            uo = o
        if isinstance(e,str):
            # TODO: some problem with 'string_escape': it escape \n and mess up formating
            # ue = unicode(e.encode('string_escape'))
            ue = e.decode('latin-1')
        else:
            ue = e


        row = dict(
            # style = n == 2 and 'error' or (n == 1 and 'fail' or 'none'),
            desc = desc,
            output = uo+ue,
            status = self.STATUS[n],
        )

        return row



##############################################################################
# Facilities for running tests from the command line
##############################################################################

# Note: Reuse unittest.TestProgram to launch test. In the future we may
# build our own launcher to support more specific command line
# parameters like test title, CSS, etc.
class TestProgram(unittest.TestProgram):
    """
    A variation of the unittest.TestProgram. Please refer to the base
    class for command line parameters.
    """
    def runTests(self):
        # Pick HTMLTestRunner as the default test runner.
        # base class's testRunner parameter is not useful because it means
        # we have to instantiate HTMLTestRunner before we know self.verbosity.
        if self.testRunner is None:
            self.testRunner = HTMLTestRunner(verbosity=self.verbosity)
        unittest.TestProgram.runTests(self)

main = TestProgram

##############################################################################
# Executing this module from the command line
##############################################################################

if __name__ == "__main__":
    main(module=None)
