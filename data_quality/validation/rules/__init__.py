"""
Validation rules package.

This package contains all the individual validation rule implementations.
Each rule file should import and register its rules with the ValidationRuleRegistry.
"""

# Import all rule modules to ensure they get registered
from . import duplicates

__all__ = ['duplicates']