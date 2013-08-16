import os
from bitbucket import BitBucket
from invoke import task, run
import hgapi
from blessings import Terminal
import ConfigParser

Config = ConfigParser.ConfigParser()

def sessionBB():
    home_dir = os.getenv("HOME")
    filerc = os.path.join(home_dir, '.bitbucketrc')

    if not os.path.exists(filerc):
        return None

    Config.readfp(open(filerc))
    username = Config.get('bitbucket','username')
    password = Config.get('bitbucket','password')
    bb = Bitbucket(username, password)
    return bb

@task
def create(name, owner, description):
    bb = sessionBB()
    repo = bb.repository.create(name, scm='hg')

