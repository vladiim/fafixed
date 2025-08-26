"""
Validation framework for transaction data quality checks.

This module provides a framework for implementing and running validation rules
against transaction data from integrated accounting systems.
"""

from .registry import ValidationRuleRegistry
from .base import BaseValidationRule, ValidationResult, ValidationSeverity
from .exceptions import ValidationError, RuleConfigurationError

__all__ = [
    'ValidationRuleRegistry',
    'BaseValidationRule', 
    'ValidationResult',
    'ValidationSeverity',
    'ValidationError',
    'RuleConfigurationError'
]