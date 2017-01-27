#!/usr/bin/env python
from invoke import Collection, task, run
import psycopg2
import time

JOBS = 3
FORMAT = 'directory'

def execute(command, **kwargs):
    if not 'warn' in kwargs:
        kwargs['warn'] = True
    if not 'hide' in kwargs:
        kwargs['hide'] = True
    print 'Running: %s' % command
    return run(command, **kwargs)

@task()
def dump(database):
    '''
    Dumps the content of the given database to
    ~/backups/<database name>-<timestamp> in PostgreSQL directory format using
    3 jobs/processes.
    '''
    path = '~/backups/' + database + '-' + time.strftime('%Y-%m-%d_%H:%M:%S')
    jobs = JOBS
    if FORMAT != 'directory':
        jobs = 1
    command = ('pg_dump --jobs %(jobs)d --format %(format)s -f %(path)s '
        '%(database)s' % {
            'jobs': jobs,
            'format': FORMAT,
            'path': path,
            'database': database,
            })
    execute(command)
    return path

@task()
def restore(path, database):
    '''
    Restores the content of the given path into the given database name.
    The content of the path should be in PostgreSQL directory format and it
    uses 3 jobs/processes.
    '''
    jobs = JOBS
    if FORMAT not in ('directory', 'custom'):
        jobs = 1
    command = ('pg_restore --jobs %(jobs)s --format %(format)s %(path)s '
        '-d %(database)s' % {
            'jobs': jobs,
            'format': FORMAT,
            'path': path,
            'database': database,
            })
    return execute(command)

@task()
def drop(database):
    '''
    Drops the given database but makes a backup using the database.dump command
    first.
    '''
    dump(database)
    execute('dropdb %s' % database)

@task()
def owner(database, to_owner):
    '''
    Changes the owner of the given database to the given owner username.
    '''
    connection = psycopg2.connect('dbname=%s' % database)
    cursor = connection.cursor()
    cursor.execute('ALTER DATABASE "%s" OWNER TO "%s"' % (database, to_owner))

    cursor.execute("SELECT tablename FROM pg_tables WHERE "
        "schemaname = 'public'")
    tables = set([x[0] for x in cursor.fetchall()])
    cursor.execute("SELECT sequence_name FROM information_schema.sequences "
        "WHERE sequence_schema = 'public'")
    tables |= set([x[0] for x in cursor.fetchall()])
    cursor.execute("SELECT table_name FROM information_schema.views WHERE "
        "table_schema = 'public'")
    tables |= set([x[0] for x in cursor.fetchall()])
    for table in tables:
        cursor.execute('ALTER TABLE public."%s" OWNER TO "%s"' % (table,
                to_owner))
    connection.commit()
    print 'Changed %d tables, sequences and views to %s' % (len(tables),
        to_owner)

def local_copy_with_template(from_database, to_database, to_owner):
    # If we're on the same host, just try to use CREATE DATABASE with
    # TEMPLATE
    #connection = psycopg2.connect('dbname=template1')
    #cursor = connection.cursor()
    query = ('CREATE DATABASE %(to_database)s TEMPLATE '
        '%(from_database)s' % {
            'to_database': to_database,
            'from_database': from_database,
            })
    if to_owner:
        query += ' OWNER = %(owner)s' % {
            'owner': to_owner,
            }
    #cursor.execute(query)
    result = execute('psql -d template1 -c "%s"' % query)
    if not result.ok:
        return False
    return True

def local_copy(from_database, to_database):
    path = dump(from_database)
    execute('createdb %s' % to_database)
    restore(path, to_database)

@task()
def copy(from_, to, to_owner=None):
    '''
    Copies the content a database into a new one. Databases may be in different
    hosts. Optionally it also allows you to specify the target owner which
    is a shortcut for calling database.owner in the same command.

    Syntax:

    invoke database.copy [from_host:]from_database [to_host:]to_database
    '''
    if ':' in from_:
        from_host, from_database = from_.split(':')
    else:
        from_host, from_database = None, from_
    if ':' in to:
        to_host, to_database = to.split(':')
    else:
        to_host, to_database = None, to
    print from_host, from_database, to_host, to_database
    if not from_host and not to_host:
        print 'Copying from %s to %s' % (from_database, to_database)
        if local_copy_with_template(from_database, to_database, to_owner):
            return
        local_copy(from_database, to_database)
        if to_owner:
            owner(to_database, to_owner)
        return


DatabaseCollection = Collection()
DatabaseCollection.add_task(drop)
DatabaseCollection.add_task(dump)
DatabaseCollection.add_task(owner)
DatabaseCollection.add_task(copy)
