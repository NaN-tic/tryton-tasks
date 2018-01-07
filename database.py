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
def dump(database, ssh=None):
    '''
    Dumps the content of the given database to
    ~/backups/<database name>-<timestamp> in PostgreSQL directory format using
    3 jobs/processes.
    '''
    if ssh:
        path = '.'
    else:
        path = '~'
    path += '/backups/'
    relative_path = database + '-' + time.strftime('%Y-%m-%d_%H:%M:%S')
    path += relative_path
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
    if ssh:
        command = '%s %s' % (ssh, command)
    execute(command)
    return path, relative_path

@task()
def restore(path, database, ssh=None):
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
    if ssh:
        command = '%s %s' % (ssh, command)
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
    connection.close()
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
    path, _ = dump(from_database)
    execute('createdb %s' % to_database)
    restore(path, to_database)

def remote_dump(host, database):
    remote_path, relative_path = dump(database, 'ssh %s' % host)
    local_path = '~/backups/'
    execute('rsync -avzr %s:%s %s' % (host, remote_path, local_path))
    local_path += relative_path
    return local_path, relative_path

def remote_restore(local_path, relative_path, host, database):
    remote_path = './backups/'
    execute('rsync -avzr %s %s:%s' % (local_path, host, remote_path))
    remote_path += relative_path
    restore(remote_path, database, 'ssh %s' % host)

@task()
def copy(from_, to, to_owner=None):
    '''
    Copies the content a database into a new one. Databases may be in different
    hosts. Optionally it also allows you to specify the target owner which
    is a shortcut for calling database.owner in the same command.

    Syntax:

    invoke database.copy [from_host:]from_database [to_host:]to_database

    Note that owner only can be changed when the to_host is empty (that is,
    database is copied to the local machine).
    '''
    if ':' in from_:
        from_host, from_database = from_.split(':')
    else:
        from_host, from_database = None, from_
    if ':' in to:
        to_host, to_database = to.split(':')
    else:
        to_host, to_database = None, to
    if not from_host and not to_host:
        if local_copy_with_template(from_database, to_database, to_owner):
            return

    # Dump
    if from_host:
        local_path, relative_path = remote_dump(from_host, from_database)
    else:
        local_path, relative_path = dump(from_database)

    # Restore
    if to_host:
        execute('ssh %s createdb %s' % (to_host, to_database))
        remote_restore(local_path, relative_path, to_host, to_database)
    else:
        execute('createdb %s' % to_database)
        restore(local_path, to_database)
        if to_owner:
            owner(to_database, to_owner)


@task()
def cluster(database):
    '''
    Runs CLUSTER to all tables in the database using its primary key (which
    should be the "id" field in Tryton tables).

    This may reduce substatially the size of the database and can be run
    concurrently with other processes.

    Note that decreasing the database size may not always improve
    performance (it may degradate writes in some circumstances).
    '''
    connection = psycopg2.connect('dbname=%s' % database)
    cursor = connection.cursor()
    cursor.execute("SELECT table_name, table_schema FROM information_schema.tables WHERE "
        "table_type = 'BASE TABLE' AND table_schema='public'")
    for table, schema in cursor.fetchall():
        try:
            query = 'CLUSTER "%s"."%s" USING "%s_pkey"' % (schema, table,
                    table)
            cursor.execute(query)
            connection.commit()
        except psycopg2.ProgrammingError:
            print('Error executing: %s' % query)
            connection.rollback()
    connection.close()


DatabaseCollection = Collection()
DatabaseCollection.add_task(drop)
DatabaseCollection.add_task(dump)
DatabaseCollection.add_task(owner)
DatabaseCollection.add_task(copy)
DatabaseCollection.add_task(cluster)
