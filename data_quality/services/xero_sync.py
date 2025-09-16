"""
Xero tracking categories synchronization service.
"""
import logging
from typing import Dict, Any, List

from data_quality.models import XeroTrackingCategory, XeroTrackingOption
from connections.services.providers.xero import XeroConnectionService
from xero_python.accounting import AccountingApi

logger = logging.getLogger(__name__)


class XeroTrackingSyncService:
    """Service for syncing tracking categories from Xero to local cache"""
    
    def __init__(self, connection):
        """
        Initialize sync service for a specific connection.
        
        Args:
            connection: Connection instance for Xero integration
        """
        self.connection = connection
    
    def sync_tracking_categories(self) -> Dict[str, Any]:
        """
        Sync tracking categories and options from Xero to local cache.
        
        Returns:
            Dict with sync results and statistics
        """
        try:
            logger.info(f"Starting tracking categories sync for connection {self.connection.id}")
            
            # Get Xero API client
            api_client = self._get_xero_api_client()

            # Fetch tracking categories from Xero
            response = api_client.get_tracking_categories(xero_tenant_id=self.connection.tenant_id)
            
            # Process the response
            stats = {
                'categories_synced': 0,
                'categories_created': 0,
                'categories_updated': 0,
                'categories_archived': 0,
                'options_synced': 0,
                'options_created': 0,
                'options_updated': 0,
                'options_archived': 0,
            }
            
            # Track which categories we've seen in Xero
            xero_category_ids = set()
            
            for xero_category in response.tracking_categories:
                xero_category_ids.add(xero_category.tracking_category_id)
                
                # Create or update category
                category, created = XeroTrackingCategory.objects.update_or_create(
                    connection=self.connection,
                    xero_category_id=xero_category.tracking_category_id,
                    defaults={
                        'name': xero_category.name,
                        'status': xero_category.status,
                    }
                )
                
                if created:
                    stats['categories_created'] += 1
                    logger.debug(f"Created new category: {category.name}")
                else:
                    stats['categories_updated'] += 1
                    logger.debug(f"Updated existing category: {category.name}")
                
                stats['categories_synced'] += 1
                
                # Sync options for this category
                option_stats = self._sync_category_options(category, xero_category.options)
                for key, value in option_stats.items():
                    stats[key] += value
            
            # Archive categories that no longer exist in Xero
            archived_count = self._archive_missing_categories(xero_category_ids)
            stats['categories_archived'] = archived_count
            
            logger.info(f"Tracking categories sync completed: {stats}")
            
            return {
                'success': True,
                **stats
            }
            
        except Exception as e:
            logger.error(f"Error syncing tracking categories: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def _sync_category_options(self, category: XeroTrackingCategory, xero_options: List) -> Dict[str, int]:
        """
        Sync options for a specific tracking category.
        
        Args:
            category: Local tracking category instance
            xero_options: List of options from Xero API
            
        Returns:
            Dict with option sync statistics
        """
        stats = {
            'options_synced': 0,
            'options_created': 0,
            'options_updated': 0,
            'options_archived': 0,
        }
        
        # Track which options we've seen in Xero
        xero_option_ids = set()
        
        for xero_option in xero_options:
            xero_option_ids.add(xero_option.tracking_option_id)
            
            # Create or update option
            option, created = XeroTrackingOption.objects.update_or_create(
                category=category,
                xero_option_id=xero_option.tracking_option_id,
                defaults={
                    'name': xero_option.name,
                    'status': xero_option.status,
                }
            )
            
            if created:
                stats['options_created'] += 1
            else:
                stats['options_updated'] += 1
            
            stats['options_synced'] += 1
        
        # Archive options that no longer exist in Xero
        missing_options = XeroTrackingOption.objects.filter(
            category=category,
            status='ACTIVE'
        ).exclude(xero_option_id__in=xero_option_ids)
        
        archived_count = missing_options.update(status='ARCHIVED')
        stats['options_archived'] = archived_count
        
        return stats
    
    def _archive_missing_categories(self, xero_category_ids: set) -> int:
        """
        Archive categories that no longer exist in Xero.
        
        Args:
            xero_category_ids: Set of category IDs that exist in Xero
            
        Returns:
            Number of categories archived
        """
        missing_categories = XeroTrackingCategory.objects.filter(
            connection=self.connection,
            status='ACTIVE'
        ).exclude(xero_category_id__in=xero_category_ids)
        
        archived_count = missing_categories.update(status='ARCHIVED')
        
        if archived_count > 0:
            logger.info(f"Archived {archived_count} categories that no longer exist in Xero")
        
        return archived_count
    
    def get_cached_tracking_categories(self) -> List[Dict[str, Any]]:
        """
        Get cached tracking categories formatted for UI consumption.
        
        Returns:
            List of category dictionaries with options
        """
        categories = XeroTrackingCategory.objects.filter(
            connection=self.connection,
            status='ACTIVE'
        ).prefetch_related('options')
        
        result = []
        for category in categories:
            active_options = category.options.filter(status='ACTIVE')
            
            result.append({
                'id': category.xero_category_id,
                'name': category.name,
                'options': [
                    {
                        'id': option.xero_option_id,
                        'name': option.name
                    }
                    for option in active_options
                ]
            })
        
        return result
    
    def _get_xero_api_client(self):
        """
        Get initialized Xero API client for this connection.

        Returns:
            AccountingApi: Initialized Xero Accounting API client
        """
        try:
            # Get the Xero connection service for this connection
            xero_service = XeroConnectionService(self.connection)

            # Create API client with proper token management
            api_client = xero_service._create_api_client()

            # Return AccountingApi instance
            accounting_api = AccountingApi(api_client)

            logger.debug(f"Created Xero API client for connection {self.connection.id}")
            return accounting_api

        except Exception as e:
            logger.error(f"Failed to create Xero API client for connection {self.connection.id}: {e}")
            raise