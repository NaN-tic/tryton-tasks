#!/usr/bin/env python
import contextlib
import os
import psycopg2
import sys
from blessings import Terminal
from invoke import task, run

try:
    from trytond.transaction import Transaction
    from trytond.modules import *
    #from trytond.modules import Graph, Node, get_module_info
except ImportError, e:
    print >> sys.stderr, "trytond importation error: ", e

try:
    from proteus import config as pconfig, Wizard, Model
except ImportError:
    proteus_path = os.path.abspath(os.path.normpath(os.path.join(os.getcwd(),
                'proteus')))
    if os.path.isdir(proteus_path):
        sys.path.insert(0, proteus_path)
    try:
        from proteus import config as pconfig, Wizard, Model
    except ImportError, e:
        print >> sys.stderr, "proteus importation error: ", e

try:
    from sql import Table
    ir_module = Table('ir_module_module')
    ir_model_data = Table('ir_model_data')
except ImportError:
    ir_module = None
    ir_model_data = None

trytond_path = os.path.abspath(os.path.normpath(os.path.join(os.getcwd(),
            'trytond')))
if os.path.isdir(trytond_path):
    sys.path.insert(0, trytond_path)

os.environ['TZ'] = "Europe/Madrid"

t = Terminal()

discard = ['trytond', 'tryton', 'proteus', 'nereid_app',
           'sao', 'tasks', 'utils', 'config', 'patches']


def check_database(database, connection_params):
    if connection_params is None:
        connection_params = {}
    else:
        connection_params = connection_params.copy()
    connection_params['dbname'] = database
    try:
        psycopg2.connect(**connection_params)
    except Exception, e:
        print t.bold('Invalid database connection params:')
        print str(e)
        return False
    return True


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
def parent_compute(database, table, field, host='localhost', port='5432',
        user='angel', password='password'):

    def _parent_store_compute(cr, table, field):
        def browse_rec(root, pos=0):
            where = field + '=' + str(root)

            if not root:
                where = parent_field + 'IS NULL'

            cr.execute('SELECT id FROM %s WHERE %s \
                ORDER BY %s' % (table, where, field))
            pos2 = pos + 1
            childs = cr.fetchall()
            for id in childs:
                pos2 = browse_rec(id[0], pos2)
            cr.execute('update %s set "left"=%s, "right"=%s\
                where id=%s' % (table, pos, pos2, root))
            return pos2 + 1

        query = 'SELECT id FROM %s WHERE %s IS NULL order by %s' % (
            table, field, field)
        pos = 0
        cr.execute(query)
        for (root,) in cr.fetchall():
            pos = browse_rec(root, pos)
        return True

    db = psycopg2.connect(dbname=database, host=host, port=port, user=user,
        password=password)

    cursor = db.cursor()
    _parent_store_compute(cursor, table, field)
    db.commit()
    db.close()


@task()
def missing(database, install=False, show=True):
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
        print "Press Key to continue..."
        sys.stdin.read(1)

    if install:
        run('trytond/bin/trytond -d %s -i %s' % (database, miss))

    return ",".join(miss)


@task()
def forgotten(database, show=True):
    """
    Return a list of modules that exists in the DB but not in *.cfg files
    """
    set_context(database)
    cursor = Transaction().cursor
    cursor.execute(*ir_module.select(ir_module.name, ir_module.state))
    db_module_list = set([(r[0], r[1]) for r in cursor.fetchall()])

    forgotten_uninstalled = []
    forgotten_installed = []
    for module, state in db_module_list:
        try:
            get_module_info(module)
        except IOError:
            if state in ('installed', 'to install', 'to upgrade'):
                forgotten_installed.append(module)
            else:
                forgotten_uninstalled.append(module)

    if show:
        if forgotten_uninstalled:
            print t.bold("Forgotten modules:")
            print "  - " + "\n  - ".join(forgotten_uninstalled)
            print ""
        if forgotten_installed:
            print t.red("Forgotten installed modules:")
            print "  - " + "\n  - ".join(forgotten_installed)
            print ""
    return forgotten_uninstalled, forgotten_installed


@task()
def uninstall(database, modules='forgotten', connection_params=None):
    if not database or not modules:
        return

    if modules == 'forgotten':
        unused, modules = forgotten(database, show=False)
    else:
        modules = modules.split(',')
    if not modules:
        return

    print t.bold("uninstall: ") + ", ".join(modules)
    if connection_params is None:
        connection_params = {}
    if not check_database(database, connection_params):
        return

    config = pconfig.set_trytond(database_type='postgresql',
        database_name=database, **connection_params)

    Module = Model.get('ir.module.module')
    modules_to_uninstall = Module.find([
            ('name', 'in', modules),
            ])
    Module.uninstall([m.id for m in modules_to_uninstall],
        config.context)

    module_install_upgrade = Wizard('ir.module.module.install_upgrade')
    module_install_upgrade.execute('upgrade')
    module_install_upgrade.execute('config')
    print ""
