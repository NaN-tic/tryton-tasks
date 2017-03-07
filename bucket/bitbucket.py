#!/usr/bin/env python
from invoke import Collection

from .pullrequests import PullRequestCollection
from .repository import RepoCollection


BitbucketCollection = Collection()
BitbucketCollection.add_collection(PullRequestCollection, 'request')
BitbucketCollection.add_collection(RepoCollection, 'repo')
