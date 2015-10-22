#!/usr/bin/env python
import os
import ssl
import sys
import datetime

from invoke import run, task, Collection

from .config import get_config
from . import reviewboard
from .scm import get_branch, branches
from .utils import t
import logging
from tabulate import tabulate

try:
    from proteus import config as pconfig, Model
except ImportError, e:
    print >> sys.stderr, "trytond importation error: ", e

os.environ['TZ'] = "Europe/Madrid"
settings = get_config()

logger = logging.getLogger("nan-tasks")


def get_tryton_connection():
    tryton = settings['tryton']
    try:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return pconfig.set_xmlrpc(tryton['server'], context=ssl_context)
    except AttributeError:
        # If python is older than 2.7.9 it doesn't have
        # ssl.create_default_context() but it neither verify certificates
        return pconfig.set_xmlrpc(tryton['server'])


@task
def ct(log_file):
    get_tryton_connection()
    create_test_task(log_file)


def create_test_task(log_file):

    get_tryton_connection()
    settings = get_config()
    tryton = settings['tryton']

    Project = Model.get('project.work')
    Employee = Model.get('company.employee')
    Party = Model.get('party.party')
    Tracker = Model.get('project.work.tracker')
    employee = Employee(int(tryton.get('default_employee_id')))
    parent = Project(int(tryton.get('default_project_id')))
    party = Party(int(tryton.get('default_party_id')))
    tracker = Tracker(int(tryton.get('default_tracker_id')))

    f = open(log_file, 'r')
    lines = []
    for line in f.readlines():
        if 'init' in line or 'modules' in line:
            continue
        lines.append(line)
    f.close()

    work = Project()
    work.type = 'task'
    work.product = None
    work.timesheet_work_name = 'Test Exception'
    work.parent = parent
    work.tracker = tracker
    work.party = party
    work.problem = "\n".join(lines)
    work.assigned_employee = employee
    work.save()


@task()
def tasks(party=None, user=None):
    get_tryton_connection()

    Project = Model.get('project.work')
    domain = [('state', '=', 'opened')]

    if party:
        domain.append(('party.name', 'ilike', "%" + party + "%"))
    if user:
        domain.append(('assigned_employee', 'ilike', "%" + user + "%"))

    projects = Project.find(domain)
    for project in projects:
        print "(%s) %s - (%s) %s [%s]" % (
            project.assigned_employee and project.assigned_employee.rec_name,
            project.rec_name,
            project.effort,
            project.task_phase.name,
            project.party.rec_name)


@task()
def close_review(work):
    get_tryton_connection()
    Review = Model.get('project.work.codereview')
    reviews = Review.find([('work.code', '=', work)])
    for review in reviews:
        reviewboard.close(review.review_id)

@task()
def fetch_reviews(branch='default', component=None, exclude_components=None):
    _fetch_reviews(branch, component, exclude_components)


def _fetch_reviews(branch='default', component=None, exclude_components=None):
    get_tryton_connection()
    Review = Model.get('project.work.codereview')
    reviews = Review.find([
            ('state', '=', 'opened'),
            ('branch', '=', branch),
            ])
    if not exclude_components:
        exclude_components = []
    for review in reviews:
        if component and review.component and \
                review.component.name != component:
            continue
        if review.component and review.component.name in exclude_components:
            continue
        if review.component:
            path = os.path.join('modules', review.component.name)
        else:
            path = ''
        try:
            print "fetch review:", path, review.review_id
            reviewboard.fetch(path, review.review_id)
            reviewboard.create_review_file(path, review.review_id)
        except:
            print "Exception"
            logger.exception("Exception has occured", exc_info=1)


@task()
def fetch_review(work):
    import traceback
    get_tryton_connection()
    Review = Model.get('project.work.codereview')
    reviews = Review.find([('work.code', '=', work), ('state', '=', 'opened')])
    for review in reviews:
        if review.component:
            path = os.path.join('modules', review.component.name)
        else:
            path = ''
        if not os.path.exists(path):
            os.makedirs(path)

        try:
            print "fetch review:", path, review.review_id
            reviewboard.fetch(path, review.review_id)
            reviewboard.create_review_file(path, review.review_id)
        except:
            # exc_type, exc_value, exc_traceback = sys.exc_info()
         #   traceback.print_exc()
            logger.exception("Exception has occured", exc_info=1)



@task()
def upload_review(work, path, review=None, new=False):
    get_tryton_connection()
    Review = Model.get('project.work.codereview')
    Task = Model.get('project.work')
    Component = Model.get('project.work.component')

    tasks = Task.find([('code', '=', work)])
    if not tasks:
        print >>sys.stderr, t.red('Error: Task %s was not found.' % work)
        sys.exit(1)
    task = tasks[0]

    module = path.split('/')[-1]
    components = Component.find([('name', '=', module)])
    if not components:
        component = Component(name=module)
        component.save()
    else:
        component = components[0]

    review_file = os.path.join(path, '.review.cfg')
    if new and os.path.exists(review_file):
        os.remove(review_file)

    review_id = reviewboard.create(path, task.rec_name,
        task.comment, task.code, review)

    review = Review.find([
            ('review_id', '=', str(review_id)),
            ('work', '=', task.id),
            ])
    if not review:
        review = Review()
    else:
        review = review[0]

    review.name = task.rec_name + "(" + module + ")"
    review.review_id = str(review_id)
    review.url = 'http://git.nan-tic.com/reviews/r/%s' % review_id
    review.work = task
    review.branch = get_branch(path)
    review.component = component
    review.save()


def work_report(date):
    get_tryton_connection()

    Timesheet = Model.get('timesheet.line')

    lines = Timesheet.find([('date', '=', date)])
    result = {}
    for line in lines:
        if not result.get(line.employee.rec_name):
            result[line.employee.rec_name] = {}
        work_name = line.project_work.rec_name
        if not result[line.employee.rec_name].get(work_name):
            if not line.hours:
                work_name = '* ' + work_name

            result[line.employee.rec_name][work_name] = {
                'hours': line.hours,
                'tracker': line.project_work.tracker.rec_name,
                'state': line.project_work.state,
                'phase': line.project_work.task_phase.rec_name,
            }
        else:
            result[line.employee.rec_name][work_name]['hours'] += line.hours

    for employee, tasks in result.iteritems():
        print "\nemployee:", employee
        table = []
        for work, val in tasks.iteritems():
            table += [[work] + val.values()]

        print tabulate(table)

@task()
def working(date=None):
    if date is None:
        date = datetime.date.today()
    work_report(date)


@task()
def components(database):
    get_tryton_connection()

    DBComponent = Model.get('nantic.database.component')

    components = DBComponent.find([('database.name', '=', database),
            ('state', '=', 'accepted')])

    for component in components:
        print component.component.name


@task()
def check_migration(database):
    output = run('psql -d %s -c "select name from ir_module_module where state=\'installed\'"' % database, hide='both')
    modules = [x.strip() for x in output.stdout.split('\n')]
    branches(None, modules)



ProjectCollection = Collection()
ProjectCollection.add_task(upload_review)
ProjectCollection.add_task(fetch_review)
ProjectCollection.add_task(close_review)
ProjectCollection.add_task(tasks)
ProjectCollection.add_task(ct)
ProjectCollection.add_task(working)
ProjectCollection.add_task(components)
ProjectCollection.add_task(check_migration)
