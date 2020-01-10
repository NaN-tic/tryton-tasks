#!/usr/bin/env python
from invoke import Collection, task, run
from datetime import date
import hgapi
import git
import os
import sys
from blessings import Terminal
from multiprocessing import Process
from multiprocessing import Pool
from path import Path
import shutil
from collections import OrderedDict

import patches
from .utils import t, _ask_ok, read_config_file, execBashCommand, \
    remove_dir, NO_MODULE_REPOS

MAX_PROCESSES = 25

DEFAULT_BRANCH = {
    'git': 'master',
    'hg': 'default'
    }

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARN = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = "\033[1m"


def get_url(url):
    if not 'SSH_AUTH_SOCK' in os.environ:
        if url.startswith('ssh'):
            url = 'https' + url[3:]
    return url

def get_repo(section, config, function=None, development=False):
    repository = {}
    repository['name'] = section
    repository['type'] = config.get(section, 'repo')
    repository['url'] = config.get(section, 'url')
    repository['path'] = os.path.join(config.get(section, 'path'), section)
    repository['branch'] = (config.get(section, 'branch')
        if config.has_option(section, 'branch')
        else DEFAULT_BRANCH[repository['type']])
    repository['revision'] = (config.get(section, 'revision')
        if not development and config.has_option(section, 'revision')
        else None)
    repository['pypi'] = (config.get(section, 'pypi')
        if config.has_option(section, 'pypi') else None)
    repository['function'] = None
    if function and not (function == 'update' and repository['type'] == 'git'):
        repository['function'] = eval("%s_%s" % (repository['type'], function))
    return repository


@task()
def close_branch(directory, branch):
    """ Close branch for all modules """

    for module_path in Path(directory).dirs():
        repo = hgapi.Repo(module_path)

        branches = []
        try:
            branches = [x['name'] for x in repo.get_branches() if x]
        except:
            continue

        if branch in branches:
            print module_path
            repo.hg_update(branch, True)
            repo.hg_commit('close branch', close_branch=True)


@task()
def unknown(unstable=True, status=False, show=True, remove=False, quiet=False):
    """
    Return a list of modules/repositories that exists in filesystem but not in
    config files
    ;param status: show status for unknown repositories.
    """
    Config = read_config_file(unstable=unstable)
    configs_module_list = [section for section in Config.sections()
        if section not in NO_MODULE_REPOS]

    modules_wo_repo = []
    repo_not_in_cfg = []
    for module_path in Path('./modules').dirs():
        module_name = module_path.basename()
        if module_name in configs_module_list:
            continue

        if (module_path.joinpath('.hg').isdir() or
                module_path.joinpath('.git').isdir()):
            repo_not_in_cfg.append(module_name)
            if status and module_path.joinpath('.hg').isdir():
                hg_status(module_name, module_path.parent, False, None)
            elif status and module_path.joinpath('.git').isdir():
                git_status(module_name, module_path.parent, False, None)
        else:
            modules_wo_repo.append(module_name)

    if show:
        if modules_wo_repo:
            print t.bold("Unknown module (without repository):")
            print "  - " + "\n  - ".join(modules_wo_repo)
            print ""
        if not status and repo_not_in_cfg:
            print t.bold("Unknown repository:")
            print "  - " + "\n  - ".join(repo_not_in_cfg)
            print ""

    if remove:
        for repo in modules_wo_repo + repo_not_in_cfg:
            path = os.path.join('./modules', repo)
            remove_dir(path, quiet)

    return modules_wo_repo, repo_not_in_cfg


def wait_processes(processes, maximum=MAX_PROCESSES, exit_code=None):
    i = 0
    while len(processes) > maximum:
        if i >= len(processes):
            i = 0
        p = processes[i]
        p.join(0.1)
        if p.is_alive():
            i += 1
        else:
            if exit_code is not None:
                exit_code.append(processes[i].exitcode)
            del processes[i]


def check_revision(client, module, revision, branch):
    if client.revision(revision).branch != branch:
        print t.bold_red('[' + module + ']')
        print ("Invalid revision '%s': it isn't in branch '%s'"
            % (revision, branch))
        return -1
    return 0


def git_clone(url, path, branch="master", revision="master"):
    repo = git.Repo.clone_from(url, path, branch=branch)
    print "Repo " + t.bold(path) + t.green(" Cloned")
    return 0


