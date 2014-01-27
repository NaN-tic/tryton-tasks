#!/usr/bin/env python

import os
from invoke import task, run

try:
    from trytond.transaction import Transaction
    from trytond.modules import *
except ImportError:
    pass

try:
    from sql import Table
    ir_module = Table('ir_module_module')
    ir_model_data = Table('ir_model_data')
except ImportError:
    ir_module = None
    ir_model_data = None

discard = ['trytond', 'tryton', 'proteus', 'nereid_app',
           'sao', 'tasks', 'utils', 'config', 'patches']


os.environ['TZ'] = "Europe/Madrid"


def set_context(database_name):
    if not Transaction().cursor:
        Transaction().start(database_name, 0)
    else:
        contextlib.nested(Transaction().new_cursor(),
            Transaction().set_user(0),
            Transaction().reset_context())


def create_graph(module_list):
    graph = Graph()
    packages = []

    for module in module_list:
        try:
            info = get_module_info(module)
        except IOError:
            if module != 'all':
                raise Exception('Module %s not found' % module)
        packages.append((module, info.get('depends', []),
                info.get('extras_depend', []), info))

    current, later = set([x[0] for x in packages]), set()
    all_packages = set(current)
    while packages and current > later:
        package, deps, xdep, info = packages[0]

        # if all dependencies of 'package' are already in the graph,
        # add 'package' in the graph
        all_deps = deps + [x for x in xdep if x in all_packages]
        if reduce(lambda x, y: x and y in graph, all_deps, True):
            if not package in current:
                packages.pop(0)
                continue
            later.clear()
            current.remove(package)
            graph.add_node(package, all_deps)
            node = Node(package, graph)
            node.info = info
        else:
            later.add(package)
            packages.append((package, deps, xdep, info))
        packages.pop(0)

    missings = set()
    for package, deps, _, _ in packages:
        if package not in later:
            continue
        missings |= set((x for x in deps if x not in graph))

    return graph, packages, later, missings - later


@task()
def missing(database, show=True):
    set_context(database)
    cursor = Transaction().cursor
    cursor.execute(*ir_module.select(ir_module.name,
                        where=ir_module.state.in_(('installed', 'to install',
                                'to upgrade', 'to remove'))))
    module_list = set([name for (name,) in cursor.fetchall()])
    miss = set()

    modules_iteration = 0
    while len(module_list) != modules_iteration:
        modules_iteration = len(module_list)
        graph, packages, later, missing = create_graph(module_list)
        miss |= missing
        module_list.update(miss)

    if show:
        print "Missing dependencies,".join(miss)
    return ",".join(miss)


@task()
def install_missing(database):
    miss = missing(database, False)
    if not miss:
        return
    print "Install Missing dependencies:",miss
    print "Press Key to continue..."
    sys.stdin.read(1)

    run('trytond/bin/trytond -d %s -i %s' % (database, miss))
