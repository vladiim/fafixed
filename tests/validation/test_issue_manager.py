"""
Tests for IssueManager aggregation logic.

Tests that the IssueManager properly:
1. Creates new issues for new validation results
2. Aggregates similar issues within same account + chart scope
3. Keeps issues separate across different scopes
4. Tracks occurrences properly
"""

from django.contrib.auth.models import User

from core.models import Account
from integrations.models import Integration, IntegrationProvider, Issue
from integrations.validation.base import ValidationResult, ValidationSeverity
from .base_validation_test import BaseValidationTestCase


class IssueManagerTestCase(BaseValidationTestCase):
    
    fixtures = ['test_integration_stack.json']
    
    def setUp(self):
        """Set up test data"""
        super().setUp()  # This handles cleanup
        
        # Create unique test ID to avoid conflicts
        import uuid
        test_id = str(uuid.uuid4())[:8]
        
        self.user1 = User.objects.get(pk=1)
        self.user2 = User.objects.create_user(f'testuser2_mgr_{test_id}', f'test2_mgr_{test_id}@example.com', 'password')
        
        self.account1 = Account.objects.get(pk=1)
        self.account2 = Account.objects.create(name=f'Account 2 Manager {test_id}', account_type='organization')
        
        self.xero_provider = IntegrationProvider.objects.get(pk=1)
        
        # Different integrations for testing scoping with unique IDs
        self.integration_1a = Integration.objects.create(
            account=self.account1,
            created_by=self.user1,
            provider=self.xero_provider,
            external_account_id=f'xero-mgr-org-a-{test_id}',
            external_account_name='Chart A Manager',
            organization_name='Organization A Manager',
            status='active'
        )
        
        self.integration_1b = Integration.objects.create(
            account=self.account1,
            created_by=self.user1,
            provider=self.xero_provider,
            external_account_id=f'xero-mgr-org-b-{test_id}',
            external_account_name='Chart B Manager',
            organization_name='Organization B Manager',
            status='active'
        )
        
        self.integration_2a = Integration.objects.create(
            account=self.account2,
            created_by=self.user2,
            provider=self.xero_provider,
            external_account_id=f'xero-mgr-org-a-{test_id}',  # Same chart, different account
            external_account_name='Chart A Manager',
            organization_name='Organization A Manager',
            status='active'
        )

    def create_validation_result(self, rule_name="duplicate_transactions", severity=ValidationSeverity.HIGH):
        """Helper to create ValidationResults"""
        return ValidationResult.create_issue(
            rule_name=rule_name,
            severity=severity,
            title=f"Test {rule_name} issue",
            description=f"Found {rule_name} problem",
            affected_transactions=[
                {"id": "txn_123", "amount": 100.00, "description": "Test transaction"}
            ],
            metadata={"test": True}
        )

    def test_creates_new_issue_for_first_occurrence(self):
        """Should create a new issue for the first occurrence of a validation problem"""
        validation_result = self.create_validation_result("duplicate_transactions")
        
        # Create issue using manager
        issue = Issue.objects.create_or_update_issue(self.integration_1a, validation_result)
        
        # Verify issue was created with correct properties
        self.assertIsNotNone(issue.id)
        self.assertTrue(issue.prefix_id.startswith('iss_'))
        self.assertEqual(issue.integration, self.integration_1a)
        self.assertEqual(issue.category, 'duplicate_transactions')  # Uses rule name directly
        self.assertEqual(issue.severity, 'high')
        self.assertEqual(issue.status, 'open')
        self.assertEqual(issue.count, 1)
        self.assertEqual(len(issue.occurrence_ids), 1)
        self.assertIsNotNone(issue.issue_key)
        
        # Verify issue_key contains proper scoping
        expected_key = f"{self.account1.id}:{self.integration_1a.external_account_id}:duplicate_transactions:high"
        self.assertEqual(issue.issue_key, expected_key)

    def test_aggregates_similar_issues_same_scope(self):
        """Should aggregate similar issues within the same account + chart scope"""
        validation_result1 = self.create_validation_result("duplicate_transactions")
        validation_result2 = self.create_validation_result("duplicate_transactions")
        
        # Create first issue
        issue1 = Issue.objects.create_or_update_issue(self.integration_1a, validation_result1)
        
        # Create second similar issue - should update the first
        issue2 = Issue.objects.create_or_update_issue(self.integration_1a, validation_result2)
        
        # Should be the same issue object
        self.assertEqual(issue1.id, issue2.id)
        self.assertEqual(issue2.count, 2)  # Count should increase
        self.assertEqual(len(issue2.occurrence_ids), 2)  # Two occurrences tracked
        
        # Should only be one issue in database
        self.assertEqual(Issue.objects.filter(integration=self.integration_1a).count(), 1)

    def test_keeps_issues_separate_different_charts(self):
        """Should keep issues separate when they're from different charts of accounts"""
        validation_result = self.create_validation_result("duplicate_transactions")
        
        # Create issue in chart A
        issue_a = Issue.objects.create_or_update_issue(self.integration_1a, validation_result)
        
        # Create same type of issue in chart B (same account, different chart)
        issue_b = Issue.objects.create_or_update_issue(self.integration_1b, validation_result)
        
        # Should be different issues
        self.assertNotEqual(issue_a.id, issue_b.id)
        self.assertNotEqual(issue_a.issue_key, issue_b.issue_key)
        
        # Each should have count = 1 (no aggregation across charts)
        self.assertEqual(issue_a.count, 1)
        self.assertEqual(issue_b.count, 1)
        
        # Total of 2 issues
        self.assertEqual(Issue.objects.count(), 2)

    def test_keeps_issues_separate_different_accounts(self):
        """Should keep issues separate across different accounts (tenant isolation)"""
        validation_result = self.create_validation_result("duplicate_transactions")
        
        # Create issue in account 1
        issue_acc1 = Issue.objects.create_or_update_issue(self.integration_1a, validation_result)
        
        # Create same type of issue in account 2 (same chart, different account)
        issue_acc2 = Issue.objects.create_or_update_issue(self.integration_2a, validation_result)
        
        # Should be completely separate issues
        self.assertNotEqual(issue_acc1.id, issue_acc2.id)
        self.assertNotEqual(issue_acc1.issue_key, issue_acc2.issue_key)
        
        # Each should have count = 1 (no aggregation across accounts)
        self.assertEqual(issue_acc1.count, 1)
        self.assertEqual(issue_acc2.count, 1)
        
        # Verify tenant isolation
        account1_issues = Issue.objects.get_issues_for_account(self.account1)
        account2_issues = Issue.objects.get_issues_for_account(self.account2)
        
        self.assertEqual(account1_issues.count(), 1)
        self.assertEqual(account2_issues.count(), 1)
        self.assertIn(issue_acc1, account1_issues)
        self.assertIn(issue_acc2, account2_issues)

    def test_different_rule_names_create_separate_issues(self):
        """Should create separate issues for different rule names even in same scope"""
        duplicate_result = self.create_validation_result("duplicate_transactions")
        missing_data_result = self.create_validation_result("missing_data")
        
        # Create issues with different rule names
        issue1 = Issue.objects.create_or_update_issue(self.integration_1a, duplicate_result)
        issue2 = Issue.objects.create_or_update_issue(self.integration_1a, missing_data_result)
        
        # Should be different issues
        self.assertNotEqual(issue1.id, issue2.id)
        self.assertEqual(issue1.category, 'duplicate_transactions')
        self.assertEqual(issue2.category, 'missing_data')
        self.assertNotEqual(issue1.issue_key, issue2.issue_key)

    def test_different_severities_create_separate_issues(self):
        """Should create separate issues for different severities of same rule"""
        high_result = self.create_validation_result("duplicate_transactions", ValidationSeverity.HIGH)
        critical_result = self.create_validation_result("duplicate_transactions", ValidationSeverity.CRITICAL)
        
        # Create issues with different severities
        issue1 = Issue.objects.create_or_update_issue(self.integration_1a, high_result)
        issue2 = Issue.objects.create_or_update_issue(self.integration_1a, critical_result)
        
        # Should be different issues
        self.assertNotEqual(issue1.id, issue2.id)
        self.assertEqual(issue1.severity, 'high')
        self.assertEqual(issue2.severity, 'critical')
        self.assertNotEqual(issue1.issue_key, issue2.issue_key)

    def test_occurrence_tracking(self):
        """Should properly track individual occurrences"""
        validation_result1 = self.create_validation_result("duplicate_transactions")
        validation_result2 = self.create_validation_result("duplicate_transactions")
        
        # Create first occurrence
        issue = Issue.objects.create_or_update_issue(self.integration_1a, validation_result1)
        first_occurrence_id = issue.occurrence_ids[0]
        
        # Add second occurrence
        updated_issue = Issue.objects.create_or_update_issue(self.integration_1a, validation_result2)
        
        # Should have 2 occurrences tracked
        self.assertEqual(len(updated_issue.occurrence_ids), 2)
        self.assertEqual(updated_issue.get_unresolved_count(), 2)
        
        # Occurrence IDs should be different
        self.assertNotEqual(updated_issue.occurrence_ids[0], updated_issue.occurrence_ids[1])
        
        # Latest occurrence should be updated
        self.assertIsNotNone(updated_issue.latest_occurrence)
        self.assertEqual(updated_issue.latest_occurrence['metadata'], {"test": True})

    def test_category_display_name(self):
        """Should convert rule names to human-readable category names"""
        validation_result = self.create_validation_result("duplicate_transactions")
        issue = Issue.objects.create_or_update_issue(self.integration_1a, validation_result)
        
        # Should convert underscore to space and title case
        self.assertEqual(issue.get_category_display_name(), "Duplicate Transactions")
        
        # Test another rule name
        missing_result = self.create_validation_result("missing_data") 
        missing_issue = Issue.objects.create_or_update_issue(self.integration_1b, missing_result)
        self.assertEqual(missing_issue.get_category_display_name(), "Missing Data")

    def test_issue_scoping_methods(self):
        """Should provide proper scoping query methods"""
        # Create issues in different scopes
        result = self.create_validation_result("duplicate_transactions")
        
        issue_1a = Issue.objects.create_or_update_issue(self.integration_1a, result)
        issue_1b = Issue.objects.create_or_update_issue(self.integration_1b, result)
        issue_2a = Issue.objects.create_or_update_issue(self.integration_2a, result)
        
        # Test account scoping
        account1_issues = Issue.objects.get_issues_for_account(self.account1)
        account2_issues = Issue.objects.get_issues_for_account(self.account2)
        
        self.assertEqual(account1_issues.count(), 2)  # 1a and 1b
        self.assertEqual(account2_issues.count(), 1)  # 2a only
        
        # Test chart scoping  
        chart_1a_issues = Issue.objects.get_issues_for_chart(self.integration_1a)
        chart_1b_issues = Issue.objects.get_issues_for_chart(self.integration_1b)
        chart_2a_issues = Issue.objects.get_issues_for_chart(self.integration_2a)
        
        self.assertEqual(chart_1a_issues.count(), 1)  # Only 1a
        self.assertEqual(chart_1b_issues.count(), 1)  # Only 1b  
        self.assertEqual(chart_2a_issues.count(), 1)  # Only 2a
        
        # Verify correct issues in each scope
        self.assertIn(issue_1a, account1_issues)
        self.assertIn(issue_1b, account1_issues)
        self.assertIn(issue_2a, account2_issues)
        
        self.assertIn(issue_1a, chart_1a_issues)
        self.assertIn(issue_1b, chart_1b_issues) 
        self.assertIn(issue_2a, chart_2a_issues)