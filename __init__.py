# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import sale


def register():
    Pool.register(
        sale.SaleLine,
        module='sale_line_product_available', type_='model')
    Pool.register(
        sale.SaleLineDate,
        depends=['purchase', 'stock'],
        module='sale_line_product_available', type_='model')