def hg_clone(url, path, branch="default", revision=None):
    url = get_url(url)
    extended_args = ['--pull']
    revision = revision or branch
    if revision:
        extended_args.append('-u')
        extended_args.append(revision)
    try:
        client = hgapi.hg_clone(url, path, *extended_args)
        res = check_revision(client, path, revision, branch)
    except hgapi.HgException, e:
        print t.bold_red('[' + path + ']')
        print "Error running %s: %s" % (e.exit_code, str(e))
        return -1
    except:
        return -1

    print "Repo " + t.bold(path) + t.green(" Updated") + \
        " to Revision:" + revision
    return res


def _clone(repo):
    return repo['function'](repo['url'], repo['path'],
        branch=repo['branch'], revision=repo['revision'])

@task()
def clone(config=None, unstable=True, development=False):
    # Updates config repo to get new repos in config files
    git_pull('config', '.', True)

    Config = read_config_file(config, unstable=unstable)
    processes = []
    for section in Config.sections():
        repo = get_repo(section, Config, 'clone')
        if not os.path.exists(repo['path']):
            p = Process(target=repo['function'], args=(repo['url'],
                repo['path'], repo['branch'], repo['revision']))
            p.start()
            processes.append(p)
        wait_processes(processes)
    wait_processes(processes, 0)



    # Config = read_config_file(config, unstable=unstable)
    # p = Pool(MAX_PROCESSES)
    # repos = []
    # for section in Config.sections():
    #     repo = get_repo(section, Config, 'clone', development)
    #     if not os.path.exists(repo['path']):
    #         repo = get_repo(section, Config, 'clone', development)
    #         repos.append(repo)
    # exit_codes = p.map(_clone, repos)
    # return


def print_status(module, files):
    status_key_map = {
        'A': 'Added',
        'M': 'Modified',
        'R': 'Removed',
        '!': 'Deleted',
        '?': 'Untracked',
        'D': 'Deleted',
    }

    status_key_color = {
        'A': 'green',
        'M': 'yellow',
        'R': 'red',
        '!': 'red',
        '=': 'blue',
        'D': 'red',
        '?': 'red',
    }

    msg = []
    for key, value in files.iteritems():
        tf = status_key_map.get(key)
        col = eval('t.' + status_key_color.get(key, 'normal'))
        for f in value:
            msg.append(col + " %s (%s):%s " % (tf, key, f) + t.normal)
    if msg:
        msg.insert(0, "[%s]" % module)
        print '\n'.join(msg)


def git_status(module, path, url=None, verbose=False):
    repo = git.Repo(path)
    config = repo.config_reader()
    config.read()
    actual_url = config.get_value('remote "origin"', 'url')
    if actual_url != url:
        print >> sys.stderr, (t.bold('[%s]' % module) +
            t.red(' URL differs: ') + t.bold(actual_url + ' != ' + url))
    diff = repo.index.diff(None)
    files = {}
    for change in diff.change_type:
        files[change] = []

    if diff:
        for change in diff.change_type:
            for d in diff.iter_change_type(change):
                files[change].append(d.a_blob.path)
    print_status(module, files)
    res = []
    for x,k in files.items():
        res += k
    return res


def hg_status(module, path, url=None, verbose=False):
    repo = hgapi.Repo(path)
    hg_check_url(module, path, url)
    st = repo.hg_status(empty=True)
    print_status(module, st)
    return st


def _status(repo):
    return repo['function'](repo['name'], repo['path'], repo['url'],
        repo['verbose'])


@task()
def status(config=None, unstable=True, no_quilt=False, verbose=False):
    if not no_quilt:
        patches._pop()
    p = Pool(MAX_PROCESSES)
    Config = read_config_file(config, unstable=unstable)
    repos = []
    for section in Config.sections():
        repo = get_repo(section, Config, 'status')
        if not os.path.exists(repo['path']):
            print >> sys.stderr, t.red("Missing repositori: ") + \
                t.bold(repo['path'])
            continue
        repos.append(repo)
        repo['verbose'] = verbose
    p.map(_status, repos)
    if not no_quilt:
        patches._push()


