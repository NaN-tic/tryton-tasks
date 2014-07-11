#!/usr/bin/env python
from invoke import task, run, Collection
import scm
import utils
import project

# from .scm import prefetch, fetch, get_repo, remove_dir,
#      hg_clone, git_clone
# from .utils import read_config_file


@task()
def test(coverage=False, flakes=False, fail_fast=True, dbtype='sqlite',
         mail=False, module=None):

    cmd = ['./test.py']
    if coverage:
        cmd.append('--coverage')
    if flakes:
        cmd.append('--flakes')
    if fail_fast:
        cmd.append('--fail-fast')
    cmd.append('--db-type %s' % dbtype)
    if mail:
        cmd.append('--mail')

    run(" ".join(cmd), echo=True)


@task
def runall(test_file, branch='default'):
    setup(branch, development=False)
    runtests(test_file, branch, development=False, include_reviews=False)
    runtests(test_file, branch, development=False, include_reviews=True)
    setup(branch, development=True)
    runtests(test_file, branch, development=True, include_reviews=False)
    runtests(test_file, branch, development=True, include_reviews=True)


@task
def runtests(test_file=None, branch='default', development=False,
        include_reviews=False):

    sections = []
    if test_file:
        config = utils.read_config_file(test_file)
        sections = config.sections()

    coverage = True
    flakes = True
    fail_fast = True
    mail = True

    if include_reviews:
        project.fetch_reviews(branch, exclude_components=config.sections())

    test(False, False, fail_fast, 'sqlite', mail)
    test(coverage, flakes, fail_fast, 'postgresql', mail)

    for section in sections:
        repo = utils.get_repo(section, config, 'clone', development)
        if repo['branch'] != branch:
            continue
        func = eval('scm.%s', repo['function'])
        func(repo['url'], repo['path'], repo['branch'], repo['revision'])
        if include_reviews:
            project.fetch_reviews(component=section)
        test(False, False, fail_fast, 'sqlite', mail, section)
        test(coverage, flakes, fail_fast, 'postgresql', mail, section)
        utils.remove_dir(repo['path'], quiet=True)

    clean()


@task()
def clean():
    scm.prefetch()


@task()
def setup(branch='default', development=False):
    clean()
    scm.branch(branch, clean=True)
    clean()
    scm.fetch()


TestCollection = Collection()
TestCollection.add_task(test)
TestCollection.add_task(clean)
TestCollection.add_task(setup)
TestCollection.add_task(runtests)
