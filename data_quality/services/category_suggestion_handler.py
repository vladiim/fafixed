"""
Category Suggestion Handler for processing user actions on suggestions.
"""
import logging
from typing import Dict, Any, List, Tuple
from django.utils import timezone
from django.db import transaction

from data_quality.models import CategorySuggestion, CategoryDetectionRule
from data_quality.tasks import verify_transaction_categorization

logger = logging.getLogger(__name__)


class CategorySuggestionHandler:
    """Handler for processing user actions on category suggestions"""
    
    def handle_ignore_action(self, suggestion: CategorySuggestion, user) -> Dict[str, Any]:
        """
        Handle user action to ignore a suggestion.
        
        Args:
            suggestion: CategorySuggestion to ignore
            user: User making the decision
            
        Returns:
            Dict with action result and metadata
        """
        logger.info(f"Processing ignore action for suggestion {suggestion.id} by user {user.id}")
        
        # Validate suggestion can be processed
        is_valid, error = self._validate_suggestion_for_action(suggestion)
        if not is_valid:
            return {
                'success': False,
                'error': error,
                'suggestion_id': suggestion.id
            }
        
        try:
            with transaction.atomic():
                # Update suggestion status
                suggestion.status = 'IGNORED'
                suggestion.decided_by = user
                suggestion.decided_at = timezone.now()
                suggestion.save()
                
                # Update rule statistics
                rule = suggestion.detection_rule
                rule.ignored_count += 1
                rule.save(update_fields=['ignored_count'])
                
                # Create audit trail
                audit_entry = self._create_audit_entry(
                    action='ignore',
                    suggestion=suggestion,
                    user=user,
                    metadata={
                        'rule_name': rule.name,
                        'transaction_id': suggestion.xero_transaction_id
                    }
                )
                
                logger.info(f"Successfully processed ignore action for suggestion {suggestion.id}")
                
                return {
                    'success': True,
                    'action': 'ignore',
                    'suggestion_id': suggestion.id,
                    'audit_trail': audit_entry
                }
                
        except Exception as e:
            logger.error(f"Error processing ignore action for suggestion {suggestion.id}: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Failed to process ignore action: {str(e)}',
                'suggestion_id': suggestion.id
            }
    
    def handle_mark_done_action(self, suggestion: CategorySuggestion, user) -> Dict[str, Any]:
        """
        Handle user action to mark suggestion as done (already categorized in Xero).
        
        Args:
            suggestion: CategorySuggestion to mark as done
            user: User making the decision
            
        Returns:
            Dict with action result and metadata
        """
        logger.info(f"Processing mark done action for suggestion {suggestion.id} by user {user.id}")
        
        # Validate suggestion can be processed
        is_valid, error = self._validate_suggestion_for_action(suggestion)
        if not is_valid:
            return {
                'success': False,
                'error': error,
                'suggestion_id': suggestion.id
            }
        
        try:
            with transaction.atomic():
                # Update suggestion status
                suggestion.status = 'APPLIED'
                suggestion.decided_by = user
                suggestion.decided_at = timezone.now()
                suggestion.save()
                
                # Update rule statistics
                rule = suggestion.detection_rule
                rule.applied_count += 1
                rule.save(update_fields=['applied_count'])
                
                # Queue Xero verification task
                verification_task = verify_transaction_categorization.delay(suggestion.id)
                
                # Create audit trail
                audit_entry = self._create_audit_entry(
                    action='mark_done',
                    suggestion=suggestion,
                    user=user,
                    metadata={
                        'rule_name': rule.name,
                        'transaction_id': suggestion.xero_transaction_id,
                        'verification_task_id': str(verification_task.id)
                    }
                )
                
                logger.info(f"Successfully processed mark done action for suggestion {suggestion.id}")
                
                return {
                    'success': True,
                    'action': 'mark_done',
                    'suggestion_id': suggestion.id,
                    'verification_task_id': str(verification_task.id),
                    'audit_trail': audit_entry
                }
                
        except Exception as e:
            logger.error(f"Error processing mark done action for suggestion {suggestion.id}: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Failed to process mark done action: {str(e)}',
                'suggestion_id': suggestion.id
            }
    
    def handle_fix_action(self, suggestion: CategorySuggestion, user) -> Dict[str, Any]:
        """
        Handle user action to fix categorization in Xero.
        
        Args:
            suggestion: CategorySuggestion to fix
            user: User making the decision
            
        Returns:
            Dict with action result and metadata
        """
        logger.info(f"Processing fix action for suggestion {suggestion.id} by user {user.id}")
        
        # Validate suggestion can be processed
        is_valid, error = self._validate_suggestion_for_action(suggestion)
        if not is_valid:
            return {
                'success': False,
                'error': error,
                'suggestion_id': suggestion.id
            }
        
        try:
            with transaction.atomic():
                # Update suggestion status
                suggestion.status = 'APPLIED'
                suggestion.decided_by = user
                suggestion.decided_at = timezone.now()
                suggestion.save()
                
                # Update rule statistics
                rule = suggestion.detection_rule
                rule.applied_count += 1
                rule.save(update_fields=['applied_count'])
                
                # Generate Xero transaction URL
                xero_url = self._generate_xero_transaction_url(suggestion)
                
                # Queue Xero verification task (user will make changes manually)
                verification_task = verify_transaction_categorization.delay(suggestion.id)
                
                # Create audit trail
                audit_entry = self._create_audit_entry(
                    action='fix',
                    suggestion=suggestion,
                    user=user,
                    metadata={
                        'rule_name': rule.name,
                        'transaction_id': suggestion.xero_transaction_id,
                        'xero_url': xero_url,
                        'verification_task_id': str(verification_task.id)
                    }
                )
                
                logger.info(f"Successfully processed fix action for suggestion {suggestion.id}")
                
                return {
                    'success': True,
                    'action': 'fix',
                    'suggestion_id': suggestion.id,
                    'xero_url': xero_url,
                    'verification_task_id': str(verification_task.id),
                    'audit_trail': audit_entry
                }
                
        except Exception as e:
            logger.error(f"Error processing fix action for suggestion {suggestion.id}: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Failed to process fix action: {str(e)}',
                'suggestion_id': suggestion.id
            }
    
    def handle_bulk_ignore_action(self, suggestions: List[CategorySuggestion], user) -> Dict[str, Any]:
        """
        Handle bulk ignore action for multiple suggestions.
        
        Args:
            suggestions: List of CategorySuggestion objects to ignore
            user: User making the decision
            
        Returns:
            Dict with bulk action results
        """
        logger.info(f"Processing bulk ignore action for {len(suggestions)} suggestions by user {user.id}")
        
        processed_count = 0
        failed_count = 0
        errors = []
        
        for suggestion in suggestions:
            try:
                result = self.handle_ignore_action(suggestion, user)
                if result['success']:
                    processed_count += 1
                else:
                    failed_count += 1
                    errors.append({
                        'suggestion_id': suggestion.id,
                        'error': result['error']
                    })
            except Exception as e:
                failed_count += 1
                errors.append({
                    'suggestion_id': suggestion.id,
                    'error': str(e)
                })
        
        logger.info(f"Bulk ignore action completed: {processed_count} processed, {failed_count} failed")
        
        return {
            'success': failed_count == 0,
            'action': 'bulk_ignore',
            'processed_count': processed_count,
            'failed_count': failed_count,
            'errors': errors
        }
    
    def get_suggestion_status(self, suggestion: CategorySuggestion) -> Dict[str, Any]:
        """
        Get current status information for a suggestion.
        
        Args:
            suggestion: CategorySuggestion to get status for
            
        Returns:
            Dict with status information
        """
        return {
            'status': suggestion.status,
            'is_processed': suggestion.status in ['APPLIED', 'IGNORED', 'SUPERSEDED'],
            'decided_by': suggestion.decided_by.username if suggestion.decided_by else None,
            'decided_at': suggestion.decided_at.isoformat() if suggestion.decided_at else None,
            'created_at': suggestion.created_at.isoformat(),
            'rule_name': suggestion.detection_rule.name,
            'suggested_category': suggestion.suggested_category.name,
            'transaction_id': suggestion.xero_transaction_id,
            'transaction_description': suggestion.transaction_description,
            'transaction_amount': float(suggestion.transaction_amount) if suggestion.transaction_amount else None
        }
    
    def get_pending_suggestions_for_connection(self, connection) -> List[CategorySuggestion]:
        """
        Get all pending suggestions for a connection.
        
        Args:
            connection: Connection to get suggestions for
            
        Returns:
            List of pending CategorySuggestion objects
        """
        return list(CategorySuggestion.objects.filter(
            connection=connection,
            status='PENDING'
        ).select_related('detection_rule', 'suggested_category').order_by('-created_at'))
    
    def get_suggestion_statistics_for_rule(self, rule: CategoryDetectionRule) -> Dict[str, Any]:
        """
        Get statistics for suggestions generated by a rule.
        
        Args:
            rule: CategoryDetectionRule to get statistics for
            
        Returns:
            Dict with suggestion statistics
        """
        suggestions = CategorySuggestion.objects.filter(detection_rule=rule)
        
        total_count = suggestions.count()
        pending_count = suggestions.filter(status='PENDING').count()
        applied_count = suggestions.filter(status='APPLIED').count()
        ignored_count = suggestions.filter(status='IGNORED').count()
        superseded_count = suggestions.filter(status='SUPERSEDED').count()
        
        return {
            'rule_id': rule.id,
            'rule_name': rule.name,
            'total_suggestions': total_count,
            'pending_count': pending_count,
            'applied_count': applied_count,
            'ignored_count': ignored_count,
            'superseded_count': superseded_count,
            'action_rate': ((applied_count + ignored_count) / total_count * 100) if total_count > 0 else 0
        }
    
    def _validate_suggestion_for_action(self, suggestion: CategorySuggestion) -> Tuple[bool, str]:
        """
        Validate that a suggestion can be processed.
        
        Args:
            suggestion: CategorySuggestion to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if suggestion.status != 'PENDING':
            if suggestion.status == 'SUPERSEDED':
                return False, 'This suggestion has been superseded by a newer suggestion'
            else:
                return False, 'This suggestion has already been processed'
        
        return True, None
    
    def _generate_xero_transaction_url(self, suggestion: CategorySuggestion) -> str:
        """
        Generate Xero URL for editing a transaction.
        
        Args:
            suggestion: CategorySuggestion with transaction details
            
        Returns:
            Xero transaction URL
        """
        connection = suggestion.connection
        transaction_id = suggestion.xero_transaction_id
        
        # Xero URL format for bank transactions
        base_url = "https://go.xero.com/organisationlogin/default.aspx"
        redirect_url = f"/Bank/ViewTransaction.aspx?bankTransactionID={transaction_id}"
        
        return f"{base_url}?shortcode={connection.external_account_id}&redirecturl={redirect_url}"
    
    def _create_audit_entry(self, action: str, suggestion: CategorySuggestion, user, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create audit trail entry for user action.
        
        Args:
            action: Action type (ignore, mark_done, fix)
            suggestion: CategorySuggestion being acted upon
            user: User performing the action
            metadata: Additional metadata for the audit entry
            
        Returns:
            Dict with audit entry data
        """
        audit_entry = {
            'action': action,
            'suggestion_id': suggestion.id,
            'user_id': user.id,
            'user_username': user.username,
            'timestamp': timezone.now().isoformat(),
            'connection_id': suggestion.connection.id,
            'rule_id': suggestion.detection_rule.id,
            'transaction_id': suggestion.xero_transaction_id,
            'metadata': metadata or {}
        }
        
        # Log audit entry for external audit systems
        logger.info(f"Audit trail: {audit_entry}")
        
        return audit_entry