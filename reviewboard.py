#!/usr/bin/env python

from invoke import task, run
from .scm import module_diff
from .config import get_config
import ConfigParser
import os
import tempfile


try:
    from rbtools.api.client import RBClient
except:
    pass

def review_file(review_id):
    pass

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


@task
def create(module, summary, description, bug, review=None):
    """
        Create  or update review
    """
    diff, base_diff = module_diff(module, show=False)
    root = get_root()
    if review:
        review_request = root.get_review_request(review_request_id=review)
    else:
        review_request = root.get_review_requests().create(
            repository=get_repository())
    review_request.get_diffs().upload_diff(diff.encode('utf-8'),
        base_diff.encode('utf-8'))
    draft = review_request.get_draft()
    draft.update(
        summary=summary.encode('utf-8'),
        description=description.encode('utf-8'),
        bugs_closed=bug,
        )
    user = root.get_session().get_user()
    draft = draft.update(target_people=user.username)
    draft.update(public=True)
    return draft


@task
def list():
    """
    List your reviews in Review Board
    """
    root = get_root()
    requests = root.get_review_requests()
    for request in requests:
        print "%(id)s - %(summary)s Updated:%(last_updated)s" % request
        for bug in request['bugs_closed']:
            print "Bug: %s" % bug
        print "%(description)s\n" % request

def request_by_bug(bug):
    root = get_root()
    requests = root.get_review_requests()
    res = []
    for request in requests:
        if bug in request['bugs_closed']:
            res.append(request)
    return res

def request_by_id(review_id):
    root = get_root()
    review_request = root.get_review_request(review_request_id=review_id)
    return [review_request]

def get_requests(bug=None, review=None):
    requests = []
    if bug:
        requests = request_by_bug(bug)
    if review:
        requests += request_by_id(review)

    return requests


@task
def fetch(module, bug=None, review=None):
    """
        Download and apply patch.
    """

    requests = requests(bug, review)

    for request in requests:
        diffs = request.get_diffs()
        diff_revision = diffs.total_results
        diff = diffs.get_item(diff_revision)
        diff_body = diff.get_patch().data
        tmp_patch_file = make_tempfile(diff_body)
        run('cd %s; patch -p1 -m < %s' %(module, tmp_patch_file))


@task
def close(bug=None, review=None, close_type='submitted'):
    """ @type submitted | discarded """

    requests = get_requests(bug, review)
    for request in requests:
        request = request.update(status=close_type)

