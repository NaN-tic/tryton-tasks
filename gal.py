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
from decimal import Decimal
from invoke import task

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
            if line:
                print t.bold(line)
                eval(line)

@task
def get_galfile():
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
        print >>sys.stderr, t.red('It is not possible to replay tip '
            'version because there is a set() operation in the list of '
            'commands to execute')
        sys.exit(1)

    # Disable commits before replaying
    for revision in repo.revisions(slice(0, 'tip')):
        description = revision.desc
        action, parameters = json.loads(description)
        print '%s(**%s)' % (action, parameters)


#
# Extension commands
#

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
    with open('tasks/streets.txt', 'r') as f:
        streets = f.read().split('\n')
    with open('tasks/names.txt', 'r') as f:
        names = f.read().split('\n')
    with open('tasks/surnames.txt', 'r') as f:
        surnames = f.read().split('\n')
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
    Account = Model.get('account.account')
    Category = Model.get('product.category')
    Company = Model.get('company.company')
    company = Company(1)

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

        if hasattr(template, 'account_expense'):
            expense = Account.find([
                ('kind', '=', 'expense'),
                ('company', '=', company.id),
                ])
            if expense:
                template.account_expense = expense[0]
        if hasattr(template, 'account_revenue'):
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
        create_chart.form.account_code_digits = digits
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

    If no year specified the current year is used.
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
        fiscalyear.start_date = TODAY + relativedelta(month=1, day=1)
        fiscalyear.end_date = TODAY + relativedelta(month=12, day=31)
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
def create_payment_terms():
    """
    It cretes 3 payment terms:
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

    Invoice.post([x.id for x in invoices], config.context)
    gal_commit()
