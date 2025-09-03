"""
Simple unit tests for PrefixIdMixin - test behavior using existing models
"""

from django.test import TestCase
from core.models import UserProfile, Account
from shared.models import PrefixIdMixin


class TestPrefixIdMixin(TestCase):
    
    def test_generates_prefix_id_on_account_save(self):
        """Test prefix_id is generated automatically for Account"""
        account = Account(name="Test Org", account_type="organization")
        account.save()
        
        self.assertTrue(account.prefix_id.startswith('acc_'))
        self.assertEqual(len(account.prefix_id), 12)  # acc_ + 8 chars
    
    def test_prefix_ids_are_unique_for_accounts(self):
        """Test different Account instances get different prefix_ids"""
        account1 = Account.objects.create(name="First Org", account_type="organization")
        account2 = Account.objects.create(name="Second Org", account_type="organization")
        
        self.assertNotEqual(account1.prefix_id, account2.prefix_id)
    
    def test_prefix_id_persists_on_account_resave(self):
        """Test prefix_id doesn't change on subsequent saves for Account"""
        account = Account.objects.create(name="Test Org", account_type="organization")
        original_id = account.prefix_id
        
        account.name = "Updated Org"
        account.save()
        
        self.assertEqual(account.prefix_id, original_id)
    
    def test_get_prefix_id_method(self):
        """Test get_prefix_id method works correctly"""
        account = Account.objects.create(name="Test Org", account_type="organization")
        
        self.assertEqual(account.get_prefix_id(), account.prefix_id)
        self.assertTrue(account.get_prefix_id().startswith('acc_'))