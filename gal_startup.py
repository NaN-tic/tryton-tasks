#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import argparse
import datetime
import logging
import os
import sys
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from random import randrange

directory = os.path.abspath(os.path.normpath(os.path.join(os.getcwd(),
                    'trytond')))
proteus_directory = os.path.abspath(os.path.normpath(os.path.join(os.getcwd(),
                    'proteus')))

if os.path.isdir(directory):
    sys.path.insert(0, directory)
if os.path.isdir(proteus_directory):
    sys.path.insert(0, proteus_directory)

from proteus import (
    config as pconfig,
    Model,
    Wizard)

TODAY = datetime.date.today()
NOW = datetime.datetime.now()

logger = logging.getLogger('Startup')


def parse_arguments():
    # usage = 'usage: %prog [options] <database>'
    # parser = argparse.ArgumentParser(usage=usage)
    parser = argparse.ArgumentParser()
    parser.add_argument('database')
    parser.add_argument('--module', '-m', metavar='MODULE_NAME',
        dest='modules', action='append',
        help='module that will be installed/upgraded.')
    parser.add_argument('--demo', action='store_true',
        help='create demo data after create real data')
    parser.add_argument('--only-demo', action='store_true',
        help='only create demo date. Database must exists with real data '
        'created')
    parser.add_argument('--language', '-l', default='es_ES')
    parser.add_argument('--verbose', '-v', action='store_true',
        help='Print more verbose log messages', default=False)

    settings = parser.parse_args()

    if settings.verbose:
        logger.setLevel(logging.DEBUG)
        logging.basicConfig(stream=sys.stderr, level=logging.ERROR)
    else:
        logger.setLevel(logging.INFO)
        logging.basicConfig(stream=sys.stderr, level=logging.ERROR)

    return settings


def connect_database(database, password='admin', database_type='postgresql'):
    return pconfig.set_trytond(database, password=password,
        config_file=os.environ.get('TRYTOND_CONFIG', 'trytond.conf'))


def set_active_languages(config, lang_codes=None):
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
        print("Upgrading all because new translatable languages has been added")
        upgrade_modules(config, all=True)


def upgrade_modules(config, modules=None, all=False):
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


def install_modules(config, modules):
    '''
    Function get from tryton_demo.py in tryton-tools repo:
    http://hg.tryton.org/tryton-tools
    '''
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
    return modules, installed_modules


def create_post_move_sequence(config, fiscalyears=None):
    '''
    Create differents post moes for every fiscalyear
    '''

    FiscalYear = Model.get('account.fiscalyear')
    Sequence = Model.get('ir.sequence')
    if not fiscalyears:
        fiscalyears = FiscalYear.find([])

    sequences = []

    for fiscalyear in fiscalyears:
        sequence = Sequence()
        sequence.code = 'account.move'
        sequence.name = fiscalyear.name
        sequence.save()
        sequences.append((sequence.id, fiscalyear.id))
    return sequences


