"""
Unit tests for connections app models.

These tests focus on model behavior and business logic rather than Django ORM internals.
They're designed to be flexible and survive the upcoming model migration.
"""
import pytest
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta
import json

from core.models import Account
from integrations.models import (
    IntegrationProvider, Integration, IntegrationCredential, 
    OAuthState, IntegrationSync
)
from connections.models import Provider


@pytest.fixture
def user():
    return User.objects.create_user(username='testuser')


@pytest.fixture
def account():
    return Account.objects.create(name='Test Account')


@pytest.fixture
def account2():
    return Account.objects.create(name='Test Account 2')


@pytest.fixture
def provider():
    return IntegrationProvider.objects.create(
        name='xero',
        display_name='Xero',
        provider_type='xero',
        auth_url_template='https://api.xero.com/oauth/authorize',
        token_url='https://api.xero.com/oauth/token',
        scopes_default=['accounting.transactions']
    )


@pytest.fixture
def integration(user, account, provider):
    return Integration.objects.create(
        account=account,
        created_by=user,
        provider=provider,
        external_account_id='xero_123',
        external_account_name='Test Xero Account',
        organization_name='Test Organization'
    )


@pytest.fixture
def credential(integration):
    return IntegrationCredential.objects.create(
        integration=integration,
        access_token='secret_access_token',
        refresh_token='secret_refresh_token',
        scopes=['accounting.transactions']
    )


@pytest.mark.django_db  
class TestProvider:
    """Test new Provider model in connections app"""
    
    def test_provider_creation(self):
        """Provider can be created with valid data"""
        provider = Provider.objects.create(
            name='xero',
            display_name='Xero',
            provider_type='xero',
            auth_url_template='https://api.xero.com/oauth/authorize',
            token_url='https://api.xero.com/oauth/token',
            scopes_default=['accounting.transactions']
        )
        
        assert provider.name == 'xero'
        assert provider.display_name == 'Xero'
        assert provider.is_active is True  # Default value
        assert provider.created_at is not None
        assert provider.updated_at is not None
    
    def test_provider_str_representation(self):
        """Provider string representation uses display_name"""
        provider = Provider.objects.create(
            name='xero',
            display_name='Xero',
            provider_type='xero',
            auth_url_template='https://api.xero.com/oauth/authorize',
            token_url='https://api.xero.com/oauth/token'
        )
        assert str(provider) == 'Xero'
    
    def test_provider_name_uniqueness(self):
        """Provider names must be unique globally"""
        Provider.objects.create(
            name='xero',
            display_name='Xero',
            provider_type='xero',
            auth_url_template='https://api.xero.com/oauth/authorize',
            token_url='https://api.xero.com/oauth/token'
        )
        
        with pytest.raises(Exception):  # IntegrityError
            from django.db import transaction
            with transaction.atomic():
                Provider.objects.create(
                    name='xero',  # Same name
                    display_name='Xero 2',
                    provider_type='xero',
                    auth_url_template='https://api.xero.com/oauth/authorize',
                    token_url='https://api.xero.com/oauth/token'
                )


@pytest.mark.django_db
class TestIntegrationProvider:
    """Test Provider model behavior (currently IntegrationProvider) - LEGACY"""
    
    def test_provider_creation(self, provider):
        """Provider can be created with valid data"""
        assert provider.name == 'xero'
        assert provider.display_name == 'Xero'
        assert provider.is_active is True  # Default value
        assert provider.created_at is not None
        assert provider.updated_at is not None
    
    def test_provider_str_representation(self, provider):
        """Provider string representation uses display_name"""
        assert str(provider) == 'Xero'
    
    def test_provider_name_uniqueness(self, provider):
        """Provider names must be unique globally (not per account)"""
        with pytest.raises(Exception):  # Could be IntegrityError or ValidationError
            IntegrationProvider.objects.create(
                name='xero',  # Same name
                display_name='Xero 2',
                provider_type='xero',
                auth_url_template='https://api.xero.com/oauth/authorize',
                token_url='https://api.xero.com/oauth/token'
            )
    
    def test_provider_optional_fields(self):
        """Provider works with optional fields"""
        provider = IntegrationProvider.objects.create(
            name='test',
            display_name='Test',
            provider_type='xero',
            auth_url_template='https://test.com',
            token_url='https://test.com',
            revoke_url='https://test.com/revoke'
        )
        assert provider.revoke_url == 'https://test.com/revoke'
    
    def test_provider_json_field_default(self):
        """Provider scopes_default field works as JSON with list default"""
        provider = IntegrationProvider.objects.create(
            name='test',
            display_name='Test',
            provider_type='xero',
            auth_url_template='https://test.com',
            token_url='https://test.com'
        )
        assert provider.scopes_default == []


