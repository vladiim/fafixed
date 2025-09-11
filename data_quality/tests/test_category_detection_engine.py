"""
Tests for CategoryDetectionEngine - TDD implementation.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from decimal import Decimal
from unittest.mock import Mock, patch
import re

from connections.models import Connection, Provider
from data_quality.models import (
    XeroTrackingCategory, 
    CategoryDetectionRule, 
    CategorySuggestion,
    ConditionOperator
)
from data_quality.services.category_detection import CategoryDetectionEngine
from core.models import Account


class CategoryDetectionEngineTest(TestCase):
    """Test CategoryDetectionEngine functionality"""
    
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
        self.provider = Provider.objects.create(
            name='xero',
            display_name='Xero',
            provider_type='xero',
            auth_url_template='https://api.xero.com/oauth/authorize',
            token_url='https://api.xero.com/oauth/token'
        )
        self.connection = Connection.objects.create(
            account=self.account,
            provider=self.provider,
            external_account_id='test-xero-org-id',
            external_account_name='Test Xero Org',
            organization_name='Test Organization',
            status='active',
            created_by=self.user
        )
        
        # Create test tracking categories
        self.office_category = XeroTrackingCategory.objects.create(
            connection=self.connection,
            xero_category_id='office-supplies-cat',
            name='Office Supplies',
            status='ACTIVE'
        )
        self.fuel_category = XeroTrackingCategory.objects.create(
            connection=self.connection,
            xero_category_id='fuel-cat',
            name='Vehicle Fuel',
            status='ACTIVE'
        )
        
        # Create detection engine
        self.engine = CategoryDetectionEngine(self.connection)
        
        # Sample transaction data
        self.sample_transaction = {
            'id': 'txn-123',
            'description': 'Office Depot - Pens and Paper',
            'contact_name': 'Office Depot',
            'reference': 'INV-2024-001',
            'amount': Decimal('45.50'),
            'date': '2024-01-15'
        }

    def test_engine_initialization(self):
        """Test engine initializes with connection"""
        engine = CategoryDetectionEngine(self.connection)
        self.assertEqual(engine.connection, self.connection)

    def test_evaluate_simple_contains_condition_match(self):
        """Test evaluating a simple CONTAINS condition that matches"""
        condition = {
            'field': 'description',
            'operator': 'CONTAINS',
            'value': 'office depot'
        }
        
        result = self.engine.evaluate_condition(self.sample_transaction, condition)
        self.assertTrue(result)

    def test_evaluate_simple_contains_condition_no_match(self):
        """Test evaluating a simple CONTAINS condition that doesn't match"""
        condition = {
            'field': 'description',
            'operator': 'CONTAINS',
            'value': 'walmart'
        }
        
        result = self.engine.evaluate_condition(self.sample_transaction, condition)
        self.assertFalse(result)

    def test_evaluate_equals_condition_case_insensitive(self):
        """Test EQUALS operator is case insensitive"""
        condition = {
            'field': 'contact_name',
            'operator': 'EQUALS',
            'value': 'OFFICE DEPOT'
        }
        
        result = self.engine.evaluate_condition(self.sample_transaction, condition)
        self.assertTrue(result)

    def test_evaluate_starts_with_condition(self):
        """Test STARTS_WITH operator"""
        condition = {
            'field': 'description',
            'operator': 'STARTS_WITH',
            'value': 'office'
        }
        
        result = self.engine.evaluate_condition(self.sample_transaction, condition)
        self.assertTrue(result)

    def test_evaluate_ends_with_condition(self):
        """Test ENDS_WITH operator"""
        condition = {
            'field': 'description',
            'operator': 'ENDS_WITH',
            'value': 'paper'
        }
        
        result = self.engine.evaluate_condition(self.sample_transaction, condition)
        self.assertTrue(result)

    def test_evaluate_regex_condition(self):
        """Test REGEX operator"""
        condition = {
            'field': 'reference',
            'operator': 'REGEX',
            'value': r'INV-\d{4}-\d{3}'
        }
        
        result = self.engine.evaluate_condition(self.sample_transaction, condition)
        self.assertTrue(result)

    def test_evaluate_greater_than_condition(self):
        """Test GREATER_THAN operator with numeric field"""
        condition = {
            'field': 'amount',
            'operator': 'GREATER_THAN',
            'value': 40.0
        }
        
        result = self.engine.evaluate_condition(self.sample_transaction, condition)
        self.assertTrue(result)

    def test_evaluate_less_than_condition(self):
        """Test LESS_THAN operator with numeric field"""
        condition = {
            'field': 'amount',
            'operator': 'LESS_THAN',
            'value': 50.0
        }
        
        result = self.engine.evaluate_condition(self.sample_transaction, condition)
        self.assertTrue(result)

    def test_evaluate_not_equals_condition(self):
        """Test NOT_EQUALS operator"""
        condition = {
            'field': 'contact_name',
            'operator': 'NOT_EQUALS',
            'value': 'Walmart'
        }
        
        result = self.engine.evaluate_condition(self.sample_transaction, condition)
        self.assertTrue(result)

    def test_evaluate_not_contains_condition(self):
        """Test NOT_CONTAINS operator"""
        condition = {
            'field': 'description',
            'operator': 'NOT_CONTAINS',
            'value': 'walmart'
        }
        
        result = self.engine.evaluate_condition(self.sample_transaction, condition)
        self.assertTrue(result)

    def test_evaluate_condition_missing_field(self):
        """Test condition evaluation when field is missing from transaction"""
        condition = {
            'field': 'nonexistent_field',
            'operator': 'CONTAINS',
            'value': 'test'
        }
        
        result = self.engine.evaluate_condition(self.sample_transaction, condition)
        self.assertFalse(result)

    def test_evaluate_condition_empty_field(self):
        """Test condition evaluation when field is empty"""
        transaction = self.sample_transaction.copy()
        transaction['description'] = ''
        
        condition = {
            'field': 'description',
            'operator': 'CONTAINS',
            'value': 'office'
        }
        
        result = self.engine.evaluate_condition(transaction, condition)
        self.assertFalse(result)

    def test_evaluate_rule_all_conditions_match(self):
        """Test rule evaluation with ALL logic when all conditions match"""
        rule = CategoryDetectionRule.objects.create(
            connection=self.connection,
            name='Office Supplies Rule',
            suggested_category=self.office_category,
            conditions=[
                {
                    'field': 'description',
                    'operator': 'CONTAINS',
                    'value': 'office'
                },
                {
                    'field': 'contact_name',
                    'operator': 'EQUALS',
                    'value': 'Office Depot'
                }
            ],
            condition_logic='ALL'
        )
        
        result = self.engine.evaluate_rule(self.sample_transaction, rule)
        self.assertTrue(result)

    def test_evaluate_rule_all_conditions_partial_match(self):
        """Test rule evaluation with ALL logic when only some conditions match"""
        rule = CategoryDetectionRule.objects.create(
            connection=self.connection,
            name='Office Supplies Rule',
            suggested_category=self.office_category,
            conditions=[
                {
                    'field': 'description',
                    'operator': 'CONTAINS',
                    'value': 'office'
                },
                {
                    'field': 'contact_name',
                    'operator': 'EQUALS',
                    'value': 'Walmart'  # This won't match
                }
            ],
            condition_logic='ALL'
        )
        
        result = self.engine.evaluate_rule(self.sample_transaction, rule)
        self.assertFalse(result)

    def test_evaluate_rule_any_conditions_partial_match(self):
        """Test rule evaluation with ANY logic when only some conditions match"""
        rule = CategoryDetectionRule.objects.create(
            connection=self.connection,
            name='Office Supplies Rule',
            suggested_category=self.office_category,
            conditions=[
                {
                    'field': 'description',
                    'operator': 'CONTAINS',
                    'value': 'office'  # This will match
                },
                {
                    'field': 'contact_name',
                    'operator': 'EQUALS',
                    'value': 'Walmart'  # This won't match
                }
            ],
            condition_logic='ANY'
        )
        
        result = self.engine.evaluate_rule(self.sample_transaction, rule)
        self.assertTrue(result)

    def test_evaluate_rule_any_conditions_no_match(self):
        """Test rule evaluation with ANY logic when no conditions match"""
        rule = CategoryDetectionRule.objects.create(
            connection=self.connection,
            name='Fuel Rule',
            suggested_category=self.fuel_category,
            conditions=[
                {
                    'field': 'description',
                    'operator': 'CONTAINS',
                    'value': 'fuel'
                },
                {
                    'field': 'contact_name',
                    'operator': 'EQUALS',
                    'value': 'Shell'
                }
            ],
            condition_logic='ANY'
        )
        
        result = self.engine.evaluate_rule(self.sample_transaction, rule)
        self.assertFalse(result)

    def test_evaluate_rule_inactive_rule(self):
        """Test that inactive rules are not evaluated"""
        rule = CategoryDetectionRule.objects.create(
            connection=self.connection,
            name='Inactive Rule',
            suggested_category=self.office_category,
            conditions=[
                {
                    'field': 'description',
                    'operator': 'CONTAINS',
                    'value': 'office'
                }
            ],
            is_active=False
        )
        
        result = self.engine.evaluate_rule(self.sample_transaction, rule)
        self.assertFalse(result)

    def test_create_suggestion_for_transaction(self):
        """Test creating a suggestion for a matching transaction"""
        rule = CategoryDetectionRule.objects.create(
            connection=self.connection,
            name='Office Supplies Rule',
            suggested_category=self.office_category,
            conditions=[
                {
                    'field': 'description',
                    'operator': 'CONTAINS',
                    'value': 'office'
                }
            ]
        )
        
        suggestion = self.engine.create_suggestion(self.sample_transaction, rule)
        
        self.assertIsInstance(suggestion, CategorySuggestion)
        self.assertEqual(suggestion.connection, self.connection)
        self.assertEqual(suggestion.detection_rule, rule)
        self.assertEqual(suggestion.xero_transaction_id, 'txn-123')
        self.assertEqual(suggestion.suggested_category, self.office_category)
        self.assertEqual(suggestion.transaction_description, 'Office Depot - Pens and Paper')
        self.assertEqual(suggestion.transaction_contact, 'Office Depot')
        self.assertEqual(suggestion.transaction_amount, Decimal('45.50'))
        self.assertEqual(suggestion.status, 'PENDING')

    def test_create_suggestion_prevents_duplicates(self):
        """Test that duplicate suggestions are not created"""
        rule = CategoryDetectionRule.objects.create(
            connection=self.connection,
            name='Office Supplies Rule',
            suggested_category=self.office_category,
            conditions=[
                {
                    'field': 'description',
                    'operator': 'CONTAINS',
                    'value': 'office'
                }
            ]
        )
        
        # Create first suggestion
        suggestion1 = self.engine.create_suggestion(self.sample_transaction, rule)
        self.assertIsNotNone(suggestion1)
        
        # Attempt to create duplicate - should return existing
        suggestion2 = self.engine.create_suggestion(self.sample_transaction, rule)
        self.assertEqual(suggestion1.id, suggestion2.id)

    def test_run_detection_single_rule_match(self):
        """Test running detection with a single matching rule"""
        rule = CategoryDetectionRule.objects.create(
            connection=self.connection,
            name='Office Supplies Rule',
            suggested_category=self.office_category,
            conditions=[
                {
                    'field': 'description',
                    'operator': 'CONTAINS',
                    'value': 'office'
                }
            ]
        )
        
        transactions = [self.sample_transaction]
        suggestions = self.engine.run_detection(transactions)
        
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0].detection_rule, rule)
        self.assertEqual(suggestions[0].xero_transaction_id, 'txn-123')

    def test_run_detection_multiple_rules_priority(self):
        """Test that higher priority rules are evaluated first (first match wins)"""
        # Low priority rule
        low_priority_rule = CategoryDetectionRule.objects.create(
            connection=self.connection,
            name='Low Priority Rule',
            suggested_category=self.fuel_category,
            conditions=[
                {
                    'field': 'description',
                    'operator': 'CONTAINS',
                    'value': 'depot'  # This also matches
                }
            ],
            priority=1
        )
        
        # High priority rule
        high_priority_rule = CategoryDetectionRule.objects.create(
            connection=self.connection,
            name='High Priority Rule',
            suggested_category=self.office_category,
            conditions=[
                {
                    'field': 'description',
                    'operator': 'CONTAINS',
                    'value': 'office'
                }
            ],
            priority=10
        )
        
        transactions = [self.sample_transaction]
        suggestions = self.engine.run_detection(transactions)
        
        # Should only get one suggestion from the high priority rule
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0].detection_rule, high_priority_rule)

    def test_run_detection_no_matches(self):
        """Test running detection when no rules match"""
        rule = CategoryDetectionRule.objects.create(
            connection=self.connection,
            name='Fuel Rule',
            suggested_category=self.fuel_category,
            conditions=[
                {
                    'field': 'description',
                    'operator': 'CONTAINS',
                    'value': 'gasoline'
                }
            ]
        )
        
        transactions = [self.sample_transaction]
        suggestions = self.engine.run_detection(transactions)
        
        self.assertEqual(len(suggestions), 0)

    def test_run_detection_multiple_transactions(self):
        """Test running detection on multiple transactions"""
        rule = CategoryDetectionRule.objects.create(
            connection=self.connection,
            name='Office Supplies Rule',
            suggested_category=self.office_category,
            conditions=[
                {
                    'field': 'description',
                    'operator': 'CONTAINS',
                    'value': 'office'
                }
            ]
        )
        
        transactions = [
            self.sample_transaction,
            {
                'id': 'txn-456',
                'description': 'Office Max - Staplers',
                'contact_name': 'Office Max',
                'reference': 'INV-2024-002',
                'amount': Decimal('25.99'),
                'date': '2024-01-16'
            },
            {
                'id': 'txn-789',
                'description': 'Shell - Gasoline',
                'contact_name': 'Shell',
                'reference': 'FUEL-001',
                'amount': Decimal('65.00'),
                'date': '2024-01-17'
            }
        ]
        
        suggestions = self.engine.run_detection(transactions)
        
        # Should get 2 suggestions (first two transactions match office rule)
        self.assertEqual(len(suggestions), 2)
        self.assertEqual(suggestions[0].xero_transaction_id, 'txn-123')
        self.assertEqual(suggestions[1].xero_transaction_id, 'txn-456')

    def test_run_detection_skips_existing_suggestions(self):
        """Test that detection skips transactions that already have suggestions"""
        rule = CategoryDetectionRule.objects.create(
            connection=self.connection,
            name='Office Supplies Rule',
            suggested_category=self.office_category,
            conditions=[
                {
                    'field': 'description',
                    'operator': 'CONTAINS',
                    'value': 'office'
                }
            ]
        )
        
        # Create existing suggestion
        existing_suggestion = CategorySuggestion.objects.create(
            connection=self.connection,
            detection_rule=rule,
            xero_transaction_id='txn-123',
            suggested_category=self.office_category,
            transaction_description='Office Depot - Pens and Paper',
            status='PENDING'
        )
        
        transactions = [self.sample_transaction]
        suggestions = self.engine.run_detection(transactions)
        
        # Should return empty list since suggestion already exists
        self.assertEqual(len(suggestions), 0)

    def test_invalid_operator_raises_error(self):
        """Test that invalid operators raise appropriate errors"""
        condition = {
            'field': 'description',
            'operator': 'INVALID_OPERATOR',
            'value': 'test'
        }
        
        with self.assertRaises(ValueError):
            self.engine.evaluate_condition(self.sample_transaction, condition)

    def test_invalid_regex_pattern_handles_gracefully(self):
        """Test that invalid regex patterns are handled gracefully"""
        condition = {
            'field': 'description',
            'operator': 'REGEX',
            'value': '[invalid regex pattern'  # Missing closing bracket
        }
        
        # Should return False rather than raising an exception
        result = self.engine.evaluate_condition(self.sample_transaction, condition)
        self.assertFalse(result)

    def test_numeric_comparison_with_string_field(self):
        """Test numeric comparison operators handle string fields gracefully"""
        condition = {
            'field': 'description',  # String field
            'operator': 'GREATER_THAN',
            'value': 100
        }
        
        # Should return False rather than raising an exception
        result = self.engine.evaluate_condition(self.sample_transaction, condition)
        self.assertFalse(result)

    def test_engine_performance_with_many_rules(self):
        """Test engine performance with many rules (basic performance test)"""
        # Create 50 rules with different priorities
        for i in range(50):
            CategoryDetectionRule.objects.create(
                connection=self.connection,
                name=f'Rule {i}',
                suggested_category=self.office_category,
                conditions=[
                    {
                        'field': 'description',
                        'operator': 'CONTAINS',
                        'value': f'pattern{i}'
                    }
                ],
                priority=i
            )
        
        # Create one matching rule
        matching_rule = CategoryDetectionRule.objects.create(
            connection=self.connection,
            name='Matching Rule',
            suggested_category=self.office_category,
            conditions=[
                {
                    'field': 'description',
                    'operator': 'CONTAINS',
                    'value': 'office'
                }
            ],
            priority=100
        )
        
        transactions = [self.sample_transaction]
        
        # This should complete quickly and return the matching suggestion
        suggestions = self.engine.run_detection(transactions)
        
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0].detection_rule, matching_rule)