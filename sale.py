# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval

__all__ = ['SaleLine']

STATES = {
    'invisible': Eval('_parent_sale', {}).get('state').in_(['done', 'cancel']),
    }


class SaleLine:
    __name__ = 'sale.line'
    __metaclass__ = PoolMeta
    available_quantity = fields.Function(fields.Float('Available Quantity',
            states=STATES), '_get_quantity')
    forecast_quantity = fields.Function(fields.Float('Forecast Quantity',
            states=STATES), '_get_quantity')

    @fields.depends('product', 'quantity', 'sale', 'type')
    def on_change_product(self):
        Line = Pool().get('sale.line')

        super(SaleLine, self).on_change_product()

        self.available_quantity = None
        self.forecast_quantity = None
        if self.product:
            id_ = self.id
            qty = Line._get_quantity([self], [
                'available_quantity', 'forecast_quantity'])
            self.available_quantity = qty['available_quantity'][id_]
            forecast_quantity = qty['forecast_quantity'][id_]
            if self.quantity and (self.sale and self.sale.state == 'confirmed'):
                forecast_quantity -= self.quantity
            self.forecast_quantity = forecast_quantity

    @fields.depends('product', 'quantity', 'sale', 'type')
    def on_change_quantity(self):
        Line = Pool().get('sale.line')

        super(SaleLine, self).on_change_quantity()

        if self.product and (self.sale and self.sale.state == 'confirmed'):
            id_ = self.id
            quantities = Line._get_quantity([self], ['forecast_quantity'])
            quantity = quantities['forecast_quantity'][id_]
            if id_ > 0:
                quantity += Line(id_).quantity
            if self.quantity:
                quantity -= self.quantity
            self.forecast_quantity = quantity

    @classmethod
    def _get_quantity(cls, lines, names):
        pool = Pool()
        Location = pool.get('stock.location')
        Product = pool.get('product.product')
        Date = pool.get('ir.date')

        product_ids = list(set([x.product.id for x in lines if x.product]))

        res = {}
        for name in names:
            res[name] = dict((l.id, None) for l in lines)
        if not product_ids:
            return res

        # get the quantity according to the warehouses from sale
        warehouses = set()
        for line in lines:
            if line.sale and line.sale.warehouse:
                warehouses.add(line.sale.warehouse.id)
        if warehouses:
            warehouses = list(warehouses)
        else:
            warehouses = [x.id for x in Location.search([
                'type', '=', 'warehouse'])]

        context = {
            'locations': warehouses,
            'stock_date_end': Date.today(),
            'with_childs': True,
            }

        confirmed_lines = cls.search([
                ('sale.state', '=', 'confirmed'),
                ('product', '!=', None),
                ['OR',
                    ('sale.warehouse', 'in', warehouses),
                    ('sale.warehouse', '=', None),
                    ],
                ])
        confirmed_quantities = {}
        for x in confirmed_lines:
            product_id = x.product.id
            if product_id in confirmed_quantities:
                confirmed_quantities[product_id] += x.quantity
            else:
                confirmed_quantities[product_id] = x.quantity

        for name in names:
            if name == 'forecast_quantity':
                context.update({'forecast': True})
            with Transaction().set_context(context):
                products = Product.browse(product_ids)

            res[name] = dict([(x.id, None) for x in lines])
            values = {}
            for product in products:
                product_id = product.id
                if name == 'available_quantity':
                    values[product_id] = product.quantity
                else:
                    if product_id in confirmed_quantities:
                        confirmed_quantity = confirmed_quantities[product_id]
                    else:
                        confirmed_quantity = 0.0
                    values[product_id] = (product.forecast_quantity -
                        confirmed_quantity)

            for line in lines:
                if line.type == 'line' and line.product:
                    res[name][line.id] = values.get(line.product.id)
        return res
