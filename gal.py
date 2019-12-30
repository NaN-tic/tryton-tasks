# encoding: utf-8
#!/usr/bin/env python
import os
import sys
import time
import subprocess
import hgapi
import random
import json
import datetime
import codecs
import iban
from functools32 import lru_cache
from dateutil.relativedelta import relativedelta
from datetime import timedelta
from decimal import Decimal
from invoke import task, Collection

from .utils import t

global restore_step
global commit_msg
restore_step = True

directory = os.path.abspath(os.path.normpath(os.path.join(os.getcwd(),
                    'trytond')))
proteus_directory = os.path.abspath(os.path.normpath(os.path.join(os.getcwd(),
                    'proteus')))

if os.path.isdir(directory):
    sys.path.insert(0, directory)
if os.path.isdir(proteus_directory):
    sys.path.insert(0, proteus_directory)

try:
    from proteus import config as pconfig, Model, Wizard, \
        __version__ as proteus_version
except:
    pass


TODAY = datetime.date.today()

commits_enabled = True


def random_datetime(start, end):
    """
    This function will return a random datetime between two datetime
    objects.
    """
    delta = end - start
    int_delta = (delta.days * 24 * 60 * 60) + delta.seconds
    random_second = random.randrange(int_delta)
    return start + timedelta(seconds=random_second)

def check_output(*args):
    print t.bold(' '.join(args))
    process = subprocess.Popen(args, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    data = stdout + stderr
    if process.returncode:
        print stdout, t.red(stderr)
    else:
        print t.green('Ok')
    return data

def connect_database(database=None, password='admin',
        database_type='postgresql', language=None):
    if database is None:
        database = 'gal'
    if language is None:
        language = 'en_US'
    global config
    global version
    if proteus_version.startswith('3.2'):
        config = pconfig.set_trytond(database, database_type=database_type,
            password=password, language=language, config_file='trytond.conf')
    else:
        os.environ['TRYTOND_DATABASE_URI'] = '%s:///' % database_type
        os.environ['DB_NAME'] = database

        # Tries to use sqlite without these two lines:
        from trytond.config import config
        config.set('database', 'uri', '%s://' % database_type)

        from trytond.tests.test_tryton import db_exist

        if not db_exist():
            from trytond.protocols.dispatcher import create as tcreate
            tcreate(database, None, language, password)

        config = pconfig.set_trytond(database, config_file='trytond.conf')
        config.pool.test = False


def database_name():
    import uuid
    return uuid.uuid4()


def dump(dbname=None):
    if dbname is None:
        dbname = 'gal'
        from trytond import backend
        Database = backend.get('Database')
        Database(dbname).close()
        Database('template1').close()
        # Sleep to let connections close
        time.sleep(1)
    dump_file = 'gal.sql'
    # Ensure gal repository exists before dump
    gal_repo()
    check_output('pg_dump', '-f', gal_path(dump_file), dbname)
    gal_repo().hg_add(dump_file)


def dropdb(dbname=None):
    if dbname is None:
        dbname = 'gal'
    check_output('dropdb', dbname)


def restore(dbname=None):
    global restore_step
    if not restore_step:
        return

    if dbname is None:
        dbname = 'gal'
    dump_file = 'gal.sql'
    dropdb(dbname)
    check_output('createdb', dbname)
    check_output('psql', '-f', gal_path(dump_file), dbname)

def gal_path(path=None):
    res = 'gal'
    if path:
        res = os.path.join(res, path)
    return res

def gal_repo():
    path = gal_path()
    if os.path.exists(path) and not os.path.isdir(path):
        print >>sys.stderr, t.red('Error: gal file exists')
        sys.exit(1)
    if os.path.isdir(path) and not os.path.isdir(os.path.join(path, '.hg')):
        print >>sys.stderr, t.red('Invalid gal repository')
        sys.exit(1)
    repo = gitapi.Repo(path)
    if not os.path.exists(path):
        os.mkdir(path)
        repo.hg_init()
    return repo

def gal_action(action, **kwargs):
    global commit_msg
    commit_msg = json.dumps((action, kwargs))

def gal_commit(do_dump=True):
    if not commits_enabled:
        return
    if do_dump:
        dump()
    gal_repo().hg_commit(commit_msg)

@lru_cache()
def module_installed(module):
    Module = Model.get('ir.module.module')
    return bool(Module.find([
            ('name', '=', module),
            ]))

@task()
def create(language=None, password=None):
    """
    Creates a new tryton database and stores it in the gal repository.
    """
    gal_repo()
    gal_action('create', language=language, password=password)
    dropdb()
    connect_database(language=language)
    gal_commit()

@task()
def replay(name):
    """
    Executes all steps needed to create a database like the one in the gal
    repository.
    """
    repo = gal_repo()
    print 'Actions to replay:'
    has_set = False
    for revision in repo.revisions(slice(0, 'tip')):
        description = revision.desc
        action, parameters = json.loads(description)
        if action == 'set':
            has_set = True
        print t.bold('%s(%s)' % (action, parameters))

    print
    if has_set:
        print >>sys.stderr, t.red('It is not possible to replay tip '
            'version because there is a set() operation in the list of '
            'commands to execute')
        sys.exit(1)

    # Disable commits before replaying
    commits_enabled = False
    print 'Replaying actions:'
    for revision in repo.revisions(slice(0, 'tip')):
        description = revision.desc
        action, parameters = json.loads(description)
        print t.bold('%s(%s)' % (action, parameters))
        # TODO: This is not safe. Run with care.
        eval('%s(%s)' % (action, parameters))

@task()
def get(name):
    """
    Restores current gal database with the given database name
    """
    restore(name)

@task()
def set(name):
    """
    Saves the given database as current gal database
    """
    gal_action('set')
    dump(name)
    gal_commit(do_dump=False)

@task()
def build(filename=None, no_restore=False):
    """
    Creates a database with the commands found in the specified filename.

    If no filename is given it will search for a file named 'Galfile'
    """
    if filename is None:
        filename = 'Galfile'
    print "Building %s..." % filename

    global restore_step
    resore_step = True
    if no_restore:
        restore_step = False

    with codecs.open(filename, 'r', 'utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                print t.bold(unicode(line))
                eval(line)


@task()
def galfile():
    """
    Prints the Galfile to be used to reproduce current gal database.

    The result can be used by gal.build operation.
    """
    repo = gal_repo()
    has_set = False
    for revision in repo.revisions(slice(0, 'tip')):
        description = revision.desc
        action, parameters = json.loads(description)
        if action == 'set':
            has_set = True

    if has_set:
        print >>sys.stderr, t.red('It will not be possible to build the '
            'generated Galfile because it contains at least one set command.')

    # Disable commits before replaying
    for revision in repo.revisions(slice(0, 'tip')):
        description = revision.desc
        action, parameters = json.loads(description)
        print '%s(**%s)' % (action, parameters)


@task()
def execute_script(script):
    gal_action('execute_script', script=script)

    restore()
    connect_database()

    if script.endswith('.rst'):
        import unittest
        import doctest
        import trytond.tests.test_tryton
        suite = trytond.tests.test_tryton.suite()
        suite.addTests(doctest.DocFileSuite(script, module_relative=False,
                encoding='utf-8'))
        result = unittest.TestResult()
        suite.run(result)
        if result.errors or result.failures:
            if result.errors:
                print "Errors:"
                for error in result.errors:
                    print error[0]
                    print error[1]
                    print
                print
            if result.failures:
                print "Failures:"
                for failure in result.failures:
                    print failure[0]
                    print failure[1]
                    print
            # Ensure we do not commit
            return
    elif script.endswith('.py'):
        with open(script, 'r') as f:
            code = f.read()
        exec(code)
    else:
        print >>sys.stderr, t.red("Don't know how to execute %s" % script)
        sys.exit(1)

    gal_commit()

#
# Extension commands
#
@task()
def update_all():
    """
    Update all modules. Equivalent to execute trytond with "-u all" parameter
    """
    gal_action('update_all')
    restore()
    connect_database()

    upgraded_modules = upgrade_modules(all=True)

    gal_commit()
    return upgraded_modules

def upgrade_modules(modules=None, all=False):
    '''
    Function get from tryton_demo.py in tryton-tools repo:
    http://hg.tryton.org/tryton-tools
    '''
    assert all or modules

    Module = Model.get('ir.module.module')
    if all:
        modules = Module.find([
                ('state', '=', 'installed'),
                ])
    else:
        modules = Module.find([
                ('name', 'in', modules),
                ('state', '=', 'installed'),
                ])

    Module.upgrade([x.id for x in modules], config.context)
    Wizard('ir.module.module.install_upgrade').execute('upgrade')

    ConfigWizardItem = Model.get('ir.module.module.config_wizard.item')
    for item in ConfigWizardItem.find([('state', '!=', 'done')]):
        item.state = 'done'
        item.save()

    upgraded_modules = [x.name for x in Module.find([
                ('state', '=', 'to_upgrade'),
                ])]
    return upgraded_modules

@task()
def set_active_languages(lang_codes=None):
    """
    Sets the given languages (for example 'ca_ES,es_ES') as active languages
    in the database.

    If no languages are given 'ca_ES,es_ES' are used by default.
    """
    gal_action('set_active_languages', lang_codes=lang_codes)
    restore()
    connect_database()
    if lang_codes:
        lang_codes = lang_codes.split(',')

    Lang = Model.get('ir.lang')
    User = Model.get('res.user')

    if not lang_codes:
        lang_codes = ['ca_ES', 'es_ES']
    langs = Lang.find([
            ('code', 'in', lang_codes),
            ])
    assert len(langs) > 0

    Lang.write([l.id for l in langs], {
            'translatable': True,
            }, config.context)

    default_langs = [l for l in langs if l.code == lang_codes[0]]
    if not default_langs:
        default_langs = langs
    users = User.find([])
    if users:
        User.write([u.id for u in users], {
                'language': default_langs[0].id,
                }, config.context)

    # Reload context
    User = Model.get('res.user')
    config._context = User.get_preferences(True, config.context)

    if not all(l.translatable for l in langs):
        # langs is fetched before wet all translatable
        print "Upgrading all because new translatable languages has been added"
        upgrade_modules(config, all=True)
    gal_commit()


@task()
def install_modules(modules):
    '''
    Installs the given modules (for example, 'party,product') to current gal
    database.

    Function taken from tryton_demo.py in tryton-tools repo:
    http://hg.tryton.org/tryton-tools
    '''
    gal_action('install_modules', modules=modules)
    restore()
    connect_database()
    # Clear cache
    module_installed.cache_clear()

    modules = modules.split(',')

    Module = Model.get('ir.module.module')
    modules = Module.find([
            ('name', 'in', modules),
            #('state', '!=', 'installed'),
            ])
    Module.install([x.id for x in modules], config.context)
    modules = [x.name for x in Module.find([
                ('state', 'in', ('to install', 'to_upgrade')),
                ])]
    Wizard('ir.module.module.install_upgrade').execute('upgrade')

    ConfigWizardItem = Model.get('ir.module.module.config_wizard.item')
    for item in ConfigWizardItem.find([('state', '!=', 'done')]):
        item.state = 'done'
        item.save()

    installed_modules = [m.name
        for m in Module.find([('state', '=', 'installed')])]

    gal_commit()
    return modules, installed_modules


@task()
def load_spanish_banks():
    '''
    Execute Load Spanish Banks wizard. Requires bank_es module
    '''
    gal_action('load_spanish_banks')
    restore()
    connect_database()
    Wizard('load.banks').execute('accept')
    gal_commit()


@task()
def load_spanish_zips():
    '''
    Execute Load Spanish Zips wizard. Requires country_zip_es module
    '''
    gal_action('load_spanish_zips')
    restore()
    connect_database()
    Wizard('load.country.zips').execute('accept')
    gal_commit()

@lru_cache()
def get_payment_terms():
    Term = Model.get('account.invoice.payment_term')
    return Term.find([])

@lru_cache()
def get_payment_types(kind):
    Type = Model.get('account.payment.type')
    return Type.find([('kind', '=', kind)])

@lru_cache()
def get_languages():
    Lang = Model.get('ir.lang')
    return Lang.find([
            ('code', 'in', ['ca_ES', 'es_ES', 'en_US']),
            ])

@lru_cache()
def get_price_lists():
    PriceList = Model.get('product.price_list')
    return PriceList.find([])

@lru_cache()
def get_banks():
    if not module_installed('bank'):
        return
    Bank = Model.get('bank')
    return Bank.find([])

@lru_cache()
def get_company():
    Company = Model.get('company.company')
    companies = Company.find([])
    if companies:
        return companies[0]

@lru_cache()
def get_model_id(module, fs_id):
    ModelData = Model.get('ir.model.data')
    data, = ModelData.find([
            ('module', '=', 'account_es'),
            ('fs_id', '=', fs_id),
            ])
    Class = Model.get(data.model)
    return data.model, data.db_id

def get_object(module, fs_id):
    model, id = get_model_id(module, fs_id)
    Class = Model.get(model)
    return Class(id)

def create_party(name, street=None, streetbis=None, zip=None, city=None,
        subdivision_code=None, country_code='ES', phone=None, website=None,
        email=None, address_name=None, account_payable=None,
        account_receivable=None):
    Address = Model.get('party.address')
    ContactMechanism = Model.get('party.contact_mechanism')
    Country = Model.get('country.country')
    Party = Model.get('party.party')
    Subdivision = Model.get('country.subdivision')

    parties = Party.find([('name', '=', name)])
    if parties:
        return parties[0]

    country, = Country.find([('code', '=', country_code)])
    if subdivision_code:
        subdivision, = Subdivision.find([('code', '=', subdivision_code)])
    else:
        subdivision = None

    if zip is None:
        # Create a ZIP from Barcelona if none was provided
        zip = '08' + str(random.randrange(1000)).zfill(3)

    party = Party(name=name)
    party.addresses.pop()
    party.addresses.append(
        Address(
            name=address_name,
            street=street,
            streetbis=streetbis,
            zip=zip,
            city=city,
            country=country,
            subdivision=subdivision))
    if phone:
        party.contact_mechanisms.append(
            ContactMechanism(type='phone',
                value=phone))
    if website:
        party.contact_mechanisms.append(
            ContactMechanism(type='website',
                value=website))
    if email:
        party.contact_mechanisms.append(
            ContactMechanism(type='email',
                value=email))
    party.lang = random.choice(get_languages())

    if account_payable:
        party.account_payable = account_payable
    if account_receivable:
        party.account_receivable = account_receivable
    if hasattr(party, 'customer_payment_term'):
        terms = get_payment_terms()
        if terms:
            term = random.choice(terms)
            party.customer_payment_term = term
            party.supplier_payment_term = term
    if hasattr(party, 'customer_payment_type'):
        types = get_payment_types('receivable')
        if types:
            party.customer_payment_type = random.choice(types)
    if hasattr(party, 'customer_payment_type'):
        types = get_payment_types('payable')
        if types:
            party.supplier_payment_type = random.choice(types)
    if hasattr(party, 'sale_price_list'):
        price_lists = get_price_lists()
        if price_lists:
            party.sale_price_list = random.choice(price_lists)
    if hasattr(party, 'include_347'):
        party.include_347 = True

    party.save()
    return party

@task()
def create_random_parties(count=4000):
    """
    Create 'count' parties taking random information from the following files:
    - companies.txt
    - streets.txt
    - names.txt
    - surnames.txt
    """
    gal_action('create_random_parties', count=count)
    restore()
    connect_database()

    with open('tasks/companies.txt', 'r') as f:
        companies = f.read().split('\n')
    companies = [x.strip() for x in companies if x.strip()]
    with open('tasks/streets.txt', 'r') as f:
        streets = f.read().split('\n')
    streets = [x.strip() for x in streets if x.strip()]
    with open('tasks/names.txt', 'r') as f:
        names = f.read().split('\n')
    names = [x.strip() for x in names if x.strip()]
    with open('tasks/surnames.txt', 'r') as f:
        surnames = f.read().split('\n')
    surnames = [x.strip() for x in surnames if x.strip()]
    phones = ['93', '972', '973', '977', '6', '900']
    for x in xrange(count):
        company = random.choice(companies)
        name = random.choice(names)
        surname1 = random.choice(surnames)
        surname2 = random.choice(surnames)
        street = random.choice(streets)
        name = '%s %s, %s' % (surname1, surname2, name)
        street = '%s, %d' % (street, random.randrange(1, 100))
        phone = random.choice(phones)
        while len(phone) < 9:
            phone += str(random.randrange(9))
        create_party(company, street=street, zip=None, city=None,
            subdivision_code=None, country_code='ES', phone=phone,
            website=None, address_name=name)

    gal_commit()


@task()
def create_parties(count=1000):
    """
    Create 'count' parties taking random information from the following files:
    - companies.txt
    - streets.txt
    - names.txt
    - surnames.txt
    """
    gal_action('create_parties', count=count)
    restore()
    connect_database()

    with open('tasks/companies.txt', 'r') as f:
        companies = f.read().split('\n')
    companies = [x.strip() for x in companies if x.strip()]
    companies = random.sample(companies, min(len(companies), count))
    with open('tasks/streets.txt', 'r') as f:
        streets = f.read().split('\n')
    streets = [x.strip() for x in streets if x.strip()]
    with open('tasks/names.txt', 'r') as f:
        names = f.read().split('\n')
    names = [x.strip() for x in names if x.strip()]
    with open('tasks/surnames.txt', 'r') as f:
        surnames = f.read().split('\n')
    surnames = [x.strip() for x in surnames if x.strip()]
    phones = ['93', '972', '973', '977', '6', '900']
    for company in companies:
        name = random.choice(names)
        surname1 = random.choice(surnames)
        surname2 = random.choice(surnames)
        street = random.choice(streets)
        name = '%s %s, %s' % (surname1, surname2, name)
        street = '%s, %d' % (street, random.randrange(1, 100))
        phone = random.choice(phones)
        while len(phone) < 9:
            phone += str(random.randrange(9))
        create_party(company, street=street, zip=None, city=None,
            subdivision_code=None, country_code='ES', phone=phone,
            website=None, address_name=name)

    gal_commit()

@task()
def create_bank_accounts():
    gal_action('create_bank_accounts')
    restore()
    connect_database()

    Party = Model.get('party.party')
    Invoice = Model.get('account.invoice')
    banks = get_banks()
    if not module_installed('account_bank'):
        print t.red('account_bank module must be installed before creating '
            'bank accounts.')
    for party in Party.find([]):
        BankAccount = Model.get('bank.account')
        AccountNumber = Model.get('bank.account.number')

        bank = random.choice(banks)
        account = BankAccount()
        party.bank_accounts.append(account)
        account.bank = bank
        number = AccountNumber()
        account.numbers.append(number)
        country = 'ES'
        account_code = bank.bank_code
        account_code += ''.join([str(x) for x in random.sample(range(10) *
                    4, 4)])
        account_number = ''.join([str(x) for x in random.sample(range(10) *
                    12, 12)])
        number.type = 'iban'
        number.number = iban.create_iban(country, account_code, account_number)
        account.save()

        if module_installed('account_bank'):
            if hasattr(party, 'payable_bank_account'):
                party.payable_bank_account = account
            if hasattr(party, 'receivable_bank_account'):
                party.receivable_bank_account = account
            if hasattr(party, 'payable_company_bank_account'):
                company = get_company()
                if company:
                    accounts = company.party.bank_accounts
                    if accounts:
                        party.receivable_company_bank_account = accounts[0]
            if hasattr(party, 'receivable_company_bank_account'):
                company = get_company()
                if company:
                    accounts = company.party.bank_accounts
                    if accounts:
                        party.payable_company_bank_account = accounts[0]
        for invoice in Invoice.find([('party', '=', party.id)]):
            if (invoice.payment_type
                    and invoice.payment_type.account_bank == 'party'):
                invoice.bank_account = account
            invoice.save()

        party.save()
    gal_commit()

@task()
def create_product_category(name):
    """
    Creates product category with the supplied name.
    """
    gal_action('create_product_category', name=name)
    restore()
    connect_database()

    Category = Model.get('product.category')
    category = Category(name=name)
    category.save()

    gal_commit()


@task()
def create_product_categories(count=20):
    """
    Creates 'count' (20 by default) product categories.
    """
    gal_action('create_product_categories', count=count)
    restore()
    connect_database()

    Category = Model.get('product.category')
    for name in ('A', 'B', 'C', 'D', 'E'):
        category = Category(name=name)
        category.save()

    gal_commit()


def create_product(name, code="", template=None, cost_price=None,
        list_price=None, type='goods', unit=None, consumable=False):

    ProductUom = Model.get('product.uom')
    Product = Model.get('product.product')
    ProductTemplate = Model.get('product.template')
    Tax = Model.get('account.tax')
    Category = Model.get('product.category')

    categories = Category.find([])
    category = None
    if categories:
        category = random.choice(categories)

    product = Product.find([('name', '=', name), ('code', '=', code)])
    if product:
        return product[0]

    if not cost_price:
        cost_price = Decimal(random.randrange(1, 100))

    if not list_price:
        list_price = cost_price * (1 + Decimal(random.randrange(1, 100)) / 100)

    if unit is None:
        unit = ProductUom(1)

    if template is None:
        template = ProductTemplate()
        template.name = name
        template.default_uom = unit
        template.type = type
        template.consumable = consumable
        template.list_price = list_price
        template.cost_price = cost_price
        template.category = category
        if hasattr(template, 'salable'):
            template.salable = True
        if hasattr(template, 'purchasable'):
            template.purchasable = True

        if (hasattr(template, 'account_expense')
                or hasattr(template, 'account_revenue')):
            Company = Model.get('company.company')
            company = Company(1)
        if hasattr(template, 'account_expense'):
            Account = Model.get('account.account')
            expense = Account.find([
                ('kind', '=', 'expense'),
                ('company', '=', company.id),
                ])
            if expense:
                template.account_expense = expense[0]
        if hasattr(template, 'account_revenue'):
            Account = Model.get('account.account')
            revenue = Account.find([
                ('kind', '=', 'revenue'),
                ('company', '=', company.id),
                ])
            if revenue:
                template.account_revenue = revenue[0]
        if module_installed('account_es'):
            if hasattr(template, 'customer_taxes'):
                tax, = Tax.find([
                        ('template', '=',
                            get_object('account_es', 'iva_rep_21').id)
                        ])
                template.customer_taxes.append(tax)
            if hasattr(template, 'supplier_taxes'):
                tax, = Tax.find([
                        ('template', '=',
                            get_object('account_es', 'iva_sop_21').id)
                        ])
                template.supplier_taxes.append(tax)

        template.products[0].code = code
        template.save()
        product = template.products[0]
    else:
        product = Product()
        product.template = template
        product.code = code
        product.save()
    return product

@task()
def create_products(count=400):
    """
    Creates the 'count' first products from the icecat database in catalog.xml.
    """
    gal_action('create_products', count=count)
    restore()
    connect_database()

    import xmltodict
    with open('tasks/catalog.xml', 'r') as f:
        xml = xmltodict.parse(f.read())
    i = 0
    for item in xml.get('ICECAT-interface').get('files.index').get('file'):
        name = item.get('@Model_Name')
        create_product(name)
        i += 1
        if i >= count:
            break

    gal_commit()

@task()
def create_company(name, street=None, streetbis=None, zip=None, city=None,
        subdivision_code=None, country_code='ES', currency_code='EUR',
        phone=None, website=None, email=None):
    '''
    Creates a company in current gal database.

    Based on tryton_demo.py in tryton-tools repo:
    http://hg.tryton.org/tryton-tools
    '''
    gal_action('create_company', name=name, street=street, streetbis=streetbis,
        zip=zip, city=city, subdivision_code=subdivision_code,
        country_code=country_code, currency_code=currency_code, phone=phone,
        website=website, email=email)
    restore()
    connect_database()

    Company = Model.get('company.company')
    Currency = Model.get('currency.currency')

    party = create_party(name, street=street, streetbis=streetbis, zip=zip,
        city=city, subdivision_code=subdivision_code, country_code=country_code,
        phone=phone, website=website, email=email)

    companies = Company.find([('party', '=', party.id)])
    if companies:
        return companies[0]

    currency, = Currency.find([('code', '=', currency_code)])

    company_config = Wizard('company.company.config')
    company_config.execute('company')
    company = company_config.form
    company.party = party
    company.currency = currency
    company_config.execute('add')

    # Reload context
    User = Model.get('res.user')
    config._context = User.get_preferences(True, config.context)

    company, = Company.find([('party', '=', party.id)])

    gal_commit()
    return company

@task()
def create_employee(name, company=None, user=None):
    """
    Creates the employee with the given name in the given company and links
    it with the given user.

    If company is not set the first company found on the system is used.
    If user is not set, 'admin' user is used.
    """
    gal_action('create_employee', name=name, company=company, user=user)
    restore()
    connect_database()

    Company = Model.get('company.company')
    Employee = Model.get('company.employee')
    Party = Model.get('party.party')
    User = Model.get('res.user')

    if user is None:
        user = 'admin'
    if company:
        company, = Company.find([('name', '=', company)])
    else:
        company, = Company.find([], limit=1)

    party = Party()
    party.name = name
    party.save()

    employee = Employee()
    employee.party = party
    employee.company = company
    employee.save()

    user, = User.find([('login', '=', user)], limit=1)
    user.employees.append(employee)
    user.employee = employee
    user.save()

    gal_commit()

@task()
def create_account_chart(company, module=None, fs_id=None, digits=None):
    """
    Creates the chart of accounts defined by module and fs_id for the given
    company.

    If no 'module' and 'fs_id' are given, the last template chart created is
    used.
    """
    gal_action('create_account_chart', company=company, module=module,
        fs_id=fs_id, digits=digits)
    restore()
    connect_database()

    AccountTemplate = Model.get('account.account.template')
    Account = Model.get('account.account')
    Company = Model.get('company.company')
    ModelData = Model.get('ir.model.data')

    root_accounts = Account.find([('parent', '=', None)])
    if root_accounts:
        return

    if module and fs_id:
        data = ModelData.find([
                ('module', '=', module),
                ('fs_id', '=', fs_id),
                ], limit=1)

        assert len(data) == 1, ('Unexpected num of root templates '
            'with name "%s": %s' % (module, fs_id))
        template = data[0].db_id
        template = AccountTemplate(template)
    else:
        template, = AccountTemplate.find([('parent', '=', None)],
            order=[('id', 'DESC')], limit=1)

    company, = Company.find([
            ('party.name', '=', company),
            ])

    create_chart = Wizard('account.create_chart')
    create_chart.execute('account')
    create_chart.form.account_template = template
    create_chart.form.company = company
    if digits:
        create_chart.form.account_code_digits = int(digits)
    create_chart.execute('create_account')

    receivable = Account.find([
            ('kind', '=', 'receivable'),
            ('company', '=', company.id),
            ])
    receivable = receivable[0]
    payable = Account.find([
            ('kind', '=', 'payable'),
            ('company', '=', company.id),
            ])[0]
    #revenue, = Account.find([
    #        ('kind', '=', 'revenue'),
    #        ('company', '=', company.id),
    #        ])
    #expense, = Account.find([
    #        ('kind', '=', 'expense'),
    #        ('company', '=', company.id),
    #        ])
    #cash, = Account.find([
    #        ('kind', '=', 'other'),
    #        ('company', '=', company.id),
    #        ('name', '=', 'Main Cash'),
    #        ])
    create_chart.form.account_receivable = receivable
    create_chart.form.account_payable = payable
    create_chart.execute('create_properties')

    gal_commit()

@task()
def create_fiscal_year(company, year=None):
    """
    It creates a new fiscal year with monthly periods and the appropriate
    invoice sequences for the given company.

    If no year is specified the current year is used.
    """
    gal_action('create_fiscal_year', company=company, year=None)
    restore()
    connect_database()

    FiscalYear = Model.get('account.fiscalyear')
    Module = Model.get('ir.module.module')
    Sequence = Model.get('ir.sequence')
    SequenceStrict = Model.get('ir.sequence.strict')
    Company = Model.get('company.company')

    if year is None:
        year = TODAY.year
    date = datetime.date(int(year), 1, 1)

    company, = Company.find([('party.name', '=', company)])

    installed_modules = [m.name
        for m in Module.find([('state', '=', 'installed')])]

    post_move_sequence = Sequence.find([
            ('name', '=', '%s' % year),
            ('code', '=', 'account_move'),
            ('company', '=', company.id),
            ])
    if post_move_sequence:
        post_move_sequence = post_move_sequence[0]
    else:
        post_move_sequence = Sequence(name='%s' % year,
            code='account.move', company=company)
        post_move_sequence.save()

    fiscalyear = FiscalYear.find([
            ('name', '=', '%s' % year),
            ('company', '=', company.id),
            ])
    if fiscalyear:
        fiscalyear = fiscalyear[0]
    else:
        fiscalyear = FiscalYear(name='%s' % year)
        fiscalyear.start_date = date + relativedelta(month=1, day=1)
        fiscalyear.end_date = date + relativedelta(month=12, day=31)
        fiscalyear.company = company
        fiscalyear.post_move_sequence = post_move_sequence
        if 'account_invoice' in installed_modules:
            for attr, name in (('out_invoice_sequence', 'Customer Invoice'),
                    ('in_invoice_sequence', 'Supplier Invoice'),
                    ('out_credit_note_sequence', 'Customer Credit Note'),
                    ('in_credit_note_sequence', 'Supplier Credit Note')):
                sequence = SequenceStrict.find([
                        ('name', '=', '%s %s' % (name, year)),
                        ('code', '=', 'account.invoice'),
                        ('company', '=', company.id),
                        ])
                if sequence:
                    sequence = sequence[0]
                else:
                    sequence = SequenceStrict(
                        name='%s %s' % (name, year),
                        code='account.invoice',
                        company=company)
                    sequence.save()
                setattr(fiscalyear, attr, sequence)
        fiscalyear.save()

    if not fiscalyear.periods:
        FiscalYear.create_period([fiscalyear.id], config.context)

    gal_commit()
    return fiscalyear

@task()
def create_payment_term(name, type='remainder', percentage=None, divisor=None,
        amount=None, day=None, month=None, weekday=None, months=0, weeks=0,
        days=0):
    """
    It creates a payment term with the supplied values.
    Default values are to create a Cash payment term
    """
    gal_action('create_payment_term', name=name, type=type,
        percentage=percentage, divisor=divisor, amount=amount, day=day,
        month=month, weekday=weekday, months=months, weeks=weeks, days=days)
    restore()
    connect_database()

    Term = Model.get('account.invoice.payment_term')
    TermLine = Model.get('account.invoice.payment_term.line')

    term = Term()
    term.name = name
    term.active = True
    line = TermLine()
    line.type = type
    if percentage is not None:
        line.percentage = percentage
    if divisor is not None:
        line.divisor = divisor
    if amount is not None:
        line.amount = amount
    line.day = day
    line.month = month
    line.weekday = weekday
    line.months = months
    line.weeks = weeks
    line.days = days
    term.lines.append(line)
    term.save()

    gal_commit()
    return term


@task()
def create_payment_terms():
    """
    It creates 3 payment terms:
    - 30 days
    - 60 days
    - 90 days
    """
    gal_action('create_payment_terms')
    restore()
    connect_database()

    Term = Model.get('account.invoice.payment_term')
    TermLine = Model.get('account.invoice.payment_term.line')

    term = Term()
    term.name = '30 D'
    term.active = True
    line = TermLine()
    line.months = 1
    term.lines.append(line)
    term.save()

    term = Term()
    term.name = '60 D'
    line = TermLine()
    line.months = 2
    term.lines.append(line)
    term.save()

    term = Term()
    term.name = '90 D'
    line = TermLine()
    line.months = 3
    term.lines.append(line)
    term.save()

    gal_commit()


@task()
def create_payment_types(language='ca'):
    """
    """
    gal_action('create_payment_types')
    restore()
    connect_database()

    Type = Model.get('account.payment.type')
    names = {
        'bank-transfer': {
            'ca': 'Transferència Bancària',
            'en': 'Bank Transfer',
            'es': 'Transferencia Bancaria',
            },
        'direct-debit': {
            'ca': 'Domiciliació bancària',
            'en': 'Direct Debit',
            'es': 'Domiciliación bancaria',
            },
        'cash': {
            'ca': 'Efectiu',
            'en': 'Cash',
            'es': 'Efectivo',
            },
        'credit-card': {
            'ca': 'Targeta de crèdit',
            'en': 'Credit Card',
            'es': 'Tarjeta de crédito',
            },
        }

    t = Type()
    t.name = names['bank-transfer'][language]
    t.kind = 'receivable'
    if hasattr(t, 'account_bank'):
        t.account_bank = 'company'
    t.save()

    t = Type()
    t.name = names['direct-debit'][language]
    t.kind = 'receivable'
    if hasattr(t, 'account_bank'):
        t.account_bank = 'party'
    t.save()

    t = Type()
    t.name = names['cash'][language]
    t.kind = 'receivable'
    if hasattr(t, 'account_bank'):
        t.account_bank = 'none'
    t.save()

    t = Type()
    t.name = names['bank-transfer'][language]
    t.kind = 'payable'
    if hasattr(t, 'account_bank'):
        t.account_bank = 'party'
    t.save()

    t = Type()
    t.name = names['direct-debit'][language]
    t.kind = 'payable'
    if hasattr(t, 'account_bank'):
        t.account_bank = 'company'
    t.save()

    t = Type()
    t.name = names['cash'][language]
    t.kind = 'payable'
    if hasattr(t, 'account_bank'):
        t.account_bank = 'none'
    t.save()

    gal_commit()


@task()
def create_opportunities(count=100, linecount=10):
    """
    It randomly creates leads and opportunities

    It creates 'count' leads.
    - It converts 80% of the converted leads into opportunities
    - It converts 40% of the opportunities as lost
    - It sets 80% of the remaining opportunities are converted.
    """
    gal_action('create_opportunities', count=count, linecount=linecount)
    restore()
    connect_database()

    Opportunity = Model.get('sale.opportunity')
    OpportunityLine = Model.get('sale.opportunity.line')
    Product = Model.get('product.product')
    Party = Model.get('party.party')
    Term = Model.get('account.invoice.payment_term')

    parties = Party.find([])
    products = Product.find([('salable', '=', True)])
    terms = Term.find([])

    for x in xrange(count):
        opp = Opportunity()
        party = random.choice(parties)
        product = random.choice(products)
        opp.description = '%s - %s' % (party.rec_name, product.rec_name)
        opp.party = party
        if party.addresses:
            opp.address = party.addresses[0]
        opp.start_date = random_datetime(TODAY + relativedelta(months=-12),
            TODAY)
        if not opp.payment_term:
            opp.payment_term = random.choice(terms)
        opp.probability = random.randrange(1, 9) * 10
        opp.amount = random.randrange(1, 10) * 1000

        for lc in xrange(random.randrange(1, linecount)):
            line = OpportunityLine()
            opp.lines.append(line)
            line.product = random.choice(products)
            line.quantity = random.randrange(1, 20)
        opp.save()

    gal_commit()

@task()
def process_opportunities():
    """
    It randomly processes leads

    - It converts 80% of the leads into opportunities
    - It converts 40% of the opportunities as lost
    - It sets 80% of the remaining opportunities as converted (sale created)
    """
    gal_action('process_opportunities')
    restore()
    connect_database()

    Opportunity = Model.get('sale.opportunity')
    opps = Opportunity.find([('state', '=', 'lead')])
    opps = [x.id for x in opps]
    opps = random.sample(opps, int(0.8 * len(opps)))
    if opps:
        Opportunity.opportunity(opps, config.context)

    lost = random.sample(opps, int(0.4 * len(opps)))
    if lost:
        Opportunity.lost(lost, config.context)

    # Only convert non-lost opportunities
    nopps = []
    for opp in opps:
        if opp in lost:
            continue
        nopps.append(opp)
    opps = nopps
    opps = random.sample(opps, int(0.8 * len(opps)))
    opps = [Opportunity(x) for x in opps]
    if opps:
        wizard = Wizard('sale.opportunity.convert_opportunity', opps)
    gal_commit()

@task()
def create_price_lists(count=5, productcount=10, categorycount=2):
    """
    It creates 'count' pricelists using random products and quantities
    """
    gal_action('creat_price_lists', count=count, productcount=productcount,
        categorycount=categorycount)
    restore()
    connect_database()

    PriceList = Model.get('product.price_list')
    PriceListLine = Model.get('product.price_list.line')
    Product = Model.get('product.product')
    Category = Model.get('product.category')
    category_module = module_installed('product_price_list_category')

    categories = Category.find()
    products = Product.find([('salable', '=', True)])
    for c in xrange(count):
        price_list = PriceList()
        price_list.name = str(c)

        sequence = 1
        for lc in xrange(random.randrange(1, productcount)):
            line = PriceListLine()
            price_list.lines.append(line)
            line.sequence = sequence
            line.product = random.choice(products)
            line.formula = 'unit_price * 0.90'
            sequence += 1

        if category_module:
            for lc in xrange(random.randrange(1, categorycount)):
                line = PriceListLine()
                price_list.lines.append(line)
                line.sequence = sequence
                line.category = random.choice(categories)
                line.formula = 'unit_price * 0.95'
                sequence += 1

        line = PriceListLine()
        price_list.lines.append(line)
        line.sequence = sequence
        line.formula = 'unit_price'

        price_list.save()

    gal_commit()


@task()
def create_sales(count=100, linecount=10):
    """
    It creates 'count' sales using random products (linecount maximum)
    and parties.

    If 'count' is not specified 100 is used by default.
    If 'linecount' is not specified 10 is used by default.
    """
    gal_action('create_sales', count=count, linecount=linecount)
    restore()
    connect_database()

    Sale = Model.get('sale.sale')
    SaleLine = Model.get('sale.line')
    Party = Model.get('party.party')
    Product = Model.get('product.product')
    Term = Model.get('account.invoice.payment_term')

    parties = Party.find([])
    products = Product.find([('salable', '=', True)])
    terms = Term.find([])

    for c in xrange(count):
        sale = Sale()
        sale.sale_date = random_datetime(TODAY + relativedelta(months=-12),
            TODAY)
        sale.party = random.choice(parties)
        if not sale.payment_term:
            sale.payment_term = random.choice(terms)

        for lc in xrange(random.randrange(1, linecount)):
            line = SaleLine()
            sale.lines.append(line)
            line.product = random.choice(products)
            line.quantity = random.randrange(1, 20)
        sale.save()

    gal_commit()


@task()
def process_sales():
    """
    It randomly processes some sales:

    10% of existing draft sales are left in draft state
    10% of existing draft sales are left in quotation state
    10% of existing draft sales are left in confirmed state
    70% of existing draft sales are left in processed state
    """
    gal_action('create_payment_terms')
    restore()
    connect_database()

    Sale = Model.get('sale.sale')

    sales = Sale.find([('state', '=', 'draft')])

    #TODO: Put random sale dates
    # sale.sale_date = random_datetime(TODAY + relativedelta(months=-12),
    #        TODAY)

    # Change 90% to quotation state
    sales = random.sample(sales, int(0.9 * len(sales)))
    Sale.quote([x.id for x in sales], config.context)

    # Change 90% to confirmed state
    sales = random.sample(sales, int(0.9 * len(sales)))
    Sale.confirm([x.id for x in sales], config.context)

    # Change 90% to processed state
    sales = random.sample(sales, int(0.9 * len(sales)))
    Sale.process([x.id for x in sales], config.context)

    gal_commit()

@task()
def create_purchases(count=100, linecount=10):
    """
    It creates 'count' purchases using random products (linecount maximum)
    and parties.

    If 'count' is not specified 100 is used by default.
    If 'linecount' is not specified 10 is used by default.
    """
    gal_action('create_purchases', count=count, linecount=linecount)
    restore()
    connect_database()

    Purchase = Model.get('purchase.purchase')
    PurchaseLine = Model.get('purchase.line')
    Party = Model.get('party.party')
    Product = Model.get('product.product')
    Term = Model.get('account.invoice.payment_term')

    parties = Party.find([])
    products = Product.find([('purchasable', '=', True)])
    terms = Term.find([])

    for c in xrange(count):
        purchase = Purchase()
        purchase.party = random.choice(parties)
        if not purchase.payment_term:
            purchase.payment_term = random.choice(terms)

        for lc in xrange(random.randrange(1, linecount)):
            line = PurchaseLine()
            purchase.lines.append(line)
            line.product = random.choice(products)
            line.quantity = random.randrange(1, 20)
        purchase.save()

    gal_commit()


@task()
def process_purchases():
    """
    It randomly processes some purchases:

    10% of existing draft purchases are left in draft state
    10% of existing draft purchases are left in quotation state
    80% of existing draft purchases are left in confirmed state
    """
    gal_action('create_payment_terms')
    restore()
    connect_database()

    Purchase = Model.get('purchase.purchase')

    purchases = Purchase.find([('state', '=', 'draft')])

    # Change 90% to quotation state
    purchases = random.sample(purchases, int(0.9 * len(purchases)))
    Purchase.quote([x.id for x in purchases], config.context)

    # Change 90% to confirmed state
    purchases = random.sample(purchases, int(0.9 * len(purchases)))
    Purchase.confirm([x.id for x in purchases], config.context)

    gal_commit()

@task()
def create_inventory(maxquantity=1000):
    """
    It randomly makes an inventory of 80% of existing products.

    The remaining 20% is left with existing stock (usually 0).

    A random value between 0 and maxquantity (1000 by default) will be used.
    """
    gal_action('create_inventory', maxquantity=maxquantity)
    restore()
    connect_database()

    Inventory = Model.get('stock.inventory')
    InventoryLine = Model.get('stock.inventory.line')
    Location = Model.get('stock.location')
    Product = Model.get('product.product')

    location = Location.find([('type', '=', 'warehouse')])[0].storage_location

    inventory = Inventory()
    inventory.location = location
    inventory.save()
    products = Product.find([
            ('type', '=', 'goods'),
            ('consumable', '=', False),
            ])
    products = random.sample(products, int(0.8 * len(products)))

    for product in products:
        inventory_line = InventoryLine()
        inventory.lines.append(inventory_line)
        inventory_line.product = product
        inventory_line.quantity = random.randrange(maxquantity)
        inventory_line.expected_quantity = 0.0
    inventory.save()
    Inventory.confirm([inventory.id], config.context)

    gal_commit()

@task()
def process_customer_shipments():
    """
    It randomly processes waiting customer shipments.

    20% of existing waiting customer shipments are left in waiting state
    80% are tried to be assigned (may not be assigned if stock is not enough)
    90% of the assigned ones are packed
    90% of the packed ones are done
    """
    gal_action('process_customer_shipments')
    restore()
    connect_database()
    Shipment = Model.get('stock.shipment.out')
    shipments = Shipment.find([('state', '=', 'waiting')])
    shipments = [x.id for x in shipments]

    shipments = random.sample(shipments, int(0.8 * len(shipments)))
    for shipment in shipments:
        Shipment.assign_try([shipment], config.context)
    shipments = random.sample(shipments, int(0.9 * len(shipments)))
    Shipment.pack(shipments, config.context)
    shipments = random.sample(shipments, int(0.9 * len(shipments)))
    Shipment.done(shipments, config.context)

    gal_commit()

def process_invoices(type_):
    """
    It randomly confirms supplier invoices.

    90% of customer invoices are confirmed.
    """
    Invoice = Model.get('account.invoice')
    invoices = Invoice.find([
            ('type', '=', type_),
            ('state', '=', 'draft'),
            ])

    invoices = random.sample(invoices, int(0.9 * len(invoices)))
    for invoice in invoices:
        # TODO: For consistency, better use the date of the maximum
        # date of the # sales/purchases (if available) composing the lines of
        # the invoice
        invoice.invoice_date = random_datetime(
            TODAY + relativedelta(months=-12), TODAY)
        if hasattr(invoice, 'payment_type') and not invoice.payment_type:
            if type_ in ('out_invoice', 'in_credit_note'):
                payment_type = invoice.party.customer_payment_type
            else:
                payment_type = invoice.party.supplier_payment_type
            if payment_type:
                invoice.payment_type = payment_type
            else:
                invoice.payment_type = random.choice(
                    get_payment_types('receivable' if type_ in ('out_invoice',
                            'in_credit_note') else 'payable'))
        invoice.save()
    Invoice.post([x.id for x in invoices], config.context)

@task()
def process_customer_invoices():
    """
    It randomly confirms customer invoices.

    90% of customer invoices are confirmed.
    """
    gal_action('process_customer_invoices')
    restore()
    connect_database()
    process_invoices('out_invoice')
    gal_commit()

@task()
def process_supplier_invoices():
    """
    It randomly confirms supplier invoices.

    90% of customer invoices are confirmed.
    """
    gal_action('process_supplier_invoices')
    restore()
    connect_database()
    process_invoices('in_invoice')
    gal_commit()


def create_invoices(type_, count=100, linecount=10):
    """
    It creates 'count' invoices using random products (linecount maximum)
    and parties.

    If 'count' is not specified 100 is used by default.
    If 'linecount' is not specified 10 is used by default.
    """
    Account = Model.get('account.account')
    Invoice = Model.get('account.invoice')
    InvoiceLine = Model.get('account.invoice.line')
    Party = Model.get('party.party')
    Product = Model.get('product.product')
    Term = Model.get('account.invoice.payment_term')
    Journal = Model.get('account.journal')

    parties = Party.find([])
    products = Product.find([('salable', '=', True)])
    terms = Term.find([])
    if type_.startswith('out'):
        journal_code = 'REV'
    else:
        journal_code = 'EXP'
    journal, = Journal.find(['code', '=', journal_code], limit=1)

    for c in xrange(count):
        invoice = Invoice()
        invoice.type = type_
        invoice.invoice_date = random_datetime(TODAY + relativedelta(months=-12),
            TODAY)
        invoice.party = random.choice(parties)
        invoice.journal = journal

        if not invoice.payment_term:
            invoice.payment_term = random.choice(terms)

        for lc in xrange(random.randrange(1, linecount)):
            line = InvoiceLine()
            invoice.lines.append(line)
            line.type = 'line'
            line.product = random.choice(products)
            line.quantity = random.randrange(1, 20)
        invoice.save()

@task()
def create_customer_invoices(count=100, linecount=10):
    """
    It creates 'count' custoemr invoices using random products (linecount
    maximum) and parties.

    If 'count' is not specified 100 is used by default.
    If 'linecount' is not specified 10 is used by default.
    """
    gal_action('create_customer_invoices', count=count, linecount=linecount)
    restore()
    connect_database()
    create_invoices('out_invoice', count=count, linecount=linecount)
    gal_commit()

@task()
def create_supplier_invoices(count=100, linecount=10):
    """
    It creates 'count' supplier invoices using random products (linecount
    maximum) and parties.

    If 'count' is not specified 100 is used by default.
    If 'linecount' is not specified 10 is used by default.
    """
    gal_action('create_supplier_invoices', count=count, linecount=linecount)
    restore()
    connect_database()
    create_invoices('in_invoice', count=count, linecount=linecount)
    gal_commit()

@task()
def process_supplier_shipments():
    """
    It randomly processes waiting supplier shipments.

    10% of existing purchase orders are left processing
    90% are added to a shipment and set as received
    90% of those shipments are set as done
    """
    gal_action('process_supplier_shipments')
    restore()
    connect_database()
    Move = Model.get('stock.move')
    Shipment = Model.get('stock.shipment.in')
    Purchase = Model.get('purchase.purchase')

    shipments = []
    purchases = Purchase.find([('state', '=', 'confirmed')])
    purchases = random.sample(purchases, int(0.9 * len(purchases)))
    for purchase in purchases:
        shipment = Shipment()
        shipment.supplier = purchase.party
        shipment.save()
        shipments.append(shipment)
        lines = []
        for line in purchase.lines:
            for move in line.moves:
                # TODO: Improve performance, but append crashes
                #shipment.incoming_moves.append(move)
                move.shipment = shipment
                move.save()

    Shipment.receive([x.id for x in shipments], config.context)
    shipments = random.sample(shipments, int(0.9 * len(shipments)))
    Shipment.done([x.id for x in shipments], config.context)

    gal_commit()

@task()
def create_boms(name='pc', inputcount=10, inputquantity=10):
    """
    Creates boms for all products that contain the word 'name' in their name.

    It creates between 1 and inputcount inputs with quantity between 1 and
    inputquantity.

    If name is empty it creates boms for 20% of the products available in the
    database.
    """
    gal_action('create_boms', name=name, inputcount=inputcount, inputquantity=inputquantity)
    restore()
    connect_database()

    Product = Model.get('product.product')
    BOM = Model.get('production.bom')
    Input = Model.get('production.bom.input')
    Output = Model.get('production.bom.output')
    ProductBOM = Model.get('product.product-production.bom')

    products = Product.find([])
    products = [x.id for x in products]
    if name:
        to_produce = Product.find([('name', 'ilike', '%' + name + '%')])
    else:
        to_produce = random.sample(products, int(0.2 * len(products)))
        to_produce = Product.find([('id', 'in', to_produce)])
    to_purchase = Product.find([('id', 'not in', [x.id for x in to_produce])])
    for product in to_produce:
        product.purchasable = False

        bom = BOM()
        bom.name = ''
        if product.code:
            bom.name = '[%s] ' % product.code
        bom.name += product.template.name

        # Use sample because product must be unique per BOM
        for input_product in random.sample(to_purchase, random.randrange(1, inputcount)):
            input_ = Input()
            bom.inputs.append(input_)
            input_.product = input_product
            input_.quantity = random.randrange(1, inputquantity)

        output = Output()
        bom.outputs.append(output)
        output.product = product
        output.quantity = 1
        bom.save()

        pb = ProductBOM()
        pb.bom = bom
        product.boms.append(pb)
        product.save()

    gal_commit()

@task()
def create_production_requests():
    gal_action('create_production_requests')
    restore()
    connect_database()

    Wizard('production.create_request').execute('create_')
    gal_commit()


@task()
def create_purchase_requests():
    gal_action('create_purchase_requests')
    restore()
    connect_database()

    Wizard('purchase.request.create').execute('create_')
    gal_commit()

@task()
def create_reservations():
    gal_action('create_reservations')
    restore()
    connect_database()

    Wizard('stock.create_reservations').execute('create_')
    gal_commit()

@task()
def create_csb43():
    gal_action('create_csb43')
    restore()
    connect_database()
    from retrofix import c43
    from retrofix.record import Record

    #records = []
    #record = Record(c43.FILE_HEADER_RECORD)
    #record.bank_code =
    #record.date = datetime.now()
    #records.append(record)
    #record = Record(c43.ACCOUNT_HEADER_RECORD)
    #record.bank_code =
    #record.bank_office =
    #record.account_number =
    #record.start_date =
    #record.end_date =
    #record.initial_balance =
    #record.currency_code =
    #record.information_mode =
    #record.customer_name =
    #record.free =
    #records.append(record)
    #record = Record(c43.MOVE_RECORD)
    ##record.record_code
    ##record.free
    #record.bank_office
    #record.operation_date
    #record.value_date
    #record.common_concept_code
    #record.bank_concept_code
    #record.amount
    #record.document_number
    #record.reference_1
    #record.reference_2
    #records.append(record)
    #record = Record(c43.ACCOUNT_FOOTER_RECORD)
    #record.record_code
    #record.bank_code
    #record.bank_office
    #record.account_number
    #record.debit_record_count
    #record.debit_total
    #record.credit_record_count
    #record.credit_total
    #record.final_balance
    #record.currency_code
    #record.free
    #records.append(record)
#
#    record = Record(c43.FILE_FOOTER_RECORD)
#    record.record_code
#    record.nines
#    record.record_count
#    record.free
#    records.append(record)

    c43.write()

    gal_commit()

@task()
def create_marketing_invoices():
    gal_action('create_marketing_invoices')
    restore()
    connect_database()

    Campaign = Model.get('sale.opportunity.campaign')
    Invoice = Model.get('account.invoice')
    InvoiceLine = Model.get('account.invoice.line')
    Term = Model.get('account.invoice.payment_term')
    term = Term.find([])[0]
    Product = Model.get('product.product')
    product = Product.find([('rec_name', 'ilike', 'Hores Tasques')])[0]

    i = 0
    campaign = Campaign(32)
    for party in campaign.parties:
        print "Doing", i + 1, party.rec_name
        invoice = Invoice()
        invoice.party = party
        invoice.payment_term = term
        invoice.invoice_date = datetime.date.today()
        line = InvoiceLine()
        invoice.lines.append(line)
        line.product = product
        line.quantity = 50
        line.description = u'Llicència ERP anual'
        line.unit_price = Decimal('0')
        line.gross_unit_price = Decimal('0')
        line.discount = Decimal('0')
        invoice.save()
        i += 1
    gal_commit()


GalCollection = Collection()
GalCollection.add_task(create)
GalCollection.add_task(replay)
GalCollection.add_task(get)
GalCollection.add_task(set)
GalCollection.add_task(build)
GalCollection.add_task(galfile)
GalCollection.add_task(execute_script)
GalCollection.add_task(update_all)
GalCollection.add_task(set_active_languages)
GalCollection.add_task(install_modules)
GalCollection.add_task(load_spanish_banks)
GalCollection.add_task(load_spanish_zips)
GalCollection.add_task(create_parties)
GalCollection.add_task(create_bank_accounts)
GalCollection.add_task(create_product_categories)
GalCollection.add_task(create_product_category)
GalCollection.add_task(create_products)
GalCollection.add_task(create_company)
GalCollection.add_task(create_employee)
GalCollection.add_task(create_account_chart)
GalCollection.add_task(create_fiscal_year)
GalCollection.add_task(create_payment_term)
GalCollection.add_task(create_payment_terms)
GalCollection.add_task(create_opportunities)
GalCollection.add_task(process_opportunities)
GalCollection.add_task(create_sales)
GalCollection.add_task(process_sales)
GalCollection.add_task(create_purchases)
GalCollection.add_task(process_purchases)
GalCollection.add_task(create_inventory)
GalCollection.add_task(process_customer_shipments)
GalCollection.add_task(process_customer_invoices)
GalCollection.add_task(process_supplier_shipments)
GalCollection.add_task(create_boms)
GalCollection.add_task(create_production_requests)
GalCollection.add_task(create_purchase_requests)
GalCollection.add_task(create_reservations)
GalCollection.add_task(create_marketing_invoices)
GalCollection.add_task(create_customer_invoices)
GalCollection.add_task(create_supplier_invoices)

