# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import json
import logging
from datetime import datetime

from trytond.model import ModelView, Workflow, fields
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.rpc import RPC

__all__ = ['SaleLine']


class SaleLine:
    __name__ = 'sale.line'
    __metaclass__ = PoolMeta

    available_quantity = fields.Function(fields.Float('Available Quantity'),
        '_get_quantity')
    forecast_quantity = fields.Function(fields.Float('Forecast Quantity'),
        '_get_quantity')

    @fields.depends('product')
    def on_change_product(self):
        super(SaleLine, self).on_change_product()
        Line = Pool().get('sale.line')
        self.available_quantity = 0

        if self.product:
            qty = Line._get_quantity([self], ['available_quantity'])
            self.available_quantity = qty['available_quantity'][self.id]

    @classmethod
    def _get_quantity(cls, lines, names):
        pool = Pool()
        Location = pool.get('stock.location')
        Product = pool.get('product.product')
        Date = pool.get('ir.date')
        product_ids = list(set([x.product.id for x in lines if x.product]))
        context = {
            'locations': [x.id for x in
                Location.search(['type', '=', 'warehouse'])],
            'stock_date_end': Date.today(),
            }
        res = {}
        with Transaction().set_context(context):
            products = Product.browse(product_ids)

        confirmed_lines = cls.search([
                ('sale.state', '=', 'confirmed'),
                ])
        confirmed_quantities = {}
        for x in confirmed_lines:
            if not x.product:
                continue
            if x.product.id in confirmed_quantities:
                confirmed_quantities[x.product.id] += x.quantity
            else:
                confirmed_quantities[x.product.id] = x.quantity

        for name in names:
            res[name] = dict([(x.id, None) for x in lines])
            values = {}
            for product in products:
                if name == 'available_quantity':
                    values[product.id] = product.quantity
                else:
                    if product.id in confirmed_quantities:
                        confirmed_quantity = confirmed_quantities[product.id]
                    else:
                        confirmed_quantity = 0.0
                    values[product.id] = (product.forecast_quantity -
                        confirmed_quantity)
            for line in lines:
                if line.type == 'line' and line.product:
                    res[name][line.id] = values.get(line.product.id)
        return res
