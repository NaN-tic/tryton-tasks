import ConfigParser
import os
import psycopg2
import sys
from blessings import Terminal
from invoke import task
from path import path

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


def read_config_file(config_file=None, type='repos'):
    assert type in ('repos', 'patches', 'all'), "Invalid 'type' param"

    Config = ConfigParser.ConfigParser()
    if config_file is not None:
        Config.readfp(open(config_file))
    else:
        for r, d, f in os.walk("./config"):
            for files in f:
                if files.endswith(".cfg"):
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


@task
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
