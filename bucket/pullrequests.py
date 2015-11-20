#!/usr/bin/env python
from invoke import task, Collection
from .util import post, get, prettyprint, config


@task()
def create(owner, repo, src, title, dest='default', description='',
        reviewers=None, debug=True):

    url = ('https://api.bitbucket.org/2.0/repositories/{owner}/{repo}/'
        'pullrequests').format(owner=owner, repo=repo)

    data = {}
    data['title'] = title
    data['source'] = {'branch': {'name': src}}
    data['close_source_branch'] = True
    data['description'] = description

    if reviewers:
        reviewers = reviewers.split(',')
    reviewers = reviewers or config.get('default_reviewers')
    data['reviewers'] = []

    for reviewer in reviewers:
        data['reviewers'].append({'username': reviewer})

    res = post(url, data)

    if debug:
        prettyprint(res)

    msg = ("\npullrequests {id}, title: {title} "
           " created: {created_on} "
           " updated: {updated_on} "
           " state: {state} ").format(
                id=res['id'],
                title=res['title'],
                created_on=res['created_on'],
                updated_on=res['updated_on'],
                state=res['state'],
            )
    print msg
    return res


def _list(owner, repo):

    url = ('https://api.bitbucket.org/2.0/repositories/{owner}/{repo}/'
        'pullrequests').format(owner=owner, repo=repo)

    url += "?state=[OPEN,MERGED,DECLINED]"
    data = {}
    res = get(url, data)
    prettyprint(res['values'])


@task
def show(owner, repo):
    return _list(owner, repo)


@task()
def merge(owner, repo, pullrequest_id, message):

    url = ('https://api.bitbucket.org/2.0/repositories/{owner}/{repo}/'
        'pullrequests/{pull_request_id}/merge').format(
            owner=owner, repo=repo, pull_request_id=pullrequest_id)
    data = {}
    if message:
        data['message'] = message
    res = post(url, data)
    prettyprint(res)


@task()
def decline(owner, repo, pull_request_id, message):
    url = ('https://api.bitbucket.org/2.0/repositories/{owner}/{repo}/'
        'pullrequests/{pull_request_id}/decline').format(
            owner=owner, repo=repo, pull_request_id=pull_request_id)
    data = {}
    if message:
        data['message'] = message
    res = post(url, data)
    prettyprint(res)


PullRequestCollection = Collection()
PullRequestCollection.add_task(show)
PullRequestCollection.add_task(create)
PullRequestCollection.add_task(merge)
PullRequestCollection.add_task(decline)