def git_base_diff(path, module):
    files = " ".join(git_status(module, path))
    branch = get_branch(path)
    diff = run('cd %s; git diff %s ' % (path, files), hide=True,
        encoding='utf-8')
    rev = run('cd %s; git hash-object -t tree /dev/null' % (path),
        hide=True, warn=True, encoding='utf-8')
    base_diff = run('cd %s;git diff-tree -p %s %s %s' % (path,
        rev.stdout.replace('\n', ''), 'HEAD',  files), hide=True, warn=True,
        encoding='utf-8')
    return diff.stdout, base_diff.stdout


def get_branch(path, repo_type='git'):
    if repo_type == 'hg':
        branch = run('cd %s; hg branch' % path, hide=True)
        branch = branch.stdout.split('\n')[0]
    else:
        branch = run('cd %s; git branch' % path, hide=True)
        branch = branch.stdout.split('\n')[0].replace('*','').replace('\r','')
    return branch


def hg_base_diff(path, module):
    files = " ".join(hg_status(module, path))
    branch = get_branch(path)
    diff = run('cd %s; hg diff --git %s ' % (path, files), hide=True,
        encoding='utf-8')
    base_diff = run('cd %s; hg diff --git -r null:%s  %s' % (path, branch,
        files), hide=True, warn=True, encoding='utf-8')
    return diff.stdout, base_diff.stdout


@task()
def module_diff( path, module, base=True, show=True, fun=git_base_diff):
    diff, base_diff = fun(path, module)
    if show:
        print t.bold(path + " module diff:")
        if diff:
            print diff
        print t.bold(path + " module base diff:")
        if base_diff:
            print base_diff
        print ""
    return diff, base_diff


def git_diff(module, path, rev1=None, rev2=None):
    repo = git.Repo(path)
    diff = repo.git.diff(None)
    msg = []
    if diff:
        d = diff.split('\n')
        for line in d:
            if line and line[0] == '-':
                if module not in ['patches', 'features']:
                    line = line.replace('--- a','--- a/'+path[2:] )
                line = t.red + line + t.normal
            elif line and line[0] == '+':
                if module not in ['patches', 'features']:
                    line = line.replace('+++ b','+++ b/'+path[2:] )
                line = t.green + line + t.normal

            if line:
                msg.append(line)
    if msg == []:
        return
    msg.insert(0, t.bold('\n[' + module + "]\n"))
    print("\n".join(msg))


def hg_diff(module, path, rev1=None, rev2=None):
    t = Terminal()
    try:
        msg = []
        path_repo = path
        if not os.path.exists(path_repo):
            print >> sys.stderr, (t.red("Missing repositori:")
                + t.bold(path_repo))
            return

        repo = hgapi.Repo(path_repo)
        if rev2 is None:
            rev2 = get_branch(path_repo)
        msg = []
        for diff in repo.hg_diff(rev1, rev2):
            if diff:
                d = diff['diff'].split('\n')
                for line in d:
                    if line and line[0] == '-':
                        line = t.red + line + t.normal
                    elif line and line[0] == '+':
                        line = t.green + line + t.normal

                    if line:
                        msg.append(line)
        if msg == []:
            return
        msg.insert(0, t.bold('\n[' + module + "]\n"))
        print "\n".join(msg)
    except:
        msg.insert(0, t.bold('\n[' + module + "]\n"))
        msg.append(str(sys.exc_info()[1]))
        print >> sys.stderr, "\n".join(msg)

@task()
def diff(config=None, unstable=True, verbose=True, rev1=None, rev2=None):
    Config = read_config_file(config, unstable=unstable)
    processes = []
    for section in Config.sections():
        repo = get_repo(section, Config, 'diff')
        p = Process(target=repo['function'], args=(section, repo['path'],
            rev1, rev2))
        p.start()
        processes.append(p)
        wait_processes(processes)
    wait_processes(processes, 0)


def hg_summary(module, path, verbose):
    path_repo = os.path.join(path, module)
    if not os.path.exists(path_repo):
        print >> sys.stderr, t.red("Missing repositori:") + t.bold(path_repo)
        return
    repo = hgapi.Repo(path_repo)
    cmd = ['summary', '--remote']
    summary = repo.hg_command(*cmd)
    print t.bold("= " + module + " =")
    print summary


@task()
def summary(config=None, unstable=True, verbose=False):
    Config = read_config_file(config, unstable=unstable)
    processes = []
    for section in Config.sections():
        repo = Config.get(section, 'repo')
        path = Config.get(section, 'path')
        func = hg_summary
        if repo != 'hg':
            print >> sys.stderr, "Not developed yet"
            continue
        p = Process(target=func, args=(section, path, verbose))
        p.start()
        processes.append(p)
        wait_processes(processes)
    wait_processes(processes, 0)


