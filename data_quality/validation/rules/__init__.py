"""
Validation rules package.

This package contains all the individual validation rule implementations.
Each rule file should import and register its rules with the ValidationRuleRegistry.
"""

# Don't import here to avoid circular imports
# The registry will discover and import rules dynamically
__all__ = ['duplicates']