#!/usr/bin/env python

import configparser
import os
import tempfile
import choice

from invoke import task, run, Collection
try:
    from rbtools.api.client import RBClient
except:
    pass

from .scm import module_diff
from .config import get_config


def review_file(module):
    cfg = os.path.join(module, ".review.cfg")
    if not os.path.exists(cfg):
        return None

    Config = configparser.ConfigParser()
    cfg_file = open(cfg)
    Config.readfp(cfg_file)
    cfg_file.close()
    return Config.getint('Review', 'id')


def create_review_file(module, review_id):
    cfg = os.path.join(module, ".review.cfg")
    cfg_file = open(cfg, 'w+')
    Config = configparser.ConfigParser()
    Config.readfp(cfg_file)
    Config.add_section('Review')
    Config.set('Review', 'id', str(review_id))
    Config.write(cfg_file)
    cfg_file.close()


def make_tempfile(content=None):
    """
    Creates a temporary file and returns the path. The path is stored
    in an array for later cleanup.
    """
    fd, tmpfile = tempfile.mkstemp()

    if content:
        os.write(fd, content)
    os.close(fd)
    return tmpfile


def get_root():
    settings = get_config()
    review = settings['reviewboard']
    client = RBClient(review['server'])
    client.login(review['user'], review['password'])

    return client.get_root()


def get_repository():
    root = get_root()
    repository = root.get_repositories()[-1].id
    return repository


@task()
def create(module, summary, description, bug, group='NaN'):
    """
        Create  or update review
    """
    diff, base_diff = module_diff(module, show=False, addremove=True)
    root = get_root()
    review_id = review_file(module)

    if review_id:
        upgrade_review = choice.Binary('Do you like upgrade the review '
            '%s (%s)?' % (review_id, module), True).ask()
        if not upgrade_review:
            review_id = None

    if review_id is None:
        review_request = root.get_review_requests().create(
            repository=get_repository())
        create_review_file(module, review_request.id)
    else:
        review_request = root.get_review_request(
            review_request_id=review_file(module))

    review_request.get_diffs().upload_diff(diff.encode('utf-8'),
        base_diff.encode('utf-8'))
    draft = review_request.get_draft()
    review_description = description or summary or ''
    draft.update(
        summary=summary.encode('utf-8'),
        description=review_description.encode('utf-8'),
        bugs_closed=bug,
        )
    user = root.get_session().get_user()
    draft = draft.update(target_people=user.username, target_groups=group)
    draft.update(public=True)
    return review_request['id']


@task()
def reviews():
    """
    List your reviews in Review Board
    """
    root = get_root()
    requests = root.get_review_requests()
    for request in requests:
        print("%(id)s - %(summary)s Updated:%(last_updated)s" % request)
        for bug in request['bugs_closed']:
            print("Bug: %s" % bug)
        print("%(description)s\n" % request)


def request_by_id(review_id):
    root = get_root()
    review_request = root.get_review_request(review_request_id=review_id)
    return [review_request]


@task()
def fetch(module, review):
    """
        Download and apply patch.
    """
    requests = request_by_id(review)
    for request in requests:
        diffs = request.get_diffs()
        diff_revision = diffs.total_results
        diff = diffs.get_item(diff_revision)
        diff_body = diff.get_patch().data
        tmp_patch_file = make_tempfile(diff_body)
        if not os.path.exists(module):
            run('mkdir %s' % module)
        run('cd %s; patch -p1 -m < %s' % (module, tmp_patch_file), echo=True)


@task()
def close_all():
    root = get_root()
    requests = root.get_review_requests()
    for request in requests:
        request = request.update(status='discarded')


@task()
def close(review=None, close_type='submitted'):
    """ @type submitted | discarded """

    request, = request_by_id(review)
    request = request.update(status=close_type)


ReviewCollection = Collection()
ReviewCollection.add_task(close)
ReviewCollection.add_task(close_all)
ReviewCollection.add_task(fetch)
ReviewCollection.add_task(reviews)
ReviewCollection.add_task(create)