def hg_outgoing(module, path, verbose):
    path_repo = os.path.join(path, module)
    if not os.path.exists(path_repo):
        print >> sys.stderr, t.red("Missing repositori:") + t.bold(path_repo)
        return
    repo = hgapi.Repo(path_repo)
    cmd = ['outgoing']
    if verbose:
        cmd.append('-v')

    try:
        out = repo.hg_command(*cmd)
    except hgapi.HgException, e:
        if 'no changes found' in str(e):
            return
        print t.bold_red('[' + module + ']')
        print "Error running %s (%s): %s" % (t.bold(*cmd), e.exit_code, str(e))
        return
    if out:
        print t.bold("= " + module + " =")
        print out

def git_outgoing(module, path, verbose):
    path_repo = os.path.join(path, module)
    if not os.path.exists(path_repo):
        print >> sys.stderr, t.red("Missing repositori:") + t.bold(path_repo)
        return
    repo = git.Repo(path)
    cmd = ['--pretty=oneline','--abbrev-commit','--graph','@{u}..']
    if verbose:
        cmd += ['-p']
    out = repo.git.log(*cmd)
    if out:
        print(t.bold("= " + module + " ="))
        print(out)

def _outgoing(repo):
    return repo['function'](repo['name'], repo['path'], repo['verbose'])

@task()
def outgoing(config=None, unstable=True, verbose=False):
    Config = read_config_file(config, unstable=unstable)
    processes = []
    for section in Config.sections():
        repo = Config.get(section, 'repo')
        path = Config.get(section, 'path')
        func = hg_outgoing
        p = Process(target=func, args=(section, path, verbose))
        p.start()
        processes.append(p)
        wait_processes(processes)
    wait_processes(processes, 0)


def git_pull(module, path, update=False, clean=False, branch=None,
        revision=None, ignore_missing=False):
    """
    Params update, clean, branch and revision are not used.
    """
    path_repo = os.path.join(path, module)
    if not os.path.exists(path_repo):
        if ignore_missing:
            return 0
        print >> sys.stderr, t.red("Missing repositori:") + t.bold(path_repo)
        return -1

    cwd = os.getcwd()
    os.chdir(path_repo)

    cmd = ['git', 'pull']
    result = run(' '.join(cmd), warn=True, hide='both')

    if not result.ok:
        print >> sys.stderr, t.red("= " + module + " = KO!")
        print >> sys.stderr, result.stderr
        os.chdir(cwd)
        return -1

    # If git outputs 'Already up-to-date' do not print anything.
    if 'Already up-to-date' in result.stdout:
        os.chdir(cwd)
        return 0

    print t.bold("= " + module + " =")
    print result.stdout
    os.chdir(cwd)
    return 0


def hg_check_url(module, path, url, clean=False):

    repo = hgapi.Repo(path)
    actual_url = str(repo.config('paths', 'default')).rstrip('/')
    url = str(url).rstrip('/')
    if actual_url != url:
        print >> sys.stderr, (t.bold('[%s]' % module) +
            t.red(' URL differs ') + "(Disk!=Cfg) " + t.bold(actual_url +
                ' !=' + url))
        if clean:
            print >> sys.stderr, (t.bold('[%s]' % module) + t.red(' Removed '))
            shutil.rmtree(path)


def hg_clean(module, path, url, force=False):

    nointeract = ''
    update = '-C'
    if force:
        nointeract = '-y'
        update = '-C'

    try:
        run('cd %s;hg update %s %s' % (path, update, nointeract),
            hide='stdout')
        run('cd %s;hg purge %s' % (path, nointeract), hide='stdout')
    except:
        print t.bold(module) + " module " + t.red("has uncommited changes")

    hg_check_url(module, path, url, clean=True)


def git_clean(module, path, url, force=False):
    # TODO
    pass


def _clean(repo):
    return repo['function'](repo['name'], repo['path'], repo['url'],
        repo['force'])


@task()
def clean(force=False, config=None, unstable=True):
    patches._pop()
    p = Pool(MAX_PROCESSES)
    Config = read_config_file(config, unstable=unstable)
    repos = []
    for section in Config.sections():
        repo = get_repo(section, Config, 'clean')
        repo['force'] = force
        if os.path.exists(repo['path']):
            repos.append(repo)
    p.map(_clean, repos)


