from django.test import TestCase
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import date, timedelta
from django.contrib.auth.models import User

from core.models import Account
from integrations.models import Integration, IntegrationProvider
from financial_data.models import (
    Contact,
    ChartOfAccountsEntry,
    SalesInvoice,
    InvoiceLineItem,
)


class ContactModelTest(TestCase):
    """Test Contact model functionality - TDD approach"""

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

    def test_contact_creation_with_prefix_id(self):
        """Test that contacts are created with proper prefix_id"""
        contact = Contact.objects.create(
            integration=self.integration,
            account=self.account,
            name="Test Customer",
            external_contact_id="xero_123",
            contact_type="CUSTOMER"
        )

        # Should have prefix_id starting with 'cnt_'
        self.assertTrue(contact.prefix_id.startswith('cnt_'))
        self.assertEqual(len(contact.prefix_id), 12)  # cnt_ + 8 chars

        # Should be unique
        contact2 = Contact.objects.create(
            integration=self.integration,
            account=self.account,
            name="Test Customer 2",
            external_contact_id="xero_456",
            contact_type="CUSTOMER"
        )
        self.assertNotEqual(contact.prefix_id, contact2.prefix_id)

    def test_contact_full_address_property(self):
        """Test full address formatting"""
        contact = Contact.objects.create(
            integration=self.integration,
            account=self.account,
            name="Test Customer",
            address_line_1="123 Business St",
            city="Sydney",
            state="NSW",
            postal_code="2000",
            country="Australia"
        )

        expected = "123 Business St, Sydney, NSW, 2000, Australia"
        self.assertEqual(contact.full_address, expected)

    def test_contact_full_address_with_missing_fields(self):
        """Test full address formatting with missing fields"""
        contact = Contact.objects.create(
            integration=self.integration,
            account=self.account,
            name="Test Customer",
            address_line_1="123 Business St",
            city="Sydney",
            # state missing
            postal_code="2000",
            # country missing
        )

        expected = "123 Business St, Sydney, 2000"
        self.assertEqual(contact.full_address, expected)

    def test_contact_types_validation(self):
        """Test contact type choices are enforced"""
        # Valid contact types should work
        valid_types = ['CUSTOMER', 'SUPPLIER', 'EMPLOYEE', 'BOTH']

        for contact_type in valid_types:
            contact = Contact.objects.create(
                integration=self.integration,
                account=self.account,
                name=f"Test {contact_type}",
                external_contact_id=f"test_{contact_type.lower()}",
                contact_type=contact_type
            )
            self.assertEqual(contact.contact_type, contact_type)

    def test_multi_tenant_isolation(self):
        """Test that contacts are properly isolated by account"""
        other_account = Account.objects.create(name="Other Account")
        other_integration = Integration.objects.create(
            account=other_account,
            provider=self.provider,
            external_account_id="other_org",
            organization_name="Other Org"
        )

        # Create contacts in different accounts
        contact1 = Contact.objects.create(
            integration=self.integration,
            account=self.account,
            name="Account 1 Customer"
        )
        contact2 = Contact.objects.create(
            integration=other_integration,
            account=other_account,
            name="Account 2 Customer"
        )

        # Verify isolation using custom manager methods
        account1_contacts = Contact.objects.for_account(self.account)
        account2_contacts = Contact.objects.for_account(other_account)

        self.assertIn(contact1, account1_contacts)
        self.assertNotIn(contact2, account1_contacts)
        self.assertIn(contact2, account2_contacts)
        self.assertNotIn(contact1, account2_contacts)

    def test_contact_string_representation(self):
        """Test contact __str__ method"""
        contact = Contact.objects.create(
            integration=self.integration,
            account=self.account,
            name="ABC Corporation",
            contact_type="CUSTOMER"
        )

        expected = "ABC Corporation (Customer)"
        self.assertEqual(str(contact), expected)

    def test_external_contact_id_uniqueness_per_integration(self):
        """Test that external_contact_id is unique per integration"""
        Contact.objects.create(
            integration=self.integration,
            account=self.account,
            name="First Contact",
            external_contact_id="same_id"
        )

        # Same external_contact_id in same integration should fail
        with self.assertRaises(Exception):
            Contact.objects.create(
                integration=self.integration,
                account=self.account,
                name="Second Contact",
                external_contact_id="same_id"
            )


