#!/usr/bin/env python
import os
import sys
from invoke import task, Collection
from .config import get_config
import reviewboard
from scm import get_branch
from .utils import t

try:
    from proteus import config as pconfig, Model
except ImportError, e:
    print >> sys.stderr, "trytond importation error: ", e

os.environ['TZ'] = "Europe/Madrid"
settings = get_config()


def get_tryton_connection():
    tryton = settings['tryton']
    return pconfig.set_xmlrpc(tryton['server'])


@task
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


@task
def close_review(task):
    get_tryton_connection()
    Review = Model.get('project.work.codereview')
    reviews = Review.find([('work.code', '=', task)])
    for review in reviews:
        reviewboard.close(review.review_id)


@task
def fetch_review(task):
    get_tryton_connection()
    Review = Model.get('project.work.codereview')
    reviews = Review.find([('work.code', '=', task), ('state', '=', 'opened')])
    for review in reviews:
        if review.component:
            path = os.path.join('modules', review.component.name)
        else:
            path = ''
        reviewboard.fetch(path, review.review_id)


@task
def upload_review(task, path, review=None):
    get_tryton_connection()
    Review = Model.get('project.work.codereview')
    Task = Model.get('project.work')
    Component = Model.get('project.work.component')
    module = path.split('/')[-1]
    tasks = Task.find([('code', '=', task)])
    if not tasks:
        print >>sys.stderr, t.red('Error: Task %s was not found.' % task)
        sys.exit(1)
    task = tasks[0]
    components = Component.find([('name', '=', module)])
    if not components:
        component = Component(name=module)
        component.save()
    else:
        component = components[0]
    review_id = reviewboard.create(path, task.rec_name,
        task.comment, task.code, review)

    review = Review.find([('review_id', '=', str(review_id))])
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


ProjectCollection = Collection()
ProjectCollection.add_task(upload_review)
ProjectCollection.add_task(fetch_review)
ProjectCollection.add_task(close_review)
ProjectCollection.add_task(tasks)
