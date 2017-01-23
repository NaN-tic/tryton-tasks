#!/usr/bin/env python
from invoke import Collection, task, run
import psycopg2
import time

JOBS = 2
FORMAT = 'custom'

def execute(command, **kwargs):
    if not 'warn' in kwargs:
        kwargs['warn'] = True
    if not 'hide' in kwargs:
        kwargs['hide'] = True
    print 'Running: %s' % command
    return run(command, **kwargs)

@task()
def dump(database):
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
    dump(database)
    execute('dropdb %s' % database)

@task()
def owner(database, to_owner):
    connection = psycopg2.connect('dbname=%s' % database)
    cursor = connection.cursor()
    cursor.execute("SELECT pg_catalog.pg_get_userbyid(datdba) FROM "
        "pg_catalog.pg_database WHERE datname = '%s' ORDER BY 1;" % database)
    from_owner = cursor.fetchone()[0]
    cursor.execute('ALTER DATABASE "%s" OWNER TO "%s"' % (database, to_owner))
    cursor.execute('REASSIGN OWNED BY "%s" TO "%s"' % (from_owner, to_owner))

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
        print 'Copying from %s to %s' % (from_host, to_host)
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
