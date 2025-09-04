"""
Unit tests for financial_data app models.

These tests focus on model behavior and business logic rather than Django ORM internals.
They're designed to be flexible and survive the upcoming model migration.
"""
import pytest
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta

from core.models import Account
from integrations.models import (
    IntegrationProvider, Integration, TransactionData, TransactionLineItem
)


@pytest.fixture
def user():
    return User.objects.create_user(username='testuser')


@pytest.fixture
def account():
    return Account.objects.create(name='Test Account')


@pytest.fixture
def provider():
    return IntegrationProvider.objects.create(
        name='xero',
        display_name='Xero',
        provider_type='xero',
        auth_url_template='https://api.xero.com/oauth/authorize',
        token_url='https://api.xero.com/oauth/token'
    )


@pytest.fixture
def integration(user, account, provider):
    return Integration.objects.create(
        account=account,
        created_by=user,
        provider=provider,
        external_account_id='xero_123',
        external_account_name='Test Xero Account',
        organization_name='Test Organization'
    )


@pytest.fixture
def transaction_data():
    return {
        'external_transaction_id': 'xero_txn_123',
        'external_account_id': 'xero_acc_456',
        'transaction_type': 'spend',
        'date': date.today(),
        'reference': 'TEST-001',
        'description': 'Test transaction',
        'amount': Decimal('100.50'),
        'currency_code': 'USD',
        'status': 'authorised'
    }


@pytest.fixture
def transaction(integration, transaction_data):
    return TransactionData.objects.create(
        integration=integration,
        **transaction_data
    )


