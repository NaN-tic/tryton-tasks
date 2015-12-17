#!/usr/bin/env python
import contextlib
import os
import psycopg2
import sys
from invoke import task, run, Collection

from .iban import create_iban, IBANError
from .utils import (t, read_config_file, remove_dir, NO_MODULE_REPOS,
    BASE_MODULES)

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

try:
    # TODO: Remove compatibility with versions < 3.4
    from trytond.config import CONFIG
except ImportError, e:
    try:
        from trytond.config import config as CONFIG
    except ImportError, e:
        print >> sys.stderr, "trytond importation error: ", e

trytond_path = os.path.abspath(os.path.normpath(os.path.join(os.getcwd(),
            'trytond')))
if os.path.isdir(trytond_path):
    sys.path.insert(0, trytond_path)

os.environ['TZ'] = "Europe/Madrid"


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


def set_context(database_name, config_file=os.environ.get('TRYTOND_CONFIG')):
    CONFIG.update_etc(config_file)
    if not Transaction().cursor:
        return Transaction().start(database_name, 0)
    else:
        return contextlib.nested(Transaction().new_cursor(),
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
def update_post_move_sequence(database, fiscalyear, sequence,
        host='localhost', port='5432', user='angel', password='password'):
    ''' Force update of post_move_sequence on fiscalyears '''
    db = psycopg2.connect(dbname=database, host=host, port=port, user=user,
        password=password)

    cursor = db.cursor()
    cursor.execute(
        "update account_fiscalyear set post_move_sequence = %s "
        "where id = %s " % (fiscalyear, sequence))
    cursor.execute(
        "update account_period set post_move_sequence = null where "
        "fiscalyear = %s" % (fiscalyear))
    db.commit()
    db.close()


@task()
def missing(database, config_file=os.environ.get('TRYTOND_CONFIG'),
        install=False, show=True):
    """
    Checks which modules are missing according to the dependencies of the
    modules installed in the database.
    """
    set_context(database, config_file)
    cursor = Transaction().cursor
    cursor.execute(*ir_module.select(ir_module.name,
                        where=ir_module.state.in_(('installed', 'to install',
                                'to upgrade', 'to remove'))))
    module_list = set([name for (name,) in cursor.fetchall()])
    miss = set()

    modules_iteration = 0
    while len(module_list) != modules_iteration:
        modules_iteration = len(module_list)
        _, _, _, missing = create_graph(module_list)
        miss |= missing
        module_list.update(miss)

    miss = " ".join(miss)
    if show:
        print "Missing dependencies: %s " % miss
        print "Press Key to continue..."
        sys.stdin.read(1)

    if install:
        configfile = config_file and "-c %s" % config_file or ""
        run('trytond/bin/trytond -d %s %s -u %s'
            % (database, configfile, miss))

    return miss


@task(help={
        'uninstall': 'Uninstall installed forgotten and lost modules.',
        'delete': 'Delete forgotten and lost modules form ir_module_module '
            'table of database (except installed modules if "uninstall" param '
            'is not set).',
        'remove': 'Remove directory of forgotten modules (except installed '
            'modules if "uninstall" param is not set).'
        })
def forgotten(database, config_file=os.environ.get('TRYTOND_CONFIG'),
        uninstall=False, delete=False, remove=False, show=True, unstable=True):
    """
    Return a list of modules that exists in the DB but not in *.cfg files.
    If some of these modules don't exists in filesystem (lost modules), they
    are specifically listed.
    """
    with set_context(database, config_file):
        cursor = Transaction().cursor
        cursor.execute(*ir_module.select(ir_module.name, ir_module.state))
        db_module_list = [(r[0], r[1]) for r in cursor.fetchall()]

    config = read_config_file(unstable=unstable)
    configs_module_list = [section for section in config.sections()
        if section not in NO_MODULE_REPOS]

    forgotten_uninstalled = []
    forgotten_installed = []
    lost_uninstalled = []
    lost_installed = []
    for module, state in db_module_list:
        if module not in BASE_MODULES and module not in configs_module_list:
            try:
                get_module_info(module)
            except IOError:
                if state in ('installed', 'to install', 'to upgrade'):
                    lost_installed.append(module)
                else:
                    lost_uninstalled.append(module)
                continue

            if state in ('installed', 'to install', 'to upgrade'):
                forgotten_installed.append(module)
            else:
                forgotten_uninstalled.append(module)

    if show:
        if forgotten_uninstalled:
            print t.bold("Forgotten modules (in DB but not in config files):")
            print "  - " + "\n  - ".join(forgotten_uninstalled)
            print ""
        if forgotten_installed:
            print t.red("Forgotten installed modules (in DB but not in config "
                "files):")
            print "  - " + "\n  - ".join(forgotten_installed)
            print ""
        if lost_uninstalled:
            print t.bold("Lost modules (in DB but no in filesystem):")
            print "  - " + "\n  - ".join(lost_uninstalled)
            print ""
        if lost_installed:
            print t.red("Lost installed modules (in DB but no in filesystem):")
            print "  - " + "\n  - ".join(lost_installed)
            print ""

    to_uninstall = forgotten_installed + lost_installed
    to_delete = forgotten_uninstalled + lost_uninstalled
    to_remove = forgotten_uninstalled if remove else []
    if uninstall and to_uninstall:
        if lost_installed:
            to_remove += create_fake_modules(lost_installed)
        uninstall_task(database, modules=to_uninstall)
        to_delete += forgotten_installed + lost_installed
        if remove:
            to_remove += forgotten_installed

    if delete and to_delete:
        delete_modules(database, to_delete, config_file=config_file)

    if to_remove:
        for module in to_remove:
            path = os.path.join('./modules', module)
            remove_dir(path, quiet=True)

    return (forgotten_uninstalled, forgotten_installed, lost_uninstalled,
        lost_installed)


@task(help={'modules': 'module names separated by coma.'})
def create_fake_modules(modules):
    """
    Create fake (empty) modules to allow to uninstall them.
    """
    if not modules:
        return

    if isinstance(modules, basestring):
        modules = modules.split(',')

    trytoncfg_content = [
        "[tryton]",
        "version=3.2.0",
        "depends:",
        "    ir",
        "    res",
        "xml:",
        ]

    print t.bold("Creating fake modules: ") + ", ".join(modules)
    created = []
    for module in modules:
        module_path = os.path.join('./modules', module)
        if os.path.exists(module_path):
            print ("  - Module '%s' not created because already exists in "
                "filesystem" % module_path)
            continue
        run('mkdir %s' % module_path)
        run('echo "%s" > %s/tryton.cfg'
            % ("\n".join(trytoncfg_content), module_path))
        run('touch %s/__init__.py' % module_path)
        print "  - Module '%s' created" % module_path
        created.append(module)
    return created


@task(help={'modules': 'module names separated by coma'})
def uninstall_task(database, modules,
        config_file=os.environ.get('TRYTOND_CONFIG')):
    """
    Uninstall the supplied modules (separated by coma) from database.
    """
    if not database or not modules:
        return

    if isinstance(modules, basestring):
        modules = modules.replace(" ", "").split(',')
    if not modules:
        return

    print t.bold("uninstall: ") + ", ".join(modules)
    if not check_database(database, {}):
        return

    config = pconfig.set_trytond(database=database, config_file=config_file)

    Module = Model.get('ir.module.module')
    modules_to_uninstall = Module.find([
            ('name', 'in', modules),
            ('state', '=', 'installed')
            ])
    Module.uninstall([m.id for m in modules_to_uninstall],
        config.context)

    module_install_upgrade = Wizard('ir.module.module.install_upgrade')
    module_install_upgrade.execute('upgrade')
    module_install_upgrade.execute('config')
    print ""


@task()
def delete_modules(database, modules,
        config_file=os.environ.get('TRYTOND_CONFIG'), force=False):
    """
    Delete the supplied modules (separated by coma) from ir_module_module
    table of database.
    """
    if not database or not modules:
        return

    if isinstance(modules, basestring):
        modules = modules.split(',')

    print t.bold("delete: ") + ", ".join(modules)
    set_context(database, config_file)
    cursor = Transaction().cursor
    cursor.execute(*ir_module.select(ir_module.name,
                        where=(ir_module.state.in_(('installed', 'to install',
                                'to upgrade', 'to remove')) &
                            ir_module.name.in_(tuple(modules)))))
    installed_modules = [name for (name,) in cursor.fetchall()]
    if installed_modules:
        if not force:
            print (t.red("Some supplied modules are installed: ") +
                ", ".join(installed_modules))
            return
        if force:
            print (t.red("Deleting installed supplied modules: ") +
                ", ".join(installed_modules))

    cursor.execute(*ir_module.delete(where=ir_module.name.in_(tuple(modules))))
    cursor.commit()


@task()
def convert_bank_accounts_to_iban(database,
        config_file=os.environ.get('TRYTOND_CONFIG')):
    """
    Convert all Bank Account Numbers of type 'other' to 'iban'.
    """
    if not database:
        return

    print t.bold("Convert bank account number to IBAN")
    if not check_database(database, {}):
        return

    config = pconfig.set_trytond(database=database, config_file=config_file)

    BankAccount = Model.get('bank.account')
    bank_accounts = BankAccount.find([
            ('numbers.type', '=', 'other'),
            ])
    for bank_account in bank_accounts:
        if any(n.type == 'iban' for n in bank_account.numbers):
            continue

        bank_country_code = bank_account.bank.party.vat_country or 'ES'
        assert bank_country_code == 'ES', (
            "Unexpected country of bank of account %s" % bank_account.rec_name)

        account_number = bank_account.numbers[0]
        number = account_number.number.replace(' ', '')
        assert len(number) == 20, "Unexpected length of number %s" % number
        try:
            iban = create_iban(
                bank_country_code,
                number[:8], number[10:])
        except IBANError, err:
            t.red("Error generating iban from number %s: %s" % (number, err))
            continue
        account_number.sequence = 10
        iban_account_number = bank_account.numbers.new()
        iban_account_number.type = 'iban'
        iban_account_number.sequence = 1
        iban_account_number.number = iban
        bank_account.save()
    print ""


TrytonCollection = Collection()
TrytonCollection.add_task(delete_modules)
TrytonCollection.add_task(uninstall_task, 'uninstall')
TrytonCollection.add_task(create_fake_modules)
TrytonCollection.add_task(forgotten)
TrytonCollection.add_task(missing)
TrytonCollection.add_task(update_post_move_sequence)
TrytonCollection.add_task(convert_bank_accounts_to_iban)
