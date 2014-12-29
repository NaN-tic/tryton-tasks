#!/usr/bin/env python
from invoke import task, Collection
import os
import doctest
import unittest


def _load(database, scenario, create=False):
    os.environ['TRYTOND_DATABASE_URI'] = 'postgresql://'
    os.environ['DB_NAME'] = database
    from trytond.tests.test_tryton import db_exist, create_db
    if not db_exist():
        create_db()
    import trytond.tests.test_tryton
    from trytond.tests.test_tryton import doctest_setup
    suite = trytond.tests.test_tryton.suite()
    if create:
        suite.addTests(doctest.DocFileSuite(
            scenario, module_relative=False,
            setUp=doctest_setup, encoding='utf-8'))
    else:
        suite.addTests(doctest.DocFileSuite(
            scenario, module_relative=False, encoding='utf-8'))

    unittest.TextTestRunner(verbosity=True).run(suite)


@task()
def load(database, scenario, create=False):
    _load(database, scenario, create)


StartupCollection = Collection()
StartupCollection.add_task(load)
