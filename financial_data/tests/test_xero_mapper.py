"""
Tests for XeroAccountingMapper

Tests the transformation of Xero API responses to internal accounting models
"""

from django.test import TestCase
from decimal import Decimal
from datetime import date

from core.models import Account
from integrations.models import Integration, IntegrationProvider
from financial_data.services.xero_mapper import XeroAccountingMapper


class XeroAccountingMapperTest(TestCase):
    """Test XeroAccountingMapper transformations"""

    def setUp(self):
        """Set up test data"""
        self.account = Account.objects.create(name="Test Account")
        self.provider = IntegrationProvider.objects.create(
            name="xero",
            display_name="Xero",
            provider_type="xero",
            auth_url_template="https://login.xero.com/identity/connect/authorize",
            token_url="https://identity.xero.com/connect/token"
        )
        self.integration = Integration.objects.create(
            account=self.account,
            provider=self.provider,
            external_account_id="test_org",
            organization_name="Test Org"
        )
        self.mapper = XeroAccountingMapper(self.integration)

    def test_map_contact_customer(self):
        """Test mapping Xero customer contact"""
        raw_contact = {
            'ContactID': 'xero_contact_123',
            'Name': 'ABC Company',
            'EmailAddress': 'contact@abc.com',
            'IsCustomer': True,
            'IsSupplier': False,
            'Addresses': [{
                'AddressLine1': '123 Business St',
                'City': 'Sydney',
                'Region': 'NSW',
                'PostalCode': '2000',
                'Country': 'Australia'
            }],
            'Phones': [{
                'PhoneNumber': '02-1234-5678'
            }],
            'TaxNumber': 'ABN 12 345 678 901'
        }

        contact_data = self.mapper.map_contact(raw_contact)

        self.assertEqual(contact_data['name'], 'ABC Company')
        self.assertEqual(contact_data['email'], 'contact@abc.com')
        self.assertEqual(contact_data['contact_type'], 'CUSTOMER')
        self.assertEqual(contact_data['external_contact_id'], 'xero_contact_123')
        self.assertEqual(contact_data['address_line_1'], '123 Business St')
        self.assertEqual(contact_data['city'], 'Sydney')
        self.assertEqual(contact_data['state'], 'NSW')
        self.assertEqual(contact_data['phone'], '02-1234-5678')
        self.assertEqual(contact_data['tax_number'], 'ABN 12 345 678 901')
        self.assertEqual(contact_data['integration'], self.integration)
        self.assertEqual(contact_data['account'], self.account)

    def test_map_contact_supplier(self):
        """Test mapping Xero supplier contact"""
        raw_contact = {
            'ContactID': 'xero_supplier_456',
            'Name': 'Office Supplies Ltd',
            'IsCustomer': False,
            'IsSupplier': True,
        }

        contact_data = self.mapper.map_contact(raw_contact)

        self.assertEqual(contact_data['contact_type'], 'SUPPLIER')
        self.assertEqual(contact_data['name'], 'Office Supplies Ltd')

    def test_map_contact_both_customer_and_supplier(self):
        """Test mapping contact that is both customer and supplier"""
        raw_contact = {
            'ContactID': 'xero_both_789',
            'Name': 'Multi Role Company',
            'IsCustomer': True,
            'IsSupplier': True,
        }

        contact_data = self.mapper.map_contact(raw_contact)

        self.assertEqual(contact_data['contact_type'], 'BOTH')

    def test_map_chart_of_accounts_entry_revenue(self):
        """Test mapping Xero revenue account"""
        raw_account = {
            'AccountID': 'xero_acc_200',
            'Code': '200',
            'Name': 'Sales Income',
            'Type': 'REVENUE',
            'Status': 'ACTIVE',
            'TaxType': 'OUTPUT2',
            'SystemAccount': False
        }

        account_data = self.mapper.map_chart_of_accounts_entry(raw_account)

        self.assertEqual(account_data['code'], '200')
        self.assertEqual(account_data['name'], 'Sales Income')
        self.assertEqual(account_data['account_type'], 'REVENUE')
        self.assertEqual(account_data['category'], 'SALES')
        self.assertEqual(account_data['is_active'], True)
        self.assertEqual(account_data['default_tax_code'], 'OUTPUT2')

    def test_map_chart_of_accounts_entry_expense(self):
        """Test mapping Xero expense account"""
        raw_account = {
            'AccountID': 'xero_acc_400',
            'Code': '400',
            'Name': 'Office Expenses',
            'Type': 'EXPENSE',
            'Status': 'ACTIVE',
        }

        account_data = self.mapper.map_chart_of_accounts_entry(raw_account)

        self.assertEqual(account_data['account_type'], 'EXPENSE')
        self.assertEqual(account_data['category'], 'OFFICE_EXPENSES')

    def test_map_sales_invoice(self):
        """Test mapping Xero sales invoice"""
        raw_invoice = {
            'InvoiceID': 'xero_inv_001',
            'Type': 'ACCREC',
            'InvoiceNumber': 'INV-2024-001',
            'Reference': 'PO-12345',
            'Date': '2024-01-15T00:00:00',
            'DueDate': '2024-02-14T00:00:00',
            'Status': 'AUTHORISED',
            'LineAmountTypes': 'Exclusive',
            'SubTotal': 1000.00,
            'TotalTax': 100.00,
            'Total': 1100.00,
            'AmountDue': 1100.00,
            'AmountPaid': 0.00,
            'AmountCredited': 0.00,
            'CurrencyCode': 'AUD',
            'CurrencyRate': 1.0,
            'HasAttachments': False,
            'HasErrors': False,
        }

        invoice_data = self.mapper.map_sales_invoice(raw_invoice)

        self.assertEqual(invoice_data['invoice_number'], 'INV-2024-001')
        self.assertEqual(invoice_data['reference'], 'PO-12345')
        self.assertEqual(invoice_data['status'], 'SENT')  # AUTHORISED maps to SENT
        self.assertEqual(invoice_data['subtotal'], Decimal('1000.00'))
        self.assertEqual(invoice_data['total_tax'], Decimal('100.00'))
        self.assertEqual(invoice_data['total_amount'], Decimal('1100.00'))
        self.assertEqual(invoice_data['amount_due'], Decimal('1100.00'))
        self.assertEqual(invoice_data['invoice_date'], date(2024, 1, 15))
        self.assertEqual(invoice_data['due_date'], date(2024, 2, 14))

    def test_map_invoice_line_item(self):
        """Test mapping Xero invoice line item"""
        raw_line_item = {
            'LineItemID': 'xero_line_001',
            'Description': 'Professional Services',
            'AccountCode': '200',
            'Quantity': 10.0,
            'UnitAmount': 100.00,
            'DiscountRate': 10.0,  # 10% as percentage
            'LineAmount': 900.00,
            'TaxType': 'OUTPUT2',
            'TaxAmount': 90.00,
            'ItemCode': 'PROF-SERV',
            'Tracking': [
                {
                    'TrackingCategoryID': 'track_cat_1',
                    'Name': 'Department',
                    'Option': 'Consulting'
                }
            ]
        }

        line_item_data = self.mapper.map_invoice_line_item(raw_line_item, line_number=1)

        self.assertEqual(line_item_data['description'], 'Professional Services')
        self.assertEqual(line_item_data['account_code'], '200')
        self.assertEqual(line_item_data['quantity'], Decimal('10.0'))
        self.assertEqual(line_item_data['unit_amount'], Decimal('100.00'))
        self.assertEqual(line_item_data['discount_rate'], Decimal('0.10'))  # Converted from percentage
        self.assertEqual(line_item_data['line_amount'], Decimal('900.00'))
        self.assertEqual(line_item_data['tax_amount'], Decimal('90.00'))
        self.assertEqual(line_item_data['tracking_category_1_name'], 'Department')
        self.assertEqual(line_item_data['tracking_category_1_option'], 'Consulting')
        self.assertEqual(line_item_data['line_number'], 1)

    def test_map_invoice_line_item_with_two_tracking_categories(self):
        """Test mapping line item with two tracking categories"""
        raw_line_item = {
            'Description': 'Test Item',
            'AccountCode': '200',
            'UnitAmount': 100.00,
            'LineAmount': 100.00,
            'Tracking': [
                {
                    'TrackingCategoryID': 'track_cat_1',
                    'Name': 'Department',
                    'Option': 'Sales'
                },
                {
                    'TrackingCategoryID': 'track_cat_2',
                    'Name': 'Region',
                    'Option': 'NSW'
                }
            ]
        }

        line_item_data = self.mapper.map_invoice_line_item(raw_line_item, line_number=1)

        self.assertEqual(line_item_data['tracking_category_1_name'], 'Department')
        self.assertEqual(line_item_data['tracking_category_1_option'], 'Sales')
        self.assertEqual(line_item_data['tracking_category_2_name'], 'Region')
        self.assertEqual(line_item_data['tracking_category_2_option'], 'NSW')

    def test_map_purchase_bill(self):
        """Test mapping Xero purchase bill"""
        raw_bill = {
            'InvoiceID': 'xero_bill_001',
            'Type': 'ACCPAY',
            'InvoiceNumber': 'BILL-2024-001',
            'Reference': 'Supplier Ref 123',
            'Date': '2024-01-15T00:00:00',
            'DueDate': '2024-02-14T00:00:00',
            'Status': 'AUTHORISED',
            'SubTotal': 500.00,
            'TotalTax': 50.00,
            'Total': 550.00,
            'AmountDue': 550.00,
            'AmountPaid': 0.00,
            'CurrencyCode': 'AUD',
        }

        bill_data = self.mapper.map_purchase_bill(raw_bill)

        self.assertEqual(bill_data['invoice_number'], 'BILL-2024-001')
        self.assertEqual(bill_data['reference'], 'Supplier Ref 123')
        self.assertEqual(bill_data['status'], 'AUTHORISED')
        self.assertEqual(bill_data['subtotal'], Decimal('500.00'))
        self.assertEqual(bill_data['total_amount'], Decimal('550.00'))

    def test_determine_account_category_sales(self):
        """Test account category determination for sales"""
        category = self.mapper._determine_account_category('REVENUE', '200', 'Sales Income')
        self.assertEqual(category, 'SALES')

    def test_determine_account_category_other_income(self):
        """Test account category determination for other income"""
        category = self.mapper._determine_account_category('REVENUE', '260', 'Interest Income')
        self.assertEqual(category, 'OTHER_INCOME')

    def test_determine_account_category_office_expenses(self):
        """Test account category determination for office expenses"""
        category = self.mapper._determine_account_category('EXPENSE', '400', 'Office Supplies')
        self.assertEqual(category, 'OFFICE_EXPENSES')

    def test_determine_account_category_payroll(self):
        """Test account category determination for payroll"""
        category = self.mapper._determine_account_category('EXPENSE', '500', 'Salary Expenses')
        self.assertEqual(category, 'PAYROLL')

    def test_parse_date_iso_format(self):
        """Test parsing ISO format dates"""
        parsed = self.mapper._parse_date('2024-01-15T00:00:00')
        self.assertEqual(parsed, date(2024, 1, 15))

    def test_parse_date_xero_format(self):
        """Test parsing Xero /Date()/ format"""
        # /Date(1705276800000)/ = 2024-01-15 00:00:00 UTC
        parsed = self.mapper._parse_date('/Date(1705276800000)/')
        self.assertEqual(parsed.year, 2024)
        self.assertEqual(parsed.month, 1)

    def test_parse_date_simple_format(self):
        """Test parsing simple date format"""
        parsed = self.mapper._parse_date('2024-01-15')
        self.assertEqual(parsed, date(2024, 1, 15))

    def test_parse_date_invalid(self):
        """Test parsing invalid date returns None"""
        parsed = self.mapper._parse_date('invalid-date')
        self.assertIsNone(parsed)

    def test_parse_date_empty(self):
        """Test parsing empty date returns None"""
        parsed = self.mapper._parse_date('')
        self.assertIsNone(parsed)
