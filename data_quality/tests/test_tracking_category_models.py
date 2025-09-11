"""
Tests for Xero tracking category models.
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from datetime import timedelta

from connections.models import Connection, Provider
from data_quality.models import XeroTrackingCategory, XeroTrackingOption
from core.models import Account
from django.contrib.auth.models import User


class XeroTrackingCategoryModelTest(TestCase):
    """Test XeroTrackingCategory model"""
    
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
        self.provider = Provider.objects.create(
            name='xero',
            display_name='Xero',
            provider_type='xero',
            auth_url_template='https://api.xero.com/oauth/authorize',
            token_url='https://api.xero.com/oauth/token'
        )
        self.connection = Connection.objects.create(
            account=self.account,
            provider=self.provider,
            external_account_id='test-xero-org-id',
            external_account_name='Test Xero Org',
            organization_name='Test Organization',
            status='active',
            created_by=self.user
        )
    
    def test_create_tracking_category(self):
        """Test creating a tracking category"""
        category = XeroTrackingCategory.objects.create(
            connection=self.connection,
            xero_category_id='test-uuid-123',
            name='Office Expenses',
            status='ACTIVE'
        )
        
        self.assertEqual(category.connection, self.connection)
        self.assertEqual(category.xero_category_id, 'test-uuid-123')
        self.assertEqual(category.name, 'Office Expenses')
        self.assertEqual(category.status, 'ACTIVE')
        self.assertIsNotNone(category.last_synced_at)
    
    def test_tracking_category_str_representation(self):
        """Test string representation of tracking category"""
        category = XeroTrackingCategory.objects.create(
            connection=self.connection,
            xero_category_id='test-uuid-123',
            name='Office Expenses',
            status='ACTIVE'
        )
        
        expected = f"Office Expenses ({self.connection.organization_name})"
        self.assertEqual(str(category), expected)
    
    def test_unique_together_constraint(self):
        """Test unique constraint on connection + xero_category_id"""
        # Create first category
        XeroTrackingCategory.objects.create(
            connection=self.connection,
            xero_category_id='test-uuid-123',
            name='Office Expenses',
            status='ACTIVE'
        )
        
        # Try to create duplicate - should fail
        with self.assertRaises(IntegrityError):
            XeroTrackingCategory.objects.create(
                connection=self.connection,
                xero_category_id='test-uuid-123',  # Same ID
                name='Different Name',
                status='ACTIVE'
            )
    
    def test_different_connections_can_have_same_xero_id(self):
        """Test that different connections can have same Xero category ID"""
        # Create second connection
        connection2 = Connection.objects.create(
            account=self.account,
            provider=self.provider,
            external_account_id='test-xero-org-id-2',
            external_account_name='Second Test Xero Org',
            organization_name='Second Test Organization',
            status='active',
            created_by=self.user
        )
        
        # Create category in first connection
        category1 = XeroTrackingCategory.objects.create(
            connection=self.connection,
            xero_category_id='test-uuid-123',
            name='Office Expenses',
            status='ACTIVE'
        )
        
        # Create category with same Xero ID in second connection - should work
        category2 = XeroTrackingCategory.objects.create(
            connection=connection2,
            xero_category_id='test-uuid-123',  # Same Xero ID, different connection
            name='Office Expenses',
            status='ACTIVE'
        )
        
        self.assertNotEqual(category1.connection, category2.connection)
        self.assertEqual(category1.xero_category_id, category2.xero_category_id)
    
    def test_get_active_categories_for_connection(self):
        """Test getting active categories for a connection"""
        # Create mix of active and archived categories
        active_cat = XeroTrackingCategory.objects.create(
            connection=self.connection,
            xero_category_id='active-uuid',
            name='Active Category',
            status='ACTIVE'
        )
        
        archived_cat = XeroTrackingCategory.objects.create(
            connection=self.connection,
            xero_category_id='archived-uuid',
            name='Archived Category',
            status='ARCHIVED'
        )
        
        # Get active categories
        active_categories = XeroTrackingCategory.objects.filter(
            connection=self.connection,
            status='ACTIVE'
        )
        
        self.assertIn(active_cat, active_categories)
        self.assertNotIn(archived_cat, active_categories)
        self.assertEqual(active_categories.count(), 1)
    
    def test_last_synced_auto_update(self):
        """Test that last_synced_at is automatically updated"""
        category = XeroTrackingCategory.objects.create(
            connection=self.connection,
            xero_category_id='test-uuid-123',
            name='Office Expenses',
            status='ACTIVE'
        )
        
        original_sync_time = category.last_synced_at
        
        # Update the category
        category.name = 'Updated Office Expenses'
        category.save()
        
        # last_synced_at should be updated
        self.assertGreater(category.last_synced_at, original_sync_time)


class XeroTrackingOptionModelTest(TestCase):
    """Test XeroTrackingOption model"""
    
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
        self.provider = Provider.objects.create(
            name='xero',
            display_name='Xero',
            provider_type='xero',
            auth_url_template='https://api.xero.com/oauth/authorize',
            token_url='https://api.xero.com/oauth/token'
        )
        self.connection = Connection.objects.create(
            account=self.account,
            provider=self.provider,
            external_account_id='test-xero-org-id',
            external_account_name='Test Xero Org',
            organization_name='Test Organization',
            status='active',
            created_by=self.user
        )
        self.category = XeroTrackingCategory.objects.create(
            connection=self.connection,
            xero_category_id='category-uuid',
            name='Office Expenses',
            status='ACTIVE'
        )
    
    def test_create_tracking_option(self):
        """Test creating a tracking option"""
        option = XeroTrackingOption.objects.create(
            category=self.category,
            xero_option_id='option-uuid-123',
            name='Stationery',
            status='ACTIVE'
        )
        
        self.assertEqual(option.category, self.category)
        self.assertEqual(option.xero_option_id, 'option-uuid-123')
        self.assertEqual(option.name, 'Stationery')
        self.assertEqual(option.status, 'ACTIVE')
    
    def test_tracking_option_str_representation(self):
        """Test string representation of tracking option"""
        option = XeroTrackingOption.objects.create(
            category=self.category,
            xero_option_id='option-uuid-123',
            name='Stationery',
            status='ACTIVE'
        )
        
        expected = f"Office Expenses: Stationery"
        self.assertEqual(str(option), expected)
    
    def test_unique_together_constraint(self):
        """Test unique constraint on category + xero_option_id"""
        # Create first option
        XeroTrackingOption.objects.create(
            category=self.category,
            xero_option_id='option-uuid-123',
            name='Stationery',
            status='ACTIVE'
        )
        
        # Try to create duplicate - should fail
        with self.assertRaises(IntegrityError):
            XeroTrackingOption.objects.create(
                category=self.category,
                xero_option_id='option-uuid-123',  # Same ID
                name='Different Name',
                status='ACTIVE'
            )
    
    def test_cascade_delete_when_category_deleted(self):
        """Test that options are deleted when category is deleted"""
        option = XeroTrackingOption.objects.create(
            category=self.category,
            xero_option_id='option-uuid-123',
            name='Stationery',
            status='ACTIVE'
        )
        
        # Delete category
        self.category.delete()
        
        # Option should be deleted too
        with self.assertRaises(XeroTrackingOption.DoesNotExist):
            XeroTrackingOption.objects.get(id=option.id)
    
    def test_get_active_options_for_category(self):
        """Test getting active options for a category"""
        # Create mix of active and archived options
        active_option = XeroTrackingOption.objects.create(
            category=self.category,
            xero_option_id='active-option-uuid',
            name='Active Option',
            status='ACTIVE'
        )
        
        archived_option = XeroTrackingOption.objects.create(
            category=self.category,
            xero_option_id='archived-option-uuid',
            name='Archived Option',
            status='ARCHIVED'
        )
        
        # Get active options
        active_options = XeroTrackingOption.objects.filter(
            category=self.category,
            status='ACTIVE'
        )
        
        self.assertIn(active_option, active_options)
        self.assertNotIn(archived_option, active_options)
        self.assertEqual(active_options.count(), 1)
    
    def test_different_categories_can_have_same_xero_option_id(self):
        """Test that different categories can have options with same Xero ID"""
        # Create second category
        category2 = XeroTrackingCategory.objects.create(
            connection=self.connection,
            xero_category_id='category2-uuid',
            name='Travel Expenses',
            status='ACTIVE'
        )
        
        # Create option in first category
        option1 = XeroTrackingOption.objects.create(
            category=self.category,
            xero_option_id='option-uuid-123',
            name='Office Supplies',
            status='ACTIVE'
        )
        
        # Create option with same Xero ID in second category - should work
        option2 = XeroTrackingOption.objects.create(
            category=category2,
            xero_option_id='option-uuid-123',  # Same Xero ID, different category
            name='Travel Supplies',
            status='ACTIVE'
        )
        
        self.assertNotEqual(option1.category, option2.category)
        self.assertEqual(option1.xero_option_id, option2.xero_option_id)
    
    def test_related_name_access(self):
        """Test accessing options through category's related name"""
        option1 = XeroTrackingOption.objects.create(
            category=self.category,
            xero_option_id='option1-uuid',
            name='Option 1',
            status='ACTIVE'
        )
        
        option2 = XeroTrackingOption.objects.create(
            category=self.category,
            xero_option_id='option2-uuid',
            name='Option 2',
            status='ACTIVE'
        )
        
        # Access options through related name
        category_options = self.category.options.all()
        
        self.assertIn(option1, category_options)
        self.assertIn(option2, category_options)
        self.assertEqual(category_options.count(), 2)