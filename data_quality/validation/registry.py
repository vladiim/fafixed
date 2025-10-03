"""
Registry for validation rules.
"""

from typing import Dict, List, Type, Optional
import importlib
import pkgutil
from .base import BaseValidationRule
from .exceptions import RuleNotFoundError, RuleConfigurationError
import logging

logger = logging.getLogger(__name__)


class ValidationRuleRegistry:
    """
    Registry for managing validation rules.
    
    Provides rule discovery, registration, and instantiation functionality.
    """
    
    _rules: Dict[str, Type[BaseValidationRule]] = {}
    _initialized = False
    
    @classmethod
    def register(cls, rule_class: Type[BaseValidationRule]) -> None:
        """
        Register a validation rule class.
        
        Args:
            rule_class: The validation rule class to register
        """
        if not issubclass(rule_class, BaseValidationRule):
            raise RuleConfigurationError(f"{rule_class.__name__} must inherit from BaseValidationRule")
        
        if not rule_class.name:
            raise RuleConfigurationError(f"{rule_class.__name__} must define a 'name' attribute")
        
        cls._rules[rule_class.name] = rule_class
        logger.info(f"Registered validation rule: {rule_class.name}")
    
    @classmethod
    def get_rule(cls, rule_name: str, config: Dict = None) -> BaseValidationRule:
        """
        Get an instance of a validation rule by name.
        
        Args:
            rule_name: Name of the rule to instantiate
            config: Optional configuration for the rule
            
        Returns:
            BaseValidationRule: Instance of the requested rule
            
        Raises:
            RuleNotFoundError: If the rule is not registered
        """
        cls._ensure_rules_loaded()
        
        if rule_name not in cls._rules:
            raise RuleNotFoundError(f"Validation rule '{rule_name}' not found")
        
        rule_class = cls._rules[rule_name]
        return rule_class(config=config)
    
    @classmethod
    def get_all_rules(cls) -> Dict[str, Type[BaseValidationRule]]:
        """
        Get all registered validation rules.
        
        Returns:
            Dict: Dictionary mapping rule names to rule classes
        """
        cls._ensure_rules_loaded()
        return cls._rules.copy()
    
    @classmethod
    def get_rule_names(cls) -> List[str]:
        """
        Get names of all registered validation rules.
        
        Returns:
            List[str]: List of rule names
        """
        cls._ensure_rules_loaded()
        return list(cls._rules.keys())
    
    @classmethod
    def is_registered(cls, rule_name: str) -> bool:
        """
        Check if a validation rule is registered.
        
        Args:
            rule_name: Name of the rule to check
            
        Returns:
            bool: True if rule is registered
        """
        cls._ensure_rules_loaded()
        return rule_name in cls._rules
    
    @classmethod
    def get_enabled_rules_for_connection(cls, connection) -> List[BaseValidationRule]:
        """
        Get all enabled validation rules for a specific connection.
        
        Args:
            connection: Connection instance
            
        Returns:
            List[BaseValidationRule]: List of enabled rule instances
        """
        cls._ensure_rules_loaded()
        
        enabled_rules = []
        for rule_name, rule_class in cls._rules.items():
            # Create instance with default config to check if enabled
            rule_instance = rule_class()
            
            if rule_instance.is_enabled_for_connection(connection):
                # Get connection-specific config
                config = rule_instance.get_config_for_connection(connection)
                # Create new instance with proper config
                enabled_rule = rule_class(config=config)
                enabled_rules.append(enabled_rule)
        
        return enabled_rules
    
    @classmethod
    def _ensure_rules_loaded(cls) -> None:
        """Ensure all validation rules are loaded and registered."""
        if not cls._initialized:
            cls._discover_and_load_rules()
            cls._initialized = True
    
    @classmethod
    def _discover_and_load_rules(cls) -> None:
        """
        Automatically discover and load validation rules from the rules package.
        """
        try:
            # Directly iterate over rule modules without importing the package first
            import os
            import sys

            rules_dir = os.path.join(os.path.dirname(__file__), 'rules')
            if os.path.exists(rules_dir):
                for filename in os.listdir(rules_dir):
                    if filename.endswith('.py') and not filename.startswith('__'):
                        module_name = filename[:-3]
                        try:
                            importlib.import_module(f'data_quality.validation.rules.{module_name}')
                            logger.debug(f"Loaded validation rule module: {module_name}")
                        except ImportError as e:
                            logger.error(f"Failed to import validation rule {module_name}: {e}")
        except Exception as e:
            logger.error(f"Error during rule discovery: {e}")
    
    @classmethod
    def clear_registry(cls) -> None:
        """Clear all registered rules. Mainly for testing."""
        cls._rules.clear()
        cls._initialized = False
    
    @classmethod
    def get_rule_info(cls, rule_name: str) -> Optional[Dict]:
        """
        Get information about a validation rule without instantiating it.
        
        Args:
            rule_name: Name of the rule
            
        Returns:
            Dict: Rule information or None if not found
        """
        cls._ensure_rules_loaded()
        
        if rule_name not in cls._rules:
            return None
        
        rule_class = cls._rules[rule_name]
        return {
            'name': rule_class.name,
            'description': rule_class.description,
            'default_severity': rule_class.default_severity.value,
            'class_name': rule_class.__name__
        }