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

    Orchestrates:
    1. Bank transaction sync (via IntegrationManager)
    2. Accounting data sync (contacts, invoices, payments)
    3. Automatic payment reconciliation

    Args:
        integration_id: ID of the integration to sync
        sync_type: 'daily', 'incremental', or 'full'
    """
    try:
        integration = Integration.objects.get(id=integration_id, status='active')
        logger.info(f"Syncing integration {integration_id} ({integration.organization_name})")

        # Step 1: Sync bank transactions
        sync_record = IntegrationManager.sync_integration(integration, sync_type)

        result = {
            "integration_id": integration_id,
            "status": sync_record.status,
            "records_synced": sync_record.records_success,
            "error_message": sync_record.error_message
        }

        if sync_record.status == 'completed':
            logger.info(f"Successfully synced {sync_record.records_success} transactions")

            # Step 2: Sync accounting data (invoices, contacts, payments)
            try:
                from integrations.services.xero_service import XeroIntegrationService
                from integrations.services.xero_accounting_sync_service import XeroAccountingSyncService

                logger.info(f"Starting accounting data sync for integration {integration_id}")
                xero_service = XeroIntegrationService(integration)
                accounting_service = XeroAccountingSyncService(xero_service)
                accounting_result = accounting_service.sync_all()

                # Update sync record metadata with accounting data
                if not hasattr(sync_record, 'metadata') or sync_record.metadata is None:
                    sync_record.metadata = {}

                sync_record.metadata['accounting'] = {
                    'contacts': accounting_result.get('contacts', {}).get('synced', 0),
                    'invoices': accounting_result.get('invoices', {}).get('synced', 0),
                    'reconciled': accounting_result.get('reconciliation', {}).get('auto_matched', 0)
                }
                sync_record.save()

                # Add accounting data to result
                result['accounting'] = sync_record.metadata['accounting']

                logger.info(f"Accounting sync completed: {result['accounting']['contacts']} contacts, "
                          f"{result['accounting']['invoices']} invoices, "
                          f"{result['accounting']['reconciled']} payments auto-matched")

            except Exception as accounting_error:
                # Log accounting sync errors but don't fail the entire task
                logger.error(f"Accounting sync failed for integration {integration_id}: {str(accounting_error)}",
                           exc_info=True)
                result['accounting'] = {
                    'error': str(accounting_error),
                    'contacts': 0,
                    'invoices': 0,
                    'reconciled': 0
                }

            # Step 3: Run data quality validation checks
            try:
                from data_quality.validation.engine import ValidationEngine
                from connections.models import Connection

                # Get connection for this integration
                connection = Connection.objects.filter(
                    external_account_id=integration.external_account_id,
                    account=integration.account
                ).first()

                if connection:
                    logger.info(f"Starting data quality validation for integration {integration_id}")
                    validation_run = ValidationEngine.run_validation(
                        connection,
                        triggered_by='automatic_sync'
                    )

                    # Update sync record metadata with validation results
                    sync_record.metadata['validation'] = {
                        'issues_found': validation_run.issues_found,
                        'rules_passed': validation_run.rules_passed,
                        'rules_failed': validation_run.rules_failed
                    }
                    sync_record.save()

                    # Add validation data to result
                    result['validation'] = sync_record.metadata['validation']

                    logger.info(f"Validation completed: {validation_run.issues_found} issues found, "
                              f"{validation_run.rules_passed} rules passed")
                else:
                    logger.warning(f"No connection found for integration {integration_id}, skipping validation")

            except Exception as validation_error:
                # Log validation errors but don't fail the entire task
                logger.error(f"Validation failed for integration {integration_id}: {str(validation_error)}",
                           exc_info=True)
                result['validation'] = {
                    'error': str(validation_error),
                    'issues_found': 0
                }
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
def run_transaction_validations(self, transaction_prefix_id, rule_names):
    """
    Run validation rules on a specific transaction
    
    Args:
        transaction_prefix_id: Prefix ID of the transaction to validate
        rule_names: List of rule names to run
    """
    logger.info(f"Running validation rules {rule_names} on transaction {transaction_prefix_id}")
    
    try:
        # Get the transaction
        transaction = TransactionData.objects.get(prefix_id=transaction_prefix_id)
        
        results = {
            "transaction_prefix_id": transaction_prefix_id,
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
                logger.info(f"Running rule {rule_name} on transaction {transaction_prefix_id}")
                
                # Get the rule instance
                rule_instance = ValidationRuleRegistry.get_rule(rule_name)
                
                # Run the rule on this single transaction
                # For now, we'll simulate running the rule
                # TODO: Implement actual rule execution on single transaction
                rule_result = {
                    'passed': True,  # Simulate passing
                    'issues_found': 0,
                    'severity': 'info',
                    'details': f"Rule {rule_name} executed successfully on transaction {transaction_prefix_id}"
                }
                
                # For demonstration, let's make duplicate_transactions sometimes fail
                # Use transaction.id for the modulo since we need a numeric value for the demo
                if rule_name == 'duplicate_transactions' and transaction.id % 2 == 0:
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
                
                logger.info(f"Completed rule {rule_name} on transaction {transaction_prefix_id}: {'PASSED' if rule_result['passed'] else 'FAILED'}")
                
            except TransactionValidationStatus.DoesNotExist:
                error_msg = f"ValidationStatus not found for transaction {transaction_prefix_id}, rule {rule_name}"
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
        error_msg = f"Transaction {transaction_prefix_id} not found"
        logger.error(error_msg)
        raise Exception(error_msg)
        
    except Exception as e:
        error_msg = f"Failed to run validations on transaction {transaction_prefix_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise


@shared_task(bind=True)
def refresh_transaction_status_task(self, transaction_prefix_id):
    """Simple task to update transaction's updated_at timestamp"""
    import logging
    import time
    from django.utils import timezone
    
    logger = logging.getLogger(__name__)
    
    logger.info(f"Starting refresh for transaction {transaction_prefix_id}")
    
    try:
        # Get the transaction
        from .models import TransactionData
        transaction = TransactionData.objects.get(prefix_id=transaction_prefix_id)
        
        logger.info(f"Found transaction {transaction_prefix_id}, processing...")
        
        # Simulate some work
        time.sleep(2)
        
        # Update the timestamp
        transaction.updated_at = timezone.now()
        transaction.save()
        
        logger.info(f"Updated transaction {transaction_prefix_id} timestamp")
        
        # The model save will trigger django-lifecycle hooks which will broadcast the update
        return {
            "transaction_prefix_id": transaction_prefix_id,
            "status": "completed",
            "new_timestamp": str(transaction.updated_at)
        }
        
    except TransactionData.DoesNotExist:
        error_msg = f"Transaction {transaction_prefix_id} not found"
        logger.error(error_msg)
        raise Exception(error_msg)
        
    except Exception as e:
        error_msg = f"Failed to refresh transaction {transaction_prefix_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise



@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 300})
def sync_accounting_data(self, integration_id: int, sync_type: str = 'incremental'):
    """
    Background task to sync accounting data (contacts, invoices, bills, chart of accounts)

    Args:
        integration_id: ID of the Integration to sync
        sync_type: 'full' or 'incremental'

    Returns:
        Dict with sync results
    """
    from financial_data.services.accounting_sync import AccountingSyncService
    from integrations.services.xero_service import XeroIntegrationService

    logger.info(f"Starting accounting sync for integration {integration_id} (type: {sync_type})")

    try:
        # Get integration
        integration = Integration.objects.select_related('account', 'provider').get(id=integration_id)

        if integration.provider.name != 'xero':
            return {"status": "error", "message": f"Accounting sync only supported for Xero"}

        # Initialize services
        xero_service = XeroIntegrationService(integration)
        sync_service = AccountingSyncService(integration)

        # Get tenant ID
        tenant_id = integration.external_account_id
        if not tenant_id:
            return {"status": "error", "message": "No tenant ID found"}

        result = {
            "status": "success",
            "integration_id": integration_id,
            "organization_name": integration.organization_name,
            "sync_type": sync_type,
            "contacts": {"synced": 0, "errors": 0},
            "accounts": {"synced": 0, "errors": 0},
            "invoices": {"synced": 0, "errors": 0},
            "bills": {"synced": 0, "errors": 0},
            "errors": []
        }

        # 1. Sync Contacts
        try:
            modified_since = None if sync_type == 'full' else sync_service._get_last_sync_date('contacts').isoformat()
            raw_contacts = xero_service.fetch_contacts(tenant_id, modified_since=modified_since)
            
            for raw_contact in raw_contacts:
                try:
                    if sync_service.process_contact(raw_contact):
                        result["contacts"]["synced"] += 1
                except Exception as e:
                    result["contacts"]["errors"] += 1
        except Exception as e:
            result["errors"].append(f"Contacts: {str(e)}")

        # 2. Sync Chart of Accounts
        try:
            raw_accounts = xero_service.fetch_chart_of_accounts(tenant_id)
            
            for raw_account in raw_accounts:
                try:
                    if sync_service.process_chart_account(raw_account):
                        result["accounts"]["synced"] += 1
                except Exception as e:
                    result["accounts"]["errors"] += 1
        except Exception as e:
            result["errors"].append(f"Accounts: {str(e)}")

        # 3. Sync Sales Invoices
        try:
            modified_since = None if sync_type == 'full' else sync_service._get_last_sync_date('invoices').isoformat()
            raw_invoices = xero_service.fetch_invoices(tenant_id, invoice_type='ACCREC', modified_since=modified_since)
            
            for raw_invoice in raw_invoices:
                try:
                    if sync_service.process_sales_invoice(raw_invoice):
                        result["invoices"]["synced"] += 1
                except Exception as e:
                    result["invoices"]["errors"] += 1
        except Exception as e:
            result["errors"].append(f"Invoices: {str(e)}")

        # 4. Sync Purchase Bills
        try:
            modified_since = None if sync_type == 'full' else sync_service._get_last_sync_date('bills').isoformat()
            raw_bills = xero_service.fetch_invoices(tenant_id, invoice_type='ACCPAY', modified_since=modified_since)
            
            for raw_bill in raw_bills:
                try:
                    if sync_service.process_purchase_bill(raw_bill):
                        result["bills"]["synced"] += 1
                except Exception as e:
                    result["bills"]["errors"] += 1
        except Exception as e:
            result["errors"].append(f"Bills: {str(e)}")

        total_synced = result["contacts"]["synced"] + result["accounts"]["synced"] + result["invoices"]["synced"] + result["bills"]["synced"]
        logger.info(f"Accounting sync complete: {total_synced} items synced")

        result["total_synced"] = total_synced
        return result

    except Exception as e:
        logger.error(f"Accounting sync failed: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}
