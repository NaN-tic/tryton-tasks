#!/usr/bin/env python
import sys
import psycopg2

company = 1

if len(sys.argv) != 3:
    print 'Usage: %s database company_id' % sys.argv[0]
    sys.exit()

db = sys.argv[1]
company = int(sys.argv[2])

db = psycopg2.connect(dbname=db)
cursor = db.cursor()

def delete_table(table, join=None, field='company'):
    if join is None:
        join = []
    using = []
    where = []
    t2 = table
    for j in join:
        f = j[0]
        t = j[1]
        using.append('"%s"' % t)
        where.append('"%s".id = "%s".%s' % (t, t2, f))
        t2 = t

    using = ', '.join(using)
    if using:
        using = 'USING %s' % using

    where.append('"%s".%s <> %d' % (t2, field, company))
    where = ' AND '.join(where)
    query = ('DELETE FROM "%(table)s" %(using)s WHERE '
        '%(where)s' % {
            'table': table,
            'using': using,
            'where': where,
            })
    print 'Query:', query
    cursor.execute(query)

delete_table('account_financial_statement_report')
delete_table('account_bank_reconciliation', [('move_line', 'account_move_line'),
        ('account', 'account_account')])
delete_table('account_move_line', [('account', 'account_account')])
delete_table('account_move', [('period', 'account_period'),
        ('fiscalyear', 'account_fiscalyear')])
delete_table('account_period', [('fiscalyear', 'account_fiscalyear')])
delete_table('aeat_347_record')
delete_table('account_fiscalyear')
delete_table('account_invoice')
delete_table('account_account')
delete_table('account_account_type')
delete_table('account_asset')
delete_table('account_payment_type')
delete_table('aeat_303_mapping-account_tax_code',
    [('code', 'account_tax_code')])
delete_table('account_tax_code')
delete_table('account_tax')
delete_table('account_tax_rule')
delete_table('aeat_303_mapping')
delete_table('sale_shop')
delete_table('product_price_list')


delete_table('company_company', field='id')