def create_party(config, name, street=None, zip=None, city=None,
        subdivision_code=None, country_code='ES', phone=None, website=None,
        account_payable=None, account_receivable=None):
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
        Address(street=street,
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

    party.save()
    return party


def create_company(config, name, street=None, zip=None, city=None,
        subdivision_code=None, country_code='ES', currency_code='EUR',
        phone=None, website=None):
    '''
    Based on tryton_demo.py in tryton-tools repo:
    http://hg.tryton.org/tryton-tools
    '''
    Company = Model.get('company.company')
    Currency = Model.get('currency.currency')

    party = create_party(config, name, street=street, zip=zip, city=city,
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
    return company


def create_user(config, name, login, main_company, groups=None, company=None,
        lang_code='es_ES', timezone='Europe/Madrid', create_employee=False):
    Group = Model.get('res.group')
    Lang = Model.get('ir.lang')
    User = Model.get('res.user')
    Party = Model.get('party.party')
    Employee = Model.get('company.employee')

    users = User.find([('login', '=', login)])
    if users:
        return users[0]

    user = User()
    user.name = name
    user.login = login
    user.password = login
    user.main_company = main_company
    if company:
        user.company = company
    else:
        user.company = main_company
    if lang_code:
        language, = Lang.find([('code', '=', lang_code)])
        user.language = language
    if timezone:
        user.timezone = timezone

    if groups:
        for group in Group.find([('id', 'in', [g.id for g in groups])]):
            if group not in user.groups:
                user.groups.append(group)
    if create_employee:
        party = Party(name=name)
        party.save()
        employee = Employee()
        employee.party = party
        employee.company = company or main_company
        employee.save()
        user.employees.append(employee)
        user.employee = employee
    return user


def create_sequence(name, code, strict=False, prefix=None, padding=None):
    if strict:
        Sequence = Model.get('ir.sequence.strict')
    else:
        Sequence = Model.get('ir.sequence')

    sequences = Sequence.find([
            ('name', '=', name),
            ('code', '=', code),
            ])
    if sequences:
        return sequences[0]

    sequence = Sequence(
        name=name,
        code=code,
        prefix=prefix,
        padding=padding)
    return sequence


def load_bank_es():
    'Loads all banks from spain'
    load_banks = Wizard('load.banks')
    load_banks.execute('accept')


def load_country_zip_es():
    'Loads zip codes from spain'
    load_zips = Wizard('load.country.zips')
    load_zips.execute('accept')


def create_chart_of_accounts(config, module, fs_id, company, digits=None,
        receivable_code=None, payable_code=None):
    AccountTemplate = Model.get('account.account.template')
    Account = Model.get('account.account')
    ModelData = Model.get('ir.model.data')

    root_accounts = Account.find([('parent', '=', None)])
    if root_accounts:
        return

    data = ModelData.find([
        ('module', '=', module),
        ('fs_id', '=', fs_id)], limit=1)

    assert len(data) == 1, ('Unexpected num of root templates '
        'with name "%s": %s' % (module, fs_id))

    account_template = data[0].db_id

    create_chart = Wizard('account.create_chart')
    create_chart.execute('account')
    create_chart.form.account_template = AccountTemplate(account_template)
    create_chart.form.company = company
    create_chart.form.account_code_digits = digits
    create_chart.execute('create_account')

    receivable_domain = [
        ('kind', '=', 'receivable'),
        ('company', '=', company.id),
        ]
    if receivable_code is not None:
        receivable_domain.append(('code', '=', receivable_code))
    receivable = Account.find(receivable_domain)
    receivable = receivable[0]
    payable_domain = [
        ('kind', '=', 'payable'),
        ('company', '=', company.id),
        ]
    if payable_code is not None:
        payable_domain.append(('code', '=', payable_code))
    payable = Account.find(payable_domain)[0]
    create_chart.form.account_receivable = receivable
    create_chart.form.account_payable = payable
    create_chart.execute('create_properties')
    # TODO: return create_chart


def create_fiscal_year(config, company, year=None):
    FiscalYear = Model.get('account.fiscalyear')
    Module = Model.get('ir.module.module')
    Sequence = Model.get('ir.sequence')
    SequenceStrict = Model.get('ir.sequence.strict')

    if year is None:
        year = TODAY.year

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
            for attr, name in (('out_invoice_sequence', 'Invoice'),
                    ('in_invoice_sequence', 'Supplier Invoice'),
                    ('out_credit_note_sequence', 'Credit Note'),
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

    return fiscalyear


def create_analytic_account(name, type, parent, currency=None):
    Account = Model.get('analytic_account.account')
    account = Account(name=name,
        type=type,
        state='opened',
        root=parent and parent.root or parent,
        parent=parent,
        display_balance='credit-debit')
    if currency:
        account.currency = currency
    return account


def create_location(name, type, parent=None, code=None, address=None,
        active=True, input=None, output=None, storage=None, production=None):
    Location = Model.get('stock.location')
    location = None
    if code is not None:
        location = Location.find([
                ('code', '=', code),
                ('parent', '=', parent and parent.id or None),
                ])
    if not location:
        location = Location.find([
                ('name', '=', name),
                ('parent', '=', parent and parent.id or None),
                ])
    if location:
        return location[0]
    else:
        return Location(type=type,
            name=name,
            code=code,
            parent=parent,
            input_location=input,
            output_location=output,
            storage_location=storage,
            production_location=production,
            active=active,
            address=address)


def create_product(name, code="", template=None, cost_price=None,
        list_price=None, type='goods', unit=None, consumable=False,
        category=None):

    ProductUom = Model.get('product.uom')
    Product = Model.get('product.product')
    ProductTemplate = Model.get('product.template')
    Account = Model.get('account.account')
    Company = Model.get('company.company')
    company = Company(1)

    product = Product.find([('name', '=', name), ('code', '=', code)])
    if product:
        return product[0]

    if not cost_price:
        cost_price = randrange(0, 1000)

    if not list_price:
        list_price = cost_price * randrange(1, 2)

    if unit is None:
        unit = ProductUom(1)

    if template is None:
        template = ProductTemplate()
        template.name = name
        template.default_uom = unit
        template.type = type
        template.category = category
        template.consumable = consumable
        template.list_price = Decimal(str(list_price))
        template.cost_price = Decimal(str(cost_price))

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


def create_product_category(name, parent=None, account_parent=False,
        account_expense=None, account_revenue=None, taxes_parent=False,
        customer_taxes=None, supplier_taxes=None):
    ProductCategory = Model.get('product.category')
    Tax = Model.get('account.tax')

    categories = ProductCategory.find([
                ('name', '=', name),
                ('parent', '=', parent),
                ])
    if categories:
        return categories[0]
    if customer_taxes is None:
        customer_taxes = []
    if supplier_taxes is None:
        supplier_taxes = []
    category = ProductCategory(name=name,
        parent=parent)
    category.account_parent = account_parent
    category.account_expense = account_expense
    category.account_revenue = account_revenue
    category.taxes_parent = taxes_parent
    if not taxes_parent:
        for ct in customer_taxes:
            category.customer_taxes.append(Tax(ct.id))
        for st in supplier_taxes:
            category.supplier_taxes.append(Tax(st.id))
    category.save()
    return category


def create_workcenter_category(name, cost_price=None, unit=None):

    WorkCenterCategory = Model.get('production.work_center.category')

    wc = WorkCenterCategory.find([('name', '=', name)])
    if wc:
        return wc[0]
    if not cost_price:
        cost_price = randrange(0, 1000)

    wc = WorkCenterCategory()
    wc.name = name
    wc.cost_price = Decimal(str(cost_price))
    wc.uom = unit
    wc.save()
    return wc


def create_workcenter(name, category, type='machine',
        cost_price=None, uom=None):

    WorkCenter = Model.get('production.work_center')

    wc = WorkCenter.find([('name', '=', name)])
    if wc:
        return wc[0]
    if not cost_price:
        cost_price = randrange(0, 1000)

    wc = WorkCenter()
    wc.name = name
    wc.category = category
    wc.type = type
    wc.cost_price = cost_price
    wc.uom = uom
    wc.save()
    return wc


def create_operation_type(name):
    OperationType = Model.get('production.operation.type')

    op = OperationType.find([('name', '=', name)])
    if op:
        return op[0]

    op = OperationType()
    op.name = name
    op.save()
    return op


def create_route(name):
    Route = Model.get('production.route')

    route = Route.find([('name', '=', name)])
    if route:
        return route[0]

    route = Route()
    route.name = name
    route.save()
    return route


def create_route_operation(route, sequence, operation_type, wc, wc_category,
        quantity, uom):

    OperationRoute = Model.get('production.route.operation')
    op_route = OperationRoute.find([('route', '=', route.id),
            ('operation_type', '=', operation_type.id)])

    if op_route:
        return op_route[0]

    op = OperationRoute()
    op.route = route
    op.operation_type = operation_type
    op.work_center_category = wc_category
    op.work_center = wc
    op.unit = uom
    op.quantity = quantity
    op.save()
    return op


def create_warehouse(name, code=None, address=None,
        separate_input=True, separate_output=True):
    Location = Model.get('stock.location')

    warehouses = Location.find([
            ('name', '=', name),
            ('type', '=', 'warehouse'),
            ])
    if warehouses:
        return warehouses[0]

    warehouse = create_location(name, 'warehouse', code=code, address=address)

    storage_location = create_location('%s Storage' % name, 'storage')
    storage_location.save()
    warehouse.storage_location = storage_location

    production_location = create_location('%s Production' % name, 'production')
    production_location.save()
    warehouse.production_location = production_location

    if separate_input:
        input_location = create_location('%s Input' % name, 'storage')
        input_location.save()
        warehouse.input_location = input_location
    else:
        warehouse.input_location = storage_location

    if separate_output:
        output_location = create_location('%s Output' % name, 'storage')
        output_location.save()
        warehouse.output_location = output_location
    else:
        warehouse.output_location = storage_location

    return warehouse


def remove_warehouse_and_locations(warehouse):
    Location = Model.get('stock.location')

    warehouse.type = 'storage'
    warehouse.save()

    for warehouse_loc in Location.find([('parent', 'child_of', warehouse.id)]):
        Location.delete(warehouse_loc)


if __name__ == "__main__":
    settings = parse_arguments()

    config = connect_database(settings.database)
    if not settings.modules:
        sys.exit()

    inst_upg_modules, installed_modules = install_modules(config,
        settings.modules)
    logger.info('Modules installed or upgraded: %s' % inst_upg_modules)
    logger.debug('All installed modules: %s' % installed_modules)

    if not settings.only_demo:
        logger.info('Load start data in %s' % settings.database)

        if 'company' in installed_modules:
            company = create_company(config, 'NaN·tic')
            logger.info('Company created: %s' % company)

        # TODO: create_nantic_user(config)
        if 'account_es' in installed_modules:
            create_chart_of_accounts(config, 'account_es', 'pgc_0', company, 8)
            logging.getLogger('Utils').info('Chart of accounts created')
        elif 'account' in installed_modules:
            create_chart_of_accounts(config, 'account',
                'account_type_template_minimal', company)
            logging.getLogger('Utils').info('Chart of accounts created')

        if 'bank_es' in installed_modules:
            load_bank_es()
        if 'country_zip_es' in installed_modules:
            load_country_zip_es()

        if 'account' in installed_modules:
            fiscalyear = create_fiscal_year(config, company)
            logging.getLogger('Utils').info('Fiscal year created: %s'
                % fiscalyear)
