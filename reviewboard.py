#!/usr/bin/env python

from invoke import task, run
from .scm import module_diff


def get_repository():
    from rbtools.api.client import RBClient
    client = RBClient('http://git.nan-tic.com/reviews/', user='angel',
        password='')
    root = client.get_root()
    repository = root.get_repositories()[-1].id

@task
def upload_diff(review=None):
    diff, base_diff = module_diff('tasks')
    review_request = root.get_review_requests().create(
        repository=get_repository())
    review_request.get_diffs().upload_diff(diff, base_diff)
    draft = review_request.get_draft()
    draft.update(
        summary='prova',
        description='prova',
        )
    user = root.get_session().get_user()
    draft = draft.update(target_people=user.username)
    draft.update(public=True)