def hg_branches(module, path, config_branch=None):
    client = hgapi.Repo(path)
    branches = client.get_branch_names()
    active = client.hg_branch()
    b = []
    branches.sort()
    branches.reverse()
    for branch in branches:
        br = branch

        if branch == active:
            br = "*" + br

        if branch == config_branch:
            br = "[" + br + "]"

        b.append(br)

    msg = str.ljust(module, 40, ' ') + "\t".join(b)

    if "[*" in msg:
        msg = bcolors.OKGREEN + msg + bcolors.ENDC
    elif "\t[" in msg or '\t*' in msg:
        msg = bcolors.FAIL + msg + bcolors.ENDC
    else:
        msg = bcolors.WARN + msg + bcolors.ENDC

    print msg

def git_branches(module, path, config_branch=None):
    repo = git.Repo(path)
    branches = repo.git.branch('-a')
    branches = [x.replace('remotes/origin/','').replace('*','').strip()
        for x in branches.split('\n') if 'HEAD' not in x]
    active = branches[0]
    b = []
    branches = list(set(branches))
    branches.sort()
    branches.reverse()
    for branch in branches:
        br = branch
        if branch == active:
            br = "*" + br
        if branch == config_branch:
            br = "[" + br + "]"
        b.append(br)

    msg = str.ljust(module, 40, ' ') + "\t".join(b)

    if "[*" in msg:
        msg = bcolors.OKGREEN + msg + bcolors.ENDC
    elif "\t[" in msg or '\t*' in msg:
        msg = bcolors.FAIL + msg + bcolors.ENDC
    else:
        msg = bcolors.WARN + msg + bcolors.ENDC

    print(msg)


@task()
def branches(config=None, modules=None):

    patches._pop()
    Config = read_config_file(config, unstable=True)
    p = Pool(MAX_PROCESSES)
    repos = []

    for section in Config.sections():
        if modules and section not in modules:
            continue
        repo = get_repo(section, Config, 'branches')
        repos.append(repo)

    p.map(_branches, repos)
    patches._push()

@task()
def branch(branch, clean=False, config=None, unstable=True):
    if not branch:
        print >> sys.stderr, t.red("Missing required branch parameter")
        return

    patches._pop()
    Config = read_config_file(config, unstable=unstable)

    processes = []
    p = None
    for section in Config.sections():
        repo = get_repo(section, Config)
        if repo['type'] == 'git':
            continue
        if repo['type'] != 'hg':
            print >> sys.stderr, "Not developed yet"
            continue
        p = Process(target=hg_update, args=(section, repo['path'], clean,
                branch))
        p.start()
        processes.append(p)
        wait_processes(processes)
    wait_processes(processes, 0)

    print t.bold('Applying patches...')
    patches._push()


def hg_missing_branch(module, path, branch_name, closed=True):
    path_repo = os.path.join(path, module)
    if not os.path.exists(path_repo):
        print >> sys.stderr, t.red("Missing repositori:") + t.bold(path_repo)
        return

    cwd = os.getcwd()
    os.chdir(path_repo)
    cmd = ['hg', 'branches']
    if closed:
        cmd.append('-c')
    result = run(' '.join(cmd), warn=True, hide='both')
    if branch_name not in result.stdout:
        print t.bold(module) + " misses branch %s" % branch_name
    os.chdir(cwd)


@task()
def missing_branch(branch_name, config=None, unstable=True):
    '''
    List all modules doesn't containt a branch named branc_name
    '''
    if not branch_name:
        print >> sys.stderr, t.red("Missing required branch parameter")
        return

    Config = read_config_file(config, unstable=unstable)
    processes = []
    p = None
    for section in Config.sections():
        repo = Config.get(section, 'repo')
        path = Config.get(section, 'path')
        if repo == 'git':
            continue
        if repo != 'hg':
            print >> sys.stderr, "Not developed yet"
            continue
        p = Process(target=hg_missing_branch, args=(section, path,
                branch_name))
        p.start()
        processes.append(p)
        wait_processes(processes)


