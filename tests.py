#!/usr/bin/env python
from invoke import task, run, Collection
import tempfile
import scm
import utils
import project

# from .scm import prefetch, fetch, get_repo, remove_dir,
#      hg_clone, git_clone
# from .utils import read_config_file


@task()
def test(output=None, coverage=False, flakes=False,
        fail_fast=True, dbtype='sqlite', mail=False, module=None):

    cmd = ['python','test.py']
    if output:
        cmd += ['--output', output]

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
def runall(test_file, output, branch='default', exclude_stable=False,
        exclude_development=False, exclude_reviews=False):
    if not exclude_stable:
        print "Setup & testing stable revision of branch: %s " % branch
        setup(branch, development=False)
        runtests(test_file, output, branch, development=False,
            include_reviews=False)
        if not exclude_reviews:
            runtests(test_file, output, branch, development=False,
                include_reviews=True)
    if not exclude_development:
        print "Setup & testing development revision of branch: %s " % branch
        setup(branch, development=True)
        runtests(test_file, output, branch, development=True,
            include_reviews=False)
        if not exclude_reviews:
            runtests(test_file, output, branch, development=True,
                include_reviews=True)


@task
def runtests(test_file=None, output=None, branch='default', development=False,
        include_reviews=False):

    directory = tempfile.mkdtemp()
    run("cp . %s -R" % directory)
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

    test(output, False, False, fail_fast, 'sqlite', mail)
    test(output, coverage, flakes, fail_fast, 'postgresql', mail)

    for section in sections:
        repo = utils.get_repo(section, config, 'clone', development)
        if repo['branch'] != branch:
            continue
        func = eval('scm.%s', repo['function'])
        func(repo['url'], repo['path'], repo['branch'], repo['revision'])
        if include_reviews:
            project.fetch_reviews(component=section)
        test(output, False, False, fail_fast, 'sqlite', mail, section)
        test(output, coverage, flakes, fail_fast, 'postgresql', mail, section)
        utils.remove_dir(repo['path'], quiet=True)

    run("rm -Rf %s" % directory)


@task()
def clean(force=True):
    scm.prefetch(force=force)


@task()
def setup(branch='default', development=False, force=True):
    scm.branch(branch, clean=force)
    scm.fetch()


TestCollection = Collection()
TestCollection.add_task(test)
TestCollection.add_task(clean)
TestCollection.add_task(setup)
TestCollection.add_task(runtests)
TestCollection.add_task(runall)


