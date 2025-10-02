"""
Tests for connections views, specifically the refresh_sync_integration functionality.
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from unittest.mock import patch, MagicMock
from core.models import Account, AccountUser
from integrations.models import Integration, IntegrationProvider


class RefreshSyncIntegrationTestCase(TestCase):
    """Test suite for refresh_sync_integration view"""

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

        # Set up client and login
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def test_refresh_sync_requires_authentication(self):
        """Test that refresh_sync requires user to be logged in"""
        # Logout
        self.client.logout()

        url = reverse('connections:refresh_sync_integration',
                     kwargs={'integration_prefix_id': self.integration.prefix_id})
        response = self.client.get(url)

        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.url)

    def test_refresh_sync_requires_user_access(self):
        """Test that user must have access to the integration"""
        # Create another user without access
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpass123'
        )
        self.client.logout()
        self.client.login(username='otheruser', password='otherpass123')

        url = reverse('connections:refresh_sync_integration',
                     kwargs={'integration_prefix_id': self.integration.prefix_id})
        response = self.client.get(url, follow=True)

        # Should redirect to dashboard with error (view catches get_object_or_404)
        self.assertRedirects(response, reverse('dashboard'))
        messages = list(response.context['messages'])
        self.assertTrue(any('Failed' in str(msg) for msg in messages))

    @patch('integrations.tasks.sync_single_integration')
    def test_refresh_sync_triggers_celery_task(self, mock_sync_task):
        """Test that refresh_sync triggers the Celery sync task"""
        # Mock the Celery task
        mock_delay = MagicMock()
        mock_sync_task.delay = mock_delay

        url = reverse('connections:refresh_sync_integration',
                     kwargs={'integration_prefix_id': self.integration.prefix_id})
        response = self.client.get(url, follow=True)

        # Should trigger Celery task with integration ID and incremental sync
        mock_delay.assert_called_once_with(self.integration.id, 'incremental')

        # Should redirect to dashboard
        self.assertRedirects(response, reverse('dashboard'))

    @patch('integrations.tasks.sync_single_integration')
    def test_refresh_sync_shows_success_message(self, mock_sync_task):
        """Test that refresh_sync shows appropriate success message"""
        mock_delay = MagicMock()
        mock_sync_task.delay = mock_delay

        url = reverse('connections:refresh_sync_integration',
                     kwargs={'integration_prefix_id': self.integration.prefix_id})
        response = self.client.get(url, follow=True)

        # Check success message
        messages = list(response.context['messages'])
        self.assertEqual(len(messages), 1)
        self.assertIn('Sync started', str(messages[0]))
        self.assertIn('bank data, invoices, and payments', str(messages[0]))

    @patch('integrations.tasks.sync_single_integration')
    def test_refresh_sync_handles_full_sync_parameter(self, mock_sync_task):
        """Test that refresh_sync can trigger full sync via query parameter"""
        mock_delay = MagicMock()
        mock_sync_task.delay = mock_delay

        url = reverse('connections:refresh_sync_integration',
                     kwargs={'integration_prefix_id': self.integration.prefix_id})
        response = self.client.get(url + '?sync_type=full', follow=True)

        # Should trigger full sync
        mock_delay.assert_called_once_with(self.integration.id, 'full')

    @patch('integrations.tasks.sync_single_integration')
    def test_refresh_sync_defaults_to_incremental(self, mock_sync_task):
        """Test that refresh_sync defaults to incremental sync"""
        mock_delay = MagicMock()
        mock_sync_task.delay = mock_delay

        url = reverse('connections:refresh_sync_integration',
                     kwargs={'integration_prefix_id': self.integration.prefix_id})
        response = self.client.get(url, follow=True)

        # Should default to incremental
        mock_delay.assert_called_once_with(self.integration.id, 'incremental')

    def test_refresh_sync_with_invalid_integration_id(self):
        """Test that invalid integration ID redirects to dashboard"""
        url = reverse('connections:refresh_sync_integration',
                     kwargs={'integration_prefix_id': 'int_invalid123'})
        response = self.client.get(url, follow=True)

        # Should redirect to dashboard (view catches exception)
        self.assertRedirects(response, reverse('dashboard'))

    @patch('integrations.tasks.sync_single_integration')
    def test_refresh_sync_handles_exceptions_gracefully(self, mock_sync_task):
        """Test that exceptions are handled with error message"""
        # Mock task to raise exception
        mock_sync_task.delay.side_effect = Exception("Celery connection failed")

        url = reverse('connections:refresh_sync_integration',
                     kwargs={'integration_prefix_id': self.integration.prefix_id})
        response = self.client.get(url, follow=True)

        # Should redirect to dashboard with error message
        self.assertRedirects(response, reverse('dashboard'))
        messages = list(response.context['messages'])
        self.assertEqual(len(messages), 1)
        self.assertIn('Failed to start sync', str(messages[0]))