@pytest.mark.django_db
class TestIntegration:
    """Test Connection model behavior (currently Integration)"""
    
    def test_integration_creation(self, integration, account, provider):
        """Integration can be created with valid data"""
        assert integration.account == account
        assert integration.provider == provider
        assert integration.status == 'pending'  # Default value
        assert integration.prefix_id.startswith('int_')  # Has prefix ID
        assert integration.created_at is not None
    
    def test_integration_str_representation(self, integration):
        """Integration string representation includes key info"""
        expected = "Test Account - Xero - Test Organization"
        assert str(integration) == expected
    
    def test_integration_status_choices(self, integration):
        """Integration status can be set to valid choices"""
        valid_statuses = ['pending', 'active', 'expired', 'revoked', 'error']
        for status in valid_statuses:
            integration.status = status
            integration.save()  # Should not raise
            integration.refresh_from_db()
            assert integration.status == status
    
    def test_integration_uniqueness_per_account(self, user, account, account2, provider):
        """Integration uniqueness is per account - same provider can exist for different accounts"""
        # Create integration for account1
        integration1 = Integration.objects.create(
            account=account,
            created_by=user,
            provider=provider,
            external_account_id='xero_123',
            external_account_name='Test Account',
            organization_name='Test Org'
        )
        
        # Same provider + external_account_id should fail for same account
        from django.db import transaction
        with pytest.raises(Exception):  # IntegrityError
            with transaction.atomic():
                Integration.objects.create(
                    account=account,
                    created_by=user,
                    provider=provider,
                    external_account_id='xero_123',
                    external_account_name='Test Account',
                    organization_name='Test Org'
                )
        
        # But should work for different account
        integration2 = Integration.objects.create(
            account=account2,
            created_by=user,
            provider=provider,
            external_account_id='xero_123',
            external_account_name='Test Account',
            organization_name='Test Org'
        )
        assert integration2.account == account2
    
    def test_integration_optional_timestamps(self, integration):
        """Integration optional timestamp fields work correctly"""
        # Initially null
        assert integration.connected_at is None
        assert integration.last_sync_at is None
        
        # Can be set
        now = timezone.now()
        integration.connected_at = now
        integration.last_sync_at = now
        integration.save()
        
        integration.refresh_from_db()
        assert integration.connected_at == now
        assert integration.last_sync_at == now
    
    def test_integration_config_json_field(self, user, account, provider):
        """Integration config field stores JSON data"""
        config_data = {'api_version': '2.0', 'features': ['transactions']}
        
        integration = Integration.objects.create(
            account=account,
            created_by=user,
            provider=provider,
            external_account_id='xero_123',
            external_account_name='Test Account',
            organization_name='Test Org',
            config=config_data
        )
        assert integration.config == config_data
    
    def test_integration_ordering(self, user, account, provider):
        """Integrations are ordered by creation date descending"""
        integration1 = Integration.objects.create(
            account=account,
            created_by=user,
            provider=provider,
            external_account_id='xero_123',
            external_account_name='Test Account',
            organization_name='Test Org'
        )
        
        integration2 = Integration.objects.create(
            account=account,
            created_by=user,
            provider=provider,
            external_account_id='xero_456',
            external_account_name='Test Account',
            organization_name='Test Org'
        )
        
        integrations = list(Integration.objects.all())
        assert integrations[0] == integration2  # Newer first
        assert integrations[1] == integration1


