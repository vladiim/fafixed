from celery import shared_task
from django.utils import timezone
from .models import Integration, OAuthState, IntegrationCredential
from .managers import IntegrationManager
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