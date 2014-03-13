#!/usr/bin/env python

from invoke import task, run
from .scm import module_diff
from .config import get_config
import ConfigParser


try:
    from rbtools.api.client import RBClient
except:
    pass


def get_root():
    settings =  get_config()
    review = settings['reviewboard']
    client = RBClient(review['server'])
    client.login(review['user'], review['password'])
    return client.get_root()

def get_repository():
    root = get_root()
    repository = root.get_repositories()[-1].id
    return repository

@task
def review(module, summary, description, bug, review=None):
    diff, base_diff = module_diff(module)
    root = get_root()
    if review:
        review_request = root.get_review_request(review_request_id=review)
    else:
        review_request = root.get_review_requests().create(
            repository=get_repository())
    review_request.get_diffs().upload_diff(diff, base_diff)
    draft = review_request.get_draft()
    draft.update(
        summary=summary,
        description=description,
        bugs_closed=bug,
        )
    user = root.get_session().get_user()
    draft = draft.update(target_people=user.username)
    draft.update(public=True)

def