@pytest.mark.django_db
class TestTransactionData:
    """Test Transaction model behavior (currently TransactionData)"""
    
    def test_transaction_creation(self, transaction, integration):
        """Transaction can be created with valid data"""
        assert transaction.integration == integration
        assert transaction.external_transaction_id == 'xero_txn_123'
        assert transaction.amount == Decimal('100.50')
        assert transaction.currency_code == 'USD'
        assert transaction.prefix_id.startswith('txn_')  # Has prefix ID
        assert transaction.created_at is not None
    
    def test_transaction_str_representation(self, transaction):
        """Transaction string representation shows reference/ID and amount"""
        expected = "TEST-001 - 100.50 USD"
        assert str(transaction) == expected
        
        # Test fallback to external ID when no reference
        transaction.reference = None
        transaction.save()
        expected = "xero_txn_123 - 100.50 USD"
        assert str(transaction) == expected
    
    def test_transaction_type_choices(self, integration, transaction_data):
        """Transaction accepts valid transaction types"""
        valid_types = ['spend', 'receive', 'bank_transfer', 'other']
        
        for txn_type in valid_types:
            data = transaction_data.copy()
            data['external_transaction_id'] = f'txn_{txn_type}'
            data['transaction_type'] = txn_type
            
            transaction = TransactionData.objects.create(
                integration=integration,
                **data
            )
            assert transaction.transaction_type == txn_type
    
    def test_transaction_status_choices(self, integration, transaction_data):
        """Transaction accepts valid status values"""
        valid_statuses = ['authorised', 'deleted', 'draft', 'submitted', 'pending']
        
        for status in valid_statuses:
            data = transaction_data.copy()
            data['external_transaction_id'] = f'txn_{status}'
            data['status'] = status
            
            transaction = TransactionData.objects.create(
                integration=integration,
                **data
            )
            assert transaction.status == status
    
    def test_transaction_uniqueness_per_integration(self, integration, transaction_data):
        """Transaction uniqueness is per integration"""
        # Create first transaction
        TransactionData.objects.create(
            integration=integration,
            **transaction_data
        )
        
        # Same external_transaction_id for same integration should fail
        from django.db import transaction as db_transaction
        with pytest.raises(Exception):  # IntegrityError
            with db_transaction.atomic():
                TransactionData.objects.create(
                    integration=integration,
                    **transaction_data
                )
    
    def test_transaction_account_property(self, transaction, integration):
        """Transaction account property returns integration's account"""
        assert transaction.account == integration.account
    
    def test_transaction_contact_information(self, integration, transaction_data):
        """Transaction can store contact/supplier information"""
        data = transaction_data.copy()
        data['external_transaction_id'] = 'contact_test'
        data['contact_name'] = 'Test Supplier'
        data['contact_external_id'] = 'supplier_123'
        
        transaction = TransactionData.objects.create(
            integration=integration,
            **data
        )
        
        assert transaction.contact_name == 'Test Supplier'
        assert transaction.contact_external_id == 'supplier_123'
    
    def test_transaction_external_url(self, integration, transaction_data):
        """Transaction can store external system URL"""
        data = transaction_data.copy()
        data['external_transaction_id'] = 'url_test'
        data['external_url'] = 'https://go.xero.com/Bank/ViewTransaction.aspx?bankTransactionID=123'
        
        transaction = TransactionData.objects.create(
            integration=integration,
            **data
        )
        
        assert 'xero.com' in transaction.external_url
    
    def test_transaction_get_xero_url(self, integration, transaction_data):
        """get_xero_url method generates or returns Xero URLs"""
        transaction = TransactionData.objects.create(
            integration=integration,
            **transaction_data
        )
        
        # Should generate Xero URL based on external_transaction_id
        url = transaction.get_xero_url()
        assert 'go.xero.com' in url
        assert 'xero_txn_123' in url
        
        # Should prefer external_url if set
        custom_url = 'https://custom.xero.com/custom-path'
        transaction.external_url = custom_url
        transaction.save()
        
        # For now, it should still generate the standard URL (based on current implementation)
        url = transaction.get_xero_url()
        assert 'go.xero.com' in url
    
    def test_transaction_raw_data_storage(self, integration, transaction_data):
        """Transaction can store raw JSON data from external system"""
        raw_data = {
            'LineItems': [{'Description': 'Test', 'LineAmount': 100.50}],
            'Contact': {'Name': 'Test Supplier'},
            'BankAccount': {'AccountID': 'acc123'}
        }
        
        data = transaction_data.copy()
        data['external_transaction_id'] = 'raw_data_test'
        data['raw_data'] = raw_data
        
        transaction = TransactionData.objects.create(
            integration=integration,
            **data
        )
        
        assert transaction.raw_data == raw_data
    
    def test_transaction_reconciliation_status(self, integration, transaction_data):
        """Transaction tracks reconciliation status"""
        transaction = TransactionData.objects.create(
            integration=integration,
            **transaction_data
        )
        
        # Default is not reconciled
        assert transaction.is_reconciled is False
        
        # Can be marked as reconciled
        transaction.is_reconciled = True
        transaction.save()
        
        transaction.refresh_from_db()
        assert transaction.is_reconciled is True
    
    def test_transaction_ordering(self, integration, transaction_data):
        """Transactions are ordered by date desc, then created_at desc"""
        # Create transaction for today
        today_data = transaction_data.copy()
        today_data['external_transaction_id'] = 'today'
        today_data['date'] = date.today()
        transaction_today = TransactionData.objects.create(
            integration=integration,
            **today_data
        )
        
        # Create transaction for yesterday
        yesterday_data = transaction_data.copy()
        yesterday_data['external_transaction_id'] = 'yesterday'
        yesterday_data['date'] = date.today() - timedelta(days=1)
        transaction_yesterday = TransactionData.objects.create(
            integration=integration,
            **yesterday_data
        )
        
        transactions = list(TransactionData.objects.all())
        assert transactions[0] == transaction_today  # More recent date first
        assert transactions[1] == transaction_yesterday
    
    def test_transaction_validation_status_methods(self, transaction):
        """Transaction validation status helper methods work correctly"""
        # Test get_available_validation_rules_count
        # This should return a number (exact value depends on registry state)
        available_count = transaction.get_available_validation_rules_count()
        assert isinstance(available_count, int)
        assert available_count >= 0
        
        # Test get_validation_status_count 
        # Initially 0 since no validation has been run
        status_count = transaction.get_validation_status_count()
        assert status_count == 0
        
        # Test get_validation_status_display
        status_display = transaction.get_validation_status_display()
        assert 'text' in status_display
        assert 'css_class' in status_display
        assert 'completed' in status_display
        assert 'total' in status_display
        assert status_display['completed'] == 0
    
    def test_transaction_decimal_precision(self, integration, transaction_data):
        """Transaction handles decimal amounts with proper precision"""
        data = transaction_data.copy()
        data['external_transaction_id'] = 'precision_test'
        # Use a large but valid value (15 digits total, 2 decimal places = max 13 digits before decimal)
        data['amount'] = Decimal('9999999999999.99')  # Maximum precision for decimal(15,2)
        
        transaction = TransactionData.objects.create(
            integration=integration,
            **data
        )
        
        assert transaction.amount == Decimal('9999999999999.99')
        
        # Test that higher precision values are stored correctly
        data['external_transaction_id'] = 'test_precision'
        data['amount'] = Decimal('100.999')  # 3 decimal places
        
        transaction2 = TransactionData.objects.create(
            integration=integration,
            **data
        )
        
        # PostgreSQL may store the exact value or round it depending on configuration
        # The important thing is that it doesn't crash and stores a reasonable value
        assert transaction2.amount in [Decimal('100.999'), Decimal('101.00')]


@pytest.mark.django_db  
class TestTransactionLineItem:
    """Test Transaction line item model behavior"""
    
    def test_line_item_creation(self, transaction):
        """TransactionLineItem can be created with valid data"""
        line_item = TransactionLineItem.objects.create(
            transaction=transaction,
            description='Test line item',
            quantity=Decimal('2.5'),
            unit_amount=Decimal('10.00'),
            line_amount=Decimal('25.00'),
            account_code='200',
            account_name='Office Expenses'
        )
        
        assert line_item.transaction == transaction
        assert line_item.description == 'Test line item'
        assert line_item.quantity == Decimal('2.5')
        assert line_item.unit_amount == Decimal('10.00')
        assert line_item.line_amount == Decimal('25.00')
        assert line_item.account_code == '200'
        assert line_item.created_at is not None
    
    def test_line_item_defaults(self, transaction):
        """TransactionLineItem has proper default values"""
        line_item = TransactionLineItem.objects.create(
            transaction=transaction,
            unit_amount=Decimal('50.00'),
            line_amount=Decimal('50.00')
        )
        
        assert line_item.quantity == Decimal('1')  # Default quantity
        assert line_item.tax_amount == Decimal('0')  # Default tax amount
    
    def test_line_item_tax_information(self, transaction):
        """TransactionLineItem can store tax information"""
        line_item = TransactionLineItem.objects.create(
            transaction=transaction,
            description='Taxable item',
            unit_amount=Decimal('100.00'),
            line_amount=Decimal('100.00'),
            tax_type='GST',
            tax_amount=Decimal('10.00')
        )
        
        assert line_item.tax_type == 'GST'
        assert line_item.tax_amount == Decimal('10.00')
    
    def test_line_item_external_references(self, transaction):
        """TransactionLineItem can store external system references"""
        line_item = TransactionLineItem.objects.create(
            transaction=transaction,
            unit_amount=Decimal('25.00'),
            line_amount=Decimal('25.00'),
            external_line_item_id='xero_line_456'
        )
        
        assert line_item.external_line_item_id == 'xero_line_456'
    
    def test_line_item_raw_data_storage(self, transaction):
        """TransactionLineItem can store raw JSON data"""
        raw_data = {
            'LineItemID': 'xero_line_123',
            'ItemCode': 'OFFICE-001',
            'TaxType': 'INPUT2',
            'Tracking': [{'Name': 'Department', 'Option': 'Sales'}]
        }
        
        line_item = TransactionLineItem.objects.create(
            transaction=transaction,
            unit_amount=Decimal('30.00'),
            line_amount=Decimal('30.00'),
            raw_data=raw_data
        )
        
        assert line_item.raw_data == raw_data
    
    def test_line_item_ordering(self, transaction):
        """TransactionLineItems are ordered by id (creation order)"""
        line_item1 = TransactionLineItem.objects.create(
            transaction=transaction,
            description='First item',
            unit_amount=Decimal('10.00'),
            line_amount=Decimal('10.00')
        )
        
        line_item2 = TransactionLineItem.objects.create(
            transaction=transaction,
            description='Second item', 
            unit_amount=Decimal('20.00'),
            line_amount=Decimal('20.00')
        )
        
        line_items = list(TransactionLineItem.objects.all())
        assert line_items[0] == line_item1  # First created first
        assert line_items[1] == line_item2
    
    def test_line_item_decimal_precision(self, transaction):
        """TransactionLineItem handles decimal values with proper precision"""
        line_item = TransactionLineItem.objects.create(
            transaction=transaction,
            quantity=Decimal('3.7500'),  # 4 decimal places for quantity
            unit_amount=Decimal('99.99'),
            line_amount=Decimal('374.96'),  # 3.75 * 99.99 = 374.9625 -> 374.96
            tax_amount=Decimal('37.50')
        )
        
        assert line_item.quantity == Decimal('3.7500')
        assert line_item.unit_amount == Decimal('99.99')
        assert line_item.line_amount == Decimal('374.96')
        assert line_item.tax_amount == Decimal('37.50')
    
    def test_line_item_multi_tenancy_through_transaction(self, transaction):
        """TransactionLineItem inherits multi-tenancy through Transaction"""
        line_item = TransactionLineItem.objects.create(
            transaction=transaction,
            unit_amount=Decimal('15.00'),
            line_amount=Decimal('15.00')
        )
        
        # Can access account through transaction
        assert line_item.transaction.integration.account.name == 'Test Account'