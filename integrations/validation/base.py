"""
Base classes for validation rules.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from django.utils import timezone


class ValidationSeverity(Enum):
    """Severity levels for validation results."""
    CRITICAL = "critical"
    HIGH = "high" 
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ValidationResult:
    """Result of a validation rule execution."""
    rule_name: str
    passed: bool
    severity: Optional[ValidationSeverity] = None
    title: Optional[str] = None
    description: Optional[str] = None
    affected_transactions: List[Dict[str, Any]] = None
    metadata: Dict[str, Any] = None
    executed_at: timezone.datetime = None
    
    def __post_init__(self):
        if self.affected_transactions is None:
            self.affected_transactions = []
        if self.metadata is None:
            self.metadata = {}
        if self.executed_at is None:
            self.executed_at = timezone.now()
    
    @classmethod
    def success(cls, rule_name: str, metadata: Dict[str, Any] = None) -> 'ValidationResult':
        """Create a successful validation result."""
        return cls(
            rule_name=rule_name,
            passed=True,
            metadata=metadata or {}
        )
    
    @classmethod
    def create_issue(cls, rule_name: str, severity: ValidationSeverity, title: str,
                    description: str = None, affected_transactions: List[Dict[str, Any]] = None,
                    metadata: Dict[str, Any] = None) -> 'ValidationResult':
        """Create a validation result that represents an issue."""
        return cls(
            rule_name=rule_name,
            passed=False,
            severity=severity,
            title=title,
            description=description or title,
            affected_transactions=affected_transactions or [],
            metadata=metadata or {}
        )


class BaseValidationRule(ABC):
    """
    Abstract base class for all validation rules.
    
    Each validation rule should inherit from this class and implement the validate method.
    """
    
    # Must be overridden in subclasses
    name: str = None
    description: str = None
    default_severity: ValidationSeverity = ValidationSeverity.MEDIUM
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the validation rule with optional configuration.
        
        Args:
            config: Rule-specific configuration dictionary
        """
        if self.name is None:
            raise NotImplementedError("Validation rule must define a 'name' attribute")
        if self.description is None:
            raise NotImplementedError("Validation rule must define a 'description' attribute")
        
        self.config = config or {}
        self.severity = self._get_severity()
    
    def _get_severity(self) -> ValidationSeverity:
        """Get the severity level for this rule, allowing config override."""
        severity_str = self.config.get('severity')
        if severity_str:
            try:
                return ValidationSeverity(severity_str.lower())
            except ValueError:
                # Fall back to default if invalid severity in config
                pass
        return self.default_severity
    
    @abstractmethod
    def validate(self, integration) -> ValidationResult:
        """
        Run the validation rule against an integration's transaction data.
        
        Args:
            integration: The Integration instance to validate
            
        Returns:
            ValidationResult: Result of the validation
        """
        pass
    
    def get_display_name(self) -> str:
        """Get a human-readable display name for this rule."""
        return self.description
    
    def is_enabled_for_integration(self, integration) -> bool:
        """
        Check if this rule is enabled for a specific integration.
        
        Args:
            integration: The Integration instance
            
        Returns:
            bool: True if rule should run for this integration
        """
        from ..models import ValidationRuleConfig
        
        try:
            rule_config = ValidationRuleConfig.objects.get(
                integration=integration,
                rule_name=self.name
            )
            return rule_config.is_enabled
        except ValidationRuleConfig.DoesNotExist:
            # Default to enabled if no config exists
            return True
    
    def get_config_for_integration(self, integration) -> Dict[str, Any]:
        """
        Get the configuration for this rule for a specific integration.
        
        Args:
            integration: The Integration instance
            
        Returns:
            Dict: Combined default and integration-specific config
        """
        from ..models import ValidationRuleConfig
        
        # Start with rule's default config
        combined_config = self.config.copy()
        
        try:
            rule_config = ValidationRuleConfig.objects.get(
                integration=integration,
                rule_name=self.name
            )
            # Override with integration-specific config
            combined_config.update(rule_config.config)
            
            # Override severity if specified
            if rule_config.severity_override:
                combined_config['severity'] = rule_config.severity_override
                
        except ValidationRuleConfig.DoesNotExist:
            # Use default config only
            pass
        
        return combined_config
    
    def __str__(self):
        return f"{self.name}: {self.description}"
    
    def __repr__(self):
        return f"<{self.__class__.__name__}(name='{self.name}', severity='{self.default_severity.value}')>"