#!/usr/bin/env python
from invoke import Collection

from .pullrequests import PullRequestCollection
from .repository import RepoCollection


BitbucketCollection = Collection()
BitbucketCollection.add_collection(PullRequestCollection, 'request')
BitbucketCollection.add_collection(RepoCollection, 'repo')

# BitbucketCollection.add_task(create)
# # BitbucketCollection.add_task(delete)
# BitbucketCollection.add_task(repos)
# BitbucketCollection.add_task(detail)

# BitbucketRequestsCollection = Collection()
# BitbucketRequestsCollection.add_task(create_pull_request, 'create')

