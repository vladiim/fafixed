from celery import shared_task
from django.utils import timezone
from .models import Integration, OAuthState, IntegrationCredential, TransactionData, TransactionValidationStatus
from .managers import IntegrationManager
from .validation.engine import ValidationEngine
from .validation.registry import ValidationRuleRegistry
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def sync_all_integrations(self, sync_type='daily'):
    """
    Background task to sync all active integrations
    
    Args:
        sync_type: 'daily', 'incremental', or 'full'
    """
    logger.info(f"Starting {sync_type} sync for all active integrations")
    
    # Get all active integrations
    active_integrations = Integration.objects.filter(
        status='active',
        provider__name='xero'
    ).select_related('account', 'provider')
    
    if not active_integrations.exists():
        logger.info("No active integrations found to sync")
        return {"status": "success", "message": "No active integrations found"}
    
    results = {
        "total_integrations": active_integrations.count(),
        "successful_syncs": 0,
        "failed_syncs": 0,
        "errors": []
    }
    
    for integration in active_integrations:
        try:
            logger.info(f"Syncing integration {integration.id} ({integration.organization_name})")
            
            # Perform the sync
            sync_record = IntegrationManager.sync_integration(integration, sync_type)
            
            if sync_record.status == 'completed':
                results["successful_syncs"] += 1
                logger.info(f"Successfully synced {sync_record.records_success} transactions for integration {integration.id}")
            else:
                results["failed_syncs"] += 1
                error_msg = f"Sync failed for integration {integration.id}: {sync_record.error_message}"
                results["errors"].append(error_msg)
                logger.error(error_msg)
                
        except Exception as e:
            results["failed_syncs"] += 1
            error_msg = f"Exception syncing integration {integration.id}: {str(e)}"
            results["errors"].append(error_msg)
            logger.error(error_msg, exc_info=True)
    
    logger.info(f"Sync completed. Success: {results['successful_syncs']}, Failed: {results['failed_syncs']}")
    return results


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 2, 'countdown': 300})
def sync_single_integration(self, integration_id, sync_type='incremental'):
    """
    Background task to sync a single integration
    
    Args:
        integration_id: ID of the integration to sync
        sync_type: 'daily', 'incremental', or 'full'
    """
    try:
        integration = Integration.objects.get(id=integration_id, status='active')
        logger.info(f"Syncing integration {integration_id} ({integration.organization_name})")
        
        sync_record = IntegrationManager.sync_integration(integration, sync_type)
        
        result = {
            "integration_id": integration_id,
            "status": sync_record.status,
            "records_synced": sync_record.records_success,
            "error_message": sync_record.error_message
        }
        
        if sync_record.status == 'completed':
            logger.info(f"Successfully synced {sync_record.records_success} transactions")
        else:
            logger.error(f"Sync failed: {sync_record.error_message}")
        
        return result
        
    except Integration.DoesNotExist:
        error_msg = f"Integration {integration_id} not found or not active"
        logger.error(error_msg)
        return {"integration_id": integration_id, "status": "error", "error_message": error_msg}
    except Exception as e:
        error_msg = f"Exception syncing integration {integration_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"integration_id": integration_id, "status": "error", "error_message": error_msg}


