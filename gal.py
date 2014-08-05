#!/usr/bin/env python
import os
import sys
import time
import subprocess
import hgapi
import random
import json
import datetime
from dateutil.relativedelta import relativedelta
from datetime import timedelta
from decimal import Decimal
from invoke import task, Collection

from .utils import t

directory = os.path.abspath(os.path.normpath(os.path.join(os.getcwd(),
                    'trytond')))
proteus_directory = os.path.abspath(os.path.normpath(os.path.join(os.getcwd(),
                    'proteus')))

if os.path.isdir(directory):
    sys.path.insert(0, directory)
if os.path.isdir(proteus_directory):
    sys.path.insert(0, proteus_directory)

try:
    from proteus import config as pconfig, Model, Wizard
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
        database_type='postgresql', language='en_US'):
    if database is None:
        database = 'gal'
    global config
    config = pconfig.set_trytond(database, database_type=database_type,
        password=password, language=language, config_file='trytond.conf')

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
    print check_output('pg_dump', '-f', gal_path(dump_file), dbname)
    gal_repo().hg_add(dump_file)

def dropdb(dbname=None):
    if dbname is None:
        dbname = 'gal'
    check_output('dropdb', dbname)

def restore(dbname=None):
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
    repo = hgapi.Repo(path)
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

@task
def create(language=None, password=None):
    """
    Creates a new tryton database and stores it in the gal repository.
    """
    gal_repo()
    gal_action('create', language=language, password=password)
    dropdb()
    connect_database(language=language)
    gal_commit()

@task
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

@task
def get(name):
    """
    Restores current gal database with the given database name
    """
    restore(name)

@task
def set(name):
    """
    Saves the given database as current gal database
    """
    gal_action('set')
    dump(name)
    gal_commit(do_dump=False)

@task
def build(filename=None):
    """
    Creates a database with the commands found in the specified filename.

    If no filename is given it will search for a file named 'Galfile'
    """
    if filename is None:
        filename = 'Galfile'
    print "Building %s..." % filename
    with open(filename, 'r') as f:
        for line in f:
            if line and not line.strip().startswith('#'):
                print t.bold(line)
                eval(line)

@task
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


#
# Extension commands
#
@task
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

@task
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


@task
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


@task
def load_spanish_banks():
    '''
    Execute Load Spanish Banks wizard. Requires bank_es module
    '''
    gal_action('load_spanish_banks')
    restore()
    connect_database()
    Wizard('load.banks').execute('accept')
    gal_commit()


@task
def load_spanish_zips():
    '''
    Execute Load Spanish Zips wizard. Requires country_zip_es module
    '''
    gal_action('load_spanish_zips')
    restore()
    connect_database()
    Wizard('load.country.zips').execute('accept')
    gal_commit()


def create_party(name, street=None, zip=None, city=None,
        subdivision_code=None, country_code='ES', phone=None, website=None,
        address_name=None, account_payable=None, account_receivable=None):
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

    party = Party(name=name)
    party.addresses.pop()
    party.addresses.append(
        Address(
            name=address_name,
            street=street,
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

    if account_payable:
        party.account_payable = account_payable
    if account_receivable:
        party.account_receivable = account_receivable
    if hasattr(party, 'customer_payment_term'):
        Term = Model.get('account.invoice.payment_term')
        terms = Term.find([])
        if terms:
            term = random.choice(terms)
            party.customer_payment_term = term
            party.supplier_payment_term = term

    party.save()
    return party

@task
def create_parties(count=4000):
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


@task
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


@task
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
    Category = Model.get('product.category')

    categories = Category.find([])
    category = None
    if categories:
        category = random.choice(categories)

    product = Product.find([('name', '=', name), ('code', '=', code)])
    if product:
        return product[0]

    if not cost_price:
        cost_price = random.randrange(0, 1000)

    if not list_price:
        list_price = cost_price * random.randrange(1, 2)

    if unit is None:
        unit = ProductUom(1)

    if template is None:
        template = ProductTemplate()
        template.name = name
        template.default_uom = unit
        template.type = type
        template.consumable = consumable
        template.list_price = Decimal(str(list_price))
        template.cost_price = Decimal(str(cost_price))
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

        template.products[0].code = code
        template.save()
        product = template.products[0]
    else:
        product = Product()
        product.template = template
        product.code = code
        product.save()
    return product

@task
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

@task
def create_company(name, street=None, zip=None, city=None,
        subdivision_code=None, country_code='ES', currency_code='EUR',
        phone=None, website=None):
    '''
    Creates a company in current gal database.

    Based on tryton_demo.py in tryton-tools repo:
    http://hg.tryton.org/tryton-tools
    '''
    gal_action('create_company', name=name, street=street, zip=zip, city=city,
        subdivision_code=subdivision_code, country_code=country_code,
        currency_code=currency_code, phone=phone, website=website)
    restore()
    connect_database()

    Company = Model.get('company.company')
    Currency = Model.get('currency.currency')

    party = create_party(name, street=street, zip=zip, city=city,
        subdivision_code=subdivision_code, country_code=country_code,
        phone=phone, website=website)

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

@task
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

@task
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

@task
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

@task
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


@task
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

@task
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
        opp.start_date = random_datetime(TODAY + relativedelta(months=-12),
            TODAY)
        if not opp.payment_term:
            opp.payment_term = random.choice(terms)

        for lc in xrange(random.randrange(1, linecount)):
            line = OpportunityLine()
            opp.lines.append(line)
            line.product = random.choice(products)
            line.quantity = random.randrange(1, 20)
        opp.save()

    gal_commit()

@task
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

@task
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


@task
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

@task
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


@task
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

@task
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

@task
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

@task
def process_customer_invoices():
    """
    It randomly confirms customer invoices.

    90% of customer invoices are confirmed.
    """
    gal_action('process_customer_invoices')
    restore()
    connect_database()

    Invoice = Model.get('account.invoice')
    invoices = Invoice.find([
            ('type', '=', 'out_invoice'),
            ('state', '=', 'draft'),
            ])
    invoices = random.sample(invoices, int(0.9 * len(invoices)))
    for invoice in invoices:
        # TODO: For consistency, better use the date of the maximum
        # date of the # sales composing the lines of the invoice
        invoice.invoice_date = random_datetime(
            TODAY + relativedelta(months=-12), TODAY)
        invoice.save()

    Invoice.post([x.id for x in invoices], config.context)
    gal_commit()

@task
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

GalCollection = Collection()
GalCollection.add_task(create)
GalCollection.add_task(replay)
GalCollection.add_task(get)
GalCollection.add_task(set)
GalCollection.add_task(build)
GalCollection.add_task(galfile)
GalCollection.add_task(update_all)
GalCollection.add_task(set_active_languages)
GalCollection.add_task(install_modules)
GalCollection.add_task(load_spanish_banks)
GalCollection.add_task(load_spanish_zips)
GalCollection.add_task(create_parties)
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
