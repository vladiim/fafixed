"""
Tests for CategoryDetectionRule and CategorySuggestion models.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from decimal import Decimal
import json

from integrations.models import Integration
from integrations.models import IntegrationProvider
from data_quality.models import (
    XeroTrackingCategory, 
    CategoryDetectionRule, 
    CategorySuggestion,
    ConditionOperator
)
from core.models import Account


class CategoryDetectionRuleModelTest(TestCase):
    """Test CategoryDetectionRule model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.account = Account.objects.create(
            name='Test Account',
            account_type='organization'
        )
        self.provider = IntegrationProvider.objects.create(
            name='xero',
            display_name='Xero',
            provider_type='xero',
            auth_url_template='https://api.xero.com/oauth/authorize',
            token_url='https://api.xero.com/oauth/token'
        )
        self.connection = Integration.objects.create(
            account=self.account,
            provider=self.provider,
            external_account_id='test-xero-org-id',
            external_account_name='Test Xero Org',
            organization_name='Test Organization',
            status='active',
            created_by=self.user
        )
        self.category = XeroTrackingCategory.objects.create(
            connection=self.connection,
            xero_category_id='cat-uuid-123',
            name='Test Category',
            status='ACTIVE'
        )
    
    def test_create_rule_with_minimal_fields(self):
        """Test creating a rule with only required fields"""
        rule = CategoryDetectionRule.objects.create(
            connection=self.connection,
            name='Test Rule',
            suggested_category=self.category,
            conditions=[
                {
                    'field': 'description',
                    'operator': 'CONTAINS',
                    'value': 'office supplies'
                }
            ]
        )
        
        self.assertIsNotNone(rule.id)
        self.assertEqual(rule.name, 'Test Rule')
        self.assertEqual(rule.connection, self.connection)
        self.assertEqual(rule.suggested_category, self.category)
        self.assertTrue(rule.is_active)
        self.assertEqual(rule.priority, 0)
        self.assertIsNotNone(rule.created_at)
        self.assertIsNotNone(rule.updated_at)
    
    def test_create_rule_with_all_fields(self):
        """Test creating a rule with all fields"""
        conditions = [
            {
                'field': 'description',
                'operator': 'CONTAINS',
                'value': 'office supplies'
            },
            {
                'field': 'contact_name', 
                'operator': 'EQUALS',
                'value': 'Staples'
            }
        ]
        
        rule = CategoryDetectionRule.objects.create(
            connection=self.connection,
            name='Complex Rule',
            description='A rule for office supplies from Staples',
            suggested_category=self.category,
            conditions=conditions,
            condition_logic='ALL',
            priority=10,
            is_active=False
        )
        
        self.assertEqual(rule.description, 'A rule for office supplies from Staples')
        self.assertEqual(rule.conditions, conditions)
        self.assertEqual(rule.condition_logic, 'ALL')
        self.assertEqual(rule.priority, 10)
        self.assertFalse(rule.is_active)
    
    def test_rule_name_unique_per_connection(self):
        """Test that rule names must be unique per connection"""
        CategoryDetectionRule.objects.create(
            connection=self.connection,
            name='Unique Rule',
            suggested_category=self.category,
            conditions=[{'field': 'description', 'operator': 'CONTAINS', 'value': 'test'}]
        )
        
        with self.assertRaises(IntegrityError):
            CategoryDetectionRule.objects.create(
                connection=self.connection,
                name='Unique Rule',
                suggested_category=self.category,
                conditions=[{'field': 'description', 'operator': 'CONTAINS', 'value': 'test2'}]
            )
    
    def test_rule_name_can_be_same_across_connections(self):
        """Test that rule names can be the same across different connections"""
        # Create second connection
        connection2 = Integration.objects.create(
            account=self.account,
            provider=self.provider,
            external_account_id='test-xero-org-id-2',
            external_account_name='Test Xero Org 2',
            organization_name='Test Organization 2',
            status='active',
            created_by=self.user
        )
        category2 = XeroTrackingCategory.objects.create(
            connection=connection2,
            xero_category_id='cat-uuid-456',
            name='Test Category 2',
            status='ACTIVE'
        )
        
        # Create rules with same name on different connections
        rule1 = CategoryDetectionRule.objects.create(
            connection=self.connection,
            name='Same Name Rule',
            suggested_category=self.category,
            conditions=[{'field': 'description', 'operator': 'CONTAINS', 'value': 'test1'}]
        )
        
        rule2 = CategoryDetectionRule.objects.create(
            connection=connection2,
            name='Same Name Rule',
            suggested_category=category2,
            conditions=[{'field': 'description', 'operator': 'CONTAINS', 'value': 'test2'}]
        )
        
        self.assertNotEqual(rule1.id, rule2.id)
        self.assertEqual(rule1.name, rule2.name)
    
    def test_conditions_json_field(self):
        """Test that conditions are properly stored as JSON"""
        conditions = [
            {
                'field': 'description',
                'operator': 'REGEX',
                'value': r'^\d{4}-\d{2}-\d{2}.*invoice'
            },
            {
                'field': 'amount',
                'operator': 'GREATER_THAN',
                'value': 100.50
            }
        ]
        
        rule = CategoryDetectionRule.objects.create(
            connection=self.connection,
            name='JSON Test Rule',
            suggested_category=self.category,
            conditions=conditions
        )
        
        # Refresh from database
        rule.refresh_from_db()
        
        self.assertEqual(rule.conditions, conditions)
        self.assertEqual(len(rule.conditions), 2)
        self.assertEqual(rule.conditions[0]['field'], 'description')
        self.assertEqual(rule.conditions[1]['value'], 100.50)
    
    def test_condition_logic_choices(self):
        """Test condition logic field accepts valid choices"""
        # Test ALL
        rule_all = CategoryDetectionRule.objects.create(
            connection=self.connection,
            name='ALL Logic Rule',
            suggested_category=self.category,
            conditions=[{'field': 'description', 'operator': 'CONTAINS', 'value': 'test'}],
            condition_logic='ALL'
        )
        self.assertEqual(rule_all.condition_logic, 'ALL')
        
        # Test ANY
        rule_any = CategoryDetectionRule.objects.create(
            connection=self.connection,
            name='ANY Logic Rule',
            suggested_category=self.category,
            conditions=[{'field': 'description', 'operator': 'CONTAINS', 'value': 'test'}],
            condition_logic='ANY'
        )
        self.assertEqual(rule_any.condition_logic, 'ANY')
    
    def test_priority_ordering(self):
        """Test that rules can be ordered by priority"""
        rule1 = CategoryDetectionRule.objects.create(
            connection=self.connection,
            name='Low Priority Rule',
            suggested_category=self.category,
            conditions=[{'field': 'description', 'operator': 'CONTAINS', 'value': 'test1'}],
            priority=1
        )
        
        rule2 = CategoryDetectionRule.objects.create(
            connection=self.connection,
            name='High Priority Rule',
            suggested_category=self.category,
            conditions=[{'field': 'description', 'operator': 'CONTAINS', 'value': 'test2'}],
            priority=10
        )
        
        rule3 = CategoryDetectionRule.objects.create(
            connection=self.connection,
            name='Default Priority Rule',
            suggested_category=self.category,
            conditions=[{'field': 'description', 'operator': 'CONTAINS', 'value': 'test3'}]
        )
        
        # Order by priority descending
        rules = CategoryDetectionRule.objects.filter(
            connection=self.connection
        ).order_by('-priority')
        
        self.assertEqual(rules[0], rule2)  # Priority 10
        self.assertEqual(rules[1], rule1)  # Priority 1
        self.assertEqual(rules[2], rule3)  # Priority 0 (default)
    
    def test_string_representation(self):
        """Test model string representation"""
        rule = CategoryDetectionRule.objects.create(
            connection=self.connection,
            name='Test Rule',
            suggested_category=self.category,
            conditions=[{'field': 'description', 'operator': 'CONTAINS', 'value': 'test'}]
        )
        
        expected = f"Test Rule -> {self.category.name}"
        self.assertEqual(str(rule), expected)
    
    def test_related_name_from_connection(self):
        """Test accessing rules from connection via related name"""
        rule = CategoryDetectionRule.objects.create(
            connection=self.connection,
            name='Related Name Test',
            suggested_category=self.category,
            conditions=[{'field': 'description', 'operator': 'CONTAINS', 'value': 'test'}]
        )
        
        self.assertIn(rule, self.connection.category_detection_rules.all())
    
    def test_related_name_from_category(self):
        """Test accessing rules from category via related name"""
        rule = CategoryDetectionRule.objects.create(
            connection=self.connection,
            name='Category Related Test',
            suggested_category=self.category,
            conditions=[{'field': 'description', 'operator': 'CONTAINS', 'value': 'test'}]
        )
        
        self.assertIn(rule, self.category.detection_rules.all())


