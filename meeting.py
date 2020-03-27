#!/usr/bin/env python
import os
import sys
import datetime
import shutil
from invoke import task, Collection
from .utils import t

TEMPLATE = """
Hora inici:
Hora final:


Assistents
----------

-

 -

- nan-tic

 -


Ordre del dia
-------------


Contingut
---------
"""

@task()
def create(context):
    today = datetime.date.today().strftime('%Y-%m-%d')
    filename = 'doc/meetings/%s.rst' % today
    if os.path.exists(filename):
        sys.stderr.write('%s already exists\n' % t.red(filename))
        return

    f = open(filename, 'w')
    f.write('%s\n' % today)
    f.write('%s\n' % ('=' * len(today)))
    f.write(TEMPLATE)
    f.close()

    print t.green('Created meeting file %s' % filename)


MeetingCollection = Collection()
MeetingCollection.add_task(create)
