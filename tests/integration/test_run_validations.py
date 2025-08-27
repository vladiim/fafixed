"""
Tests for Run Validations functionality with Turbo Frames.
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from unittest.mock import patch, MagicMock
from datetime import date
from decimal import Decimal
import uuid
import json

from core.models import Account
from integrations.models import Integration, TransactionData, TransactionValidationStatus
from integrations.validation.registry import ValidationRuleRegistry


class RunValidationsTestCase(TestCase):
    
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

    @patch('integrations.validation.registry.ValidationRuleRegistry.get_enabled_rules_for_integration')
    def test_run_validations_endpoint_exists(self, mock_get_enabled_rules):
        """Test that the run validations endpoint exists and accepts POST"""
        mock_get_enabled_rules.return_value = []
        
        transaction = self.create_transaction(reference='Test Transaction')
        
        url = reverse('run_transaction_validations', kwargs={'transaction_id': transaction.id})
        response = self.client.post(url, {
            'rules': ['duplicate_transactions', 'missing_data']
        })
        
        # Should not be 404 - endpoint should exist
        self.assertNotEqual(response.status_code, 404)

    @patch('integrations.validation.registry.ValidationRuleRegistry.get_enabled_rules_for_integration')
    @patch('integrations.tasks.run_transaction_validations.delay')
    def test_run_validations_creates_pending_statuses(self, mock_task, mock_get_enabled_rules):
        """Test that submitting validation rules creates pending TransactionValidationStatus records"""
        # Mock enabled rules
        mock_rule_1 = MagicMock()
        mock_rule_1.name = 'duplicate_transactions'
        mock_rule_2 = MagicMock()
        mock_rule_2.name = 'missing_data'
        mock_get_enabled_rules.return_value = [mock_rule_1, mock_rule_2]
        
        transaction = self.create_transaction(reference='Test Transaction')
        
        # Should have no validation statuses initially
        self.assertEqual(transaction.validation_statuses.count(), 0)
        
        url = reverse('run_transaction_validations', kwargs={'transaction_id': transaction.id})
        response = self.client.post(url, {
            'rules': ['duplicate_transactions', 'missing_data']
        })
        
        # Should create pending validation status records
        self.assertEqual(transaction.validation_statuses.count(), 2)
        
        statuses = list(transaction.validation_statuses.all())
        rule_names = [status.rule_name for status in statuses]
        
        # Check that both rules were created (order doesn't matter)
        self.assertIn('duplicate_transactions', rule_names)
        self.assertIn('missing_data', rule_names)
        
        # Check that both have pending status
        for status in statuses:
            self.assertEqual(status.status, 'pending')
        
        # Should trigger celery task
        mock_task.assert_called_once()

    @patch('integrations.validation.registry.ValidationRuleRegistry.get_enabled_rules_for_integration')
    def test_run_validations_returns_updated_turbo_frame(self, mock_get_enabled_rules):
        """Test that the endpoint returns a Turbo Frame with updated validation status"""
        # Mock enabled rules
        mock_rule_1 = MagicMock()
        mock_rule_1.name = 'duplicate_transactions'
        mock_get_enabled_rules.return_value = [mock_rule_1]
        
        transaction = self.create_transaction(reference='Test Transaction')
        
        url = reverse('run_transaction_validations', kwargs={'transaction_id': transaction.id})
        response = self.client.post(url, {
            'rules': ['duplicate_transactions']
        }, HTTP_TURBO_FRAME=f'transaction-{transaction.id}-actions')
        
        # Debug output
        if response.status_code != 200:
            print(f"Response status: {response.status_code}")
            print(f"Response content: {response.content.decode()[:1000]}...")
            
        self.assertEqual(response.status_code, 200)
        # Should contain turbo-frame element
        self.assertContains(response, f'<turbo-frame id="transaction-{transaction.id}-actions"')
        # Should show running state while validations are running
        self.assertContains(response, 'Running Validations...')

    @patch('integrations.validation.registry.ValidationRuleRegistry.get_enabled_rules_for_integration')
    def test_run_validations_with_completed_status(self, mock_get_enabled_rules):
        """Test validation status display when some validations are completed"""
        # Mock enabled rules
        mock_rule_1 = MagicMock()
        mock_rule_1.name = 'duplicate_transactions'
        mock_rule_2 = MagicMock()
        mock_rule_2.name = 'missing_data'
        mock_get_enabled_rules.return_value = [mock_rule_1, mock_rule_2]
        
        transaction = self.create_transaction(reference='Test Transaction')
        
        # Create one completed validation status
        TransactionValidationStatus.objects.create(
            transaction=transaction,
            rule_name='duplicate_transactions',
            status='completed',
            passed=True,
            issues_found=0
        )
        
        url = reverse('transaction_list', kwargs={'integration_prefix_id': self.integration.prefix_id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        # Should show 1 completed out of 2 total
        self.assertContains(response, 'Run Validation Rules (1/2)')
        # Should have orange/some styling for partial completion
        self.assertContains(response, 'border-orange-300 text-orange-700 bg-orange-50')

    @patch('integrations.validation.registry.ValidationRuleRegistry.get_enabled_rules_for_integration')
    def test_run_validations_with_all_completed(self, mock_get_enabled_rules):
        """Test validation status display when all validations are completed"""
        # Mock enabled rules
        mock_rule_1 = MagicMock()
        mock_rule_1.name = 'duplicate_transactions'
        mock_get_enabled_rules.return_value = [mock_rule_1]
        
        transaction = self.create_transaction(reference='Test Transaction')
        
        # Create completed validation status
        TransactionValidationStatus.objects.create(
            transaction=transaction,
            rule_name='duplicate_transactions',
            status='completed',
            passed=False,
            issues_found=3
        )
        
        url = reverse('transaction_list', kwargs={'integration_prefix_id': self.integration.prefix_id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        # Should show all completed
        self.assertContains(response, 'Run Validation Rules (1/1)')
        # Should have green/all styling for full completion
        self.assertContains(response, 'border-green-300 text-green-700 bg-green-50')

    def test_run_validations_only_selected_rules(self):
        """Test that only selected rules are run, not all available rules"""
        transaction = self.create_transaction(reference='Test Transaction')
        
        url = reverse('run_transaction_validations', kwargs={'transaction_id': transaction.id})
        response = self.client.post(url, {
            'rules': ['duplicate_transactions']  # Only one rule selected
        })
        
        # Should only create validation status for selected rule
        self.assertEqual(transaction.validation_statuses.count(), 1)
        self.assertEqual(transaction.validation_statuses.first().rule_name, 'duplicate_transactions')

    def test_run_validations_no_rules_selected(self):
        """Test behavior when no rules are selected"""
        transaction = self.create_transaction(reference='Test Transaction')
        
        url = reverse('run_transaction_validations', kwargs={'transaction_id': transaction.id})
        response = self.client.post(url, {})
        
        # Should not create any validation statuses
        self.assertEqual(transaction.validation_statuses.count(), 0)
        # Should return error or appropriate response
        self.assertContains(response, 'No validation rules selected')

    def test_run_validations_invalid_transaction_id(self):
        """Test that invalid transaction ID returns 404"""
        url = reverse('run_transaction_validations', kwargs={'transaction_id': 99999})
        response = self.client.post(url, {
            'rules': ['duplicate_transactions']
        })
        
        self.assertEqual(response.status_code, 404)

    def test_run_validations_permission_check(self):
        """Test that users can only run validations on their own account's transactions"""
        # Create another user and account
        other_user = User.objects.create_user(
            username='other@example.com',
            email='other@example.com',
            password='testpass'
        )
        
        from core.models import Account, AccountUser, UserProfile
        other_account = Account.objects.create(
            name='Other Account',
            account_type='organization'
        )
        
        AccountUser.objects.create(
            account=other_account,
            user=other_user,
            role='owner'
        )
        
        # Create integration for other account
        from integrations.models import IntegrationProvider
        provider = IntegrationProvider.objects.get(name='xero')
        other_integration = Integration.objects.create(
            account=other_account,
            provider=provider,
            external_account_id='other-tenant',
            external_account_name='Other Org',
            organization_name='Other Organization',
            status='active',
            created_by=other_user,
            prefix_id='int_other123'
        )
        
        # Create transaction for other account
        other_transaction = self.create_transaction(
            integration=other_integration,
            reference='Other Transaction'
        )
        
        # Try to run validations on other account's transaction
        url = reverse('run_transaction_validations', kwargs={'transaction_id': other_transaction.id})
        response = self.client.post(url, {
            'rules': ['duplicate_transactions']
        })
        
        # Should be forbidden
        self.assertEqual(response.status_code, 403)