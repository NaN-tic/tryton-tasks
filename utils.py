from blessings import Terminal
from invoke import task, Collection
from path import path
import ConfigParser
import os
import psycopg2
import shutil
import subprocess
import sys

try:
    from proteus import config, Wizard, Model
except ImportError:
    proteus_path = os.path.abspath(os.path.normpath(os.path.join(os.getcwd(),
                'proteus')))
    if os.path.isdir(proteus_path):
        sys.path.insert(0, proteus_path)
    try:
        from proteus import config, Wizard, Model
    except ImportError, e:
        print >> sys.stderr, "proteus importation error: ", e

trytond_path = os.path.abspath(os.path.normpath(os.path.join(os.getcwd(),
            'trytond')))
if os.path.isdir(trytond_path):
    sys.path.insert(0, trytond_path)

NO_MODULE_REPOS = ['trytond', 'tryton', 'proteus', 'nereid_app', 'sao',
    'tasks', 'utils', 'config', 'patches']
BASE_MODULES = ['ir', 'res', 'tests', 'webdav']

t = Terminal()


def _exit(initial_path, message=None):
    if path.getcwd() != initial_path:
        os.chdir(initial_path)
    if not message:
        return sys.exit(0)
    sys.exit(message)


def _ask_ok(prompt, default_answer=None):
    ok = raw_input(prompt) or default_answer
    if ok.lower() in ('y', 'ye', 'yes'):
        return True
    if ok.lower() in ('n', 'no', 'nop', 'nope'):
        return False
    _exit("Yes or no, please")


def _check_required_file(filename, directory_name, directory_path):
    if not directory_path.joinpath(filename).exists():
        _exit('%s file not found in %s directory: %s' % (filename,
                directory_name, directory_path))


def get_config_files():
    """ Return all config files paths """
    config_files = []
    for r, d, f in os.walk("./config"):
        for files in f:
            if not files.endswith(".cfg"):
                continue
            config_files.append(os.path.join(r, files))
    return config_files


def read_config_file(config_file=None, type='repos', unstable=True):
    assert type in ('repos', 'patches', 'all'), "Invalid 'type' param"

    Config = ConfigParser.ConfigParser()
    if config_file is not None:
        Config.readfp(open(config_file))
    else:
        for r, d, f in os.walk("./config"):
            for files in f:
                if not files.endswith(".cfg"):
                    continue
                if not unstable and files.endswith("-unstable.cfg"):
                    continue
                if 'templates' in r:
                    continue
                Config.readfp(open(os.path.join(r, files)))

    if type == 'all':
        return Config
    for section in Config.sections():
        is_patch = (Config.has_option(section, 'patch')
                and Config.getboolean(section, 'patch'))
        if type == 'repos' and is_patch:
            Config.remove_section(section)
        elif type == 'patches' and not is_patch:
            Config.remove_section(section)
    return Config


@task()
def update_parent_left_right(database, table, field, host='localhost',
        port='5432', user='angel', password='angel'):
    def _parent_store_compute(cr, table, field):
            def browse_rec(root, pos=0):
                where = field + '=' + str(root)

                if not root:
                    where = field + 'IS NULL'

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

    print "calculating parent_left of table", table, "and field:", field
    _parent_store_compute(db.cursor(), table, field)


@task()
def prepare_translations(database, langs=None, host=None, port=None,
        dbuser=None, dbpassword=None,
        config_file=os.environ.get('TRYTOND_CONFIG')):
    """
    Runs the set, clean and update wizards in the given database.
    """
    print t.bold('prepare_translations: database=%s, langs=%s') % (database,
        langs)
    if not _check_database(database, host, port, dbuser, dbpassword):
        return

    config.set_trytond(database=database, config_file=config_file)

    Lang = Model.get('ir.lang')
    if langs is None:
        languages = Lang.find([
                ('translatable', '=', True),
                ])
    else:
        langs = langs.split(',')
        languages = Lang.find([
                ('code', 'in', langs),
                ])
        if set(langs) != set(l.code for l in languages):
            print t.bold('Invalid languages: %s') % languages
            return

    translation_set = Wizard('ir.translation.set')
    translation_set.execute('set_')
    translation_set.execute('end')

    translation_clean = Wizard('ir.translation.clean')
    translation_clean.execute('clean')
    translation_clean.execute('end')

    for language in languages:
        translation_update = Wizard('ir.translation.update')
        translation_update.form.language = language
        translation_update.execute('update')
        print "%s translation updated" % language.name


