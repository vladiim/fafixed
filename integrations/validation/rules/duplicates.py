"""
Duplicate transaction detection validation rule.
"""

from typing import Dict, Any, List
from django.db.models import Count, Q
from ..base import BaseValidationRule, ValidationResult, ValidationSeverity
from ..registry import ValidationRuleRegistry
from ...models import TransactionData
import logging

logger = logging.getLogger(__name__)


class DuplicateTransactionRule(BaseValidationRule):
    """
    Detects duplicate transactions based on configurable matching criteria.
    
    This rule identifies transactions that appear to be duplicates by comparing
    key transaction attributes like amount, date, reference, and contact.
    """
    
    name = "duplicate_transactions"
    description = "Detects duplicate transactions based on matching criteria"
    default_severity = ValidationSeverity.HIGH
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        
        # Default matching criteria - can be overridden in config
        default_config = {
            'match_fields': ['amount', 'date', 'reference'],  # Fields to match on
            'ignore_empty_reference': True,  # Don't match on empty/null references
            'ignore_pending_status': True,  # Ignore transactions with 'pending' status
            'minimum_duplicates': 2,  # Minimum number of matching transactions to flag
            'date_tolerance_days': 0,  # Allow date differences within N days
        }
        
        # Merge default config with provided config
        for key, value in default_config.items():
            if key not in self.config:
                self.config[key] = value
    
    def validate(self, integration) -> ValidationResult:
        """
        Find duplicate transactions for the given integration.
        
        Args:
            integration: Integration instance to validate
            
        Returns:
            ValidationResult: Result containing any duplicate issues found
        """
        try:
            integration_id = integration.id if integration else 'None'
            logger.info(f"Running duplicate transaction validation for integration {integration_id}")
            
            if not integration:
                raise ValueError("Integration cannot be None")
            
            # Get base queryset of transactions for this integration
            queryset = TransactionData.objects.filter(integration=integration)
            
            # Apply status filtering if configured
            if self.config.get('ignore_pending_status', True):
                queryset = queryset.exclude(status='pending')
            
            # Build the matching criteria based on configured fields
            match_fields = self.config.get('match_fields', ['amount', 'date', 'reference'])
            duplicates_data = self._find_duplicates_by_fields(queryset, match_fields)
            
            if not duplicates_data:
                logger.info(f"No duplicate transactions found for integration {integration.id}")
                return ValidationResult.success(
                    rule_name=self.name,
                    metadata={
                        'total_transactions_checked': queryset.count(),
                        'match_fields': match_fields,
                        'duplicates_found': 0
                    }
                )
            
            # Process and format the duplicate data
            duplicate_groups = self._process_duplicate_groups(duplicates_data, integration)
            total_duplicates = sum(group['count'] for group in duplicate_groups)
            
            logger.warning(f"Found {len(duplicate_groups)} duplicate groups affecting {total_duplicates} transactions")
            
            # Create validation result with issue details
            return ValidationResult.create_issue(
                rule_name=self.name,
                severity=self.severity,
                title=f"Found {len(duplicate_groups)} duplicate transaction groups",
                description=f"Detected {total_duplicates} transactions across {len(duplicate_groups)} duplicate groups. "
                           f"Matching criteria: {', '.join(match_fields)}",
                affected_transactions=duplicate_groups,
                metadata={
                    'total_transactions_checked': queryset.count(),
                    'match_fields': match_fields,
                    'duplicate_groups': len(duplicate_groups),
                    'total_duplicates': total_duplicates,
                    'config': self.config
                }
            )
            
        except Exception as e:
            logger.error(f"Error during duplicate transaction validation: {e}", exc_info=True)
            return ValidationResult.create_issue(
                rule_name=self.name,
                severity=ValidationSeverity.CRITICAL,
                title="Duplicate detection validation failed",
                description=f"An error occurred during duplicate transaction detection: {str(e)}",
                metadata={'error': str(e)}
            )
    
    def _find_duplicates_by_fields(self, queryset, match_fields: List[str]) -> List[Dict]:
        """
        Find duplicates based on the specified match fields.
        
        Args:
            queryset: QuerySet of transactions to check
            match_fields: List of field names to match on
            
        Returns:
            List of dictionaries containing duplicate group data
        """
        # Build values() call dynamically based on match fields
        values_fields = []
        for field in match_fields:
            if field in ['amount', 'date', 'reference', 'contact_name', 'external_account_id', 'description']:
                values_fields.append(field)
        
        if not values_fields:
            return []
        
        # Find groups of transactions with matching field values
        duplicates_query = queryset.values(*values_fields).annotate(
            count=Count('id'),
            transaction_ids=Count('id')  # We'll get actual IDs separately
        ).filter(
            count__gte=self.config.get('minimum_duplicates', 2)
        )
        
        # Apply reference filtering if configured
        if self.config.get('ignore_empty_reference', True) and 'reference' in values_fields:
            duplicates_query = duplicates_query.exclude(
                Q(reference__isnull=True) | Q(reference__exact='')
            )
        
        return list(duplicates_query.order_by('-count'))
    
    def _process_duplicate_groups(self, duplicates_data: List[Dict], integration) -> List[Dict]:
        """
        Process duplicate groups to get detailed transaction information.
        
        Args:
            duplicates_data: Raw duplicate group data from database
            integration: Integration instance
            
        Returns:
            List of processed duplicate group dictionaries
        """
        duplicate_groups = []
        
        for group_data in duplicates_data:
            # Build filter to find exact transactions in this duplicate group
            group_filter = Q(integration=integration)
            
            for field, value in group_data.items():
                if field not in ['count', 'transaction_ids']:
                    group_filter &= Q(**{field: value})
            
            # Get the actual transaction records for this group
            transactions = TransactionData.objects.filter(group_filter).order_by('-date', '-created_at')
            
            if transactions.count() >= self.config.get('minimum_duplicates', 2):
                # Format transaction data for the result
                transaction_list = []
                for txn in transactions:
                    transaction_list.append({
                        'id': txn.id,
                        'external_transaction_id': txn.external_transaction_id,
                        'date': txn.date.isoformat() if txn.date else None,
                        'amount': float(txn.amount) if txn.amount else 0,
                        'reference': txn.reference or '',
                        'description': txn.description or '',
                        'contact_name': txn.contact_name or '',
                        'status': txn.status,
                        'external_url': txn.external_url
                    })
                
                duplicate_groups.append({
                    'count': transactions.count(),
                    'matching_fields': {k: v for k, v in group_data.items() 
                                      if k not in ['count', 'transaction_ids']},
                    'transactions': transaction_list,
                    'total_amount': float(sum(t.amount or 0 for t in transactions))
                })
        
        return duplicate_groups
    
    def get_display_name(self) -> str:
        """Get human-readable display name."""
        match_fields = self.config.get('match_fields', ['amount', 'date', 'reference'])
        return f"Duplicate Transactions (matching on {', '.join(match_fields)})"


# Register the rule
ValidationRuleRegistry.register(DuplicateTransactionRule)