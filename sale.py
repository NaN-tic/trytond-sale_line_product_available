# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import datetime
from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval

__all__ = ['SaleLine']

STATES = {
    'invisible': Eval('_parent_sale', {}).get('state').in_(['done', 'cancel']),
    }


class SaleLine(metaclass=PoolMeta):
    __name__ = 'sale.line'
    available_quantity = fields.Function(fields.Float('Available Quantity',
            states=STATES), '_get_quantity')
    forecast_quantity = fields.Function(fields.Float('Forecast Quantity',
            states=STATES), '_get_quantity')

    def set_available_quantity(self):
        Line = Pool().get('sale.line')

        if self.product and self.sale_state in ('draft', 'quotation'):
            id_ = self.id
            qty = Line._get_quantity([self], [
                'available_quantity', 'forecast_quantity'])
            self.available_quantity = qty['available_quantity'][id_]
            self.forecast_quantity = qty['forecast_quantity'][id_]
        else:
            self.available_quantity = None
            self.forecast_quantity = None

    @fields.depends('product', 'quantity', 'sale', 'sale_state', 'warehouse',
        'type', 'available_quantity', 'forecast_quantity')
    def on_change_product(self):
        super(SaleLine, self).on_change_product()
        self.set_available_quantity()

    @fields.depends('product', 'quantity', 'sale', 'sale_state', 'warehouse',
        'type', 'available_quantity', 'forecast_quantity')
    def on_change_quantity(self):
        super(SaleLine, self).on_change_quantity()
        self.set_available_quantity()

    @classmethod
    def _get_quantity(cls, lines, names):
        pool = Pool()
        Product = pool.get('product.product')
        Date = pool.get('ir.date')

        today = Date().today()
        product_ids = list(set([x.product.id for x in lines if x.product]))

        res = {n: {l.id: None for l in lines} for n in names}
        if not product_ids:
            return res

        warehouse_ids = set()
        for line in lines:
            if line.warehouse:
                warehouse_ids.add(line.warehouse.id)
            elif line.sale and line.sale.warehouse:
                warehouse_ids.add(line.sale.warehouse.id)
        location_ids = list(warehouse_ids)
        if not location_ids:
            return res

        confirmed_lines = cls.search([
                ('sale.state', '=', 'confirmed'),
                ('product', '!=', None),
                ['OR',
                    ('sale.warehouse', 'in', location_ids),
                    ('sale.warehouse', '=', None),
                    ],
                ])
        confirmed_quantities = {}
        for x in confirmed_lines:
            key = (x.warehouse.id, x.product.id)
            if key in confirmed_quantities:
                confirmed_quantities[key] += x.quantity
            else:
                confirmed_quantities[key] = x.quantity

        sale_dates = set(l.sale.sale_date or today for l in lines if l.sale)
        stock_date_end = min(sale_dates) if sale_dates else today

        with Transaction().set_context(locations=location_ids,
                stock_date_end=stock_date_end,
                _check_access=False):
            pbl_product = Product.products_by_location(
                location_ids,
                with_childs=True,
                grouping=('product',),
                grouping_filter=(product_ids,))

        with Transaction().set_context(locations=location_ids,
                forecast=True,
                stock_date_end=datetime.date.max,
                _check_access=False):
            pbl_product_forecast = Product.products_by_location(
                location_ids,
                with_childs=True,
                grouping=('product',),
                grouping_filter=(product_ids,))

        for name in names:
            for line in lines:
                if not (line.type == 'line' and line.product):
                    continue

                product_id = line.product.id
                warehouse_id = (line.warehouse and line.warehouse.id
                    or line.sale.warehouse and line.sale.warehouse.id)
                if not warehouse_id:
                    continue
                key = (warehouse_id, product_id)

                p_qtys = 0
                pforecast_qtys = 0
                if name == 'available_quantity':
                    p_qtys += pbl_product.get(key, 0)
                elif name == 'forecast_quantity':
                    pforecast_qtys += pbl_product_forecast.get(key, 0)

                if name == 'available_quantity':
                    res[name][line.id] = p_qtys
                elif name == 'forecast_quantity':
                    cqty = confirmed_quantities.get(product_id, 0)
                    pforecast_qtys -= cqty
                    if line.quantity and line.sale_state in (
                            'draft', 'quotation'):
                        pforecast_qtys -= line.quantity
                    res[name][line.id] = pforecast_qtys

        return res
