"""
Tests for transaction validation UI functionality.
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from unittest.mock import patch, MagicMock
from datetime import date
from decimal import Decimal
import uuid

from core.models import Account
from integrations.models import Integration, TransactionData
from integrations.validation.registry import ValidationRuleRegistry


class TransactionValidationUITestCase(TestCase):
    
    fixtures = ['test_integration_stack.json']
    
    def setUp(self):
        """Set up test client and login"""
        self.client = Client()
        self.user = User.objects.get(pk=1)
        self.account = Account.objects.get(pk=1)
        self.integration = Integration.objects.get(pk=1)
        
        # Set a known password for the test user
        self.user.set_password('testpass')
        self.user.save()
        
        self.client.login(username='testuser@example.com', password='testpass')

    def create_transaction(self, **kwargs):
        """Helper to create transactions with sensible defaults"""
        defaults = {
            'integration': self.integration,
            'external_account_id': 'acc-456',
            'transaction_type': 'spend',
            'date': date.today(),
            'amount': Decimal('100.00'),
            'currency_code': 'AUD',
            'status': 'authorised'
        }
        # Generate unique external_transaction_id if not provided
        if 'external_transaction_id' not in kwargs:
            defaults['external_transaction_id'] = f'txn-{uuid.uuid4().hex[:8]}'
            
        return TransactionData.objects.create(**{**defaults, **kwargs})

    @patch('integrations.validation.registry.ValidationRuleRegistry.get_rule_names')
    def test_transaction_list_no_transactions(self, mock_get_rule_names):
        """Test transaction list with no transactions shows empty state"""
        mock_get_rule_names.return_value = [
            'duplicate_transactions',
            'missing_data',
            'amount_discrepancies'
        ]
        
        url = reverse('transaction_list', kwargs={'integration_prefix_id': self.integration.prefix_id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No Transactions Found')
        self.assertContains(response, 'No transaction data available')
        self.assertContains(response, 'Sync Transactions')

    @patch('integrations.validation.registry.ValidationRuleRegistry.get_enabled_rules_for_integration')
    def test_transaction_list_with_unvalidated_transaction(self, mock_get_enabled_rules):
        """Test transaction list shows correct validation status (0/3) for unvalidated transaction"""
        # Mock 3 enabled rules for this integration
        mock_rule_1 = MagicMock()
        mock_rule_1.name = 'duplicate_transactions'
        mock_rule_2 = MagicMock()
        mock_rule_2.name = 'missing_data'
        mock_rule_3 = MagicMock()
        mock_rule_3.name = 'amount_discrepancies'
        
        mock_get_enabled_rules.return_value = [mock_rule_1, mock_rule_2, mock_rule_3]
        
        transaction = self.create_transaction(
            reference='Test Transaction',
            description='Test transaction description'
        )
        
        url = reverse('transaction_list', kwargs={'integration_prefix_id': self.integration.prefix_id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Transaction')
        self.assertContains(response, 'Run Validation Rules (0/3)')
        # Status should be red/none since no validations have been run
        self.assertContains(response, 'border-red-300 text-red-700 bg-red-50')

    @patch('integrations.validation.registry.ValidationRuleRegistry.get_rule_names')
    def test_transaction_list_with_partially_validated_transaction(self, mock_get_rule_names):
        """Test transaction list shows correct validation status (1/3) for partially validated transaction"""
        mock_get_rule_names.return_value = [
            'duplicate_transactions',
            'missing_data',
            'amount_discrepancies'
        ]
        
        transaction = self.create_transaction(
            transaction_type='receive',
            reference='Partially Validated Transaction',
            description='This transaction has some validations run',
            amount=Decimal('250.50')
        )
        
        # TODO: Create validation status indicating 1 rule has been run
        # This will be implemented when we create TransactionValidationStatus model
        
        url = reverse('transaction_list', kwargs={'integration_prefix_id': self.integration.prefix_id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Partially Validated Transaction')
        # Should show validation status as (1/3) - 1 validation run out of 3 available
        self.assertContains(response, 'Run Validation Rules (1/3)')
        # Status should be orange/some since some validations have been run
        self.assertContains(response, 'validation-status-some')

    @patch('integrations.validation.registry.ValidationRuleRegistry.get_rule_names')
    def test_transaction_list_with_fully_validated_transaction(self, mock_get_rule_names):
        """Test transaction list shows correct validation status (3/3) for fully validated transaction"""
        mock_get_rule_names.return_value = [
            'duplicate_transactions',
            'missing_data',
            'amount_discrepancies'
        ]
        
        transaction = self.create_transaction(
            transaction_type='bank_transfer',
            reference='Fully Validated Transaction',
            description='This transaction has all validations run',
            amount=Decimal('500.75')
        )
        
        # TODO: Create validation status indicating all 3 rules have been run
        # This will be implemented when we create TransactionValidationStatus model
        
        url = reverse('transaction_list', kwargs={'integration_prefix_id': self.integration.prefix_id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Fully Validated Transaction')
        self.assertContains(response, 'Run Validation Rules (3/3)')
        self.assertContains(response, 'validation-status-all')

    @patch('integrations.validation.registry.ValidationRuleRegistry.get_rule_names')
    def test_validation_rule_count_helper(self, mock_get_rule_names):
        """Test that the validation rule count helper returns correct total"""
        mock_get_rule_names.return_value = [
            'duplicate_transactions',
            'missing_data',
            'amount_discrepancies',
            'date_anomalies',
            'tax_code_errors'
        ]
        
        transaction = self.create_transaction(reference='Rule Count Test')
        
        url = reverse('transaction_list', kwargs={'integration_prefix_id': self.integration.prefix_id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        # Should show 5 total rules available
        self.assertContains(response, 'Run Validation Rules (0/5)')

    def test_transaction_actions_column_present(self):
        """Test that transactions table includes actions column"""
        transaction = self.create_transaction(reference='Actions Test Transaction')
        
        url = reverse('transaction_list', kwargs={'integration_prefix_id': self.integration.prefix_id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        # Should have actions column header
        self.assertContains(response, 'Actions')
        # Should have view button
        self.assertContains(response, 'View')
        # Should have validation rules dropdown button
        self.assertContains(response, 'Run Validation Rules')

    @patch('integrations.validation.registry.ValidationRuleRegistry.get_enabled_rules_for_integration')
    def test_integration_specific_rule_count(self, mock_get_enabled_rules):
        """Test that rule count is specific to the integration (some rules might be disabled)"""
        # Mock that only 2 rules are enabled for this integration
        mock_rule_1 = MagicMock()
        mock_rule_1.name = 'duplicate_transactions'
        mock_rule_2 = MagicMock() 
        mock_rule_2.name = 'missing_data'
        
        mock_get_enabled_rules.return_value = [mock_rule_1, mock_rule_2]
        
        transaction = self.create_transaction(
            transaction_type='receive',
            reference='Integration Rules Test'
        )
        
        url = reverse('transaction_list', kwargs={'integration_prefix_id': self.integration.prefix_id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        # Should show only 2 rules available for this integration
        self.assertContains(response, 'Run Validation Rules (0/2)')