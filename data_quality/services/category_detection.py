"""
Category Detection Engine for evaluating detection rules against transactions.
"""
import logging
import re
from typing import Dict, Any, List, Union
from decimal import Decimal

from data_quality.models import (
    CategoryDetectionRule, 
    CategorySuggestion,
    ConditionOperator
)

logger = logging.getLogger(__name__)


class CategoryDetectionEngine:
    """Engine for evaluating category detection rules against transactions"""
    
    def __init__(self, connection):
        """
        Initialize detection engine for a specific connection.
        
        Args:
            connection: Connection instance for rule evaluation
        """
        self.connection = connection
    
    def run_detection(self, transactions: List[Dict[str, Any]]) -> List[CategorySuggestion]:
        """
        Run detection rules against a list of transactions.
        
        Args:
            transactions: List of transaction dictionaries
            
        Returns:
            List of CategorySuggestion objects created
        """
        logger.info(f"Running category detection for {len(transactions)} transactions")
        
        # Get all active detection rules ordered by priority
        rules = CategoryDetectionRule.objects.filter(
            connection=self.connection,
            is_active=True
        ).order_by('-priority', 'name')
        
        if not rules.exists():
            logger.debug("No active detection rules found for connection")
            return []
        
        suggestions = []
        
        for transaction in transactions:
            transaction_id = transaction.get('id')
            if not transaction_id:
                logger.warning("Transaction missing ID, skipping")
                continue
            
            # Skip if we already have a suggestion for this transaction
            if self._has_existing_suggestion(transaction_id):
                logger.debug(f"Skipping transaction {transaction_id} - suggestion already exists")
                continue
            
            # Evaluate rules in priority order (first match wins)
            for rule in rules:
                if self.evaluate_rule(transaction, rule):
                    suggestion = self.create_suggestion(transaction, rule)
                    if suggestion:
                        suggestions.append(suggestion)
                        logger.debug(f"Created suggestion for transaction {transaction_id} using rule {rule.name}")
                    break  # First match wins
        
        logger.info(f"Created {len(suggestions)} new category suggestions")
        return suggestions
    
    def evaluate_rule(self, transaction: Dict[str, Any], rule: CategoryDetectionRule) -> bool:
        """
        Evaluate whether a transaction matches a detection rule.
        
        Args:
            transaction: Transaction data dictionary
            rule: CategoryDetectionRule to evaluate
            
        Returns:
            True if transaction matches rule conditions
        """
        if not rule.is_active:
            return False
        
        conditions = rule.conditions
        if not conditions:
            return False
        
        # Evaluate based on condition logic
        if rule.condition_logic == 'ALL':
            # All conditions must match
            return all(
                self.evaluate_condition(transaction, condition)
                for condition in conditions
            )
        elif rule.condition_logic == 'ANY':
            # Any condition can match
            return any(
                self.evaluate_condition(transaction, condition)
                for condition in conditions
            )
        else:
            logger.warning(f"Unknown condition logic: {rule.condition_logic}")
            return False
    
    def evaluate_condition(self, transaction: Dict[str, Any], condition: Dict[str, Any]) -> bool:
        """
        Evaluate a single condition against a transaction.
        
        Args:
            transaction: Transaction data dictionary
            condition: Condition dictionary with field, operator, value
            
        Returns:
            True if condition matches
        """
        field = condition.get('field')
        operator = condition.get('operator')
        expected_value = condition.get('value')
        
        if not all([field, operator]):
            logger.warning(f"Invalid condition: missing field or operator")
            return False
        
        # Get actual value from transaction
        actual_value = transaction.get(field)
        
        # Handle missing or None values
        if actual_value is None:
            return False
        
        try:
            return self._evaluate_operator(actual_value, operator, expected_value)
        except ValueError:
            # Re-raise ValueError for invalid operators
            raise
        except Exception as e:
            logger.warning(f"Error evaluating condition {condition}: {e}")
            return False
    
    def _evaluate_operator(self, actual_value: Any, operator: str, expected_value: Any) -> bool:
        """
        Evaluate a specific operator condition.
        
        Args:
            actual_value: Actual value from transaction
            operator: Operator string (e.g., 'CONTAINS', 'EQUALS')
            expected_value: Expected value to compare against
            
        Returns:
            True if operator condition matches
        """
        # Convert to strings for most string operations (case insensitive)
        if operator in ['EQUALS', 'NOT_EQUALS', 'CONTAINS', 'NOT_CONTAINS', 'STARTS_WITH', 'ENDS_WITH']:
            actual_str = str(actual_value).lower()
            expected_str = str(expected_value).lower()
        
        if operator == ConditionOperator.EQUALS:
            return actual_str == expected_str
        
        elif operator == ConditionOperator.NOT_EQUALS:
            return actual_str != expected_str
        
        elif operator == ConditionOperator.CONTAINS:
            return expected_str in actual_str
        
        elif operator == ConditionOperator.NOT_CONTAINS:
            return expected_str not in actual_str
        
        elif operator == ConditionOperator.STARTS_WITH:
            return actual_str.startswith(expected_str)
        
        elif operator == ConditionOperator.ENDS_WITH:
            return actual_str.endswith(expected_str)
        
        elif operator == ConditionOperator.REGEX:
            try:
                pattern = str(expected_value)
                return bool(re.search(pattern, str(actual_value), re.IGNORECASE))
            except re.error:
                logger.warning(f"Invalid regex pattern: {expected_value}")
                return False
        
        elif operator == ConditionOperator.GREATER_THAN:
            try:
                actual_num = self._convert_to_number(actual_value)
                expected_num = self._convert_to_number(expected_value)
                if actual_num is not None and expected_num is not None:
                    return actual_num > expected_num
                return False
            except (ValueError, TypeError):
                return False
        
        elif operator == ConditionOperator.LESS_THAN:
            try:
                actual_num = self._convert_to_number(actual_value)
                expected_num = self._convert_to_number(expected_value)
                if actual_num is not None and expected_num is not None:
                    return actual_num < expected_num
                return False
            except (ValueError, TypeError):
                return False
        
        elif operator == ConditionOperator.GREATER_THAN_OR_EQUAL:
            try:
                actual_num = self._convert_to_number(actual_value)
                expected_num = self._convert_to_number(expected_value)
                if actual_num is not None and expected_num is not None:
                    return actual_num >= expected_num
                return False
            except (ValueError, TypeError):
                return False
        
        elif operator == ConditionOperator.LESS_THAN_OR_EQUAL:
            try:
                actual_num = self._convert_to_number(actual_value)
                expected_num = self._convert_to_number(expected_value)
                if actual_num is not None and expected_num is not None:
                    return actual_num <= expected_num
                return False
            except (ValueError, TypeError):
                return False
        
        else:
            raise ValueError(f"Unsupported operator: {operator}")
    
    def _convert_to_number(self, value: Any) -> Union[Decimal, None]:
        """
        Convert value to Decimal for numeric comparisons.
        
        Args:
            value: Value to convert
            
        Returns:
            Decimal value or None if conversion fails
        """
        if value is None:
            return None
        
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        
        if isinstance(value, Decimal):
            return value
        
        if isinstance(value, str):
            try:
                return Decimal(value)
            except:
                return None
        
        return None
    
    def create_suggestion(self, transaction: Dict[str, Any], rule: CategoryDetectionRule) -> CategorySuggestion:
        """
        Create a CategorySuggestion for a transaction that matches a rule.
        
        Args:
            transaction: Transaction data dictionary
            rule: Matching CategoryDetectionRule
            
        Returns:
            CategorySuggestion object (created or existing)
        """
        transaction_id = transaction.get('id')
        if not transaction_id:
            logger.warning("Cannot create suggestion: transaction missing ID")
            return None
        
        # Check for existing suggestion and return it if found
        existing_suggestion = CategorySuggestion.objects.filter(
            detection_rule=rule,
            xero_transaction_id=transaction_id
        ).first()
        
        if existing_suggestion:
            return existing_suggestion
        
        # Create new suggestion
        suggestion = CategorySuggestion.objects.create(
            connection=self.connection,
            detection_rule=rule,
            xero_transaction_id=transaction_id,
            suggested_category=rule.suggested_category,
            transaction_description=transaction.get('description'),
            transaction_contact=transaction.get('contact_name'),
            transaction_amount=self._convert_to_decimal(transaction.get('amount')),
            status='PENDING'
        )
        
        logger.debug(f"Created suggestion {suggestion.id} for transaction {transaction_id}")
        return suggestion
    
    def _convert_to_decimal(self, value: Any) -> Union[Decimal, None]:
        """
        Convert value to Decimal for amount field.
        
        Args:
            value: Value to convert
            
        Returns:
            Decimal value or None if conversion fails
        """
        if value is None:
            return None
        
        if isinstance(value, Decimal):
            return value
        
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        
        if isinstance(value, str):
            try:
                return Decimal(value)
            except:
                return None
        
        return None
    
    def _has_existing_suggestion(self, transaction_id: str) -> bool:
        """
        Check if a suggestion already exists for a transaction.
        
        Args:
            transaction_id: Transaction ID to check
            
        Returns:
            True if suggestion exists
        """
        return CategorySuggestion.objects.filter(
            connection=self.connection,
            xero_transaction_id=transaction_id
        ).exists()