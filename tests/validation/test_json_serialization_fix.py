"""
Focused test to reproduce and fix JSON serialization issue.

The issue: ValidationResult.affected_transactions contains Decimal types that aren't JSON serializable.
"""

from decimal import Decimal
import json

from integrations.validation.base import ValidationResult, ValidationSeverity
from .base_validation_test import BaseValidationTestCase


class JSONSerializationFixTestCase(BaseValidationTestCase):
    
    def test_validation_result_with_decimal_fails_json_serialization(self):
        """Test that ValidationResult with Decimal data fails JSON serialization"""
        
        # Create a ValidationResult similar to what DuplicateTransactionRule produces
        # but with problematic Decimal types
        problematic_transactions = [
            {
                'count': 2,
                'matching_fields': {'amount': Decimal('100.50'), 'reference': 'REF001'},
                'transactions': [
                    {
                        'id': 1,
                        'amount': Decimal('100.50'),  # This Decimal type causes the issue
                        'date': '2024-01-01',
                        'reference': 'REF001'
                    },
                    {
                        'id': 2, 
                        'amount': Decimal('100.50'),  # This Decimal type causes the issue
                        'date': '2024-01-01',
                        'reference': 'REF001'
                    }
                ],
                'total_amount': Decimal('201.00')  # This Decimal type causes the issue
            }
        ]
        
        validation_result = ValidationResult.create_issue(
            rule_name='duplicate_transactions',
            severity=ValidationSeverity.HIGH,
            title='Test duplicates',
            description='Test description',
            affected_transactions=problematic_transactions
        )
        
        # This should fail with JSON serialization error
        with self.assertRaises(TypeError) as context:
            json.dumps(validation_result.affected_transactions)
        
        # Verify it's specifically about Decimal not being serializable
        error_msg = str(context.exception)
        self.assertIn('Decimal', error_msg)
        self.assertIn('not JSON serializable', error_msg)
    
    def test_after_fix_validation_result_serializes_properly(self):
        """After implementing fix, this should pass"""
        
        # Same problematic data as above
        problematic_transactions = [
            {
                'count': 2,
                'matching_fields': {'amount': Decimal('100.50'), 'reference': 'REF001'},
                'transactions': [
                    {'id': 1, 'amount': Decimal('100.50'), 'date': '2024-01-01'},
                    {'id': 2, 'amount': Decimal('100.50'), 'date': '2024-01-01'}
                ],
                'total_amount': Decimal('201.00')
            }
        ]
        
        validation_result = ValidationResult.create_issue(
            rule_name='duplicate_transactions',
            severity=ValidationSeverity.HIGH,
            title='Test duplicates',
            description='Test description',
            affected_transactions=problematic_transactions
        )
        
        # After fix, this should work
        # (Will fail initially, should pass after we implement the fix)
        from integrations.models import IssueManager
        
        # This should use our serialization fix
        serialized_data = IssueManager()._serialize_affected_transactions(
            validation_result.affected_transactions
        )
        
        # Should be JSON serializable now
        json_str = json.dumps(serialized_data)
        self.assertIsInstance(json_str, str)
        
        # Should contain the same essential data but with serializable types
        self.assertEqual(len(serialized_data), 1)
        self.assertEqual(serialized_data[0]['count'], 2)
        # Decimals should be converted to floats
        self.assertEqual(serialized_data[0]['total_amount'], 201.0)
        self.assertEqual(serialized_data[0]['transactions'][0]['amount'], 100.5)