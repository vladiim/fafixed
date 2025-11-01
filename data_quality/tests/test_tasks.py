"""
Tests for data quality Celery tasks.
"""
from django.test import TestCase
from unittest.mock import Mock, patch
from django.utils import timezone
from datetime import timedelta

from integrations.models import Integration
from integrations.models import IntegrationProvider
from data_quality.models import (
    XeroTrackingCategory, 
    XeroTrackingOption,
    CategoryDetectionRule,
    CategorySuggestion
)
from data_quality.tasks import (
    sync_tracking_categories_for_connection,
    sync_tracking_categories_for_all_connections,
    cleanup_archived_tracking_data
)
from core.models import Account
from django.contrib.auth.models import User


class TrackingCategoriesTasksTest(TestCase):
    """Test tracking categories Celery tasks"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.account = Account.objects.create(
            name='Test Account',
            account_type='organization'
        )
        self.provider = IntegrationProvider.objects.create(
            name='xero',
            display_name='Xero',
            provider_type='xero',
            auth_url_template='https://api.xero.com/oauth/authorize',
            token_url='https://api.xero.com/oauth/token'
        )
        self.connection = Integration.objects.create(
            account=self.account,
            provider=self.provider,
            external_account_id='test-xero-org-id',
            external_account_name='Test Xero Org',
            organization_name='Test Organization',
            status='active',
            created_by=self.user
        )
    
    @patch('data_quality.tasks.XeroTrackingSyncService')
    def test_sync_tracking_categories_for_connection_success(self, mock_sync_service_class):
        """Test successful sync for single connection"""
        # Mock sync service
        mock_sync_service = Mock()
        mock_sync_service_class.return_value = mock_sync_service
        mock_sync_service.sync_tracking_categories.return_value = {
            'success': True,
            'categories_synced': 5,
            'options_synced': 15
        }
        
        # Execute task
        result = sync_tracking_categories_for_connection(self.connection.id)
        
        # Verify sync service was called correctly
        mock_sync_service_class.assert_called_once_with(self.connection)
        mock_sync_service.sync_tracking_categories.assert_called_once()
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['categories_synced'], 5)
        self.assertEqual(result['options_synced'], 15)
        
        # Verify connection last_sync_at was updated
        self.connection.refresh_from_db()
        self.assertIsNotNone(self.connection.last_sync_at)
    
    @patch('data_quality.tasks.XeroTrackingSyncService')
    @patch('data_quality.tasks.sync_tracking_categories_for_connection.retry')
    def test_sync_tracking_categories_for_connection_failure(self, mock_retry, mock_sync_service_class):
        """Test handling of sync failure"""
        # Mock sync service with failure
        mock_sync_service = Mock()
        mock_sync_service_class.return_value = mock_sync_service
        mock_sync_service.sync_tracking_categories.return_value = {
            'success': False,
            'error': 'Xero API error'
        }
        
        # Mock retry to prevent actual retry during test
        mock_retry.side_effect = lambda **kwargs: None
        
        # Execute task
        result = sync_tracking_categories_for_connection(self.connection.id)
        
        # Verify result
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Xero API error')
        
        # Verify connection last_sync_at was NOT updated
        self.connection.refresh_from_db()
        self.assertIsNone(self.connection.last_sync_at)
    
    def test_sync_tracking_categories_for_connection_not_found(self):
        """Test handling of non-existent connection"""
        # Execute task with non-existent connection ID
        result = sync_tracking_categories_for_connection(99999)
        
        # Verify error handling
        self.assertFalse(result['success'])
        self.assertIn('Connection 99999 not found', result['error'])
    
    @patch('data_quality.tasks.sync_tracking_categories_for_connection.delay')
    def test_sync_tracking_categories_for_all_connections(self, mock_delay):
        """Test sync for all connections"""
        # Create additional connections
        connection2 = Integration.objects.create(
            account=self.account,
            provider=self.provider,
            external_account_id='test-xero-org-id-2',
            external_account_name='Test Xero Org 2',
            organization_name='Test Organization 2',
            status='active',
            created_by=self.user
        )
        
        # Create inactive connection (should be skipped)
        Connection.objects.create(
            account=self.account,
            provider=self.provider,
            external_account_id='inactive-xero-org-id',
            external_account_name='Inactive Xero Org',
            organization_name='Inactive Organization',
            status='expired',
            created_by=self.user
        )
        
        # Mock the delay method to return mock results
        def mock_delay_side_effect(connection_id):
            mock_task_result = Mock()
            if connection_id == self.connection.id:
                mock_task_result.get.return_value = {'success': True, 'categories_synced': 5}
            else:
                mock_task_result.get.return_value = {'success': True, 'categories_synced': 3}
            return mock_task_result
        
        mock_delay.side_effect = mock_delay_side_effect
        
        # Execute task
        result = sync_tracking_categories_for_all_connections()
        
        # Verify results
        self.assertEqual(result['total_connections'], 2)  # Only active connections
        self.assertEqual(result['successful_syncs'], 2)
        self.assertEqual(result['failed_syncs'], 0)
        self.assertEqual(len(result['sync_results']), 2)
        
        # Verify delay was called for each active connection
        self.assertEqual(mock_delay.call_count, 2)
        mock_delay.assert_any_call(self.connection.id)
        mock_delay.assert_any_call(connection2.id)
    
    @patch('data_quality.tasks.sync_tracking_categories_for_connection.delay')
    def test_sync_tracking_categories_for_all_connections_with_failures(self, mock_delay):
        """Test sync for all connections with some failures"""
        # Mock delay with mixed results
        def mock_delay_side_effect(connection_id):
            mock_task_result = Mock()
            if connection_id == self.connection.id:
                mock_task_result.get.return_value = {'success': True, 'categories_synced': 5}
            else:
                mock_task_result.get.side_effect = Exception("Task timeout")
            return mock_task_result
        
        mock_delay.side_effect = mock_delay_side_effect
        
        # Create second connection
        connection2 = Integration.objects.create(
            account=self.account,
            provider=self.provider,
            external_account_id='test-xero-org-id-2',
            external_account_name='Test Xero Org 2',
            organization_name='Test Organization 2',
            status='active',
            created_by=self.user
        )
        
        # Execute task
        result = sync_tracking_categories_for_all_connections()
        
        # Verify mixed results
        self.assertEqual(result['total_connections'], 2)
        self.assertEqual(result['successful_syncs'], 1)
        self.assertEqual(result['failed_syncs'], 1)
        
        # Verify failure is recorded
        failed_result = next(r for r in result['sync_results'] if not r['result']['success'])
        self.assertIn('Task timeout', failed_result['result']['error'])
    
    def test_cleanup_archived_tracking_data(self):
        """Test cleanup of old archived tracking data"""
        # Create test data
        category = XeroTrackingCategory.objects.create(
            connection=self.connection,
            xero_category_id='cat-uuid-123',
            name='Test Category',
            status='ACTIVE'
        )
        
        option = XeroTrackingOption.objects.create(
            category=category,
            xero_option_id='opt-uuid-456',
            name='Test Option',
            status='ACTIVE'
        )
        
        # Create old archived data
        old_category = XeroTrackingCategory.objects.create(
            connection=self.connection,
            xero_category_id='old-cat-uuid',
            name='Old Category',
            status='ARCHIVED'
        )
        
        old_option = XeroTrackingOption.objects.create(
            category=old_category,
            xero_option_id='old-opt-uuid',
            name='Old Option',
            status='ARCHIVED'
        )
        
        # Make the archived data old by updating last_synced_at
        old_date = timezone.now() - timedelta(days=100)
        XeroTrackingCategory.objects.filter(id=old_category.id).update(last_synced_at=old_date)
        
        # Create recent archived data (should not be cleaned)
        recent_archived_category = XeroTrackingCategory.objects.create(
            connection=self.connection,
            xero_category_id='recent-cat-uuid',
            name='Recent Archived Category',
            status='ARCHIVED'
        )
        
        # Execute cleanup task
        result = cleanup_archived_tracking_data(days_old=90)
        
        # Verify cleanup results
        self.assertEqual(result['categories_cleaned'], 1)
        self.assertEqual(result['options_cleaned'], 1)
        
        # Verify old data was deleted
        self.assertFalse(XeroTrackingCategory.objects.filter(id=old_category.id).exists())
        self.assertFalse(XeroTrackingOption.objects.filter(id=old_option.id).exists())
        
        # Verify active data still exists
        self.assertTrue(XeroTrackingCategory.objects.filter(id=category.id).exists())
        self.assertTrue(XeroTrackingOption.objects.filter(id=option.id).exists())
        
        # Verify recent archived data still exists
        self.assertTrue(XeroTrackingCategory.objects.filter(id=recent_archived_category.id).exists())
    
    def test_cleanup_archived_tracking_data_no_old_data(self):
        """Test cleanup when no old data exists"""
        # Create only recent data
        category = XeroTrackingCategory.objects.create(
            connection=self.connection,
            xero_category_id='cat-uuid-123',
            name='Recent Category',
            status='ARCHIVED'
        )
        
        # Execute cleanup task
        result = cleanup_archived_tracking_data(days_old=90)
        
        # Verify no cleanup was performed
        self.assertEqual(result['categories_cleaned'], 0)
        self.assertEqual(result['options_cleaned'], 0)
        
        # Verify data still exists
        self.assertTrue(XeroTrackingCategory.objects.filter(id=category.id).exists())


class CategoryVerificationTaskTest(TestCase):
    """Test category verification tasks"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.account = Account.objects.create(
            name='Test Account',
            account_type='organization'
        )
        self.provider = IntegrationProvider.objects.create(
            name='xero',
            display_name='Xero',
            provider_type='xero',
            auth_url_template='https://api.xero.com/oauth/authorize',
            token_url='https://api.xero.com/oauth/token'
        )
        self.connection = Integration.objects.create(
            account=self.account,
            provider=self.provider,
            external_account_id='test-xero-org-id',
            external_account_name='Test Xero Org',
            organization_name='Test Organization',
            status='active',
            created_by=self.user
        )
        
        # Create test tracking category and rule
        self.category = XeroTrackingCategory.objects.create(
            connection=self.connection,
            xero_category_id='office-supplies-cat',
            name='Office Supplies',
            status='ACTIVE'
        )
        
        self.rule = CategoryDetectionRule.objects.create(
            connection=self.connection,
            name='Office Supplies Rule',
            suggested_category=self.category,
            conditions=[{'field': 'description', 'operator': 'CONTAINS', 'value': 'office'}]
        )
        
        self.suggestion = CategorySuggestion.objects.create(
            connection=self.connection,
            detection_rule=self.rule,
            xero_transaction_id='txn-123',
            suggested_category=self.category,
            status='APPLIED'
        )

    def test_verify_transaction_categorization_success(self):
        """Test successful verification task execution"""
        from data_quality.tasks import verify_transaction_categorization
        
        # Execute task
        result = verify_transaction_categorization(self.suggestion.id)
        
        # Verify placeholder result
        self.assertTrue(result['success'])
        self.assertEqual(result['suggestion_id'], self.suggestion.id)
        self.assertEqual(result['transaction_id'], 'txn-123')
        self.assertEqual(result['verification_status'], 'pending_implementation')

    def test_verify_transaction_categorization_invalid_suggestion(self):
        """Test verification task with invalid suggestion ID"""
        from data_quality.tasks import verify_transaction_categorization
        
        # Execute task with invalid ID
        result = verify_transaction_categorization(99999)
        
        # Verify error handling
        self.assertFalse(result['success'])
        self.assertIn('not found', result['error'])