class CategorySuggestionModelTest(TestCase):
    """Test CategorySuggestion model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.account = Account.objects.create(
            name='Test Account',
            account_type='organization'
        )
        self.provider = IntegrationProvider.objects.create(
            name='xero',
            display_name='Xero',
            provider_type='xero',
            auth_url_template='https://api.xero.com/oauth/authorize',
            token_url='https://api.xero.com/oauth/token'
        )
        self.connection = Integration.objects.create(
            account=self.account,
            provider=self.provider,
            external_account_id='test-xero-org-id',
            external_account_name='Test Xero Org',
            organization_name='Test Organization',
            status='active',
            created_by=self.user
        )
        self.category = XeroTrackingCategory.objects.create(
            connection=self.connection,
            xero_category_id='cat-uuid-123',
            name='Test Category',
            status='ACTIVE'
        )
        self.rule = CategoryDetectionRule.objects.create(
            connection=self.connection,
            name='Test Rule',
            suggested_category=self.category,
            conditions=[{'field': 'description', 'operator': 'CONTAINS', 'value': 'test'}]
        )
    
    def test_create_suggestion_with_minimal_fields(self):
        """Test creating a suggestion with only required fields"""
        suggestion = CategorySuggestion.objects.create(
            connection=self.connection,
            detection_rule=self.rule,
            xero_transaction_id='txn-uuid-123',
            suggested_category=self.category
        )
        
        self.assertIsNotNone(suggestion.id)
        self.assertEqual(suggestion.connection, self.connection)
        self.assertEqual(suggestion.detection_rule, self.rule)
        self.assertEqual(suggestion.xero_transaction_id, 'txn-uuid-123')
        self.assertEqual(suggestion.suggested_category, self.category)
        self.assertEqual(suggestion.status, 'PENDING')
        self.assertIsNone(suggestion.transaction_description)
        self.assertIsNone(suggestion.transaction_contact)
        self.assertIsNone(suggestion.transaction_amount)
        self.assertIsNotNone(suggestion.created_at)
        self.assertIsNotNone(suggestion.updated_at)
    
    def test_create_suggestion_with_all_fields(self):
        """Test creating a suggestion with all fields"""
        suggestion = CategorySuggestion.objects.create(
            connection=self.connection,
            detection_rule=self.rule,
            xero_transaction_id='txn-uuid-456',
            suggested_category=self.category,
            transaction_description='Office supplies from Staples',
            transaction_contact='Staples Inc',
            transaction_amount=Decimal('125.50'),
            status='APPLIED'
        )
        
        self.assertEqual(suggestion.transaction_description, 'Office supplies from Staples')
        self.assertEqual(suggestion.transaction_contact, 'Staples Inc')
        self.assertEqual(suggestion.transaction_amount, Decimal('125.50'))
        self.assertEqual(suggestion.status, 'APPLIED')
    
    def test_suggestion_unique_per_transaction_rule(self):
        """Test that suggestions are unique per transaction and rule combination"""
        CategorySuggestion.objects.create(
            connection=self.connection,
            detection_rule=self.rule,
            xero_transaction_id='txn-uuid-unique',
            suggested_category=self.category
        )
        
        with self.assertRaises(IntegrityError):
            CategorySuggestion.objects.create(
                connection=self.connection,
                detection_rule=self.rule,
                xero_transaction_id='txn-uuid-unique',
                suggested_category=self.category
            )
    
    def test_suggestion_status_choices(self):
        """Test suggestion status field accepts valid choices"""
        statuses = ['PENDING', 'APPLIED', 'IGNORED', 'SUPERSEDED']
        
        for status in statuses:
            suggestion = CategorySuggestion.objects.create(
                connection=self.connection,
                detection_rule=self.rule,
                xero_transaction_id=f'txn-{status.lower()}',
                suggested_category=self.category,
                status=status
            )
            self.assertEqual(suggestion.status, status)
    
    def test_string_representation(self):
        """Test model string representation"""
        suggestion = CategorySuggestion.objects.create(
            connection=self.connection,
            detection_rule=self.rule,
            xero_transaction_id='txn-string-test',
            suggested_category=self.category,
            transaction_description='Test transaction'
        )
        
        expected = f"txn-string-test -> {self.category.name} (PENDING)"
        self.assertEqual(str(suggestion), expected)
    
    def test_related_name_from_connection(self):
        """Test accessing suggestions from connection via related name"""
        suggestion = CategorySuggestion.objects.create(
            connection=self.connection,
            detection_rule=self.rule,
            xero_transaction_id='txn-related-test',
            suggested_category=self.category
        )
        
        self.assertIn(suggestion, self.connection.category_suggestions.all())
    
    def test_related_name_from_rule(self):
        """Test accessing suggestions from rule via related name"""
        suggestion = CategorySuggestion.objects.create(
            connection=self.connection,
            detection_rule=self.rule,
            xero_transaction_id='txn-rule-related',
            suggested_category=self.category
        )
        
        self.assertIn(suggestion, self.rule.suggestions.all())
    
    def test_related_name_from_category(self):
        """Test accessing suggestions from category via related name"""
        suggestion = CategorySuggestion.objects.create(
            connection=self.connection,
            detection_rule=self.rule,
            xero_transaction_id='txn-category-related',
            suggested_category=self.category
        )
        
        self.assertIn(suggestion, self.category.suggestions.all())
    
    def test_pending_suggestions_manager(self):
        """Test filtering pending suggestions"""
        # Create suggestions with different statuses
        pending1 = CategorySuggestion.objects.create(
            connection=self.connection,
            detection_rule=self.rule,
            xero_transaction_id='txn-pending-1',
            suggested_category=self.category,
            status='PENDING'
        )
        
        pending2 = CategorySuggestion.objects.create(
            connection=self.connection,
            detection_rule=self.rule,
            xero_transaction_id='txn-pending-2',
            suggested_category=self.category,
            status='PENDING'
        )
        
        applied = CategorySuggestion.objects.create(
            connection=self.connection,
            detection_rule=self.rule,
            xero_transaction_id='txn-applied',
            suggested_category=self.category,
            status='APPLIED'
        )
        
        # Test filtering pending suggestions
        pending_suggestions = CategorySuggestion.objects.filter(status='PENDING')
        
        self.assertEqual(pending_suggestions.count(), 2)
        self.assertIn(pending1, pending_suggestions)
        self.assertIn(pending2, pending_suggestions)
        self.assertNotIn(applied, pending_suggestions)
    
    def test_cascade_delete_from_rule(self):
        """Test that suggestions are deleted when rule is deleted"""
        suggestion = CategorySuggestion.objects.create(
            connection=self.connection,
            detection_rule=self.rule,
            xero_transaction_id='txn-cascade-test',
            suggested_category=self.category
        )
        
        suggestion_id = suggestion.id
        
        # Delete the rule
        self.rule.delete()
        
        # Suggestion should be deleted
        self.assertFalse(CategorySuggestion.objects.filter(id=suggestion_id).exists())
    
    def test_protect_delete_from_category(self):
        """Test that category cannot be deleted if it has suggestions"""
        CategorySuggestion.objects.create(
            connection=self.connection,
            detection_rule=self.rule,
            xero_transaction_id='txn-protect-test',
            suggested_category=self.category
        )
        
        # Should not be able to delete category with suggestions
        with self.assertRaises(Exception):  # Will be ProtectedError or similar
            self.category.delete()


class ConditionOperatorTest(TestCase):
    """Test ConditionOperator choices"""
    
    def test_operator_choices_available(self):
        """Test that all expected operators are available"""
        expected_operators = [
            'EQUALS',
            'NOT_EQUALS',
            'CONTAINS',
            'NOT_CONTAINS',
            'STARTS_WITH',
            'ENDS_WITH',
            'REGEX',
            'GREATER_THAN',
            'LESS_THAN',
            'GREATER_THAN_OR_EQUAL',
            'LESS_THAN_OR_EQUAL'
        ]
        
        for operator in expected_operators:
            # This test ensures the choices are properly defined
            # The actual validation happens in the model
            self.assertIn(operator, [choice[0] for choice in ConditionOperator.choices])