def hg_create_branch(module, path, branch_name):
    path_repo = os.path.join(path, module)
    if not os.path.exists(path_repo):
        print >> sys.stderr, t.red("Missing repositori:") + t.bold(path_repo)
        return

    cwd = os.getcwd()
    os.chdir(path_repo)

    cmd = ['hg', 'branches']
    result = run(' '.join(cmd), warn=True, hide='both')
    if branch_name not in result.stdout:
        cmd = ['hg', 'branch', branch_name]
        result = run(' '.join(cmd), warn=True, hide='both')
        cmd = ['hg', 'commit', '-m', '"Create branch ' + branch_name + '"']
        result = run(' '.join(cmd), warn=True, hide='both')

    os.chdir(cwd)


@task()
def create_branch(branch_name, config=None, unstable=True):
    '''
    Create a branch with name branch_name to all the repositories that don't
    contain a branch with the same name.

    WARNING: This will clear all the uncommited changes in order to not
    add this changes to the new branch.
    '''
    if not branch_name:
        print >> sys.stderr, t.red("Missing required branch parameter")
        return

    patches._pop()
    print t.bold('Cleaning all changes...')
    Config = read_config_file(config, unstable=unstable)
    update(config, unstable=True, clean=True, no_quilt=True)
    Config = read_config_file(config, unstable=unstable)
    processes = []
    p = None
    for section in Config.sections():
        repo = Config.get(section, 'repo')
        path = Config.get(section, 'path')
        if repo == 'git':
            continue
        if repo != 'hg':
            print >> sys.stderr, "Not developed yet"
            continue
        p = Process(target=hg_create_branch, args=(section, path, branch_name))
        p.start()
        processes.append(p)
        wait_processes(processes)

    print t.bold('Applying patches...')
    patches._pop()


def hg_pull(module, path, update=False, clean=False, branch=None,
        revision=None, ignore_missing=False):
    if not os.path.exists(path):
        if ignore_missing:
            return 0
        print >> sys.stderr, t.red("Missing repositori:") + t.bold(path)
        return -1

    repo = hgapi.Repo(path)
    try:
        repo.hg_pull()
        if update:
            return hg_update_ng(module, path, clean, branch=branch,
                revision=revision, ignore_missing=ignore_missing)
    except hgapi.HgException, e:
        print t.bold_red('[' + module + ']')
        print "Error running %s : %s" % (e.exit_code, str(e))
        return -1
    except:
        return -1
    return 0


def _pull(repo):
    return repo['function'](repo['name'], repo['path'], update=repo['update'],
        branch=repo['branch'], revision=repo['revision'],
        ignore_missing=repo['ignore_missing'])


@task()
def pull(config=None, unstable=True, update=True, development=False,
         ignore_missing=False, no_quilt=False):
    if not no_quilt:
        patches._pop()

    Config = read_config_file(config, unstable=unstable)
    p = Pool(MAX_PROCESSES)
    repos = []
    for section in Config.sections():
        # TODO: provably it could be done with a wrapper
        repo = get_repo(section, Config, 'pull', development)
        repo['update'] = update
        repo['ignore_missing'] = ignore_missing
        repos.append(repo)
    exit_codes = p.map(_pull, repos)

    if not no_quilt:
        patches._push()
    return sum(exit_codes)


def hg_push(module, path, url, new_branches=False):
    path_repo = os.path.join(path, module)
    if not os.path.exists(path_repo):
        print >> sys.stderr, t.red("Missing repositori:") + t.bold(path_repo)
        return

    cwd = os.getcwd()
    os.chdir(path_repo)

    cmd = ['hg', 'push', url]
    if new_branches:
        cmd.append('--new-branch')
    result = run(' '.join(cmd), warn=True, hide='both')

    print t.bold("= " + module + " =")
    print result.stdout
    os.chdir(cwd)


@task()
def push(config=None, unstable=True, new_branches=False):
    '''
    Pushes all pending commits to the repo url.

    url that start with http are excluded.
    '''
    Config = read_config_file(config, unstable=unstable)
    processes = []
    p = None
    for section in Config.sections():
        repo = Config.get(section, 'repo')
        path = Config.get(section, 'path')
        # Don't push to repos that start with http as we don't have access to
        url = Config.get(section, 'url')
        if url[:4] == 'http':
            continue
        if repo == 'hg':
            func = hg_push
        elif repo == 'git':
            continue
        else:
            print >> sys.stderr, "Not developed yet"
            continue
        p = Process(target=func, args=(section, path, url, new_branches))
        p.start()
        processes.append(p)
        wait_processes(processes)
    wait_processes(processes, 0)


