"""
Tests for Xero tracking categories sync service.
"""
from django.test import TestCase
from unittest.mock import Mock, patch, MagicMock
from django.utils import timezone
from datetime import timedelta

from integrations.models import Integration
from integrations.models import IntegrationProvider
from data_quality.models import XeroTrackingCategory, XeroTrackingOption
from data_quality.services.xero_sync import XeroTrackingSyncService
from core.models import Account
from django.contrib.auth.models import User


class XeroTrackingSyncServiceTest(TestCase):
    """Test XeroTrackingSyncService"""
    
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
        
        self.sync_service = XeroTrackingSyncService(self.connection)
    
    def test_sync_service_initialization(self):
        """Test that sync service initializes correctly"""
        self.assertEqual(self.sync_service.connection, self.connection)
        self.assertIsNotNone(self.sync_service.connection)
    
    @patch('data_quality.services.xero_sync.XeroTrackingSyncService._get_xero_api_client')
    def test_sync_tracking_categories_success(self, mock_get_client):
        """Test successful sync of tracking categories from Xero"""
        # Mock Xero API response
        mock_api_client = Mock()
        mock_get_client.return_value = mock_api_client
        
        # Mock tracking categories response
        mock_tracking_category = Mock()
        mock_tracking_category.tracking_category_id = 'cat-uuid-123'
        mock_tracking_category.name = 'Expense Types'
        mock_tracking_category.status = 'ACTIVE'
        
        mock_tracking_option_1 = Mock()
        mock_tracking_option_1.tracking_option_id = 'opt-uuid-456'
        mock_tracking_option_1.name = 'Office Supplies'
        mock_tracking_option_1.status = 'ACTIVE'
        
        mock_tracking_option_2 = Mock()
        mock_tracking_option_2.tracking_option_id = 'opt-uuid-789'
        mock_tracking_option_2.name = 'Travel'
        mock_tracking_option_2.status = 'ACTIVE'
        
        mock_tracking_category.options = [mock_tracking_option_1, mock_tracking_option_2]
        
        mock_response = Mock()
        mock_response.tracking_categories = [mock_tracking_category]
        
        mock_api_client.get_tracking_categories.return_value = mock_response
        
        # Execute sync
        result = self.sync_service.sync_tracking_categories()
        
        # Verify API was called correctly
        mock_api_client.get_tracking_categories.assert_called_once_with(xero_tenant_id=self.connection.tenant_id)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['categories_synced'], 1)
        self.assertEqual(result['options_synced'], 2)
        
        # Verify database records were created
        category = XeroTrackingCategory.objects.get(
            connection=self.connection,
            xero_category_id='cat-uuid-123'
        )
        self.assertEqual(category.name, 'Expense Types')
        self.assertEqual(category.status, 'ACTIVE')
        
        # Verify options were created
        options = XeroTrackingOption.objects.filter(category=category)
        self.assertEqual(options.count(), 2)
        
        option_names = [opt.name for opt in options]
        self.assertIn('Office Supplies', option_names)
        self.assertIn('Travel', option_names)
    
    @patch('data_quality.services.xero_sync.XeroTrackingSyncService._get_xero_api_client')
    def test_sync_tracking_categories_update_existing(self, mock_get_client):
        """Test that existing categories are updated during sync"""
        # Create existing category
        existing_category = XeroTrackingCategory.objects.create(
            connection=self.connection,
            xero_category_id='cat-uuid-123',
            name='Old Name',
            status='ACTIVE'
        )
        old_sync_time = existing_category.last_synced_at
        
        # Mock Xero API response with updated data
        mock_api_client = Mock()
        mock_get_client.return_value = mock_api_client
        
        mock_tracking_category = Mock()
        mock_tracking_category.tracking_category_id = 'cat-uuid-123'
        mock_tracking_category.name = 'Updated Name'  # Changed name
        mock_tracking_category.status = 'ARCHIVED'   # Changed status
        mock_tracking_category.options = []
        
        mock_response = Mock()
        mock_response.tracking_categories = [mock_tracking_category]
        mock_api_client.get_tracking_categories.return_value = mock_response
        
        # Execute sync
        result = self.sync_service.sync_tracking_categories()
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['categories_synced'], 1)
        self.assertEqual(result['categories_updated'], 1)
        self.assertEqual(result['categories_created'], 0)
        
        # Verify existing category was updated
        updated_category = XeroTrackingCategory.objects.get(id=existing_category.id)
        self.assertEqual(updated_category.name, 'Updated Name')
        self.assertEqual(updated_category.status, 'ARCHIVED')
        self.assertGreater(updated_category.last_synced_at, old_sync_time)
    
    @patch('data_quality.services.xero_sync.XeroTrackingSyncService._get_xero_api_client')
    def test_sync_tracking_categories_xero_api_error(self, mock_get_client):
        """Test handling of Xero API errors during sync"""
        # Mock API client that raises an exception
        mock_api_client = Mock()
        mock_get_client.return_value = mock_api_client
        mock_api_client.get_tracking_categories.side_effect = Exception("Xero API Error")
        
        # Execute sync
        result = self.sync_service.sync_tracking_categories()
        
        # Verify error handling
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertEqual(result['error'], 'Xero API Error')
        
        # Verify no database records were created
        self.assertEqual(XeroTrackingCategory.objects.count(), 0)
    
    @patch('data_quality.services.xero_sync.XeroTrackingSyncService._get_xero_api_client')
    def test_sync_removes_deleted_categories(self, mock_get_client):
        """Test that categories deleted in Xero are marked as archived locally"""
        # Create existing categories
        category_1 = XeroTrackingCategory.objects.create(
            connection=self.connection,
            xero_category_id='cat-uuid-123',
            name='Category 1',
            status='ACTIVE'
        )
        
        category_2 = XeroTrackingCategory.objects.create(
            connection=self.connection,
            xero_category_id='cat-uuid-456',
            name='Category 2',
            status='ACTIVE'
        )
        
        # Mock Xero API response with only one category (one was deleted)
        mock_api_client = Mock()
        mock_get_client.return_value = mock_api_client
        
        mock_tracking_category = Mock()
        mock_tracking_category.tracking_category_id = 'cat-uuid-123'
        mock_tracking_category.name = 'Category 1'
        mock_tracking_category.status = 'ACTIVE'
        mock_tracking_category.options = []
        
        mock_response = Mock()
        mock_response.tracking_categories = [mock_tracking_category]
        mock_api_client.get_tracking_categories.return_value = mock_response
        
        # Execute sync
        result = self.sync_service.sync_tracking_categories()
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['categories_archived'], 1)
        
        # Verify category_2 was archived (not deleted, to preserve referential integrity)
        category_2.refresh_from_db()
        self.assertEqual(category_2.status, 'ARCHIVED')
        
        # Verify category_1 is still active
        category_1.refresh_from_db()
        self.assertEqual(category_1.status, 'ACTIVE')
    
    @patch('data_quality.services.xero_sync.XeroTrackingSyncService._get_xero_api_client')
    def test_sync_handles_options_changes(self, mock_get_client):
        """Test that options are properly added, updated, and archived"""
        # Create existing category with options
        category = XeroTrackingCategory.objects.create(
            connection=self.connection,
            xero_category_id='cat-uuid-123',
            name='Expense Types',
            status='ACTIVE'
        )
        
        existing_option = XeroTrackingOption.objects.create(
            category=category,
            xero_option_id='opt-uuid-456',
            name='Old Option Name',
            status='ACTIVE'
        )
        
        option_to_archive = XeroTrackingOption.objects.create(
            category=category,
            xero_option_id='opt-uuid-999',
            name='Option to Archive',
            status='ACTIVE'
        )
        
        # Mock Xero API response
        mock_api_client = Mock()
        mock_get_client.return_value = mock_api_client
        
        # Existing option with updated name
        mock_existing_option = Mock()
        mock_existing_option.tracking_option_id = 'opt-uuid-456'
        mock_existing_option.name = 'Updated Option Name'
        mock_existing_option.status = 'ACTIVE'
        
        # New option
        mock_new_option = Mock()
        mock_new_option.tracking_option_id = 'opt-uuid-789'
        mock_new_option.name = 'New Option'
        mock_new_option.status = 'ACTIVE'
        
        mock_tracking_category = Mock()
        mock_tracking_category.tracking_category_id = 'cat-uuid-123'
        mock_tracking_category.name = 'Expense Types'
        mock_tracking_category.status = 'ACTIVE'
        mock_tracking_category.options = [mock_existing_option, mock_new_option]
        
        mock_response = Mock()
        mock_response.tracking_categories = [mock_tracking_category]
        mock_api_client.get_tracking_categories.return_value = mock_response
        
        # Execute sync
        result = self.sync_service.sync_tracking_categories()
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['options_synced'], 2)
        self.assertEqual(result['options_created'], 1)
        self.assertEqual(result['options_updated'], 1)
        self.assertEqual(result['options_archived'], 1)
        
        # Verify existing option was updated
        existing_option.refresh_from_db()
        self.assertEqual(existing_option.name, 'Updated Option Name')
        
        # Verify new option was created
        new_option = XeroTrackingOption.objects.get(
            category=category,
            xero_option_id='opt-uuid-789'
        )
        self.assertEqual(new_option.name, 'New Option')
        
        # Verify old option was archived
        option_to_archive.refresh_from_db()
        self.assertEqual(option_to_archive.status, 'ARCHIVED')
    
    def test_get_cached_tracking_categories(self):
        """Test retrieving cached tracking categories for UI"""
        # Create test data
        category = XeroTrackingCategory.objects.create(
            connection=self.connection,
            xero_category_id='cat-uuid-123',
            name='Expense Types',
            status='ACTIVE'
        )
        
        option_1 = XeroTrackingOption.objects.create(
            category=category,
            xero_option_id='opt-uuid-456',
            name='Office Supplies',
            status='ACTIVE'
        )
        
        option_2 = XeroTrackingOption.objects.create(
            category=category,
            xero_option_id='opt-uuid-789',
            name='Travel',
            status='ACTIVE'
        )
        
        # Archived option should not be included
        XeroTrackingOption.objects.create(
            category=category,
            xero_option_id='opt-uuid-999',
            name='Archived Option',
            status='ARCHIVED'
        )
        
        # Get cached categories
        result = self.sync_service.get_cached_tracking_categories()
        
        # Verify structure
        self.assertEqual(len(result), 1)
        
        category_data = result[0]
        self.assertEqual(category_data['id'], 'cat-uuid-123')
        self.assertEqual(category_data['name'], 'Expense Types')
        self.assertEqual(len(category_data['options']), 2)  # Only active options
        
        option_names = [opt['name'] for opt in category_data['options']]
        self.assertIn('Office Supplies', option_names)
        self.assertIn('Travel', option_names)
        self.assertNotIn('Archived Option', option_names)
    
    def test_get_cached_tracking_categories_empty(self):
        """Test retrieving cached categories when none exist"""
        result = self.sync_service.get_cached_tracking_categories()
        self.assertEqual(result, [])
    
    def test_get_cached_tracking_categories_only_active(self):
        """Test that only active categories are returned"""
        # Create active category
        active_category = XeroTrackingCategory.objects.create(
            connection=self.connection,
            xero_category_id='cat-uuid-123',
            name='Active Category',
            status='ACTIVE'
        )
        
        # Create archived category
        XeroTrackingCategory.objects.create(
            connection=self.connection,
            xero_category_id='cat-uuid-456',
            name='Archived Category',
            status='ARCHIVED'
        )
        
        result = self.sync_service.get_cached_tracking_categories()
        
        # Should only return active category
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], 'Active Category')
    
    @patch('data_quality.services.xero_sync.XeroTrackingSyncService._get_xero_api_client')
    def test_sync_preserves_connection_isolation(self, mock_get_client):
        """Test that sync only affects the specific connection"""
        # Create another connection
        other_connection = Integration.objects.create(
            account=self.account,
            provider=self.provider,
            external_account_id='other-xero-org-id',
            external_account_name='Other Xero Org',
            organization_name='Other Organization',
            status='active',
            created_by=self.user
        )
        
        # Create category for other connection
        other_category = XeroTrackingCategory.objects.create(
            connection=other_connection,
            xero_category_id='other-cat-uuid',
            name='Other Category',
            status='ACTIVE'
        )
        
        # Mock API response for our connection
        mock_api_client = Mock()
        mock_get_client.return_value = mock_api_client
        
        mock_tracking_category = Mock()
        mock_tracking_category.tracking_category_id = 'our-cat-uuid'
        mock_tracking_category.name = 'Our Category'
        mock_tracking_category.status = 'ACTIVE'
        mock_tracking_category.options = []
        
        mock_response = Mock()
        mock_response.tracking_categories = [mock_tracking_category]
        mock_api_client.get_tracking_categories.return_value = mock_response
        
        # Execute sync
        result = self.sync_service.sync_tracking_categories()
        
        # Verify sync succeeded
        self.assertTrue(result['success'])
        
        # Verify our connection has the new category
        our_categories = XeroTrackingCategory.objects.filter(connection=self.connection)
        self.assertEqual(our_categories.count(), 1)
        self.assertEqual(our_categories.first().name, 'Our Category')
        
        # Verify other connection's category was not affected
        other_category.refresh_from_db()
        self.assertEqual(other_category.name, 'Other Category')
        self.assertEqual(other_category.status, 'ACTIVE')
        
        # Verify total categories
        total_categories = XeroTrackingCategory.objects.count()
        self.assertEqual(total_categories, 2)