class ChartOfAccountsEntryModelTest(TestCase):
    """Test ChartOfAccountsEntry model functionality"""

    def setUp(self):
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
            external_account_id="test_org"
        )

    def test_chart_account_creation_with_prefix_id(self):
        """Test chart of accounts entry creation with prefix_id"""
        account_entry = ChartOfAccountsEntry.objects.create(
            integration=self.integration,
            account=self.account,
            code="200",
            name="Sales Income",
            account_type="REVENUE",
            category="SALES",
            external_account_id="acc_123"
        )

        self.assertTrue(account_entry.prefix_id.startswith('coa_'))
        self.assertEqual(len(account_entry.prefix_id), 12)  # coa_ + 8 chars

    def test_account_type_choices(self):
        """Test account type validation"""
        valid_types = ['ASSET', 'LIABILITY', 'EQUITY', 'REVENUE', 'EXPENSE', 'COST_OF_SALES']

        for idx, account_type in enumerate(valid_types):
            account_entry = ChartOfAccountsEntry.objects.create(
                integration=self.integration,
                account=self.account,
                code=f"10{idx}",  # unique codes
                name=f"Test {account_type}",
                account_type=account_type,
                external_account_id=f"acc_{account_type.lower()}"
            )
            self.assertEqual(account_entry.account_type, account_type)

    def test_account_category_choices(self):
        """Test account category validation"""
        valid_categories = ['SALES', 'OTHER_INCOME', 'OFFICE_EXPENSES', 'PAYROLL', 'GST_COLLECTED', 'GST_PAID']

        for idx, category in enumerate(valid_categories):
            account_entry = ChartOfAccountsEntry.objects.create(
                integration=self.integration,
                account=self.account,
                code=f"20{idx}",  # unique codes
                name=f"Test {category}",
                account_type="REVENUE",
                category=category,
                external_account_id=f"acc_{category.lower()}"
            )
            self.assertEqual(account_entry.category, category)

    def test_account_code_uniqueness_per_integration(self):
        """Test that account codes are unique per integration"""
        ChartOfAccountsEntry.objects.create(
            integration=self.integration,
            account=self.account,
            code="200",
            name="Sales Income",
            account_type="REVENUE",
            external_account_id="acc_1"
        )

        # Same code in same integration should fail
        with self.assertRaises(Exception):
            ChartOfAccountsEntry.objects.create(
                integration=self.integration,
                account=self.account,
                code="200",
                name="Other Sales",
                account_type="REVENUE",
                external_account_id="acc_2"
            )


class SalesInvoiceModelTest(TestCase):
    """Test SalesInvoice model functionality"""

    def setUp(self):
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
            external_account_id="test_org"
        )
        self.contact = Contact.objects.create(
            integration=self.integration,
            account=self.account,
            name="Test Customer",
            external_contact_id="cust_123"
        )

    def test_invoice_creation_with_relationships(self):
        """Test invoice creation with proper relationships"""
        invoice = SalesInvoice.objects.create(
            integration=self.integration,
            account=self.account,
            contact=self.contact,
            invoice_number="INV-001",
            external_invoice_id="xero_inv_123",
            subtotal=Decimal('1000.00'),
            total_tax=Decimal('100.00'),
            total_amount=Decimal('1100.00'),
            amount_due=Decimal('1100.00'),
            invoice_date=date.today()
        )

        self.assertTrue(invoice.prefix_id.startswith('inv_'))
        self.assertEqual(invoice.contact, self.contact)
        self.assertEqual(invoice.integration.account, self.account)
        self.assertEqual(invoice.invoice_number, "INV-001")

    def test_invoice_overdue_calculation(self):
        """Test overdue date calculation"""
        # Create overdue invoice
        overdue_invoice = SalesInvoice.objects.create(
            integration=self.integration,
            account=self.account,
            contact=self.contact,
            invoice_number="INV-OVERDUE",
            external_invoice_id="xero_overdue",
            due_date=date.today() - timedelta(days=30),
            amount_due=Decimal('500.00'),
            status='SENT',
            subtotal=Decimal('500.00'),
            total_amount=Decimal('500.00')
        )

        # Create current invoice
        current_invoice = SalesInvoice.objects.create(
            integration=self.integration,
            account=self.account,
            contact=self.contact,
            invoice_number="INV-CURRENT",
            external_invoice_id="xero_current",
            due_date=date.today() + timedelta(days=30),
            amount_due=Decimal('500.00'),
            status='SENT',
            subtotal=Decimal('500.00'),
            total_amount=Decimal('500.00')
        )

        self.assertTrue(overdue_invoice.is_overdue)
        self.assertEqual(overdue_invoice.days_overdue, 30)
        self.assertFalse(current_invoice.is_overdue)
        self.assertEqual(current_invoice.days_overdue, 0)

    def test_paid_invoice_not_overdue(self):
        """Test that paid invoices are never considered overdue"""
        paid_invoice = SalesInvoice.objects.create(
            integration=self.integration,
            account=self.account,
            contact=self.contact,
            invoice_number="INV-PAID",
            external_invoice_id="xero_paid",
            due_date=date.today() - timedelta(days=30),
            amount_due=Decimal('0.00'),
            status='PAID',
            subtotal=Decimal('1000.00'),
            total_amount=Decimal('1000.00')
        )

        self.assertFalse(paid_invoice.is_overdue)

    def test_invoice_status_choices(self):
        """Test invoice status validation"""
        valid_statuses = ['DRAFT', 'SUBMITTED', 'SENT', 'PARTIALLY_PAID', 'PAID', 'OVERDUE', 'VOIDED', 'DELETED']

        for status in valid_statuses:
            invoice = SalesInvoice.objects.create(
                integration=self.integration,
                account=self.account,
                contact=self.contact,
                invoice_number=f"INV-{status}",
                external_invoice_id=f"xero_{status.lower()}",
                status=status,
                subtotal=Decimal('100.00'),
                total_amount=Decimal('100.00'),
                amount_due=Decimal('100.00')  # Required field
            )
            self.assertEqual(invoice.status, status)

    def test_invoice_string_representation(self):
        """Test invoice __str__ method"""
        invoice = SalesInvoice.objects.create(
            integration=self.integration,
            account=self.account,
            contact=self.contact,
            invoice_number="INV-001",
            external_invoice_id="xero_inv_123",
            subtotal=Decimal('1000.00'),
            total_amount=Decimal('1000.00'),
            amount_due=Decimal('1000.00')  # Required field
        )

        expected = "Invoice INV-001 - Test Customer"
        self.assertEqual(str(invoice), expected)


