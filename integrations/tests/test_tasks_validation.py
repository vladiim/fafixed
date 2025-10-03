"""
Tests for automatic validation integration in sync tasks.
"""
from django.test import TestCase
from unittest.mock import patch, MagicMock
from django.contrib.auth.models import User
from core.models import Account, AccountUser
from integrations.models import Integration, IntegrationProvider
from connections.models import Connection
from integrations.tasks import sync_single_integration


class SyncWithValidationTestCase(TestCase):
    """Test suite for automatic validation after sync"""

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

        # Create provider for connection
        from connections.models import Provider
        self.conn_provider, _ = Provider.objects.get_or_create(
            name='xero',
            defaults={
                'display_name': 'Xero',
                'provider_type': 'xero',
                'auth_url_template': 'https://login.xero.com/identity/connect/authorize',
                'token_url': 'https://identity.xero.com/connect/token',
                'scopes_default': ['offline_access', 'accounting.transactions']
            }
        )

        # Create connection
        self.connection = Connection.objects.create(
            account=self.account,
            provider=self.conn_provider,
            organization_name='Test Org',
            external_account_id='test-xero-org-123',
            external_account_name='Test Account',
            status='active'
        )

    @patch('integrations.tasks.IntegrationManager.sync_integration')
    @patch('integrations.services.xero_accounting_sync_service.XeroAccountingSyncService')
    @patch('data_quality.validation.engine.ValidationEngine.run_validation')
    def test_validation_runs_after_successful_sync(self, mock_validation, mock_accounting_service_class, mock_sync_integration):
        """Test that validation engine runs after successful accounting sync"""
        # Mock bank sync success
        mock_sync_record = MagicMock()
        mock_sync_record.status = 'completed'
        mock_sync_record.records_success = 100
        mock_sync_record.error_message = None
        mock_sync_record.metadata = {}
        mock_sync_integration.return_value = mock_sync_record

        # Mock accounting sync
        mock_service_instance = MagicMock()
        mock_service_instance.sync_all.return_value = {
            'contacts': {'synced': 50},
            'invoices': {'synced': 75}
        }
        mock_accounting_service_class.return_value = mock_service_instance

        # Mock validation run
        mock_validation_run = MagicMock()
        mock_validation_run.issues_found = 5
        mock_validation_run.rules_passed = 2
        mock_validation_run.rules_failed = 3
        mock_validation.return_value = mock_validation_run

        # Run task
        result = sync_single_integration(self.integration.id, 'incremental')

        # Verify validation was called
        mock_validation.assert_called_once_with(self.connection, triggered_by='automatic_sync')

        # Verify result includes validation data
        self.assertIn('validation', result)
        self.assertEqual(result['validation']['issues_found'], 5)

    @patch('integrations.tasks.IntegrationManager.sync_integration')
    @patch('integrations.services.xero_accounting_sync_service.XeroAccountingSyncService')
    @patch('data_quality.validation.engine.ValidationEngine.run_validation')
    def test_validation_skipped_if_sync_fails(self, mock_validation, mock_accounting_service_class, mock_sync_integration):
        """Test that validation is skipped if bank sync fails"""
        # Mock bank sync failure
        mock_sync_record = MagicMock()
        mock_sync_record.status = 'failed'
        mock_sync_record.records_success = 0
        mock_sync_record.error_message = 'API error'
        mock_sync_integration.return_value = mock_sync_record

        # Run task
        result = sync_single_integration(self.integration.id, 'incremental')

        # Verify validation was NOT called
        mock_validation.assert_not_called()
        mock_accounting_service_class.assert_not_called()

    @patch('integrations.tasks.IntegrationManager.sync_integration')
    @patch('integrations.services.xero_accounting_sync_service.XeroAccountingSyncService')
    @patch('data_quality.validation.engine.ValidationEngine.run_validation')
    def test_validation_errors_dont_fail_sync(self, mock_validation, mock_accounting_service_class, mock_sync_integration):
        """Test that validation errors are logged but don't fail the sync"""
        # Mock bank sync success
        mock_sync_record = MagicMock()
        mock_sync_record.status = 'completed'
        mock_sync_record.records_success = 100
        mock_sync_record.error_message = None
        mock_sync_record.metadata = {}
        mock_sync_integration.return_value = mock_sync_record

        # Mock accounting sync
        mock_service_instance = MagicMock()
        mock_service_instance.sync_all.return_value = {
            'contacts': {'synced': 50}
        }
        mock_accounting_service_class.return_value = mock_service_instance

        # Mock validation to raise exception
        mock_validation.side_effect = Exception("Validation engine crashed")

        # Run task
        result = sync_single_integration(self.integration.id, 'incremental')

        # Verify sync still succeeded
        self.assertEqual(result['status'], 'completed')

        # Verify validation was attempted
        mock_validation.assert_called_once()

        # Verify error was logged in result
        self.assertIn('validation', result)
        self.assertIn('error', result['validation'])

    @patch('integrations.tasks.IntegrationManager.sync_integration')
    @patch('integrations.services.xero_accounting_sync_service.XeroAccountingSyncService')
    @patch('data_quality.validation.engine.ValidationEngine.run_validation')
    def test_validation_metadata_stored_in_sync_record(self, mock_validation, mock_accounting_service_class, mock_sync_integration):
        """Test that validation results are stored in sync record metadata"""
        # Mock bank sync success
        mock_sync_record = MagicMock()
        mock_sync_record.status = 'completed'
        mock_sync_record.records_success = 100
        mock_sync_record.error_message = None
        mock_sync_record.metadata = {}
        mock_sync_integration.return_value = mock_sync_record

        # Mock accounting sync
        mock_service_instance = MagicMock()
        mock_service_instance.sync_all.return_value = {
            'contacts': {'synced': 25}
        }
        mock_accounting_service_class.return_value = mock_service_instance

        # Mock validation run
        mock_validation_run = MagicMock()
        mock_validation_run.issues_found = 3
        mock_validation_run.rules_passed = 5
        mock_validation_run.rules_failed = 1
        mock_validation.return_value = mock_validation_run

        # Run task
        result = sync_single_integration(self.integration.id, 'incremental')

        # Verify metadata was updated
        mock_sync_record.save.assert_called()
        self.assertEqual(mock_sync_record.metadata['validation']['issues_found'], 3)
        self.assertEqual(mock_sync_record.metadata['validation']['rules_passed'], 5)
        self.assertEqual(mock_sync_record.metadata['validation']['rules_failed'], 1)

    @patch('integrations.tasks.IntegrationManager.sync_integration')
    @patch('integrations.services.xero_accounting_sync_service.XeroAccountingSyncService')
    @patch('data_quality.validation.engine.ValidationEngine.run_validation')
    def test_validation_skipped_if_no_connection(self, mock_validation, mock_accounting_service_class, mock_sync_integration):
        """Test that validation is skipped if connection doesn't exist"""
        # Delete the connection
        self.connection.delete()

        # Mock bank sync success
        mock_sync_record = MagicMock()
        mock_sync_record.status = 'completed'
        mock_sync_record.records_success = 100
        mock_sync_record.error_message = None
        mock_sync_record.metadata = {}
        mock_sync_integration.return_value = mock_sync_record

        # Mock accounting sync
        mock_service_instance = MagicMock()
        mock_service_instance.sync_all.return_value = {
            'contacts': {'synced': 10}
        }
        mock_accounting_service_class.return_value = mock_service_instance

        # Run task
        result = sync_single_integration(self.integration.id, 'incremental')

        # Verify validation was NOT called (no connection found)
        mock_validation.assert_not_called()

        # But sync should still succeed
        self.assertEqual(result['status'], 'completed')
