#!/usr/bin/env python
from invoke import task, Collection
import os
import doctest
import unittest


def _load(database, scenario, lang_codes=None, config_file=None):
    os.environ['TRYTOND_DATABASE_URI'] = 'postgresql://'
    os.environ['DB_NAME'] = database

    if config_file:
        from trytond.config import config
        config.update_etc(config_file)

    _create_db(database, lang_codes=lang_codes, config_file=config_file)

    import trytond.tests.test_tryton
    from trytond.tests.test_tryton import doctest_setup
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(doctest.DocFileSuite(scenario, module_relative=False,
            encoding='utf-8'))

    unittest.TextTestRunner(verbosity=True).run(suite)

def _create_db(database, lang_codes=None, config_file=None):
    """
    Create and set active languages if database doesn't exists.
    Otherwise, do nothing.
    """
    os.environ['TRYTOND_DATABASE_URI'] = 'postgresql://'
    os.environ['DB_NAME'] = database

    if config_file:
        from trytond.config import config
        config.update_etc(config_file)

    from trytond.tests.test_tryton import db_exist, create_db
    if not db_exist():
        create_db()
        if _set_active_languages(database, lang_codes=lang_codes):
            _update_all(database)
        return True
    return False

def _set_active_languages(database, lang_codes=None):
    from trytond.pool import Pool
    from trytond.transaction import Transaction

    pool = Pool(database)
    with Transaction().start(database, 0) as transaction:
        Lang = pool.get('ir.lang')
        User = pool.get('res.user')

        if not lang_codes:
            lang_codes = ['ca_ES', 'es_ES']
        langs = Lang.search([
                ('code', 'in', lang_codes),
                ])
        assert len(langs) > 0

        # somem of langs are not translatable
        update_all = any(not l.translatable for l in langs)

        Lang.write(langs, {
                'translatable': True,
                })

        # Set default lang (first lang code) as users' language
        default_langs = [l for l in langs if l.code == lang_codes[0]]
        if not default_langs:
            default_langs = langs
        users = User.search([])
        if users:
            User.write(users, {
                    'language': default_langs[0].id,
                    })

        transaction.cursor.commit()

        return update_all


def _update_all(database):
    from trytond.pool import Pool
    from trytond.transaction import Transaction

    pool = Pool(database)
    with Transaction().start(database, 0) as transaction:
        Lang = pool.get('ir.lang')

        langs = Lang.search([
            ('translatable', '=', True),
            ])
        lang = [x.code for x in langs]

    pool.init(update=['ir'], lang=lang)


@task()
def create_db(database, lang_codes=None, config_file=None):
    _create_db(database, lang_codes=lang_codes, config_file=config_file)


@task()
def load(database, scenario, lang_codes=None, config_file=None):
    _load(database, scenario, lang_codes=lang_codes,
        config_file=config_file)


StartupCollection = Collection()
StartupCollection.add_task(create_db)
StartupCollection.add_task(load)
