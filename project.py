#!/usr/bin/env python
import os
import sys
from invoke import task
from .config import get_config
import reviewboard

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
def list(party=None, user=None):
    get_tryton_connection()

    Project = Model.get('project.work')
    domain = [('state', '=', 'opened')]

    if party:
        domain.append(('party.name', 'like', party))
    if user:
        domain.append(('assigned_employees', 'like', user))

    projects = Project.find(domain)
    for project in projects:
        print "(%s) %s - (%s) %s [%s]" %(
            project.assigned_employees,
            project.rec_name,
            project.effort,
            project.task_phase.name,
            project.party.rec_name)


@task
def review(task, path, branch, review=None):
    get_tryton_connection()
    Review = Model.get('project.work.codereview')
    Task = Model.get('project.work')
    Component = Model.get('project.work.component')
    module = path.split('/')[-1]
    component = Component.find([('name', '=', module)])
    tasks = Task.find( [('code', '=', task)])
    t = tasks and tasks[0]
    review_id = reviewboard.create(path, t.rec_name,
        t.comment, t.id, review)['id']

    review = Review()
    review.name = t.rec_name
    review.url = 'http://git.nan-tic.com/reviews/r/%s'%review_id
    review.work = t
    review.branch = branch
    review.component = component and component[0]
    review.save()
