"""
Validation framework for transaction data quality checks.

This module provides a framework for implementing and running validation rules
against transaction data from integrated accounting systems.
"""

from .registry import ValidationRuleRegistry
from .base import BaseValidationRule, ValidationResult, ValidationSeverity
from .exceptions import ValidationError, RuleConfigurationError
from .engine import ValidationEngine

# Auto-register validation rules
ValidationRuleRegistry._discover_and_load_rules()

__all__ = [
    'ValidationRuleRegistry',
    'BaseValidationRule', 
    'ValidationResult',
    'ValidationSeverity',
    'ValidationError',
    'RuleConfigurationError',
    'ValidationEngine'
]