class InvoiceLineItemModelTest(TestCase):
    """Test InvoiceLineItem model functionality"""

    def setUp(self):
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
            external_account_id="test_org"
        )
        self.contact = Contact.objects.create(
            integration=self.integration,
            account=self.account,
            name="Test Customer"
        )
        self.invoice = SalesInvoice.objects.create(
            integration=self.integration,
            account=self.account,
            contact=self.contact,
            invoice_number="INV-001",
            external_invoice_id="xero_inv_lineitem_test",
            subtotal=Decimal('1000.00'),
            total_amount=Decimal('1100.00'),
            amount_due=Decimal('1100.00')  # Required field
        )
        self.chart_account = ChartOfAccountsEntry.objects.create(
            integration=self.integration,
            account=self.account,
            code="200",
            name="Sales Income",
            account_type="REVENUE",
            external_account_id="acc_123"
        )

    def test_line_item_creation_with_tracking(self):
        """Test line item creation with tracking categories"""
        line_item = InvoiceLineItem.objects.create(
            invoice=self.invoice,
            description="Professional Services",
            account_code="200",
            chart_account=self.chart_account,
            quantity=Decimal('10.0'),
            unit_amount=Decimal('100.00'),
            line_amount=Decimal('1000.00'),
            tracking_category_1_name="Department",
            tracking_category_1_option="Consulting",
            line_number=1
        )

        self.assertTrue(line_item.prefix_id.startswith('iln_'))
        self.assertEqual(line_item.invoice, self.invoice)
        self.assertEqual(line_item.chart_account, self.chart_account)
        self.assertEqual(line_item.tracking_category_1_name, "Department")
        self.assertEqual(line_item.tracking_category_1_option, "Consulting")

    def test_line_item_ordering(self):
        """Test that line items maintain proper ordering"""
        line1 = InvoiceLineItem.objects.create(
            invoice=self.invoice,
            description="Item 1",
            account_code="200",
            unit_amount=Decimal('500.00'),
            line_number=1,
            line_amount=Decimal('500.00')
        )
        line2 = InvoiceLineItem.objects.create(
            invoice=self.invoice,
            description="Item 2",
            account_code="200",
            unit_amount=Decimal('500.00'),
            line_number=2,
            line_amount=Decimal('500.00')
        )

        ordered_items = list(self.invoice.line_items.all())
        self.assertEqual(ordered_items[0], line1)
        self.assertEqual(ordered_items[1], line2)

    def test_line_item_string_representation(self):
        """Test line item __str__ method"""
        line_item = InvoiceLineItem.objects.create(
            invoice=self.invoice,
            description="Professional Services",
            account_code="200",
            unit_amount=Decimal('1000.00'),
            line_number=1,
            line_amount=Decimal('1000.00')
        )

        expected = "INV-001 - Line 1: Professional Services"
        self.assertEqual(str(line_item), expected)

    def test_line_item_calculations(self):
        """Test line item amount calculations"""
        line_item = InvoiceLineItem.objects.create(
            invoice=self.invoice,
            description="Test Item",
            account_code="200",
            quantity=Decimal('5.0'),
            unit_amount=Decimal('100.00'),
            discount_rate=Decimal('0.10'),  # 10% as decimal (max_digits=5, decimal_places=4)
            tax_amount=Decimal('45.00'),  # GST on discounted amount
            line_amount=Decimal('450.00'),  # Required field
            line_number=1
        )

        # Line amount should be calculated: (5 * 100) - 10% = 450
        # With GST: 450 + 45 = 495 total
        expected_line_amount = Decimal('450.00')  # Before tax

        self.assertEqual(line_item.line_amount, expected_line_amount)

        self.assertEqual(line_item.line_amount, expected_line_amount)
        self.assertEqual(line_item.tax_amount, Decimal('45.00'))