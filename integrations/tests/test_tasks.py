"""
Tests for integration tasks, specifically accounting sync integration.
"""
from django.test import TestCase
from unittest.mock import patch, MagicMock, call
from django.contrib.auth.models import User
from core.models import Account, AccountUser
from integrations.models import Integration, IntegrationProvider
from integrations.tasks import sync_single_integration


class SyncSingleIntegrationTestCase(TestCase):
    """Test suite for sync_single_integration task with accounting sync"""

    def setUp(self):
        """Set up test fixtures"""
        # Create user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # Create account
        self.account = Account.objects.create(
            name='Test Account',
            account_type='organization'
        )

        # Link user to account
        AccountUser.objects.create(
            user=self.user,
            account=self.account,
            role='owner'
        )

        # Create Xero provider
        self.provider, _ = IntegrationProvider.objects.get_or_create(
            name='xero',
            defaults={
                'display_name': 'Xero',
                'provider_type': 'xero',
                'auth_url_template': 'https://login.xero.com/identity/connect/authorize',
                'token_url': 'https://identity.xero.com/connect/token',
                'scopes_default': ['offline_access', 'accounting.transactions']
            }
        )

        # Create integration
        self.integration = Integration.objects.create(
            account=self.account,
            provider=self.provider,
            organization_name='Test Org',
            external_account_id='test-xero-org-123',
            status='active'
        )

    @patch('integrations.tasks.IntegrationManager.sync_integration')
    @patch('integrations.services.xero_accounting_sync_service.XeroAccountingSyncService')
    def test_sync_includes_accounting_data_after_bank_sync(self, mock_accounting_service_class, mock_sync_integration):
        """Test that accounting sync runs after successful bank transaction sync"""
        # Mock bank sync success
        mock_sync_record = MagicMock()
        mock_sync_record.status = 'completed'
        mock_sync_record.records_success = 100
        mock_sync_record.error_message = None
        mock_sync_record.metadata = {}
        mock_sync_integration.return_value = mock_sync_record

        # Mock accounting sync service
        mock_service_instance = MagicMock()
        mock_accounting_result = {
            'contacts': {'synced': 50, 'errors': 0},
            'invoices': {'synced': 75, 'errors': 0},
            'reconciliation': {'auto_matched': 10}
        }
        mock_service_instance.sync_all.return_value = mock_accounting_result
        mock_accounting_service_class.return_value = mock_service_instance

        # Run task
        result = sync_single_integration(self.integration.id, 'incremental')

        # Verify bank sync was called
        mock_sync_integration.assert_called_once_with(self.integration, 'incremental')

        # Verify accounting sync was called
        mock_accounting_service_class.assert_called_once_with(self.integration)
        mock_service_instance.sync_all.assert_called_once()

        # Verify result includes accounting data
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['accounting']['contacts'], 50)
        self.assertEqual(result['accounting']['invoices'], 75)
        self.assertEqual(result['accounting']['reconciled'], 10)

    @patch('integrations.tasks.IntegrationManager.sync_integration')
    @patch('integrations.services.xero_accounting_sync_service.XeroAccountingSyncService')
    def test_accounting_sync_skipped_if_bank_sync_fails(self, mock_accounting_service_class, mock_sync_integration):
        """Test that accounting sync is skipped if bank transaction sync fails"""
        # Mock bank sync failure
        mock_sync_record = MagicMock()
        mock_sync_record.status = 'failed'
        mock_sync_record.records_success = 0
        mock_sync_record.error_message = 'API connection failed'
        mock_sync_integration.return_value = mock_sync_record

        # Run task
        result = sync_single_integration(self.integration.id, 'incremental')

        # Verify bank sync was called
        mock_sync_integration.assert_called_once()

        # Verify accounting sync was NOT called
        mock_accounting_service_class.assert_not_called()

        # Verify result shows failure
        self.assertEqual(result['status'], 'failed')
        self.assertIn('API connection failed', result['error_message'])

    @patch('integrations.tasks.IntegrationManager.sync_integration')
    @patch('integrations.services.xero_accounting_sync_service.XeroAccountingSyncService')
    def test_accounting_sync_errors_are_logged_but_dont_fail_task(self, mock_accounting_service_class, mock_sync_integration):
        """Test that accounting sync errors are logged but don't fail the entire task"""
        # Mock bank sync success
        mock_sync_record = MagicMock()
        mock_sync_record.status = 'completed'
        mock_sync_record.records_success = 100
        mock_sync_record.error_message = None
        mock_sync_record.metadata = {}
        mock_sync_integration.return_value = mock_sync_record

        # Mock accounting sync to raise exception
        mock_service_instance = MagicMock()
        mock_service_instance.sync_all.side_effect = Exception("Xero API rate limit")
        mock_accounting_service_class.return_value = mock_service_instance

        # Run task
        result = sync_single_integration(self.integration.id, 'incremental')

        # Verify bank sync succeeded
        self.assertEqual(result['status'], 'completed')

        # Verify accounting sync was attempted
        mock_service_instance.sync_all.assert_called_once()

        # Verify error was logged but task succeeded
        self.assertEqual(result['records_synced'], 100)
        # Accounting data should show error
        self.assertIn('accounting', result)
        self.assertEqual(result['accounting']['error'], 'Xero API rate limit')

    @patch('integrations.tasks.IntegrationManager.sync_integration')
    @patch('integrations.services.xero_accounting_sync_service.XeroAccountingSyncService')
    def test_sync_metadata_includes_accounting_counts(self, mock_accounting_service_class, mock_sync_integration):
        """Test that sync record metadata is updated with accounting counts"""
        # Mock bank sync success
        mock_sync_record = MagicMock()
        mock_sync_record.status = 'completed'
        mock_sync_record.records_success = 100
        mock_sync_record.error_message = None
        mock_sync_record.metadata = {}
        mock_sync_integration.return_value = mock_sync_record

        # Mock accounting sync service
        mock_service_instance = MagicMock()
        mock_accounting_result = {
            'contacts': {'synced': 25, 'errors': 1},
            'invoices': {'synced': 60, 'errors': 0},
            'reconciliation': {'auto_matched': 5, 'suggested': 3}
        }
        mock_service_instance.sync_all.return_value = mock_accounting_result
        mock_accounting_service_class.return_value = mock_service_instance

        # Run task
        result = sync_single_integration(self.integration.id, 'incremental')

        # Verify metadata was updated
        mock_sync_record.save.assert_called()
        self.assertEqual(mock_sync_record.metadata['accounting']['contacts'], 25)
        self.assertEqual(mock_sync_record.metadata['accounting']['invoices'], 60)
        self.assertEqual(mock_sync_record.metadata['accounting']['reconciled'], 5)

    @patch('integrations.tasks.IntegrationManager.sync_integration')
    def test_integration_not_found_returns_error(self, mock_sync_integration):
        """Test that missing integration returns error result"""
        # Run task with non-existent ID
        result = sync_single_integration(99999, 'incremental')

        # Verify error result
        self.assertEqual(result['status'], 'error')
        self.assertIn('not found', result['error_message'])

        # Verify sync was not attempted
        mock_sync_integration.assert_not_called()

    @patch('integrations.tasks.IntegrationManager.sync_integration')
    @patch('integrations.services.xero_accounting_sync_service.XeroAccountingSyncService')
    def test_full_sync_type_passed_through(self, mock_accounting_service_class, mock_sync_integration):
        """Test that sync_type parameter is correctly passed to sync methods"""
        # Mock bank sync success
        mock_sync_record = MagicMock()
        mock_sync_record.status = 'completed'
        mock_sync_record.records_success = 200
        mock_sync_record.error_message = None
        mock_sync_record.metadata = {}
        mock_sync_integration.return_value = mock_sync_record

        # Mock accounting sync
        mock_service_instance = MagicMock()
        mock_service_instance.sync_all.return_value = {
            'contacts': {'synced': 100},
            'invoices': {'synced': 150}
        }
        mock_accounting_service_class.return_value = mock_service_instance

        # Run task with full sync
        result = sync_single_integration(self.integration.id, 'full')

        # Verify full sync was passed to bank sync
        mock_sync_integration.assert_called_once_with(self.integration, 'full')

        # Verify accounting sync was called
        mock_service_instance.sync_all.assert_called_once()
