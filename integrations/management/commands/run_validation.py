"""
Management command to run validation rules on integrations.
"""

from django.core.management.base import BaseCommand, CommandError
from integrations.models import Integration
from integrations.validation.engine import ValidationEngine
from integrations.validation.registry import ValidationRuleRegistry


class Command(BaseCommand):
    help = 'Run validation rules on integrations'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--integration-id',
            type=int,
            help='Integration ID to validate (optional - validates all active if not specified)'
        )
        parser.add_argument(
            '--rule',
            type=str,
            action='append',
            help='Specific rule name to run (can be used multiple times)'
        )
        parser.add_argument(
            '--list-rules',
            action='store_true',
            help='List all available validation rules'
        )
    
    def handle(self, *args, **options):
        if options['list_rules']:
            self.list_available_rules()
            return
        
        # Get integrations to validate
        if options['integration_id']:
            try:
                integrations = [Integration.objects.get(
                    id=options['integration_id'],
                    status='active'
                )]
            except Integration.DoesNotExist:
                raise CommandError(f"Integration with ID {options['integration_id']} not found or not active")
        else:
            integrations = Integration.objects.filter(status='active')
            
        if not integrations:
            self.stdout.write(
                self.style.WARNING('No active integrations found to validate')
            )
            return
        
        # Get rules to run
        rule_names = options.get('rule', [])
        if rule_names:
            # Validate that all requested rules exist
            available_rules = ValidationRuleRegistry.get_rule_names()
            invalid_rules = set(rule_names) - set(available_rules)
            if invalid_rules:
                raise CommandError(f"Unknown validation rules: {', '.join(invalid_rules)}")
        
        # Run validation on each integration
        total_runs = 0
        total_issues = 0
        
        for integration in integrations:
            self.stdout.write(f"\nValidating integration: {integration.organization_name} (ID: {integration.id})")
            
            try:
                validation_run = ValidationEngine.run_validation(
                    integration=integration,
                    rule_names=rule_names if rule_names else None,
                    triggered_by='management_command'
                )
                
                total_runs += 1
                total_issues += validation_run.issues_found
                
                # Display results
                if validation_run.status == 'completed':
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  ✓ Validation completed: {validation_run.rules_passed} passed, "
                            f"{validation_run.rules_failed} failed, {validation_run.issues_found} issues found"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f"  ✗ Validation failed: {validation_run.error_message}"
                        )
                    )
                
                # Show individual rule results if available
                if 'rule_results' in validation_run.metadata:
                    for rule_name, result in validation_run.metadata['rule_results'].items():
                        status = "✓" if result['passed'] else "✗"
                        severity = f" ({result['severity']})" if result.get('severity') else ""
                        title = f" - {result['title']}" if result.get('title') else ""
                        self.stdout.write(f"    {status} {rule_name}{severity}{title}")
                        
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  ✗ Error running validation: {str(e)}")
                )
        
        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f"\nValidation Summary: {total_runs} integrations validated, "
                f"{total_issues} total issues found"
            )
        )
    
    def list_available_rules(self):
        """List all available validation rules."""
        self.stdout.write(self.style.SUCCESS("Available Validation Rules:"))
        self.stdout.write("-" * 50)
        
        rules = ValidationEngine.get_available_rules()
        if not rules:
            self.stdout.write(self.style.WARNING("No validation rules found"))
            return
        
        for rule_info in rules:
            self.stdout.write(
                f"{rule_info['name']} ({rule_info['default_severity']})"
            )
            self.stdout.write(f"  Description: {rule_info['description']}")
            self.stdout.write("")