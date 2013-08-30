#!/usr/bin/env python

from invoke import task, run
import hgapi
from blessings import Terminal
import os
import ConfigParser
from multiprocessing import Process

MAX_PROCESSES = 20

t = Terminal()
Config = ConfigParser.ConfigParser()

def read_config_file(config_file=None):
    if not config_file is None:
        Config.readfp(open(config_file))
        return

    for r,d,f in os.walk("./config"):
        for files in f:
            if files.endswith(".cfg"):
                Config.readfp(open(os.path.join(r,files)))

def wait_processes(processes, maximum=MAX_PROCESSES):
    i = 0
    while len(processes) > MAX_PROCESSES:
        if i >= len(processes):
            i = 0
        p = processes[i]
        p.join(0.1)
        if not p.is_alive():
            del processes[i]
        i += 1


@task
def clone(config=None):

    def hg_clone(url, repo_path):
        command = 'hg clone -q %s %s' % (url, repo_path)
        try:
            run(command)
        except:
            print "Error running " + t.bold(command)
            raise
        print "Repo " + t.bold(repo_path) + t.green(" Cloned")

    read_config_file(config)
    processes = []
    p = None
    for section in Config.sections():
        repo = Config.get(section, 'repo')
        url = Config.get(section, 'url')
        path = Config.get(section, 'path')
        func = hg_clone
        if repo != 'hg':
            print "Not developet yet"
            continue
        repo_path = os.path.join(path, section)
        if not os.path.exists(repo_path):
            print "Adding Module " + t.bold(section) + " to clone list"
            p = Process(target=func, args=(url, repo_path))
            p.start()
            processes.append(p)
        wait_processes(processes)
    wait_processes(processes, 0)



@task
def status(config=None, verbose=False):

    def hg_status(module, path, verbose):
        repo_path = os.path.join(path, module)
        if not os.path.exists(repo_path):
            print t.red("Missing repositori:") + t.bold(repo_path)
            return
        repo = hgapi.Repo(repo_path)
        st = repo.hg_status(empty=True)
        if not st and verbose:
            print t.bold_green('\['+ module +']')
            return
        if not st and not verbose:
            return

        msg = [t.bold_red("\n["+ module + ']')]

        if st.get('A'):
            for file_name in st['A']:
                msg.append(t.green('A '+ file_name))
        if st.get('M'):
            for file_name in st['M']:
                msg.append(t.yellow('M '+file_name))
        if st.get('R'):
            for file_name in st['R']:
                msg.append(t.red('R '+file_name))
        if st.get('!'):
            for file_name in st['!']:
                msg.append(t.bold_red('! '+ file_name))
        if st.get('?'):
            for file_name in st['?']:
                msg.append(t.blue('? ' + file_name))

        print "\n".join(msg)

    read_config_file(config)
    processes = []
    p = None
    for section in Config.sections():
        repo = Config.get(section, 'repo')
        path = Config.get(section, 'path')
        func = hg_status
        if repo != 'hg':
            print "Not developet yet"
            continue
        p = Process(target=func, args=(section, path, verbose))
        p.start()
        processes.append(p)
        wait_processes(processes)
    wait_processes(processes, 0)


@task
def diff(config=None, verbose=False):
    def hg_diff(module, path, verbose):
        path_repo = os.path.join(path, module)
        if not os.path.exists(path_repo):
            print t.red("Missing repositori:") + t.bold(path_repo)
            return
        if not verbose:
            result = run('cd %s; hg diff --stat' % path_repo, hide='stdout')
            if result.stdout:
                print t.bold(module+"\n")
                print result.stdout
            return
        repo = hgapi.Repo(path_repo)
        for diff in repo.hg_diff():
            if diff:
                print t.bold(module+"\n")
                print diff['diff']

    read_config_file(config)
    for section in Config.sections():
        repo = Config.get(section, 'repo')
        path = Config.get(section, 'path')
        hg_diff(section, path, verbose)


@task
def summary(config=None, verbose=False):
    def hg_summary(module, path, verbose):
        path_repo = os.path.join(path, module)
        if not os.path.exists(path_repo):
            print t.red("Missing repositori:") + t.bold(path_repo)
            return
        repo = hgapi.Repo(path_repo)
        cmd = ['summary','--remote']
        summary = repo.hg_command(*cmd)
        print t.bold("= " + module +" =")
        print summary

    read_config_file(config)
    processes = []
    for section in Config.sections():
        repo = Config.get(section, 'repo')
        path = Config.get(section, 'path')
        func = hg_summary
        if repo != 'hg':
            print "Not developet yet"
            continue
        p = Process(target=func, args=(section, path, verbose))
        p.start()
        processes.append(p)
        wait_processes(processes)
    wait_processes(processes, 0)


@task
def ppush(config=None, verbose=False):
    def hg_ppush(module, path, verbose):
        path_repo = os.path.join(path, module)
        if not os.path.exists(path_repo):
            print t.red("Missing repositori:") + t.bold(path_repo)
            return
        repo = hgapi.Repo(path_repo)
        cmd = ['outgoing']
        if verbose:
            cmd.append('-v')
        try:
            out = repo.hg_command(*cmd)
        except:
            #TODO:catch correct exception
            return
        print t.bold("= " + module +" =")
        print out

    read_config_file(config)
    processes = []
    for section in Config.sections():
        repo = Config.get(section, 'repo')
        path = Config.get(section, 'path')
        func = hg_ppush
        if repo != 'hg':
            print "Not developet yet"
            continue
        p = Process(target=func, args=(section, path, verbose))
        p.start()
        processes.append(p)
        wait_processes(processes)
    wait_processes(processes, 0)

@task
def pull(config=None, update=True):
    def hg_pull(module, path, update):
        path_repo = os.path.join(path, module)
        if not os.path.exists(path_repo):
            print t.red("Missing repositori:") + t.bold(path_repo)
            return
        repo = hgapi.Repo(path_repo)
        cmd = ['pull']
        if update:
            cmd.append('-u')
        try:
            out = repo.hg_command(*cmd)
        except:
            #TODO:catch correct exception
            print t.red("= " + module +" = KO!")
            return
        if "no changes found" in out:
            return
        print t.bold("= " + module +" =")
        print out

    read_config_file(config)
    processes = []
    p = None
    for section in Config.sections():
        repo = Config.get(section, 'repo')
        path = Config.get(section, 'path')
        func = hg_pull
        if repo != 'hg':
            print "Not developet yet"
            continue
        p = Process(target=func, args=(section, path, update))
        p.start()
        processes.append(p)
        wait_processes(processes)
    wait_processes(processes, 0)


@task
def update(config=None, clean=False):
    def hg_update(module, path, update):
        path_repo = os.path.join(path, module)
        if not os.path.exists(path_repo):
            print t.red("Missing repositori:") + t.bold(path_repo)
            return
        repo = hgapi.Repo(path_repo)
        cmd = ['update']
        if clean:
            cmd.append('-C')
        try:
            out = repo.hg_command(*cmd)
        except:
            #TODO:catch correct exception
            print t.red("= " + module +" = KO!")
            return
        if "0 files updated, 0 files merged, 0 files removed, 0 files unresolved" in out:
            return
        print t.bold("= " + module +" =")
        print out

    read_config_file(config)
    processes = []
    p = None
    for section in Config.sections():
        repo = Config.get(section, 'repo')
        path = Config.get(section, 'path')
        func = hg_update
        if repo != 'hg':
            print "Not developet yet"
            continue
        p = Process(target=func, args=(section, path, update))
        p.start()
        processes.append(p)
        wait_processes(processes)
    wait_processes(processes, 0)