@pytest.mark.django_db
class TestIntegrationCredential:
    """Test ConnectionCredential model behavior (currently IntegrationCredential)"""
    
    def test_credential_creation(self, credential, integration):
        """IntegrationCredential can be created with encrypted tokens"""
        assert credential.integration == integration
        assert credential.token_type == 'Bearer'  # Default
        assert credential.scopes == ['accounting.transactions']
        assert credential.created_at is not None
    
    def test_credential_token_expiration_check(self, integration):
        """is_expired method checks token expiration correctly"""
        credential = IntegrationCredential.objects.create(
            integration=integration,
            access_token='token'
        )
        
        # No expiry set - not expired
        assert credential.is_expired() is False
        
        # Expired token
        credential.expires_at = timezone.now() - timedelta(hours=1)
        credential.save()
        assert credential.is_expired() is True
        
        # Future expiry - not expired
        credential.expires_at = timezone.now() + timedelta(hours=1)
        credential.save()
        assert credential.is_expired() is False
    
    def test_credential_expires_soon_check(self, integration):
        """expires_soon method checks if token expires within timeframe"""
        credential = IntegrationCredential.objects.create(
            integration=integration,
            access_token='token'
        )
        
        # No expiry - not expiring soon
        assert credential.expires_soon() is False
        
        # Expires in 10 minutes - expires soon (default 30 min threshold)
        credential.expires_at = timezone.now() + timedelta(minutes=10)
        credential.save()
        assert credential.expires_soon() is True
        
        # Expires in 45 minutes - not expiring soon
        credential.expires_at = timezone.now() + timedelta(minutes=45)
        credential.save()
        assert credential.expires_soon() is False
        
        # Custom threshold
        credential.expires_at = timezone.now() + timedelta(minutes=10)
        credential.save()
        assert credential.expires_soon(minutes=5) is False  # 10 > 5
        assert credential.expires_soon(minutes=15) is True  # 10 < 15
    
    def test_credential_additional_credentials_management(self, integration):
        """Additional credentials can be managed safely"""
        credential = IntegrationCredential.objects.create(
            integration=integration,
            access_token='token'
        )
        
        # Initially empty
        assert credential.get_additional_credential('api_key') is None
        
        # Set credential
        credential.set_additional_credential('api_key', 'secret_key')
        credential.save()
        
        # Retrieve credential
        assert credential.get_additional_credential('api_key') == 'secret_key'
        assert credential.get_additional_credential('missing_key') is None
    
    def test_credential_additional_credentials_invalid_json_handling(self, integration):
        """Additional credentials handle invalid JSON gracefully"""
        credential = IntegrationCredential.objects.create(
            integration=integration,
            access_token='token',
            additional_credentials='invalid_json'
        )
        
        # Should return None for invalid JSON
        assert credential.get_additional_credential('any_key') is None
        
        # Setting should reset to valid JSON
        credential.set_additional_credential('new_key', 'value')
        assert credential.get_additional_credential('new_key') == 'value'
    
    def test_credential_one_to_one_relationship(self, integration):
        """IntegrationCredential has one-to-one relationship with Integration"""
        credential1 = IntegrationCredential.objects.create(
            integration=integration,
            access_token='token1'
        )
        
        # Should be able to access credential from integration
        assert integration.credentials == credential1
        
        # Creating second credential for same integration should raise error
        with pytest.raises(Exception):  # IntegrityError
            IntegrationCredential.objects.create(
                integration=integration,
                access_token='token2'
            )


@pytest.mark.django_db
class TestOAuthState:
    """Test OAuth state token model behavior"""
    
    def test_oauth_state_creation(self, integration, user):
        """OAuthState can be created with valid data"""
        state = OAuthState.objects.create(
            integration=integration,
            state_token='random_secure_token',
            created_by=user
        )
        
        assert state.integration == integration
        assert state.created_by == user
        assert state.is_used is False  # Default
        assert state.used_at is None
        assert state.created_at is not None
    
    def test_oauth_state_str_representation(self, integration, user):
        """OAuthState string representation includes integration and partial token"""
        state = OAuthState.objects.create(
            integration=integration,
            state_token='random_secure_token_123456',
            created_by=user
        )
        
        expected = "OAuth State for Test Organization - random_secure_to..."
        assert str(state) == expected
    
    def test_oauth_state_mark_as_used(self, integration, user):
        """mark_as_used method updates state correctly"""
        state = OAuthState.objects.create(
            integration=integration,
            state_token='token',
            created_by=user
        )
        
        assert state.is_used is False
        assert state.used_at is None
        
        state.mark_as_used()
        
        assert state.is_used is True
        assert state.used_at is not None
    
    def test_oauth_state_create_token_class_method(self, integration, user):
        """create_state_token class method generates secure tokens"""
        state = OAuthState.create_state_token(integration, user)
        
        assert state.integration == integration
        assert state.created_by == user
        assert len(state.state_token) == 64  # Expected length
        assert state.state_token.isalnum()  # Only letters and numbers
    
    def test_oauth_state_token_uniqueness(self, integration, user):
        """State tokens must be unique"""
        token = 'duplicate_token'
        
        OAuthState.objects.create(
            integration=integration,
            state_token=token,
            created_by=user
        )
        
        with pytest.raises(Exception):  # IntegrityError
            OAuthState.objects.create(
                integration=integration,
                state_token=token,
                created_by=user
            )
    
    def test_oauth_state_cleanup_expired_states(self, integration, user):
        """cleanup_expired_states removes old tokens"""
        # Create old state
        old_state = OAuthState.objects.create(
            integration=integration,
            state_token='old_token',
            created_by=user
        )
        old_state.created_at = timezone.now() - timedelta(hours=25)
        old_state.save()
        
        # Create recent state
        recent_state = OAuthState.objects.create(
            integration=integration,
            state_token='recent_token',
            created_by=user
        )
        
        # Cleanup with 24 hour threshold
        count = OAuthState.cleanup_expired_states(hours=24)
        
        assert count == 1
        assert not OAuthState.objects.filter(id=old_state.id).exists()
        assert OAuthState.objects.filter(id=recent_state.id).exists()
    
    def test_oauth_state_ordering(self, integration, user):
        """OAuth states are ordered by creation date descending"""
        state1 = OAuthState.objects.create(
            integration=integration,
            state_token='token1',
            created_by=user
        )
        
        state2 = OAuthState.objects.create(
            integration=integration,
            state_token='token2',
            created_by=user
        )
        
        states = list(OAuthState.objects.all())
        assert states[0] == state2  # Newer first
        assert states[1] == state1


