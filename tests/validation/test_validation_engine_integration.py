"""
Integration tests for ValidationEngine with new Issue aggregation system.

Tests the complete flow:
ValidationEngine -> ValidationResult -> IssueManager -> Issue (with proper scoping)
"""

from django.test import TestCase
from django.contrib.auth.models import User
from datetime import date

from core.models import Account
from connections.models import Connection, Provider
from financial_data.models import Transaction
from data_quality.models import Issue
from data_quality.validation.engine import ValidationEngine
from data_quality.validation.base import ValidationResult, ValidationSeverity
from .base_validation_test import BaseValidationTestCase


class ValidationEngineConnectionTestCase(BaseValidationTestCase):
    
    fixtures = ['test_integration_stack.json']
    
    def setUp(self):
        """Set up test data"""
        super().setUp()  # This handles cleanup
        
        # Ensure duplicate rule is registered for ValidationEngine tests
        from data_quality.validation.registry import ValidationRuleRegistry
        from data_quality.validation.rules.duplicates import DuplicateTransactionRule
        if not ValidationRuleRegistry.is_registered('duplicate_transactions'):
            ValidationRuleRegistry.register(DuplicateTransactionRule)
        
        self.user1 = User.objects.get(pk=1)
        # Create user2 with a unique name to avoid conflicts
        import uuid
        test_id = str(uuid.uuid4())[:8]
        self.user2 = User.objects.create_user(f'testuser2_{test_id}', f'test2_{test_id}@example.com', 'password')
        
        self.account1 = Account.objects.get(pk=1)
        self.account2 = Account.objects.create(name=f'Account 2 {test_id}', account_type='organization')
        
        self.xero_provider = Provider.objects.get(pk=1)
        
        # Create connections for different accounts and charts
        self.connection_1a = Connection.objects.create(
            account=self.account1,
            created_by=self.user1,
            provider=self.xero_provider,
            external_account_id=f'xero-org-a-{test_id}',
            external_account_name='Chart A',
            organization_name='Organization A',
            status='active'
        )
        
        self.integration_1b = Connection.objects.create(
            account=self.account1,
            created_by=self.user1,
            provider=self.xero_provider,
            external_account_id=f'xero-org-b-{test_id}',
            external_account_name='Chart B',
            organization_name='Organization B',
            status='active'
        )
        
        self.integration_2a = Connection.objects.create(
            account=self.account2,
            created_by=self.user2,
            provider=self.xero_provider,
            external_account_id=f'xero-org-a-{test_id}',  # Same chart as 1a, different account
            external_account_name='Chart A',
            organization_name='Organization A',
            status='active'
        )
        
        # Create some test transactions for the duplicate rule
        self.create_test_transactions()
    
    # tearDown is handled by base class

    def create_test_transactions(self):
        """Create test transaction data"""
        # Duplicate transactions in integration 1a
        Transaction.objects.create(
            connection=self.integration_1a,
            external_transaction_id='txn_001',
            amount=100.00,
            date=date(2024, 1, 1),  # Use date object instead of string
            reference='REF001',
            description='Test transaction',
            contact_name='Test Contact'
        )
        
        Transaction.objects.create(
            connection=self.integration_1a,
            external_transaction_id='txn_002',
            amount=100.00,  # Same amount
            date=date(2024, 1, 1),  # Same date - use date object
            reference='REF001',  # Same reference - should be flagged as duplicate
            description='Test transaction duplicate',
            contact_name='Test Contact'
        )
        
        # Similar transactions in integration 1b (different chart)
        Transaction.objects.create(
            connection=self.integration_1b,
            external_transaction_id='txn_003',
            amount=100.00,
            date=date(2024, 1, 1),  # Use date object
            reference='REF001',  # Same as above but different chart
            description='Test transaction in chart B',
            contact_name='Test Contact'
        )
        
        Transaction.objects.create(
            connection=self.integration_1b,
            external_transaction_id='txn_004',
            amount=100.00,
            date=date(2024, 1, 1),  # Use date object
            reference='REF001',
            description='Test transaction duplicate in chart B',
            contact_name='Test Contact'
        )
        
        # Duplicate transactions in integration 2a (different account, same chart as 1a)
        Transaction.objects.create(
            connection=self.integration_2a,
            external_transaction_id='txn_005',
            amount=300.00,
            date=date(2024, 1, 3),  # Use date object
            reference='REF003',
            description='Test transaction account 2',
            contact_name='Test Contact Account 2'
        )
        
        Transaction.objects.create(
            connection=self.integration_2a,
            external_transaction_id='txn_006',
            amount=300.00,  # Same amount - should create duplicate
            date=date(2024, 1, 3),  # Same date - use date object
            reference='REF003',  # Same reference - should be flagged as duplicate
            description='Test transaction duplicate account 2',
            contact_name='Test Contact Account 2'
        )

    def test_validation_engine_creates_scoped_issues(self):
        """ValidationEngine should create properly scoped issues via IssueManager"""
        
        # Run validation for integration 1a
        validation_run_1a = ValidationEngine.run_validation(self.integration_1a)
        
        # Should have created issues
        self.assertEqual(validation_run_1a.status, 'completed')
        self.assertGreater(validation_run_1a.issues_found, 0)
        
        # Check that issue was created with proper scoping
        issues_1a = Issue.objects.filter(connection=self.integration_1a)
        self.assertGreater(issues_1a.count(), 0)
        
        issue_1a = issues_1a.first()
        self.assertTrue(issue_1a.prefix_id.startswith('iss_'))
        self.assertEqual(issue_1a.category, 'duplicate_transactions')  # Uses rule name
        self.assertIn(str(self.account1.id), issue_1a.issue_key)  # Contains account ID
        self.assertIn(self.integration_1a.external_account_id, issue_1a.issue_key)  # Contains chart ID
        
        # Run validation for integration 1b (different chart, same account)
        validation_run_1b = ValidationEngine.run_validation(self.integration_1b)
        
        # Should create separate issue for different chart
        issues_1b = Issue.objects.filter(connection=self.integration_1b)
        self.assertGreater(issues_1b.count(), 0)
        
        issue_1b = issues_1b.first()
        self.assertNotEqual(issue_1a.id, issue_1b.id)  # Different issues
        self.assertNotEqual(issue_1a.issue_key, issue_1b.issue_key)  # Different keys
        self.assertIn(self.integration_1b.external_account_id, issue_1b.issue_key)  # Contains different chart ID

    def test_validation_engine_respects_tenant_isolation(self):
        """ValidationEngine should maintain tenant isolation via IssueManager"""
        
        # Run validation for both accounts with same chart
        validation_run_1a = ValidationEngine.run_validation(self.integration_1a)
        validation_run_2a = ValidationEngine.run_validation(self.integration_2a)
        
        # Both should complete successfully
        self.assertEqual(validation_run_1a.status, 'completed')
        self.assertEqual(validation_run_2a.status, 'completed')
        
        # Get issues for each account
        issues_account1 = Issue.objects.get_issues_for_account(self.account1)
        issues_account2 = Issue.objects.get_issues_for_account(self.account2)
        
        # Should have issues in each account
        self.assertGreater(issues_account1.count(), 0)
        self.assertGreater(issues_account2.count(), 0)
        
        # Issues should be completely separate (tenant isolation)
        issue_acc1 = issues_account1.first()
        issue_acc2 = issues_account2.first()
        
        self.assertNotEqual(issue_acc1.id, issue_acc2.id)
        self.assertEqual(issue_acc1.integration.account, self.account1)
        self.assertEqual(issue_acc2.integration.account, self.account2)
        
        # Issue keys should contain different account IDs
        self.assertIn(str(self.account1.id), issue_acc1.issue_key)
        self.assertIn(str(self.account2.id), issue_acc2.issue_key)
        
        # But same chart ID since it's the same external chart
        self.assertIn(self.integration_1a.external_account_id, issue_acc1.issue_key)
        self.assertIn(self.integration_2a.external_account_id, issue_acc2.issue_key)

    def test_validation_engine_aggregates_multiple_runs(self):
        """Multiple validation runs should aggregate issues properly"""
        
        # First validation run
        validation_run_1 = ValidationEngine.run_validation(self.integration_1a)
        
        # Should create initial issue
        initial_issues = Issue.objects.filter(connection=self.integration_1a)
        self.assertEqual(initial_issues.count(), 1)
        
        initial_issue = initial_issues.first()
        initial_count = initial_issue.count
        initial_occurrences = len(initial_issue.occurrence_ids)
        
        # Add more duplicate transactions
        Transaction.objects.create(
            connection=self.integration_1a,
            external_transaction_id='txn_007',
            amount=200.00,
            date=date(2024, 1, 2),  # Use date object
            reference='REF002',
            description='Another duplicate set',
            contact_name='Test Contact'
        )
        
        Transaction.objects.create(
            connection=self.integration_1a,
            external_transaction_id='txn_008',
            amount=200.00,  # Same amount
            date=date(2024, 1, 2),  # Same date - use date object
            reference='REF002',  # Same reference
            description='Another duplicate',
            contact_name='Test Contact'
        )
        
        # Second validation run
        validation_run_2 = ValidationEngine.run_validation(self.integration_1a)
        
        # Should still be only one issue (aggregated)
        updated_issues = Issue.objects.filter(connection=self.integration_1a)
        self.assertEqual(updated_issues.count(), 1)
        
        # But issue should be updated with new occurrences
        updated_issue = updated_issues.first()
        self.assertEqual(updated_issue.id, initial_issue.id)  # Same issue
        self.assertGreater(updated_issue.count, initial_count)  # Higher count
        self.assertGreater(len(updated_issue.occurrence_ids), initial_occurrences)  # More occurrences

    def test_issue_prefix_id_used_throughout(self):
        """All issues should have prefix_id and use it consistently"""
        
        # Run validation
        validation_run = ValidationEngine.run_validation(self.integration_1a)
        
        # Get created issues
        issues = Issue.objects.filter(connection=self.integration_1a)
        
        for issue in issues:
            # All issues should have prefix_id
            self.assertIsNotNone(issue.prefix_id)
            self.assertTrue(issue.prefix_id.startswith('iss_'))
            self.assertEqual(len(issue.prefix_id), 12)  # iss_ + 8 chars
            
            # prefix_id should be unique
            duplicate_prefix_ids = Issue.objects.filter(prefix_id=issue.prefix_id).count()
            self.assertEqual(duplicate_prefix_ids, 1)

    def test_category_display_names(self):
        """Issues should have proper human-readable category display names"""
        
        # Run validation
        ValidationEngine.run_validation(self.integration_1a)
        
        # Get created issues
        issues = Issue.objects.filter(connection=self.integration_1a)
        
        for issue in issues:
            # Category should be rule name
            self.assertEqual(issue.category, 'duplicate_transactions')
            
            # Display name should be human-readable
            display_name = issue.get_category_display_name()
            self.assertEqual(display_name, 'Duplicate Transactions')

    def test_validation_metadata_preserved(self):
        """Validation metadata should be preserved in issues"""
        
        # Run validation
        validation_run = ValidationEngine.run_validation(self.integration_1a)
        
        # Get created issues
        issues = Issue.objects.filter(connection=self.integration_1a)
        self.assertGreater(issues.count(), 0)
        
        issue = issues.first()
        
        # Should have occurrence data
        self.assertGreater(len(issue.occurrence_ids), 0)
        self.assertIsNotNone(issue.latest_occurrence)
        
        # Latest occurrence should have metadata
        latest = issue.latest_occurrence
        self.assertIn('timestamp', latest)
        self.assertIn('metadata', latest)
        
        # Should have affected transactions data
        self.assertGreater(len(issue.affected_transactions), 0)
        
        # Affected transactions should have proper structure
        for txn_group in issue.affected_transactions:
            self.assertIn('count', txn_group)
            self.assertIn('transactions', txn_group)
            self.assertGreater(txn_group['count'], 1)  # Duplicates should have count > 1