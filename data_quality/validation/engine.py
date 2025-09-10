"""
Validation engine for running validation rules.
"""

from typing import List, Dict, Any, Optional
from django.utils import timezone
from .registry import ValidationRuleRegistry
from .base import BaseValidationRule, ValidationResult, ValidationSeverity
from connections.models import Connection
from ..models import ValidationRun, Issue
import logging

logger = logging.getLogger(__name__)


class ValidationEngine:
    """
    Engine for executing validation rules against connection data.
    """
    
    @classmethod
    def run_validation(cls, connection: Connection, 
                      rule_names: Optional[List[str]] = None,
                      triggered_by: str = 'manual') -> ValidationRun:
        """
        Run validation rules for a connection.
        
        Args:
            connection: Connection to validate
            rule_names: Optional list of specific rule names to run. If None, runs all enabled rules.
            triggered_by: What triggered this validation run
            
        Returns:
            ValidationRun: The validation run record
        """
        logger.info(f"Starting validation run for connection {connection.prefix_id} ({connection.organization_name})")
        
        # Create validation run record
        validation_run = ValidationRun.objects.create(
            connection=connection,
            status='running',
            triggered_by=triggered_by,
            metadata={
                'requested_rules': rule_names,
                'connection_name': connection.organization_name
            }
        )
        
        try:
            # Get rules to run
            if rule_names:
                # Run specific rules
                rules = []
                for rule_name in rule_names:
                    try:
                        rule = ValidationRuleRegistry.get_rule(rule_name)
                        if rule.is_enabled_for_connection(connection):
                            # Get connection-specific config
                            config = rule.get_config_for_connection(connection)
                            rule = ValidationRuleRegistry.get_rule(rule_name, config)
                            rules.append(rule)
                    except Exception as e:
                        logger.error(f"Failed to load rule {rule_name}: {e}")
            else:
                # Run all enabled rules
                rules = ValidationRuleRegistry.get_enabled_rules_for_connection(connection)
            
            validation_run.total_rules = len(rules)
            validation_run.save()
            
            logger.info(f"Running {len(rules)} validation rules")
            
            # Execute rules
            results = []
            for rule in rules:
                try:
                    logger.debug(f"Executing rule: {rule.name}")
                    result = rule.validate(connection)
                    results.append(result)
                    
                    if result.passed:
                        validation_run.rules_passed += 1
                    else:
                        validation_run.rules_failed += 1
                        validation_run.issues_found += 1
                        
                        # Create Issue record if validation failed
                        cls._create_issue_from_result(connection, result)
                        
                except Exception as e:
                    logger.error(f"Error executing rule {rule.name}: {e}", exc_info=True)
                    validation_run.rules_failed += 1
                    
                    # Create a failure result
                    error_result = ValidationResult.create_issue(
                        rule_name=rule.name,
                        severity=rule.severity,
                        title=f"Rule execution failed: {rule.name}",
                        description=f"An error occurred while executing the rule: {str(e)}",
                        metadata={'error': str(e)}
                    )
                    results.append(error_result)
            
            # Update validation run with results
            validation_run.mark_completed()
            validation_run.metadata.update({
                'results_summary': cls._create_results_summary(results)
            })
            validation_run.save()
            
            logger.info(f"Validation run completed. Rules passed: {validation_run.rules_passed}, "
                       f"Rules failed: {validation_run.rules_failed}, Issues found: {validation_run.issues_found}")
            
        except Exception as e:
            logger.error(f"Validation run failed: {e}", exc_info=True)
            validation_run.mark_failed(str(e))
        
        return validation_run
    
    @classmethod
    def _create_issue_from_result(cls, connection: Connection, result: ValidationResult) -> Issue:
        """
        Create or update an Issue record from a ValidationResult using the new aggregation system.
        
        Args:
            connection: Connection the issue relates to
            result: ValidationResult containing issue details
            
        Returns:
            Issue: Created or updated issue record
        """
        # Use the new IssueManager for proper aggregation with account + chart scoping
        return Issue.objects.create_or_update_issue(connection, result)
    
    @classmethod
    def _create_results_summary(cls, results: List[ValidationResult]) -> Dict[str, Any]:
        """
        Create a summary of validation results.
        
        Args:
            results: List of ValidationResults
            
        Returns:
            Dict: Summary information
        """
        summary = {
            'total_rules': len(results),
            'rules_passed': sum(1 for r in results if r.passed),
            'rules_failed': sum(1 for r in results if not r.passed),
            'by_severity': {},
            'rule_results': {}
        }
        
        # Count by severity
        for result in results:
            if not result.passed and result.severity:
                severity = result.severity.value
                summary['by_severity'][severity] = summary['by_severity'].get(severity, 0) + 1
        
        # Store individual rule results
        for result in results:
            summary['rule_results'][result.rule_name] = {
                'passed': result.passed,
                'severity': result.severity.value if result.severity else None,
                'title': result.title,
                'executed_at': result.executed_at.isoformat() if result.executed_at else None
            }
        
        return summary
    
    @classmethod
    def get_available_rules(cls) -> List[Dict[str, Any]]:
        """
        Get information about all available validation rules.
        
        Returns:
            List[Dict]: List of rule information dictionaries
        """
        rules_info = []
        for rule_name in ValidationRuleRegistry.get_rule_names():
            rule_info = ValidationRuleRegistry.get_rule_info(rule_name)
            if rule_info:
                rules_info.append(rule_info)
        return rules_info
    
    @classmethod
    def run_single_rule(cls, connection: Connection, rule_name: str) -> ValidationResult:
        """
        Run a single validation rule for an connection.
        
        Args:
            connection: Connection to validate
            rule_name: Name of the rule to run
            
        Returns:
            ValidationResult: Result of the validation rule
        """
        try:
            # Get the rule with connection-specific config
            rule = ValidationRuleRegistry.get_rule(rule_name)
            config = rule.get_config_for_connection(connection)
            rule = ValidationRuleRegistry.get_rule(rule_name, config)
            
            # Execute the rule
            result = rule.validate(connection)
            
            # Create issue if rule failed
            if not result.passed:
                cls._create_issue_from_result(connection, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error running single rule {rule_name}: {e}", exc_info=True)
            return ValidationResult.create_issue(
                rule_name=rule_name,
                severity=ValidationSeverity.CRITICAL,
                title=f"Rule execution failed: {rule_name}",
                description=f"An error occurred while executing the rule: {str(e)}",
                metadata={'error': str(e)}
            )