@shared_task(bind=True)
def cleanup_expired_oauth_states(self, hours=24):
    """
    Background task to clean up expired OAuth states
    
    Args:
        hours: Delete states older than this many hours
    """
    try:
        count = OAuthState.cleanup_expired_states(hours=hours)
        logger.info(f"Cleaned up {count} expired OAuth states")
        return {"status": "success", "cleaned_states": count}
    except Exception as e:
        logger.error(f"Failed to cleanup OAuth states: {str(e)}", exc_info=True)
        return {"status": "error", "error_message": str(e)}


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 2, 'countdown': 120})
def refresh_expiring_tokens(self, minutes_ahead=60):
    """
    Background task to refresh tokens that will expire soon
    
    Args:
        minutes_ahead: Refresh tokens that expire within this many minutes
    """
    from datetime import timedelta
    
    try:
        # Find credentials that expire within the specified time window
        expiry_threshold = timezone.now() + timedelta(minutes=minutes_ahead)
        
        expiring_credentials = IntegrationCredential.objects.filter(
            expires_at__lte=expiry_threshold,
            expires_at__isnull=False,
            integration__status='active'
        ).select_related('integration')
        
        results = {
            "total_checked": expiring_credentials.count(),
            "successful_refreshes": 0,
            "failed_refreshes": 0,
            "errors": []
        }
        
        for credential in expiring_credentials:
            try:
                integration = credential.integration
                logger.info(f"Refreshing token for integration {integration.id}")
                
                success = IntegrationManager.refresh_credentials(integration)
                
                if success:
                    results["successful_refreshes"] += 1
                    logger.info(f"Successfully refreshed token for integration {integration.id}")
                else:
                    results["failed_refreshes"] += 1
                    error_msg = f"Failed to refresh token for integration {integration.id}"
                    results["errors"].append(error_msg)
                    logger.error(error_msg)
                    
            except Exception as e:
                results["failed_refreshes"] += 1
                error_msg = f"Exception refreshing token for integration {credential.integration.id}: {str(e)}"
                results["errors"].append(error_msg)
                logger.error(error_msg, exc_info=True)
        
        logger.info(f"Token refresh completed. Success: {results['successful_refreshes']}, Failed: {results['failed_refreshes']}")
        return results
        
    except Exception as e:
        logger.error(f"Failed to refresh expiring tokens: {str(e)}", exc_info=True)
        return {"status": "error", "error_message": str(e)}


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 2, 'countdown': 300})
def run_validation_rules(self, integration_id, rule_names=None, triggered_by='manual'):
    """
    Background task to run validation rules for an integration.
    
    Args:
        integration_id: ID of the integration to validate
        rule_names: Optional list of specific rule names to run
        triggered_by: What triggered this validation run
    """
    try:
        integration = Integration.objects.get(id=integration_id, status='active')
        logger.info(f"Running validation rules for integration {integration_id} ({integration.organization_name})")
        
        validation_run = ValidationEngine.run_validation(
            integration=integration,
            rule_names=rule_names,
            triggered_by=triggered_by
        )
        
        result = {
            "integration_id": integration_id,
            "validation_run_id": validation_run.id,
            "status": validation_run.status,
            "total_rules": validation_run.total_rules,
            "rules_passed": validation_run.rules_passed,
            "rules_failed": validation_run.rules_failed,
            "issues_found": validation_run.issues_found,
            "error_message": validation_run.error_message
        }
        
        logger.info(f"Validation completed for integration {integration_id}. "
                   f"Rules passed: {validation_run.rules_passed}, "
                   f"Rules failed: {validation_run.rules_failed}, "
                   f"Issues found: {validation_run.issues_found}")
        
        return result
        
    except Integration.DoesNotExist:
        error_msg = f"Integration {integration_id} not found or not active"
        logger.error(error_msg)
        return {"integration_id": integration_id, "status": "error", "error_message": error_msg}
    except Exception as e:
        error_msg = f"Exception running validation for integration {integration_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"integration_id": integration_id, "status": "error", "error_message": error_msg}


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 2, 'countdown': 30})
def run_transaction_validations(self, transaction_id, rule_names):
    """
    Run validation rules on a specific transaction
    
    Args:
        transaction_id: ID of the transaction to validate
        rule_names: List of rule names to run
    """
    logger.info(f"Running validation rules {rule_names} on transaction {transaction_id}")
    
    try:
        # Get the transaction
        transaction = TransactionData.objects.get(id=transaction_id)
        
        results = {
            "transaction_id": transaction_id,
            "rules_run": 0,
            "rules_passed": 0,
            "rules_failed": 0,
            "total_issues": 0,
            "errors": []
        }
        
        for rule_name in rule_names:
            try:
                # Get or create the validation status record
                validation_status = TransactionValidationStatus.objects.get(
                    transaction=transaction,
                    rule_name=rule_name
                )
                
                # Mark as running
                validation_status.mark_running()
                logger.info(f"Running rule {rule_name} on transaction {transaction_id}")
                
                # Get the rule instance
                rule_instance = ValidationRuleRegistry.get_rule(rule_name)
                
                # Run the rule on this single transaction
                # For now, we'll simulate running the rule
                # TODO: Implement actual rule execution on single transaction
                rule_result = {
                    'passed': True,  # Simulate passing
                    'issues_found': 0,
                    'severity': 'info',
                    'details': f"Rule {rule_name} executed successfully on transaction {transaction_id}"
                }
                
                # For demonstration, let's make duplicate_transactions sometimes fail
                if rule_name == 'duplicate_transactions' and transaction_id % 2 == 0:
                    rule_result = {
                        'passed': False,
                        'issues_found': 2,
                        'severity': 'warning',
                        'details': f"Found 2 potential duplicate transactions"
                    }
                
                # Mark as completed
                validation_status.mark_completed(
                    passed=rule_result['passed'],
                    issues_found=rule_result['issues_found'],
                    severity=rule_result['severity'],
                    result_data=rule_result
                )
                
                # Model will handle broadcasting via django-lifecycle hooks
                
                results["rules_run"] += 1
                if rule_result['passed']:
                    results["rules_passed"] += 1
                else:
                    results["rules_failed"] += 1
                    results["total_issues"] += rule_result['issues_found']
                
                logger.info(f"Completed rule {rule_name} on transaction {transaction_id}: {'PASSED' if rule_result['passed'] else 'FAILED'}")
                
            except TransactionValidationStatus.DoesNotExist:
                error_msg = f"ValidationStatus not found for transaction {transaction_id}, rule {rule_name}"
                results["errors"].append(error_msg)
                logger.error(error_msg)
                continue
                
            except Exception as rule_error:
                # Mark the specific rule as failed
                try:
                    validation_status = TransactionValidationStatus.objects.get(
                        transaction=transaction,
                        rule_name=rule_name
                    )
                    validation_status.mark_failed(str(rule_error))
                except:
                    pass
                
                error_msg = f"Error running rule {rule_name}: {str(rule_error)}"
                results["errors"].append(error_msg)
                logger.error(error_msg, exc_info=True)
                continue
        
        logger.info(f"Transaction validation task completed: {results}")
        return results
        
    except TransactionData.DoesNotExist:
        error_msg = f"Transaction {transaction_id} not found"
        logger.error(error_msg)
        raise Exception(error_msg)
        
    except Exception as e:
        error_msg = f"Failed to run validations on transaction {transaction_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise


@shared_task(bind=True)
def refresh_transaction_status_task(self, transaction_id):
    """Simple task to update transaction's updated_at timestamp"""
    import logging
    import time
    from django.utils import timezone
    
    logger = logging.getLogger(__name__)
    
    logger.info(f"Starting refresh for transaction {transaction_id}")
    
    try:
        # Get the transaction
        from .models import TransactionData
        transaction = TransactionData.objects.get(id=transaction_id)
        
        logger.info(f"Found transaction {transaction_id}, processing...")
        
        # Simulate some work
        time.sleep(2)
        
        # Update the timestamp
        transaction.updated_at = timezone.now()
        transaction.save()
        
        logger.info(f"Updated transaction {transaction_id} timestamp")
        
        # The model save will trigger django-lifecycle hooks which will broadcast the update
        return {
            "transaction_id": transaction_id,
            "status": "completed",
            "new_timestamp": str(transaction.updated_at)
        }
        
    except TransactionData.DoesNotExist:
        error_msg = f"Transaction {transaction_id} not found"
        logger.error(error_msg)
        raise Exception(error_msg)
        
    except Exception as e:
        error_msg = f"Failed to refresh transaction {transaction_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise


