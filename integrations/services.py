from django.urls import reverse
from django.http import HttpRequest
from xero_python.api_client import ApiClient
from xero_python.api_client.configuration import Configuration
from xero_python.api_client.oauth2 import OAuth2Token
from xero_python.accounting import AccountingApi
from .config import IntegrationConfigManager
from typing import Optional, Dict, Any


class XeroService:
    """Service class for Xero API interactions"""
    
    def __init__(self):
        self.config = IntegrationConfigManager.get_config('xero').get_config()
        self.api_client = self._create_api_client()
    
    def _create_api_client(self) -> ApiClient:
        """Create and configure Xero API client"""
        configuration = Configuration(
            host='https://api.xero.com'
        )
        api_client = ApiClient(configuration)
        api_client.set_oauth2_token(OAuth2Token(
            client_id=self.config['client_id'],
            client_secret=self.config['client_secret']
        ))
        return api_client
    
    def get_auth_url(self, request: HttpRequest, state: Optional[str] = None) -> str:
        """Generate OAuth authorization URL"""
        oauth2_token = OAuth2Token(
            client_id=self.config['client_id'],
            client_secret=self.config['client_secret']
        )
        
        return oauth2_token.generate_url(
            redirect_uri=self.config['redirect_uri'],
            scopes=self.config['scopes'],
            state=state
        )
    
    def handle_callback(self, auth_code: str, state: Optional[str] = None) -> OAuth2Token:
        """Handle OAuth callback and exchange code for token"""
        oauth2_token = OAuth2Token(
            client_id=self.config['client_id'],
            client_secret=self.config['client_secret']
        )
        
        oauth2_token.generate_access_token(
            code=auth_code,
            redirect_uri=self.config['redirect_uri']
        )
        
        return oauth2_token
    
    def get_organisations(self, oauth2_token: OAuth2Token) -> list:
        """Get list of organisations from Xero"""
        self.api_client.set_oauth2_token(oauth2_token)
        accounting_api = AccountingApi(self.api_client)
        
        try:
            organisations = accounting_api.get_organisations()
            return [
                {
                    'name': org.name,
                    'organisation_id': org.organisation_id,
                    'short_code': org.short_code,
                    'legal_name': org.legal_name or org.name,
                }
                for org in organisations.organisations
            ]
        except Exception as e:
            raise Exception(f"Failed to fetch organisations: {str(e)}")
    
    def get_accounts(self, oauth2_token: OAuth2Token, organisation_id: str) -> list:
        """Get chart of accounts for a specific organisation"""
        self.api_client.set_oauth2_token(oauth2_token)
        accounting_api = AccountingApi(self.api_client)
        
        try:
            accounts = accounting_api.get_accounts(
                xero_tenant_id=organisation_id
            )
            return [
                {
                    'account_id': account.account_id,
                    'name': account.name,
                    'code': account.code,
                    'type': account.type,
                    'status': account.status,
                }
                for account in accounts.accounts
                if account.status == 'ACTIVE'
            ]
        except Exception as e:
            raise Exception(f"Failed to fetch accounts: {str(e)}")