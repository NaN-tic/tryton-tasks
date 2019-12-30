#!/usr/bin/env python
import os
import ssl
import sys
import datetime
import hgapi

from invoke import run, task, Collection

from .config import get_config
from . import reviewboard
from .scm import get_branch, branches, hg_pull, hg_clone
from .utils import t
import logging
from tabulate import tabulate
# from .bucket import pullrequests
import choice


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
def fetch_review(work):

    get_tryton_connection()
    Review = Model.get('project.work.codereview')
    reviews = Review.find([('work.code', '=', work), ('state', '=', 'opened')])
    for review in reviews:
        if review.component:
            path = os.path.join('modules', review.component.name)
        else:
            path = ''

        if not os.path.exists(path):
            cl = review.url.split('/')[:-2]
            clone_url = "/".join(cl)
            hg_clone(clone_url, path, review.branch)

        hg_pull(review.component.name, path, update=True,
                branch=review.branch)


def get_request_info(url):
    rs = url.split('/')
    owner, repo, request_id = rs[-4], rs[-3], rs[-1]
    return owner, repo, request_id


def show_review(review):
    print "{id} - {name} - {url}".format(
            id=review.id, name=review.name, url=review.url)


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
    output = run('psql -d %s -c "select name from ir_module_module'
        ' where state=\'installed\'"' % database, hide='both')
    modules = [x.strip() for x in output.stdout.split('\n')]
    branches(None, modules)



@task()
def decline_review(work, review_id=None, message=None):
    get_tryton_connection()
    Review = Model.get('project.work.codereview')
    Task = Model.get('project.work')

    tasks = Task.find([('code', '=', work)])
    if not tasks:
        print >>sys.stderr, t.red('Error: Task %s was not found.' % work)
        sys.exit(1)

    w = tasks[0]
    reviews = Review.find([('work', '=', w.id), ('state', '=', 'opened')])

    for review in reviews:
        if review_id and str(review.id) != review_id:
            print review_id, review.id
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


@task()
def merge_review(work, review_id=None, message=None):
    get_tryton_connection()
    Review = Model.get('project.work.codereview')
    Task = Model.get('project.work')

    tasks = Task.find([('code', '=', work)])
    if not tasks:
        print >>sys.stderr, t.red('Error: Task %s was not found.' % work)
        sys.exit(1)

    w = tasks[0]
    reviews = Review.find([('work', '=', w.id), ('state', '=', 'opened')])

    for review in reviews:
        if review_id and str(review.id) != review_id:
            print review_id, review.id
            continue

        show_review(review)

        if not review_id:
            continue

        confirm = choice.Binary('Are you sure you want to merge?', False).ask()
        if confirm:
            owner, repo, request_id = get_request_info(review.url)
            res = pullrequests.merge(owner, repo, request_id, message)
            if res and res['state'] == 'MERGED':
                review.state = 'closed'
                review.save()


@task()
def upload_review(work, path, branch='default'):
    get_tryton_connection()
    Review = Model.get('project.work.codereview')
    Task = Model.get('project.work')
    Component = Model.get('project.work.component')

    tasks = Task.find([('code', '=', work)])
    if not tasks:
        print >>sys.stderr, t.red('Error: Task %s was not found.' % work)
        sys.exit(1)
    work = tasks[0]

    module = os.path.realpath(path).split('/')[-1]
    components = Component.find([('name', '=', module)])
    if not components:
        component = Component(name=module)
        component.save()
    else:
        component = components[0]

    repo = gitapi.Repo(path)
    url = repo.config('paths', 'default')
    url_list = url.split('/')
    owner, repo_name = (url_list[-2], url_list[-1])

    review = reviewboard.create(path, work.rec_name,
            (work.problem or '') + '\n' + (work.solution or ''), work.code)

    review_id = review

    review = Review.find([
            ('review_id', '=', str(review_id)),
            ('work', '=', work.id),
            ])
    if not review:
        review = Review()
    else:
        review = review[0]

    review.name = "[{module}]-{task_name}".format(
            module=module, task_name=work.rec_name.encode('utf-8'))
    review.review_id = str(review_id)
    review.url = ('http://reviews.nan-tic.com/r/{id}').format(
            owner=owner,
            repo=repo_name,
            id=review_id)

    review.work = work
    review.branch = branch
    review.component = component
    review.save()


ProjectCollection = Collection()
ProjectCollection.add_task(ct)
ProjectCollection.add_task(components)
ProjectCollection.add_task(check_migration)
ProjectCollection.add_task(upload_review)
# ProjectCollection.add_task(merge_review)
# ProjectCollection.add_task(fetch_review)