def hg_update_ng(module, path, clean, branch=None, revision=None,
        ignore_missing=False):
    if not os.path.exists(path):
        if ignore_missing:
            return 0
        print >> sys.stderr, t.red("Missing repositori:") + t.bold(path)
        return

    repo = hgapi.Repo(path)
    if revision and branch:
        if repo.revision(revision).branch != branch:
            print t.bold_red('[' + module + ']')
            print ("Invalid revision '%s': it isn't in branch '%s'"
                % (revision, branch))
            return -1
    elif branch:
        revision = branch
    elif not revision:
        revision = repo.hg_branch()

    try:
        repo.hg_update(revision, clean)
    except hgapi.HgException, e:
        print t.bold_red('[' + module + ']')
        print "Error running %s: %s" % (e.exit_code, str(e))
        return -1

    # TODO: add some check of output like hg_update?
    return 0


def hg_update(module, path, clean, branch=None, revision=None,
        ignore_missing=False):
    if not os.path.exists(path):
        if ignore_missing:
            return 0
        print >> sys.stderr, t.red("Missing repositori:") + t.bold(path)
        return

    cwd = os.getcwd()
    os.chdir(path)

    cmd = ['hg', 'update']
    if clean:
        cmd.append('-C')
    else:
        cmd.append('-y')  # noninteractive

    rev = None
    if branch:
        rev = branch
    if revision:
        rev = revision

    if rev:
        cmd.extend(['-r', rev])

    result = run(' '.join(cmd), warn=True, hide='both')

    if not result.ok:
        if branch is not None and u'abort: unknown revision' in result.stderr:
            os.chdir(cwd)
            return
        print >> sys.stderr, t.red("= " + module + " = KO!")
        print >> sys.stderr, result.stderr
        os.chdir(cwd)
        return

    if (u"0 files updated, 0 files merged, 0 files removed, 0 "
            u"files unresolved\n") in result.stdout:
        os.chdir(cwd)
        return

    print t.bold("= " + module + " =")
    print result.stdout
    os.chdir(cwd)


@task()
def update(config=None, unstable=True, clean=False, development=True,
        no_quilt=False):
    if not no_quilt:
        patches._pop()

    Config = read_config_file(config, unstable=unstable)
    processes = []
    p = None
    for section in Config.sections():
        repo = get_repo(section, Config, 'update')
        branch = None
        if clean:
            # Force branch only when clean is set
            branch = repo['branch']
        revision = repo['revision']
        p = Process(target=repo['function'], args=(section, repo['path'],
            clean, branch, revision))
        p.start()
        processes.append(p)
        wait_processes(processes)
    wait_processes(processes, 0)

    if not no_quilt:
        patches._push()


def git_revision(module, path, verbose):
    print "Git revision not implented"


def hg_revision(module, path, verbose=False):
    t = Terminal()
    path_repo = path
    if not os.path.exists(path_repo):
        print >> sys.stderr, (t.red("Missing repositori:")
            + t.bold(path_repo))
        return False

    repo = hgapi.Repo(path_repo)
    branches = repo.get_branches()
    revision = False
    for branch in branches:
        if branch['name'] == repo.hg_branch():
            revision = branch['version'].split(':')[1]

    return revision


def hg_is_last_revision(path, revision):
    if not revision:
        return False
    try:
        repo = hgapi.Repo(path)
        rev = repo.revision(revision)
        rev2 = repo.revision(repo.hg_id())
        if rev.date == rev2.date:
            return False
    except:
        return False
    return True



@task()
def revision(config=None, unstable=True, verbose=True):
    Config = read_config_file(config, unstable=unstable)
    processes = []
    for section in Config.sections():
        repo = get_repo(section, Config, 'revision')
        p = Process(target=repo['function'], args=(section, repo['path'],
            verbose))
        p.start()
        processes.append(p)
        wait_processes(processes)
    wait_processes(processes, 0)


