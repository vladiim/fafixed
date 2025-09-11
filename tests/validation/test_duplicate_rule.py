"""
Tests for DuplicateTransactionRule.
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta
from django.contrib.auth.models import User

from core.models import Account
from connections.models import Connection, Provider
from financial_data.models import Transaction
from data_quality.validation.rules.duplicates import DuplicateTransactionRule
from data_quality.validation.base import ValidationSeverity
from data_quality.validation.registry import ValidationRuleRegistry
from .base_validation_test import BaseValidationTestCase


class TestDuplicateTransactionRule(BaseValidationTestCase):
    """Test cases for DuplicateTransactionRule."""
    
    def setUp(self):
        """Set up test data."""
        super().setUp()  # This handles cleanup but doesn't clear registry
        
        # Create unique test ID to avoid conflicts
        import uuid
        test_id = str(uuid.uuid4())[:8]
        
        # Create test user and account
        self.user = User.objects.create_user(
            username=f'testuser_dup_{test_id}',
            email=f'test_dup_{test_id}@example.com',
            password='testpass123'
        )
        
        self.account = Account.objects.create(
            name=f'Test Account Dup {test_id}',
            account_type='organization'
        )
        
        # Create integration provider
        self.provider = Provider.objects.create(
            name=f'test_xero_dup_{test_id}',
            display_name=f'Test Xero Dup {test_id}',
            provider_type='xero',
            auth_url_template='https://test.xero.com/auth',
            token_url='https://test.xero.com/token'
        )
        
        # Create integration
        self.integration = Connection.objects.create(
            account=self.account,
            provider=self.provider,
            created_by=self.user,
            external_account_id=f'test_account_dup_{test_id}',
            external_account_name=f'Test Xero Account Dup {test_id}',
            organization_name=f'Test Organization Dup {test_id}',
            status='active'
        )
        
    # tearDown is handled by base class - no need to clear registry
    
    def test_rule_initialization(self):
        """Test rule initialization and configuration."""
        rule = DuplicateTransactionRule()
        
        self.assertEqual(rule.name, 'duplicate_transactions')
        self.assertEqual(rule.default_severity, ValidationSeverity.HIGH)
        self.assertIn('match_fields', rule.config)
        self.assertEqual(rule.config['match_fields'], ['amount', 'date', 'reference'])
    
    def test_rule_with_custom_config(self):
        """Test rule initialization with custom configuration."""
        custom_config = {
            'match_fields': ['amount', 'date'],
            'minimum_duplicates': 3,
            'ignore_empty_reference': False
        }
        
        rule = DuplicateTransactionRule(config=custom_config)
        
        self.assertEqual(rule.config['match_fields'], ['amount', 'date'])
        self.assertEqual(rule.config['minimum_duplicates'], 3)
        self.assertFalse(rule.config['ignore_empty_reference'])
        # Should still have default values for unspecified config
        self.assertTrue(rule.config['ignore_pending_status'])
    
    def test_no_duplicates_found(self):
        """Test validation when no duplicate transactions exist."""
        # Create unique transactions
        Transaction.objects.create(
            connection=self.integration,
            external_transaction_id='txn_1',
            external_account_id='acc_1',
            transaction_type='spend',
            date=date(2024, 1, 1),
            reference='REF001',
            amount=Decimal('100.00'),
            status='authorised'
        )
        
        Transaction.objects.create(
            connection=self.integration,
            external_transaction_id='txn_2',
            external_account_id='acc_1',
            transaction_type='spend',
            date=date(2024, 1, 2),
            reference='REF002',
            amount=Decimal('200.00'),
            status='authorised'
        )
        
        rule = DuplicateTransactionRule()
        result = rule.validate(self.integration)
        
        self.assertTrue(result.passed)
        self.assertEqual(result.rule_name, 'duplicate_transactions')
        self.assertIn('total_transactions_checked', result.metadata)
        self.assertEqual(result.metadata['duplicates_found'], 0)
    
    def test_exact_duplicates_found(self):
        """Test validation when exact duplicate transactions exist."""
        # Create duplicate transactions
        for i in range(3):
            Transaction.objects.create(
                connection=self.integration,
                external_transaction_id=f'txn_{i}',
                external_account_id='acc_1',
                transaction_type='spend',
                date=date(2024, 1, 1),
                reference='REF001',
                amount=Decimal('100.00'),
                status='authorised'
            )
        
        rule = DuplicateTransactionRule()
        result = rule.validate(self.integration)
        
        self.assertFalse(result.passed)
        self.assertEqual(result.severity, ValidationSeverity.HIGH)
        self.assertIn('duplicate transaction groups', result.title.lower())
        self.assertEqual(len(result.affected_transactions), 1)  # One duplicate group
        self.assertEqual(result.affected_transactions[0]['count'], 3)
        
        # Check metadata
        self.assertEqual(result.metadata['duplicate_groups'], 1)
        self.assertEqual(result.metadata['total_duplicates'], 3)
    
    def test_multiple_duplicate_groups(self):
        """Test validation with multiple groups of duplicates."""
        # Create first group of duplicates
        for i in range(2):
            Transaction.objects.create(
                connection=self.integration,
                external_transaction_id=f'group1_txn_{i}',
                external_account_id='acc_1',
                transaction_type='spend',
                date=date(2024, 1, 1),
                reference='REF001',
                amount=Decimal('100.00'),
                status='authorised'
            )
        
        # Create second group of duplicates
        for i in range(3):
            Transaction.objects.create(
                connection=self.integration,
                external_transaction_id=f'group2_txn_{i}',
                external_account_id='acc_1',
                transaction_type='receive',
                date=date(2024, 1, 2),
                reference='REF002',
                amount=Decimal('200.00'),
                status='authorised'
            )
        
        rule = DuplicateTransactionRule()
        result = rule.validate(self.integration)
        
        self.assertFalse(result.passed)
        self.assertEqual(len(result.affected_transactions), 2)  # Two duplicate groups
        self.assertEqual(result.metadata['duplicate_groups'], 2)
        self.assertEqual(result.metadata['total_duplicates'], 5)
    
    def test_ignore_empty_reference(self):
        """Test that transactions with empty references are ignored by default."""
        # Create transactions with empty references - should not be considered duplicates
        for i in range(3):
            Transaction.objects.create(
                connection=self.integration,
                external_transaction_id=f'txn_{i}',
                external_account_id='acc_1',
                transaction_type='spend',
                date=date(2024, 1, 1),
                reference='',  # Empty reference
                amount=Decimal('100.00'),
                status='authorised'
            )
        
        rule = DuplicateTransactionRule()
        result = rule.validate(self.integration)
        
        # Should pass because empty references are ignored
        self.assertTrue(result.passed)
    
    def test_include_empty_reference_when_configured(self):
        """Test including transactions with empty references when configured."""
        # Create transactions with empty references
        for i in range(2):
            Transaction.objects.create(
                connection=self.integration,
                external_transaction_id=f'txn_{i}',
                external_account_id='acc_1',
                transaction_type='spend',
                date=date(2024, 1, 1),
                reference='',  # Empty reference
                amount=Decimal('100.00'),
                status='authorised'
            )
        
        # Configure rule to include empty references
        rule = DuplicateTransactionRule(config={'ignore_empty_reference': False})
        result = rule.validate(self.integration)
        
        # Should find duplicates now
        self.assertFalse(result.passed)
        self.assertEqual(result.metadata['total_duplicates'], 2)
    
    def test_ignore_pending_status(self):
        """Test that pending transactions are ignored by default."""
        # Create duplicate transactions, some with pending status
        Transaction.objects.create(
            connection=self.integration,
            external_transaction_id='txn_1',
            external_account_id='acc_1',
            transaction_type='spend',
            date=date(2024, 1, 1),
            reference='REF001',
            amount=Decimal('100.00'),
            status='authorised'
        )
        
        Transaction.objects.create(
            connection=self.integration,
            external_transaction_id='txn_2',
            external_account_id='acc_1',
            transaction_type='spend',
            date=date(2024, 1, 1),
            reference='REF001',
            amount=Decimal('100.00'),
            status='pending'  # Should be ignored
        )
        
        rule = DuplicateTransactionRule()
        result = rule.validate(self.integration)
        
        # Should pass because pending transaction is ignored
        self.assertTrue(result.passed)
    
    def test_custom_match_fields(self):
        """Test duplicate detection with custom match fields."""
        # Create transactions that match on amount and date but not reference
        Transaction.objects.create(
            connection=self.integration,
            external_transaction_id='txn_1',
            external_account_id='acc_1',
            transaction_type='spend',
            date=date(2024, 1, 1),
            reference='REF001',
            amount=Decimal('100.00'),
            status='authorised'
        )
        
        Transaction.objects.create(
            connection=self.integration,
            external_transaction_id='txn_2',
            external_account_id='acc_1',
            transaction_type='spend',
            date=date(2024, 1, 1),
            reference='REF002',  # Different reference
            amount=Decimal('100.00'),
            status='authorised'
        )
        
        # Test with default config (should not find duplicates)
        rule_default = DuplicateTransactionRule()
        result_default = rule_default.validate(self.integration)
        self.assertTrue(result_default.passed)
        
        # Test with custom config matching only amount and date
        rule_custom = DuplicateTransactionRule(config={'match_fields': ['amount', 'date']})
        result_custom = rule_custom.validate(self.integration)
        self.assertFalse(result_custom.passed)
        self.assertEqual(result_custom.metadata['total_duplicates'], 2)
    
    def test_minimum_duplicates_threshold(self):
        """Test minimum duplicates threshold configuration."""
        # Create 2 duplicate transactions
        for i in range(2):
            Transaction.objects.create(
                connection=self.integration,
                external_transaction_id=f'txn_{i}',
                external_account_id='acc_1',
                transaction_type='spend',
                date=date(2024, 1, 1),
                reference='REF001',
                amount=Decimal('100.00'),
                status='authorised'
            )
        
        # Test with minimum_duplicates = 2 (should find duplicates)
        rule_min2 = DuplicateTransactionRule(config={'minimum_duplicates': 2})
        result_min2 = rule_min2.validate(self.integration)
        self.assertFalse(result_min2.passed)
        
        # Test with minimum_duplicates = 3 (should not find duplicates)
        rule_min3 = DuplicateTransactionRule(config={'minimum_duplicates': 3})
        result_min3 = rule_min3.validate(self.integration)
        self.assertTrue(result_min3.passed)
    
    def test_validation_result_structure(self):
        """Test the structure of validation results."""
        # Create duplicate transactions
        for i in range(2):
            Transaction.objects.create(
                connection=self.integration,
                external_transaction_id=f'txn_{i}',
                external_account_id='acc_1',
                transaction_type='spend',
                date=date(2024, 1, 1),
                reference='REF001',
                amount=Decimal('100.00'),
                status='authorised',
                contact_name='Test Contact',
                description='Test transaction'
            )
        
        rule = DuplicateTransactionRule()
        result = rule.validate(self.integration)
        
        # Check result structure
        self.assertFalse(result.passed)
        self.assertEqual(result.rule_name, 'duplicate_transactions')
        self.assertIsNotNone(result.title)
        self.assertIsNotNone(result.description)
        self.assertIsNotNone(result.executed_at)
        
        # Check affected transactions structure
        self.assertEqual(len(result.affected_transactions), 1)
        duplicate_group = result.affected_transactions[0]
        
        self.assertIn('count', duplicate_group)
        self.assertIn('matching_fields', duplicate_group)
        self.assertIn('transactions', duplicate_group)
        self.assertIn('total_amount', duplicate_group)
        
        # Check transaction details
        transactions = duplicate_group['transactions']
        self.assertEqual(len(transactions), 2)
        
        for txn in transactions:
            self.assertIn('id', txn)
            self.assertIn('external_transaction_id', txn)
            self.assertIn('date', txn)
            self.assertIn('amount', txn)
            self.assertIn('reference', txn)
            self.assertIn('status', txn)
    
    def test_error_handling(self):
        """Test error handling in validation rule."""
        # Create a rule that will cause an error (invalid integration)
        rule = DuplicateTransactionRule()
        
        # This should handle the error gracefully
        result = rule.validate(None)
        
        self.assertFalse(result.passed)
        self.assertEqual(result.severity, ValidationSeverity.CRITICAL)
        self.assertIn('validation failed', result.title.lower())
        self.assertIn('error', result.metadata)


class TestDuplicateRuleRegistration(BaseValidationTestCase):
    """Test DuplicateTransactionRule registration."""
    
    def setUp(self):
        super().setUp()  # This handles cleanup
        # The rule should already be registered from module import
        # If not, manually register it
        if not ValidationRuleRegistry.is_registered('duplicate_transactions'):
            from integrations.validation.rules.duplicates import DuplicateTransactionRule
            ValidationRuleRegistry.register(DuplicateTransactionRule)
    
    # tearDown is handled by base class
    
    def test_rule_registration(self):
        """Test that the rule registers itself properly."""
        self.assertTrue(ValidationRuleRegistry.is_registered('duplicate_transactions'))
        
        rule_info = ValidationRuleRegistry.get_rule_info('duplicate_transactions')
        self.assertIsNotNone(rule_info)
        self.assertEqual(rule_info['name'], 'duplicate_transactions')
        self.assertEqual(rule_info['default_severity'], 'high')
    
    def test_get_rule_instance(self):
        """Test getting rule instance from registry."""
        from integrations.validation.rules.duplicates import DuplicateTransactionRule
        
        rule = ValidationRuleRegistry.get_rule('duplicate_transactions')
        self.assertIsInstance(rule, DuplicateTransactionRule)
        self.assertEqual(rule.name, 'duplicate_transactions')