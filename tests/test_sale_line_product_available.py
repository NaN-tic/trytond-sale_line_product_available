# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase


class SaleLineProductAvailableTestCase(ModuleTestCase):
    'Test SaleLine Product Available'
    module = 'sale_line_product_available'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        SaleLineProductAvailableTestCase))
    return suite
