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


ProjectCollection = Collection()
ProjectCollection.add_task(ct)
ProjectCollection.add_task(components)
ProjectCollection.add_task(check_migration)
