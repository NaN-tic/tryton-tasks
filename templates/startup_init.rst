===============
{project_title}
===============

=============
General Setup
=============

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
    >>> today = datetime.date.today()
    >>> config = config.set_trytond()
    >>> config.pool.test = False


Install Module::

    >>> Module = Model.get('ir.module.module')
    >>> modules = Module.find([
    ...         ('name', '=', '{customer_module_name}'),
    ...         ])
    >>> Module.install([x.id for x in modules], config.context)
    >>> Wizard('ir.module.module.install_upgrade').execute('upgrade')


Create company::

    >>> Currency = Model.get('currency.currency')
    >>> CurrencyRate = Model.get('currency.currency.rate')
    >>> currencies = Currency.find([('code', '=', 'EUR')])
    >>> if not currencies:
    ...     euro = Currency(name='Euro', symbol=u'€', code='EUR',
    ...         rounding=Decimal('0.01'), mon_grouping='[]',
    ...         mon_decimal_point='.')
    ...     euro.save()
    ...     CurrencyRate(date=today + relativedelta(month=1, day=1),
    ...         rate=Decimal('1.0'), currency=euro).save()
    ... else:
    ...     euro, = currencies

    >>> Company = Model.get('company.company')
    >>> Party = Model.get('party.party')
    >>> company_config = Wizard('company.company.config')
    >>> company_config.execute('company')
    >>> company = company_config.form
    >>> party = Party(name='{company_name}')
    >>> party.save()
    >>> company.party = party
    >>> company.currency = euro
    >>> company_config.execute('add')
    >>> company, = Company.find()


Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)


Create fiscal year::

    >>> FiscalYear = Model.get('account.fiscalyear')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceStrict = Model.get('ir.sequence.strict')
    >>> fiscalyear = FiscalYear(name=str(today.year))
    >>> fiscalyear.start_date = today + relativedelta(month=1, day=1)
    >>> fiscalyear.end_date = today + relativedelta(month=12, day=31)
    >>> fiscalyear.company = company
    >>> post_move_seq = Sequence(name=str(today.year), code='account.move',
    ...     company=company)
    >>> post_move_seq.save()
    >>> fiscalyear.post_move_sequence = post_move_seq
    >>> invoice_seq = SequenceStrict(name=str(today.year),
    ...     code='account.invoice', company=company)
    >>> invoice_seq.save()
    >>> fiscalyear.out_invoice_sequence = invoice_seq
    >>> fiscalyear.in_invoice_sequence = invoice_seq
    >>> fiscalyear.out_credit_note_sequence = invoice_seq
    >>> fiscalyear.in_credit_note_sequence = invoice_seq
    >>> fiscalyear.save()
    >>> FiscalYear.create_period([fiscalyear.id], config.context)


Create chart of accounts::

    >>> AccountTemplate = Model.get('account.account.template')
    >>> Account = Model.get('account.account')
    >>> account_template = AccountTemplate.find([
    ...     ('parent', '=', None),
    ...     ('name', '=', 'Plan General Contable 2008'),
    ...     ])[0]
    >>> create_chart = Wizard('account.create_chart')
    >>> create_chart.execute('account')
    >>> create_chart.form.account_template = account_template
    >>> create_chart.form.company = company
    >>> create_chart.form.account_code_digits = 8
    >>> create_chart.execute('create_account')
    >>> receivable = Account.find([
    ...         ('kind', '=', 'receivable'),
    ...         ('company', '=', company.id),
    ...         ])[0]
    >>> payable = Account.find([
    ...         ('kind', '=', 'payable'),
    ...         ('company', '=', company.id),
    ...         ])[0]
    >>> revenue = Account.find([
    ...         ('kind', '=', 'revenue'),
    ...         ('company', '=', company.id),
    ...         ])[0]
    >>> expense = Account.find([
    ...         ('kind', '=', 'expense'),
    ...         ('company', '=', company.id),
    ...         ])[0]
    >>> cash = Account.find([
    ...         ('kind', '=', 'other'),
    ...         ('company', '=', company.id),
    ...         ('name', '=', 'Caja, euros'),
    ...         ])[0]
    >>> create_chart.form.account_receivable = receivable
    >>> create_chart.form.account_payable = payable
    >>> create_chart.execute('create_properties')


Load spanish Zips::

    >>> Wizard('load.country.zips').execute('accept')


Load spanish banks::

    >>> Wizard('load.banks').execute('accept')


Configure sale::

    >>> SaleConfig = Model.get('sale.configuration')
    >>> sale_config = SaleConfig(1)
    >>> sale_config.sale_shipment_method = 'order'
    >>> sale_config.sale_invoice_method = 'milestone'
    >>> sale_config.save()


Create payment term::

    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> PaymentTermLine = Model.get('account.invoice.payment_term.line')
    >>> payment_term = PaymentTerm(name='Term')
    >>> payment_term_line = PaymentTermLine(type='percent', days=20,
    ...     percentage=Decimal(50))
    >>> payment_term.lines.append(payment_term_line)
    >>> payment_term_line = PaymentTermLine(type='remainder', days=40)
    >>> payment_term.lines.append(payment_term_line)
    >>> payment_term.save()


Create Payment Type::

    >>> PaymentType = Model.get('account.payment.type')
    >>> comptat = PaymentType(name='Comptat',
    ... company=company,
    ... kind='receivable')
    >>> comptat.save()
    >>> supplier_comptat = PaymentType(name='Comptat', kind='payable')
    >>> supplier_comptat.save()
