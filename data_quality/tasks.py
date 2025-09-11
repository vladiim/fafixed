"""
Celery tasks for data quality operations.
"""
import logging
from celery import shared_task
from django.utils import timezone

from connections.models import Connection
from data_quality.services.xero_sync import XeroTrackingSyncService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def sync_tracking_categories_for_connection(self, connection_id):
    """
    Sync tracking categories for a specific connection.
    
    Args:
        connection_id: ID of the connection to sync
        
    Returns:
        Dict with sync results
    """
    try:
        connection = Connection.objects.get(id=connection_id)
        logger.info(f"Starting tracking categories sync for connection {connection.id}")
        
        # Initialize sync service
        sync_service = XeroTrackingSyncService(connection)
        
        # Perform sync
        result = sync_service.sync_tracking_categories()
        
        if result['success']:
            logger.info(f"Successfully synced tracking categories for connection {connection.id}: {result}")
            
            # Update connection last_sync_at
            connection.last_sync_at = timezone.now()
            connection.save(update_fields=['last_sync_at'])
            
        else:
            logger.error(f"Failed to sync tracking categories for connection {connection.id}: {result.get('error')}")
            
            # Retry on failure (only if we're in a real Celery worker, not during tests)
            if hasattr(self, 'request') and self.request.retries < self.max_retries:
                countdown = 60 * (2 ** self.request.retries)  # Exponential backoff
                logger.info(f"Retrying tracking categories sync in {countdown} seconds (attempt {self.request.retries + 1})")
                self.retry(countdown=countdown)
        
        return result
        
    except Connection.DoesNotExist:
        logger.error(f"Connection {connection_id} not found for tracking categories sync")
        return {
            'success': False,
            'error': f'Connection {connection_id} not found'
        }
        
    except Exception as e:
        logger.error(f"Unexpected error syncing tracking categories for connection {connection_id}: {e}", exc_info=True)
        
        # Retry on unexpected errors (only if we're in a real Celery worker, not during tests)
        if hasattr(self, 'request') and self.request.retries < self.max_retries:
            countdown = 60 * (2 ** self.request.retries)
            logger.info(f"Retrying tracking categories sync in {countdown} seconds (attempt {self.request.retries + 1})")
            self.retry(countdown=countdown, exc=e)
        
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def sync_tracking_categories_for_all_connections():
    """
    Sync tracking categories for all active Xero connections.
    
    This task is designed to be run on a schedule (e.g., daily).
    
    Returns:
        Dict with overall sync results
    """
    logger.info("Starting tracking categories sync for all connections")
    
    # Get all active Xero connections
    connections = Connection.objects.filter(
        provider__provider_type='xero',
        status='active'
    )
    
    results = {
        'total_connections': connections.count(),
        'successful_syncs': 0,
        'failed_syncs': 0,
        'sync_results': []
    }
    
    for connection in connections:
        try:
            # Queue individual sync task
            task_result = sync_tracking_categories_for_connection.delay(connection.id)
            
            # Wait for result (with timeout)
            sync_result = task_result.get(timeout=300)  # 5 minute timeout
            
            if sync_result['success']:
                results['successful_syncs'] += 1
                logger.info(f"Successfully synced tracking categories for connection {connection.id}")
            else:
                results['failed_syncs'] += 1
                logger.error(f"Failed to sync tracking categories for connection {connection.id}: {sync_result.get('error')}")
            
            results['sync_results'].append({
                'connection_id': connection.id,
                'organization_name': connection.organization_name,
                'result': sync_result
            })
            
        except Exception as e:
            results['failed_syncs'] += 1
            error_msg = f"Error syncing connection {connection.id}: {str(e)}"
            logger.error(error_msg)
            
            results['sync_results'].append({
                'connection_id': connection.id,
                'organization_name': connection.organization_name,
                'result': {
                    'success': False,
                    'error': error_msg
                }
            })
    
    logger.info(f"Completed tracking categories sync for all connections: {results['successful_syncs']} successful, {results['failed_syncs']} failed")
    
    return results


@shared_task
def cleanup_archived_tracking_data(days_old=90):
    """
    Clean up old archived tracking categories and options.
    
    Args:
        days_old: Number of days after which archived data can be cleaned up
        
    Returns:
        Dict with cleanup results
    """
    from datetime import timedelta
    from data_quality.models import XeroTrackingCategory, XeroTrackingOption
    
    logger.info(f"Starting cleanup of archived tracking data older than {days_old} days")
    
    cutoff_date = timezone.now() - timedelta(days=days_old)
    
    # Find archived categories and options to clean up
    old_categories = XeroTrackingCategory.objects.filter(
        status='ARCHIVED',
        last_synced_at__lt=cutoff_date
    )
    
    old_options = XeroTrackingOption.objects.filter(
        status='ARCHIVED',
        category__last_synced_at__lt=cutoff_date
    )
    
    categories_count = old_categories.count()
    options_count = old_options.count()
    
    # Delete old archived data
    old_options.delete()
    old_categories.delete()
    
    result = {
        'categories_cleaned': categories_count,
        'options_cleaned': options_count,
        'cutoff_date': cutoff_date.isoformat()
    }
    
    logger.info(f"Cleaned up {categories_count} archived categories and {options_count} archived options")
    
    return result


@shared_task(bind=True, max_retries=3)
def verify_transaction_categorization(self, suggestion_id):
    """
    Verify that a transaction has been correctly categorized in Xero.
    
    This task is queued when users choose "Mark Done" or "Fix" actions
    to verify that the categorization was applied correctly.
    
    Args:
        suggestion_id: ID of the CategorySuggestion to verify
        
    Returns:
        Dict with verification results
    """
    try:
        from data_quality.models import CategorySuggestion
        
        suggestion = CategorySuggestion.objects.get(id=suggestion_id)
        logger.info(f"Starting transaction categorization verification for suggestion {suggestion_id}")
        
        # TODO: Implement Xero API call to fetch transaction and verify categorization
        # For now, this is a placeholder that will be implemented when Xero API integration is ready
        
        result = {
            'success': True,
            'suggestion_id': suggestion_id,
            'transaction_id': suggestion.xero_transaction_id,
            'verification_status': 'pending_implementation',
            'message': 'Xero API verification not yet implemented - placeholder task'
        }
        
        logger.info(f"Transaction categorization verification placeholder completed for suggestion {suggestion_id}")
        return result
        
    except CategorySuggestion.DoesNotExist:
        logger.error(f"CategorySuggestion {suggestion_id} not found for verification")
        return {
            'success': False,
            'error': f'CategorySuggestion {suggestion_id} not found'
        }
        
    except Exception as e:
        logger.error(f"Error verifying transaction categorization for suggestion {suggestion_id}: {e}", exc_info=True)
        
        # Retry on unexpected errors (only if we're in a real Celery worker, not during tests)
        if hasattr(self, 'request') and self.request.retries < self.max_retries:
            countdown = 60 * (2 ** self.request.retries)  # Exponential backoff
            logger.info(f"Retrying transaction verification in {countdown} seconds (attempt {self.request.retries + 1})")
            self.retry(countdown=countdown, exc=e)
        
        return {
            'success': False,
            'error': str(e)
        }