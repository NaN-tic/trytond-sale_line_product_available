import datetime
import unittest
from decimal import Decimal

from proteus import Model
from trytond.modules.account.tests.tools import (create_chart,
    create_fiscalyear, create_tax, get_accounts)
from trytond.modules.account_invoice.tests.tools import (
    create_payment_term, set_fiscalyear_invoice_sequences)
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):

        # Install account_invoice
        config = activate_modules(['sale_line_product_available', 'purchase',
                'stock'])

        # Create company
        _ = create_company()
        company = get_company()

        # Reload the context
        User = Model.get('res.user')
        Group = Model.get('res.group')
        config._context = User.get_preferences(True, config.context)

        # Create user with permisos for sale/purchase and stock
        user = User()
        user.name = 'User'
        user.login = 'user'
        sale_group, = Group.find([('name', '=', 'Sales')])
        stock_group, = Group.find([('name', '=', 'Stock')])
        purchase_group, = Group.find([('name', '=', 'Purchase')])
        user.groups.append(sale_group)
        user.groups.append(stock_group)
        user.groups.append(purchase_group)
        user.save()

        # Create fiscal year
        fiscalyear = set_fiscalyear_invoice_sequences(
            create_fiscalyear(company))
        fiscalyear.click('create_period')

        # Create chart of accounts
        _ = create_chart(company)
        accounts = get_accounts(company)
        revenue = accounts['revenue']
        expense = accounts['expense']

        # Create tax
        tax = create_tax(Decimal('.10'))
        tax.save()

        # Create parties
        Party = Model.get('party.party')
        supplier = Party(name='Supplier')
        supplier.save()
        customer = Party(name='Customer')
        customer.save()

        # Create account category
        ProductCategory = Model.get('product.category')
        account_category = ProductCategory(name="Account Category")
        account_category.accounting = True
        account_category.account_expense = expense
        account_category.account_revenue = revenue
        account_category.customer_taxes.append(tax)
        account_category.save()

        # Create product
        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        ProductTemplate = Model.get('product.template')
        Product = Model.get('product.product')
        product = Product()
        template = ProductTemplate()
        template.name = 'product'
        template.default_uom = unit
        template.type = 'goods'
        template.salable = True
        template.purchasable = True
        template.list_price = Decimal('10')
        template.cost_price = Decimal('5')
        template.cost_price_method = 'fixed'
        template.account_category = account_category
        template.save()
        product, = template.products
        product.save()
        service = Product()
        template = ProductTemplate()
        template.name = 'service'
        template.default_uom = unit
        template.type = 'service'
        template.salable = True
        template.list_price = Decimal('30')
        template.cost_price = Decimal('10')
        template.cost_price_method = 'fixed'
        template.account_category = account_category
        template.save()
        service, = template.products
        service.save()

        # Create payment term
        payment_term = create_payment_term()
        payment_term.save()

        # purchase some products
        today = datetime.date.today()
        Purchase = Model.get('purchase.purchase')
        Location = Model.get('stock.location')
        purchase = Purchase()
        purchase.party = customer
        purchase.purchase_date = today
        purchase.delivery_date = today
        purchase.warehouse, = Location.find([('type', '=', 'warehouse')])
        purchase.payment_term = payment_term
        purchase_line = purchase.lines.new()
        purchase_line.product = product
        purchase_line.quantity = 100.0
        purchase_line.unit_price = Decimal(2.0)
        purchase.click('quote')
        purchase.click('confirm')
        self.assertEqual(purchase.state, 'processing')

        # Sale 5 products
        config.user = user.id
        Sale = Model.get('sale.sale')
        sale = Sale()
        sale.party = customer
        sale.payment_term = payment_term
        sale.warehouse, = Location.find([('type', '=', 'warehouse')])
        sale.invoice_method = 'order'
        sale.sale_date = today
        sale_line = sale.lines.new()
        sale_line.product = product
        sale_line.quantity = 5
        self.assertEqual(sale_line.available_quantity, 0.0)
        self.assertEqual(sale_line.forecast_quantity, 95.0)
        self.assertEqual(sale_line.in_planned_date,
            today.strftime("%m/%d/%Y") + ' (100\xa0u)')

        # Validate Shipments
        Move = Model.get('stock.move')
        ShipmentIn = Model.get('stock.shipment.in')
        shipment = ShipmentIn()
        shipment.supplier = customer
        for move in purchase.moves:
            incoming_move = Move(id=move.id)
            shipment.incoming_moves.append(incoming_move)
        shipment.save()
        self.assertEqual(shipment.origins, purchase.rec_name)
        shipment.click('receive')
        shipment.click('do')
        purchase.reload()
        self.assertEqual(purchase.shipment_state, 'received')
        self.assertEqual(len(purchase.shipments), 1)

        # Finis sale
        sale_line = sale.lines.new()
        sale_line.type = 'comment'
        sale_line.description = 'Comment'
        sale.click('quote')
        sale.click('confirm')
        shipment, = sale.shipments
        sale2 = Sale()
        sale2.party = customer
        sale2.payment_term = payment_term
        sale2.invoice_method = 'order'
        sale2_line = sale2.lines.new()
        sale2_line.product = product
        sale2_line.quantity = 5
        self.assertEqual(sale2_line.available_quantity, 100.0)
        self.assertEqual(sale2_line.forecast_quantity, 90.0)
        sale2.save()

        # Done shipment
        shipment.click('assign_try')
        shipment.click('pick')
        shipment.click('pack')
        shipment.click('do')
        self.assertEqual(shipment.state, 'done')

        # Check quantities in sale 2
        line2, = sale2.lines
        self.assertEqual(line2.available_quantity, 95.0)
        self.assertEqual(line2.forecast_quantity, 90.0)

        sale2.click('quote')
        sale2.click('confirm')
        line2.reload()
        self.assertEqual(line2.forecast_quantity, 90.0)
