"""
Custom exceptions for the validation framework.
"""


class ValidationError(Exception):
    """Base exception for validation errors."""
    pass


class RuleConfigurationError(ValidationError):
    """Raised when a validation rule is misconfigured."""
    pass


class RuleNotFoundError(ValidationError):
    """Raised when trying to access a validation rule that doesn't exist."""
    pass


class ValidationExecutionError(ValidationError):
    """Raised when a validation rule fails to execute properly."""
    pass