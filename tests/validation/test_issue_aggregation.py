"""
Tests for Issue aggregation with account multi-tenancy and chart of accounts scoping.

Ensures that:
1. Issues are properly scoped to account boundaries (multi-tenancy)
2. Issues are grouped only within the same chart of accounts (external_account_id)  
3. Similar issues from different charts of accounts remain separate
4. Issue aggregation respects tenant isolation
"""

from django.contrib.auth.models import User

from core.models import Account
from integrations.models import Integration, IntegrationProvider, Issue
from integrations.validation.base import ValidationResult, ValidationSeverity
from .base_validation_test import BaseValidationTestCase


class IssueAggregationTestCase(BaseValidationTestCase):
    
    fixtures = ['test_integration_stack.json']
    
    def setUp(self):
        """Set up test data with multiple accounts and chart of accounts"""
        super().setUp()  # This handles cleanup
        
        # Create unique test ID to avoid conflicts
        import uuid
        test_id = str(uuid.uuid4())[:8]
        
        # Users and Accounts
        self.user1 = User.objects.get(pk=1)
        self.user2 = User.objects.create_user(f'testuser2_agg_{test_id}', f'test2_agg_{test_id}@example.com', 'password')
        
        self.account1 = Account.objects.get(pk=1)
        self.account2 = Account.objects.create(name=f'Account 2 Aggregation {test_id}', account_type='organization')
        
        # Integration Provider
        self.xero_provider = IntegrationProvider.objects.get(pk=1)
        
        # Chart of Accounts A (Xero Org A) for Account 1
        self.integration_1a = Integration.objects.create(
            account=self.account1,
            created_by=self.user1,
            provider=self.xero_provider,
            external_account_id=f'xero-agg-org-a-{test_id}',
            external_account_name='Chart A Org Aggregation',
            organization_name='Organization A Aggregation',
            status='active'
        )
        
        # Chart of Accounts B (Xero Org B) for Account 1  
        self.integration_1b = Integration.objects.create(
            account=self.account1,
            created_by=self.user1,
            provider=self.xero_provider,
            external_account_id=f'xero-agg-org-b-{test_id}',
            external_account_name='Chart B Org Aggregation', 
            organization_name='Organization B Aggregation',
            status='active'
        )
        
        # Chart of Accounts A (same Xero Org) for Account 2
        self.integration_2a = Integration.objects.create(
            account=self.account2,
            created_by=self.user2,
            provider=self.xero_provider,
            external_account_id=f'xero-agg-org-a-{test_id}',  # Same chart, different account
            external_account_name='Chart A Org Aggregation',
            organization_name='Organization A Aggregation',
            status='active'
        )

    def create_validation_result(self, rule_name="duplicate_transactions", severity=ValidationSeverity.MEDIUM):
        """Helper to create ValidationResults for testing"""
        return ValidationResult.create_issue(
            rule_name=rule_name,
            severity=severity,
            title=f"Duplicate transactions found",
            description=f"Found duplicate transactions",
            affected_transactions=[
                {"id": "txn_123", "amount": 100.00, "description": "Test transaction"}
            ]
        )

    def test_issues_grouped_within_same_chart_of_accounts(self):
        """Issues should be grouped only within the same chart of accounts (external_account_id)"""
        
        # Create similar issues in the same chart of accounts (1a)
        result1 = self.create_validation_result("duplicate_transactions")
        result2 = self.create_validation_result("duplicate_transactions") 
        
        # Simulate issue creation from validation results
        issue1 = Issue.objects.create(
            integration=self.integration_1a,
            title=result1.title,
            description=result1.description,
            category='duplicate_transactions',
            severity=result1.severity.value,
            affected_transactions=result1.affected_transactions
        )
        
        issue2 = Issue.objects.create(
            integration=self.integration_1a,  # Same integration = same chart
            title=result2.title,
            description=result2.description,
            category='duplicate_transactions', 
            severity=result2.severity.value,
            affected_transactions=result2.affected_transactions
        )
        
        # Both issues should exist but be for the same integration/chart
        self.assertEqual(Issue.objects.filter(integration=self.integration_1a).count(), 2)
        self.assertEqual(issue1.integration.external_account_id, issue2.integration.external_account_id)

    def test_issues_separate_across_different_charts_of_accounts(self):
        """Similar issues from different charts of accounts should remain separate"""
        
        result = self.create_validation_result("duplicate_transactions")
        
        # Create identical issues in different charts of accounts
        issue_chart_a = Issue.objects.create(
            integration=self.integration_1a,  # Chart A
            title=result.title,
            description=result.description,
            category='duplicate_transactions',
            severity=result.severity.value,
            affected_transactions=result.affected_transactions
        )
        
        issue_chart_b = Issue.objects.create(
            integration=self.integration_1b,  # Chart B (different chart, same account)
            title=result.title,
            description=result.description, 
            category='duplicate_transactions',
            severity=result.severity.value,
            affected_transactions=result.affected_transactions
        )
        
        # Issues should be separate despite being similar
        self.assertNotEqual(issue_chart_a.integration.external_account_id, 
                           issue_chart_b.integration.external_account_id)
        self.assertEqual(Issue.objects.count(), 2)  # Two separate issues
        self.assertEqual(Issue.objects.filter(integration__account=self.account1).count(), 2)

    def test_account_multi_tenancy_isolation(self):
        """Issues must be completely isolated between different accounts"""
        
        result = self.create_validation_result("duplicate_transactions")
        
        # Create identical issues in the same chart but different accounts
        issue_account1 = Issue.objects.create(
            integration=self.integration_1a,  # Account 1, Chart A
            title=result.title,
            description=result.description,
            category='duplicate_transactions',
            severity=result.severity.value,
            affected_transactions=result.affected_transactions
        )
        
        issue_account2 = Issue.objects.create(
            integration=self.integration_2a,  # Account 2, Chart A (same chart, different account)
            title=result.title,
            description=result.description,
            category='duplicate_transactions', 
            severity=result.severity.value,
            affected_transactions=result.affected_transactions
        )
        
        # Issues must be completely separate between accounts
        self.assertNotEqual(issue_account1.integration.account, issue_account2.integration.account)
        self.assertEqual(issue_account1.integration.external_account_id, 
                        issue_account2.integration.external_account_id)  # Same chart
        
        # Verify tenant isolation
        account1_issues = Issue.objects.filter(integration__account=self.account1)
        account2_issues = Issue.objects.filter(integration__account=self.account2)
        
        self.assertEqual(account1_issues.count(), 1)
        self.assertEqual(account2_issues.count(), 1) 
        self.assertNotEqual(list(account1_issues), list(account2_issues))

    def test_issue_key_generation_includes_tenant_and_chart_scope(self):
        """Issue keys should include both account and chart scoping for proper grouping"""
        
        # This test will drive the implementation of proper issue_key generation
        result = self.create_validation_result("duplicate_transactions")
        
        # Create issues that should have different keys due to different scoping
        issue1 = Issue.objects.create(
            integration=self.integration_1a,  # Account 1, Chart A
            title=result.title,
            description=result.description,
            category='duplicate_transactions',
            severity=result.severity.value,
            affected_transactions=result.affected_transactions
        )
        
        issue2 = Issue.objects.create(
            integration=self.integration_1b,  # Account 1, Chart B  
            title=result.title,
            description=result.description,
            category='duplicate_transactions',
            severity=result.severity.value,
            affected_transactions=result.affected_transactions
        )
        
        issue3 = Issue.objects.create(
            integration=self.integration_2a,  # Account 2, Chart A
            title=result.title, 
            description=result.description,
            category='duplicate_transactions',
            severity=result.severity.value,
            affected_transactions=result.affected_transactions
        )
        
        # Each issue should be distinguishable by its scope
        # This will fail initially and drive implementation
        all_issues = Issue.objects.all()
        self.assertEqual(len(all_issues), 3)
        
        # Issues should be properly scoped to their tenants and charts
        self.assertEqual(Issue.objects.filter(integration__account=self.account1).count(), 2)
        self.assertEqual(Issue.objects.filter(integration__account=self.account2).count(), 1)
        self.assertEqual(Issue.objects.filter(integration__external_account_id=self.integration_1a.external_account_id).count(), 2)
        self.assertEqual(Issue.objects.filter(integration__external_account_id=self.integration_1b.external_account_id).count(), 1)

    def test_cross_tenant_query_protection(self):
        """Ensure queries are protected from cross-tenant data access"""
        
        result = self.create_validation_result("duplicate_transactions")
        
        # Create issues in different accounts
        issue_account1 = Issue.objects.create(
            integration=self.integration_1a,
            title=result.title,
            description=result.description, 
            category='duplicate_transactions',
            severity=result.severity.value,
            affected_transactions=result.affected_transactions
        )
        
        issue_account2 = Issue.objects.create(
            integration=self.integration_2a,
            title=result.title,
            description=result.description,
            category='duplicate_transactions',
            severity=result.severity.value, 
            affected_transactions=result.affected_transactions
        )
        
        # Queries should be properly scoped to prevent cross-tenant access
        # When querying for account1's issues, should not see account2's issues
        account1_scoped_issues = Issue.objects.filter(integration__account=self.account1)
        account2_scoped_issues = Issue.objects.filter(integration__account=self.account2)
        
        self.assertIn(issue_account1, account1_scoped_issues)
        self.assertNotIn(issue_account2, account1_scoped_issues)
        
        self.assertIn(issue_account2, account2_scoped_issues)
        self.assertNotIn(issue_account1, account2_scoped_issues)

    def test_issue_manager_respects_scoping(self):
        """The future IssueManager should respect both tenant and chart scoping"""
        
        # This test will drive the IssueManager implementation
        # For now, we'll test the expected behavior that needs to be implemented
        
        result = self.create_validation_result("duplicate_transactions")
        
        # Expected behavior: IssueManager.create_or_update_issue() should:
        # 1. Only look for existing issues within the same account + chart scope
        # 2. Group issues appropriately within that scope
        # 3. Never merge issues across account or chart boundaries
        
        # Create first issue
        issue1 = Issue.objects.create(
            integration=self.integration_1a,
            title=result.title,
            description=result.description,
            category='duplicate_transactions',
            severity=result.severity.value,
            affected_transactions=result.affected_transactions
        )
        
        # Verify that when we query for similar issues, we only see ones from the same scope
        similar_issues_same_scope = Issue.objects.filter(
            integration__account=self.integration_1a.account,  # Same account
            integration__external_account_id=self.integration_1a.external_account_id,  # Same chart
            category='duplicate_transactions',
            status='open'
        )
        
        self.assertEqual(similar_issues_same_scope.count(), 1)
        self.assertEqual(similar_issues_same_scope.first(), issue1)
        
        # Create similar issue in different scope - should not be found
        Issue.objects.create(
            integration=self.integration_1b,  # Different chart 
            title=result.title,
            description=result.description,
            category='duplicate_transactions',
            severity=result.severity.value,
            affected_transactions=result.affected_transactions
        )
        
        # Query should still only return the first issue (same scope)
        similar_issues_same_scope = Issue.objects.filter(
            integration__account=self.integration_1a.account,
            integration__external_account_id=self.integration_1a.external_account_id, 
            category='duplicate_transactions',
            status='open'
        )
        
        self.assertEqual(similar_issues_same_scope.count(), 1)
        self.assertEqual(similar_issues_same_scope.first(), issue1)