@pytest.mark.django_db
class TestIntegrationSync:
    """Test SyncRun model behavior (currently IntegrationSync)"""
    
    def test_sync_creation(self, integration):
        """IntegrationSync can be created with valid data"""
        sync = IntegrationSync.objects.create(
            integration=integration,
            sync_type='full'
        )
        
        assert sync.integration == integration
        assert sync.sync_type == 'full'
        assert sync.status == 'pending'  # Default
        assert sync.records_processed == 0  # Default
        assert sync.started_at is not None  # auto_now_add
    
    def test_sync_type_choices(self, integration):
        """IntegrationSync accepts valid sync types"""
        valid_types = ['full', 'incremental', 'webhook']
        
        for sync_type in valid_types:
            sync = IntegrationSync.objects.create(
                integration=integration,
                sync_type=sync_type
            )
            assert sync.sync_type == sync_type
    
    def test_sync_status_progression(self, integration):
        """IntegrationSync can progress through valid statuses"""
        sync = IntegrationSync.objects.create(
            integration=integration,
            sync_type='full'
        )
        
        valid_statuses = ['pending', 'running', 'completed', 'failed', 'cancelled']
        for status in valid_statuses:
            sync.status = status
            sync.save()
            sync.refresh_from_db()
            assert sync.status == status
    
    def test_sync_completion_tracking(self, integration):
        """IntegrationSync tracks completion timestamps"""
        sync = IntegrationSync.objects.create(
            integration=integration,
            sync_type='incremental'
        )
        
        assert sync.completed_at is None
        
        # Simulate completion
        now = timezone.now()
        sync.completed_at = now
        sync.status = 'completed'
        sync.save()
        
        sync.refresh_from_db()
        assert sync.completed_at == now
        assert sync.status == 'completed'
    
    def test_sync_record_counts(self, integration):
        """IntegrationSync tracks record processing statistics"""
        sync = IntegrationSync.objects.create(
            integration=integration,
            sync_type='full',
            records_processed=100,
            records_success=80,
            records_failed=20
        )
        
        assert sync.records_processed == 100
        assert sync.records_success == 80
        assert sync.records_failed == 20
    
    def test_sync_error_handling(self, integration):
        """IntegrationSync can store error information"""
        error_details = {
            'error_code': 'RATE_LIMIT',
            'retry_after': 60,
            'api_response': {'message': 'Too many requests'}
        }
        
        sync = IntegrationSync.objects.create(
            integration=integration,
            sync_type='incremental',
            status='failed',
            error_message='Rate limit exceeded',
            error_details=error_details
        )
        
        assert sync.error_message == 'Rate limit exceeded'
        assert sync.error_details == error_details
    
    def test_sync_metadata_storage(self, integration):
        """IntegrationSync can store sync-specific metadata"""
        metadata = {
            'last_modified_timestamp': '2023-01-01T00:00:00Z',
            'sync_filters': {'date_from': '2023-01-01'},
            'api_version': 'v2.0'
        }
        
        sync = IntegrationSync.objects.create(
            integration=integration,
            sync_type='incremental',
            metadata=metadata
        )
        
        assert sync.metadata == metadata
    
    def test_sync_ordering(self, integration):
        """IntegrationSync is ordered by started_at descending"""
        sync1 = IntegrationSync.objects.create(
            integration=integration,
            sync_type='full'
        )
        
        sync2 = IntegrationSync.objects.create(
            integration=integration,
            sync_type='incremental'
        )
        
        syncs = list(IntegrationSync.objects.all())
        assert syncs[0] == sync2  # Newer first
        assert syncs[1] == sync1


