"""
Tests for Integration duplicate prevention.

Ensures that:
1. Multiple different Xero organizations can be connected to the same FAFixed account
2. The same Xero organization cannot be connected twice to the same FAFixed account
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.db import IntegrityError

from core.models import Account
from integrations.models import Integration, IntegrationProvider


class IntegrationDuplicatePreventionTestCase(TestCase):
    
    fixtures = ['test_integration_stack.json']
    
    def setUp(self):
        """Set up test using existing fixtures"""
        self.user = User.objects.get(pk=1)
        self.account = Account.objects.get(pk=1)
        self.xero_provider = IntegrationProvider.objects.get(pk=1)

    def create_integration(self, external_account_id, **kwargs):
        """Helper to create integrations with sensible defaults"""
        defaults = {
            'account': self.account,
            'created_by': self.user,
            'provider': self.xero_provider,
            'external_account_name': f'Test Org {external_account_id}',
            'organization_name': f'Test Organization {external_account_id}',
            'status': 'active'
        }
        defaults.update(kwargs)
        return Integration.objects.create(
            external_account_id=external_account_id,
            **defaults
        )

    def test_multiple_different_xero_orgs_allowed(self):
        """Test that one FAFixed account can connect to multiple different Xero organizations"""
        
        # Create two integrations with different external_account_ids
        integration1 = self.create_integration('xero-org-a-12345')
        integration2 = self.create_integration('xero-org-b-67890')
        
        # Both should exist and have prefix_ids
        self.assertEqual(Integration.objects.filter(account=self.account).count(), 3)  # 2 new + 1 from fixture
        self.assertNotEqual(integration1.external_account_id, integration2.external_account_id)
        self.assertTrue(integration1.prefix_id.startswith('int_'))
        self.assertTrue(integration2.prefix_id.startswith('int_'))
        
    def test_duplicate_same_xero_org_prevented(self):
        """Test that the same Xero organization cannot be connected twice"""
        
        # Create first integration
        integration1 = self.create_integration('xero-org-duplicate-123')
        self.assertIsNotNone(integration1.id)
        
        # Attempt to create duplicate - should fail with IntegrityError
        with self.assertRaises(IntegrityError):
            self.create_integration('xero-org-duplicate-123')  # Same external_account_id
        
    def test_same_xero_org_different_accounts_allowed(self):
        """Test that the same Xero organization can connect to different FAFixed accounts"""
        
        # Create second account
        account2 = Account.objects.create(name='Different Account', account_type='organization')
        
        # Same external_account_id but different FAFixed accounts - should succeed
        integration1 = self.create_integration('shared-xero-org-999')
        integration2 = self.create_integration('shared-xero-org-999', account=account2)
        
        self.assertEqual(Integration.objects.filter(external_account_id='shared-xero-org-999').count(), 2)
        self.assertNotEqual(integration1.account, integration2.account)
        
    def test_unique_constraint_covers_correct_fields(self):
        """Test that constraint is on account + provider + external_account_id"""
        
        # Create base integration
        self.create_integration('constraint-test-123')
        
        # Same account + provider + external_account_id should fail
        with self.assertRaises(IntegrityError):
            self.create_integration('constraint-test-123', organization_name='Different Name')