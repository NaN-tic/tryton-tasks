#!/usr/bin/env python
import os
import ssl
import sys
import hgapi

from invoke import run, task, Collection

from .config import get_config
from .scm import hg_pull, hg_clone, _module_version
from .utils import t
import logging
# from .bucket import pullrequests
import choice


try:
    from proteus import config as pconfig, Model
except ImportError as e:
    print("trytond importation error: ", e, file=sys.stderr)

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


def get_request_info(url):
    rs = url.split('/')
    owner, repo, request_id = rs[-4], rs[-3], rs[-1]
    return owner, repo, request_id


def show_review(review):
    print("{id} - {name} - {url}".format(
            id=review.id, name=review.name, url=review.url))


@task()
def components(ctx, database):
    get_tryton_connection()

    DBComponent = Model.get('nantic.database.component')

    components = DBComponent.find([('database.name', '=', database),
            ('state', '=', 'accepted')])

    for component in components:
        print(component.component.name)


@task()
def check_migration(ctx, database, version=3.4):

    module_table = 'ir_module'
    if version == 3.4:
        module_table = 'ir_module_module'

    output = run('psql -A -d %s -c "select name from %s'
        ' where state=\'installed\'"' % (database, module_table), hide='both')
    modules = [x.strip() for x in output.stdout.split('\n')]
    _module_version(modules[1:-1])



@task()
def decline_review(ctx, work, review_id=None, message=None):
    get_tryton_connection()
    Review = Model.get('project.work.codereview')
    Task = Model.get('project.work')

    tasks = Task.find([('code', '=', work)])
    if not tasks:
        print(t.red('Error: Task %s was not found.' % work), file=sys.stderr)
        sys.exit(1)

    w = tasks[0]
    reviews = Review.find([('work', '=', w.id), ('state', '=', 'opened')])

    for review in reviews:
        if review_id and str(review.id) != review_id:
            print(review_id, review.id)
            continue

        show_review(review)

        if not review_id:
            continue

        confirm = choice.Binary('Are you sure you want to decline?',
            False).ask()
        if confirm:
            owner, repo, request_id = get_request_info(review.url)
            res = pullrequests.decline(owner, repo, request_id, message)
            if res and res['state'] == 'MERGED':
                review.state = 'closed'
                review.save()

ProjectCollection = Collection()
ProjectCollection.add_task(ct)
ProjectCollection.add_task(components)
ProjectCollection.add_task(check_migration)
