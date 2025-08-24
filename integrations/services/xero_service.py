from typing import Dict, Any, Optional, List
from .base import BaseIntegrationService, IntegrationServiceRegistry
from ..models import IntegrationSync
from xero_python.api_client import ApiClient
from xero_python.api_client.configuration import Configuration
from xero_python.api_client.oauth2 import OAuth2Token
from xero_python.accounting import AccountingApi
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class XeroIntegrationService(BaseIntegrationService):
    """Xero-specific integration service"""
    
    def __init__(self, integration):
        super().__init__(integration)
        self.config = self._get_provider_config()
        
    def _get_provider_config(self) -> Dict[str, Any]:
        """Get Xero-specific configuration"""
        from ..config import IntegrationConfigManager
        return IntegrationConfigManager.get_config('xero').get_config()
    
    def _create_api_client(self, oauth_token: Optional[OAuth2Token] = None) -> ApiClient:
        """Create Xero API client"""
        configuration = Configuration(host='https://api.xero.com')
        api_client = ApiClient(configuration)
        
        if oauth_token:
            api_client.set_oauth2_token(oauth_token)
        
        return api_client
    
    def get_auth_url(self, state: Optional[str] = None, **kwargs) -> str:
        """Generate Xero OAuth authorization URL"""
        import urllib.parse
        
        auth_params = {
            'response_type': 'code',
            'client_id': self.config['client_id'],
            'redirect_uri': self.config['redirect_uri'],
            'scope': ' '.join(self.config['scopes']),
            'state': state or str(self.integration.id)
        }
        
        auth_url = f"https://login.xero.com/identity/connect/authorize?{urllib.parse.urlencode(auth_params)}"
        return auth_url
    
    def handle_callback(self, auth_code: str, state: Optional[str] = None) -> Dict[str, Any]:
        """Handle Xero OAuth callback"""
        try:
            oauth2_token = OAuth2Token(
                client_id=self.config['client_id'],
                client_secret=self.config['client_secret']
            )
            
            # Exchange code for token
            oauth2_token.fetch_access_token(
                code=auth_code,
                redirect_uri=self.config['redirect_uri']
            )
            
            # Get organizations to verify connection
            api_client = self._create_api_client(oauth2_token)
            accounting_api = AccountingApi(api_client)
            
            try:
                organizations = accounting_api.get_organisations()
                if not organizations.organisations:
                    raise Exception("No organizations found in Xero account")
                
                # Update integration with organization details
                org = organizations.organisations[0]  # Use first org
                self.integration.external_account_id = org.organisation_id
                self.integration.organization_name = org.name
                self.integration.external_account_name = org.legal_name or org.name
                self.integration.save()
                
            except Exception as e:
                logger.error(f"Failed to fetch Xero organizations: {e}")
                raise Exception(f"Failed to verify Xero connection: {str(e)}")
            
            # Store credentials
            credentials = self.store_credentials(
                access_token=oauth2_token.access_token,
                refresh_token=oauth2_token.refresh_token,
                expires_in=oauth2_token.expires_in,
                scopes=oauth2_token.scope,
                tenant_id=self.integration.external_account_id
            )
            
            return {
                'success': True,
                'organization_name': self.integration.organization_name,
                'external_account_id': self.integration.external_account_id
            }
            
        except Exception as e:
            self.handle_auth_error(e, "OAuth callback")
            raise
    
    def refresh_token(self) -> bool:
        """Refresh Xero access token"""
        credentials = self.get_credentials()
        if not credentials or not credentials.refresh_token:
            return False
        
        try:
            oauth2_token = OAuth2Token(
                client_id=self.config['client_id'],
                client_secret=self.config['client_secret']
            )
            oauth2_token.refresh_token = credentials.refresh_token
            
            # Refresh the token
            oauth2_token.refresh_access_token()
            
            # Update stored credentials
            credentials.access_token = oauth2_token.access_token
            if oauth2_token.refresh_token:
                credentials.refresh_token = oauth2_token.refresh_token
            
            if oauth2_token.expires_in:
                credentials.expires_at = timezone.now() + timezone.timedelta(
                    seconds=oauth2_token.expires_in
                )
            
            credentials.last_refreshed_at = timezone.now()
            credentials.save()
            
            logger.info(f"Token refreshed for integration {self.integration.id}")
            return True
            
        except Exception as e:
            self.handle_auth_error(e, "Token refresh")
            return False
    
    def test_connection(self) -> Dict[str, Any]:
        """Test Xero connection"""
        credentials = self.get_credentials()
        if not credentials:
            return {'success': False, 'error': 'No credentials found'}
        
        # Auto-refresh if needed
        if credentials.expires_soon():
            if not self.refresh_token():
                return {'success': False, 'error': 'Failed to refresh token'}
            credentials.refresh_from_db()
        
        try:
            oauth2_token = OAuth2Token(
                client_id=self.config['client_id'],
                client_secret=self.config['client_secret']
            )
            oauth2_token.access_token = credentials.access_token
            
            api_client = self._create_api_client(oauth2_token)
            accounting_api = AccountingApi(api_client)
            
            # Simple test call
            organizations = accounting_api.get_organisations()
            
            return {
                'success': True,
                'organization_count': len(organizations.organisations),
                'last_tested': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_accounts(self) -> List[Dict[str, Any]]:
        """Fetch chart of accounts from Xero"""
        credentials = self.get_credentials()
        if not credentials:
            raise Exception("No credentials available")
        
        # Auto-refresh if needed
        if credentials.expires_soon():
            if not self.refresh_token():
                raise Exception("Failed to refresh token")
            credentials.refresh_from_db()
        
        try:
            oauth2_token = OAuth2Token(
                client_id=self.config['client_id'],
                client_secret=self.config['client_secret']
            )
            oauth2_token.access_token = credentials.access_token
            
            api_client = self._create_api_client(oauth2_token)
            accounting_api = AccountingApi(api_client)
            
            # Fetch accounts
            accounts_response = accounting_api.get_accounts(
                tenant_id=self.integration.external_account_id
            )
            
            accounts = []
            for account in accounts_response.accounts:
                accounts.append({
                    'id': account.account_id,
                    'name': account.name,
                    'code': account.code,
                    'type': account.type.value if account.type else None,
                    'account_class': account.account_class.value if account.account_class else None,
                    'is_system_account': account.system_account,
                    'enable_payments_to_account': account.enable_payments_to_account,
                    'show_in_expense_claims': account.show_in_expense_claims,
                    'description': account.description,
                    'tax_type': account.tax_type,
                    'currency_code': account.currency_code,
                    'org': self.integration.organization_name
                })
            
            return accounts
            
        except Exception as e:
            logger.error(f"Failed to fetch Xero accounts: {e}")
            raise Exception(f"Failed to fetch accounts: {str(e)}")
    
    def save_selected_accounts(self, selected_account_ids: List[str]) -> None:
        """Save selected account IDs to integration config"""
        # Update config with selected accounts
        config = self.integration.config.copy()
        config['selected_accounts'] = selected_account_ids
        config['accounts_selected_at'] = timezone.now().isoformat()
        
        self.integration.config = config
        self.integration.save()
        
        logger.info(f"Saved {len(selected_account_ids)} selected accounts for integration {self.integration.id}")
    
    def get_selected_accounts(self) -> List[str]:
        """Get list of selected account IDs from config"""
        return self.integration.config.get('selected_accounts', [])

    def sync_data(self, sync_type: str = 'incremental') -> IntegrationSync:
        """Sync data from Xero"""
        sync_record = self.create_sync_record(sync_type)
        
        try:
            sync_record.status = 'running'
            sync_record.save()
            
            credentials = self.get_credentials()
            if not credentials:
                raise Exception("No credentials available for sync")
            
            # Auto-refresh if needed
            if credentials.expires_soon():
                if not self.refresh_token():
                    raise Exception("Failed to refresh token for sync")
                credentials.refresh_from_db()
            
            # Perform actual sync operations here
            # This would include fetching accounts, transactions, etc.
            
            sync_record.status = 'completed'
            sync_record.completed_at = timezone.now()
            sync_record.records_success = 100  # Example
            sync_record.save()
            
            # Update integration last sync time
            self.integration.last_sync_at = timezone.now()
            self.integration.save()
            
        except Exception as e:
            sync_record.status = 'failed'
            sync_record.error_message = str(e)
            sync_record.completed_at = timezone.now()
            sync_record.save()
            
            logger.error(f"Sync failed for integration {self.integration.id}: {e}")
            raise
        
        return sync_record


# Register the service
IntegrationServiceRegistry.register('xero', XeroIntegrationService)