@pytest.fixture
def connection_provider():
    """Fixture for new connections.Provider model"""
    return Provider.objects.create(
        name='xero',
        display_name='Xero',
        provider_type='xero',
        auth_url_template='https://api.xero.com/oauth/authorize',
        token_url='https://api.xero.com/oauth/token',
        scopes_default=['accounting.transactions']
    )


@pytest.mark.django_db
class TestConnection:
    """Test new Connection model in connections app"""
    
    def test_connection_creation(self, user, account, connection_provider):
        """Connection can be created with valid data"""
        from connections.models import Connection
        
        connection = Connection.objects.create(
            account=account,
            created_by=user,
            provider=connection_provider,
            external_account_id='xero_123',
            external_account_name='Test Xero Account',
            organization_name='Test Organization'
        )
        
        assert connection.account == account
        assert connection.created_by == user
        assert connection.provider == connection_provider
        assert connection.external_account_id == 'xero_123'
        assert connection.status == 'pending'  # Default value
        assert connection.created_at is not None
        assert connection.updated_at is not None
    
    def test_connection_prefix_id_generation(self, user, account, connection_provider):
        """Connection automatically generates prefix_id starting with 'con_'"""
        from connections.models import Connection
        
        connection = Connection.objects.create(
            account=account,
            created_by=user,
            provider=connection_provider,
            external_account_id='xero_456',
            external_account_name='Test Account',
            organization_name='Test Org'
        )
        
        assert connection.prefix_id is not None
        assert connection.prefix_id.startswith('con_')
        assert len(connection.prefix_id) == 12  # 'con_' + 8 chars
        assert connection.get_prefix_id() == connection.prefix_id
    
    def test_connection_str_representation(self, user, account, connection_provider):
        """Connection string representation shows account, provider, and org name"""
        from connections.models import Connection
        
        connection = Connection.objects.create(
            account=account,
            created_by=user,
            provider=connection_provider,
            external_account_id='xero_789',
            external_account_name='Test Account',
            organization_name='My Test Organization'
        )
        
        expected = "Test Account - Xero - My Test Organization"
        assert str(connection) == expected
    
    def test_connection_unique_constraint(self, user, account, connection_provider):
        """Connection enforces unique constraint on account+provider+external_account_id"""
        from connections.models import Connection
        
        # Create first connection
        Connection.objects.create(
            account=account,
            created_by=user,
            provider=connection_provider,
            external_account_id='xero_duplicate',
            external_account_name='Account 1',
            organization_name='Org 1'
        )
        
        # Try to create duplicate
        with pytest.raises(Exception):  # IntegrityError
            Connection.objects.create(
                account=account,
                created_by=user,
                provider=connection_provider,
                external_account_id='xero_duplicate',
                external_account_name='Account 2',
                organization_name='Org 2'
            )
    
    def test_connection_status_choices(self, user, account, connection_provider):
        """Connection accepts valid status choices"""
        from connections.models import Connection
        
        valid_statuses = ['pending', 'active', 'expired', 'revoked', 'error']
        
        for status in valid_statuses:
            connection = Connection.objects.create(
                account=account,
                created_by=user,
                provider=connection_provider,
                external_account_id=f'xero_{status}',
                external_account_name='Test Account',
                organization_name='Test Org',
                status=status
            )
            assert connection.status == status
    
    def test_connection_config_json_storage(self, user, account, connection_provider):
        """Connection can store provider-specific config as JSON"""
        from connections.models import Connection
        
        config_data = {
            'webhook_url': 'https://example.com/webhook',
            'sync_frequency': 'daily',
            'enabled_features': ['transactions', 'contacts']
        }
        
        connection = Connection.objects.create(
            account=account,
            created_by=user,
            provider=connection_provider,
            external_account_id='xero_config',
            external_account_name='Config Test',
            organization_name='Config Org',
            config=config_data
        )
        
        assert connection.config == config_data
    
    def test_connection_ordering(self, user, account, connection_provider):
        """Connections are ordered by creation date descending"""
        from connections.models import Connection
        
        connection1 = Connection.objects.create(
            account=account,
            created_by=user,
            provider=connection_provider,
            external_account_id='first',
            external_account_name='First',
            organization_name='First Org'
        )
        
        connection2 = Connection.objects.create(
            account=account,
            created_by=user,
            provider=connection_provider,
            external_account_id='second',
            external_account_name='Second',
            organization_name='Second Org'
        )
        
        connections = list(Connection.objects.all())
        assert connections[0] == connection2  # Newer first
        assert connections[1] == connection1