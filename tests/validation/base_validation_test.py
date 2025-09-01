"""
Base test class for validation tests with proper cleanup.
"""

from django.test import TestCase
from integrations.models import Integration, IntegrationProvider, Issue, TransactionData, ValidationRun
from core.models import Account
from django.contrib.auth.models import User
from integrations.validation.registry import ValidationRuleRegistry


class BaseValidationTestCase(TestCase):
    """Base test case with comprehensive cleanup for validation tests"""
    
    @classmethod
    def setUpClass(cls):
        """Set up class-level fixtures"""
        super().setUpClass()
    
    def setUp(self):
        """Set up each test with clean database state"""
        # Clean up any leftover test data to ensure complete isolation
        self.cleanup_test_data()
        
        # Note: We don't clear validation registry here because ValidationEngine needs the rules
        # Individual tests can clear registry if needed for testing registry functionality
    
    def tearDown(self):
        """Clean up after each test"""
        self.cleanup_test_data()
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests in this class"""
        super().tearDownClass()
        # Additional cleanup
        cls.cleanup_all_test_data()
    
    def cleanup_test_data(self):
        """Clean up test-specific data while preserving fixture data"""
        # Delete in dependency order to avoid foreign key constraints
        
        # Clear validation runs and issues first (these are always test data)
        ValidationRun.objects.all().delete()
        Issue.objects.all().delete()
        
        # Clear transaction data (preserve any fixture transactions if they exist)
        # Since we're creating fresh transaction data in each test, this should be safe
        TransactionData.objects.all().delete()
        
        # Clear test integrations (preserve fixture integrations with IDs 1, 2, 3)  
        Integration.objects.exclude(id__in=[1, 2, 3]).delete()
        
        # Clear test providers (not from fixtures - fixtures have ID 1)
        IntegrationProvider.objects.exclude(id__in=[1]).delete()
        
        # Clear test accounts (preserve fixture accounts with ID 1)
        Account.objects.exclude(id__in=[1]).delete()
        
        # Clear test users (preserve fixture users with ID 1)
        User.objects.exclude(id__in=[1]).delete()
    
    @classmethod
    def cleanup_all_test_data(cls):
        """More aggressive cleanup for class-level teardown"""
        # This runs after all tests in a class complete
        ValidationRun.objects.all().delete()
        Issue.objects.all().delete()
        TransactionData.objects.all().delete()
        
        # Clear all test integrations
        Integration.objects.exclude(
            id__in=[1, 2, 3]  # Preserve fixture integrations if needed
        ).delete()
        
        # Clear test providers
        IntegrationProvider.objects.filter(
            name__startswith='test_'
        ).delete()
        
        # Clear test accounts  
        Account.objects.exclude(
            id__in=[1]  # Preserve fixture accounts if needed
        ).delete()
        
        # Clear test users
        User.objects.exclude(
            id__in=[1]  # Preserve fixture users if needed  
        ).delete()
        
        # Clear validation registry
        ValidationRuleRegistry.clear_registry()