@task()
def export_translations(database, modules, langs=None,
        host=None, port=None, dbuser=None, dbpassword=None,
        config_file=os.environ.get('TRYTOND_CONFIG')):
    """
    Creates translation files for the given modules and the specified languages.

    If no languages are specified, the ones marked as translatable in the
    database are used.
    """
    print t.bold('export_translations: %s, %s, %s') % (database, modules,
        langs)
    if not _check_database(database, host, port, dbuser, dbpassword):
        return

    config.set_trytond(database=database, config_file=config_file)

    Module = Model.get('ir.module.module')
    if modules == 'all':
        ir_modules = Module.find([
                ('state', '=', 'installed'),
                ])
    else:
        modules = modules.split(',')
        ir_modules = Module.find([
                ('state', '=', 'installed'),
                ('name', 'in', modules),
                ])
        missing_modules = set(modules) - set(m.name for m in ir_modules)
        if missing_modules:
            print t.bold('Invalid modules: %s') % missing_modules
            return

    Lang = Model.get('ir.lang')
    if langs is None:
        languages = Lang.find([
                ('translatable', '=', True),
                ])
    else:
        langs = langs.split(',')
        languages = Lang.find([
                ('code', 'in', langs),
                ])
        if set(langs) != set(l.code for l in languages):
            print 'Invalid languages: %s' % languages
            return

    for module in ir_modules:
        module_locale_path = os.path.abspath(os.path.normpath(
                os.path.join(os.getcwd(), 'modules', module.name, 'locale')))
        if not os.path.exists(module_locale_path):
            os.makedirs(module_locale_path)

        for language in languages:
            if language.code == 'en_US':
                continue

            translation_export = Wizard('ir.translation.export')
            translation_export.form.language = language
            translation_export.form.module = module
            translation_export.execute('export')

            file_path = os.path.join(module_locale_path,
                '%s.po' % language.code)
            with open(file_path, 'w') as f:
                f.write(str(translation_export.form.file))
            translation_export.execute('end')
            print ('Translation of "%s" in "%s" exported successfully.'
                % (module.name, language.code))


@task()
def account_reconcile(database, lines=2, months=6,
        config_file=os.environ.get('TRYTOND_CONFIG')):

    pref = config.set_trytond(database=database, config_file=config_file)

    Module = Model.get('ir.module.module')
    Company = Model.get('company.company')

    modules = Module.find([
                ('name', '=', 'account_reconcile'),
                ])
    if not modules:
        print t.bold('Module account_reconcile not found')
        return
    reconcile, = modules
    if reconcile.state != 'installed':
        Module.install([reconcile.id], pref.context)
        Wizard('ir.module.module.install_upgrade').execute('upgrade')

    for company in Company.find([]):
        print t.bold('Start reconcile for company %s (Lines %s, Months %s)'
            % (company.rec_name, lines, months))
        with pref.set_context({'company': company.id}):
            reconcile = Wizard('account.move_reconcile')
            reconcile.form.max_lines = str(lines)
            reconcile.form.max_months = months
            reconcile.form.start_date = None
            reconcile.form.end_date = None
            reconcile.execute('reconcile')


def _check_database(database, host=None, port=None, dbuser=None,
        dbpassword=None):
    connection_params = {'dbname': database}
    if host:
        connection_params['host'] = host
    if port:
        connection_params['port'] = port
    if dbuser:
        connection_params['user'] = dbuser
    if dbpassword:
        connection_params['password'] = dbpassword
    try:
        psycopg2.connect(**connection_params)
    except Exception, e:
        print t.bold('Invalid database connection params:')
        print str(e)
        return False
    return True


def execBashCommand(command, success_msg="", fail_msg="", quiet=True):
    """
        Execute bash command.
        @bashCommand: is list with the command and the options
        return: list with the output and the posible error
    """
    process = subprocess.Popen(command, stdout=subprocess.PIPE)
    output, err = process.communicate()

    if err and fail_msg:
        print fail_msg
        print err
        return False
    if not err and success_msg:
        print success_msg
        if not quiet:
            print output
    return True


def remove_dir(path, quiet=False):
    if not quiet:
        if not _ask_ok('Answer "yes" to remove path: "%s". [y/N] ' %
                (path), 'n'):
            return
    shutil.rmtree(path)


UtilsCollection = Collection()
UtilsCollection.add_task(account_reconcile)
UtilsCollection.add_task(update_parent_left_right)
UtilsCollection.add_task(prepare_translations)
UtilsCollection.add_task(export_translations)