@task()
def prefetch(force=False):
    """ Ensures clean enviroment """

    unknown(unstable=True, status=False, show=False, remove=True)

    clean(force=force)
    Config = read_config_file()
    patches._pop()
    for section in Config.sections():
        repo = get_repo(section, Config, 'status')
        files = repo['function'](section, repo['path'],
            verbose=False, url=repo['url'])
        if files == {}:
            continue
        remove_files = [os.path.join(repo['path'], x) for x in
            files.get('?', [])]
        if force or _ask_ok(
            'Answer "yes" to remove untracked files "%s" of "%s" repository '
                'in "%s" directory. [y/N] ' % (" ".join(remove_files),
                    section, repo['path']), 'n'):
            for f in remove_files:
                os.remove(f)
    patches._push()


@task()
def fetch():
    print t.bold('Pulling and updating local repository...')
    # Replace by a "hg_pull" call
    bashCommand = ['git', 'pull']
    execBashCommand(bashCommand, '',
        "It's not possible to pull the local repostory. Err:")

    patches._pop()

    print t.bold('Pulling...')
    pull(update=True, ignore_missing=True, no_quilt=True)

    print t.bold('Cloning...')
    clone()

    patches._push()

    print t.bold('Updating requirements...')
    bashCommand = ['pip', 'install', '-r', 'config/requirements.txt',
        '--exists-action','s']
    execBashCommand(bashCommand,
        'Config Requirements Installed Succesfully',
        "It's not possible to apply patche(es)")

    bashCommand = ['pip', 'install', '-r', 'tasks/requirements.txt',
        '--exists-action','s']
    execBashCommand(bashCommand,
        'Tasks Requirements Installed Succesfully',
        "It's not possible to apply patche(es)")

    if os.path.isfile('requirements.txt'):
        bashCommand = ['pip', 'install', '-r', 'requirements.txt',
            '--exists-action','s']
        execBashCommand(bashCommand,
            'Root Requirements Installed Succesfully',
            "It's not possible to apply patche(es)")

    print t.bold('Fetched.')


def increase_module_version(module, path, version):
    '''
    Increase version of module
    Cred: http://hg.tryton.org/tryton-tools/file/5f31cfd7e596/increase_version
    '''
    path_repo = os.path.join(path, module)
    if not os.path.exists(path_repo):
        print >> sys.stderr, t.red("Missing repositori:") + t.bold(path_repo)
        return

    cfg_file = os.path.join(path_repo, 'tryton.cfg')
    if not os.path.exists(path_repo):
        print >> sys.stderr, t.red("Missing tryton.cfg file:") + t.bold(
            cfg_file)
        return

    def increase(line):
        if line.startswith('version='):
            return 'version=%s\n' % version
        return line

    cwd = os.getcwd()
    os.chdir(path_repo)

    content = ''
    filename = 'tryton.cfg'
    with open(filename) as fp:
        for line in fp:
            content += increase(line)
    with open(filename, 'w') as fp:
        fp.write(content)
    today = date.today().strftime('%Y-%m-%d')
    content = 'Version %s - %s\n' % (version, today)
    filename = 'CHANGELOG'
    try:
        with open(filename) as fp:
            for line in fp:
                content += line
    except IOError:
        pass
    with open(filename, 'w') as fp:
        fp.write(content)

    os.chdir(cwd)


@task()
def increase_version(version, config=None, unstable=True, clean=False):
    '''
    Modifies all tryton.cfg files in order to set version to <version>
    '''
    if not version:
        print >> sys.stderr, t.red("Missing required version parameter")
        return
    Config = read_config_file(config, unstable=unstable)
    processes = []
    p = None
    for section in Config.sections():
        path = Config.get(section, 'path')
        p = Process(target=increase_module_version, args=(section, path,
                version))
        p.start()
        processes.append(p)
        wait_processes(processes)
    wait_processes(processes, 0)


ScmCollection = Collection()
ScmCollection.add_task(clone)
ScmCollection.add_task(status)
ScmCollection.add_task(diff)
ScmCollection.add_task(outgoing)
ScmCollection.add_task(push)
ScmCollection.add_task(pull)
ScmCollection.add_task(update)
ScmCollection.add_task(fetch)
ScmCollection.add_task(unknown)
ScmCollection.add_task(branch)
ScmCollection.add_task(missing_branch)
ScmCollection.add_task(create_branch)
ScmCollection.add_task(module_diff)
ScmCollection.add_task(increase_version)
ScmCollection.add_task(revision)
ScmCollection.add_task(clean)
ScmCollection.add_task(prefetch)
ScmCollection.add_task(branches)
ScmCollection.add_task(close_branch)
