from typing import Dict, Any, Optional, List
from ..base import BaseConnectionService, ConnectionServiceRegistry
from ...models import Sync
from integrations.utils import (
    retry_on_exceptions, APIRateLimitHandler, TokenRefreshError, 
    APIConnectionError, APIRateLimitError, DataValidationError
)
from xero_python.api_client import ApiClient
from xero_python.api_client.configuration import Configuration
from xero_python.api_client.oauth2 import OAuth2Token
from xero_python.accounting import AccountingApi
from xero_python import exceptions as xero_exceptions
from django.utils import timezone
import logging
import requests
import time
from decimal import Decimal
import datetime

logger = logging.getLogger(__name__)


def convert_decimals_for_json(data):
    """Convert non-JSON-serializable objects to JSON serializable formats"""
    if isinstance(data, dict):
        return {key: convert_decimals_for_json(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [convert_decimals_for_json(item) for item in data]
    elif isinstance(data, Decimal):
        return float(data)
    elif isinstance(data, (datetime.date, datetime.datetime)):
        return data.isoformat()
    elif hasattr(data, '__dict__') and not isinstance(data, type):
        # Handle objects with attributes (like CurrencyCode, etc.) by converting to dict
        try:
            return convert_decimals_for_json(data.__dict__)
        except:
            # If that fails, try to get string representation
            return str(data)
    elif hasattr(data, 'value'):
        # Handle enum-like objects with 'value' attribute
        return data.value
    elif not isinstance(data, (str, int, float, bool, type(None))):
        # For any other non-basic type, convert to string
        return str(data)
    else:
        return data


class XeroConnectionService(BaseConnectionService):
    """Xero-specific integration service"""
    
    def __init__(self, connection):
        super().__init__(connection)
        self.config = self._get_provider_config()
        self.rate_limiter = APIRateLimitHandler()
        
    def _get_provider_config(self) -> Dict[str, Any]:
        """Get Xero-specific configuration"""
        from integrations.config import IntegrationConfigManager
        return IntegrationConfigManager.get_config('xero').get_config()
    
    def _create_api_client(self, oauth_token: Optional[OAuth2Token] = None) -> ApiClient:
        """Create Xero API client with proper token management"""
        
        # Create OAuth2Token instance
        oauth2_token_instance = OAuth2Token(
            client_id=self.config['client_id'],
            client_secret=self.config['client_secret']
        )
        
        configuration = Configuration(
            debug=False,
            oauth2_token=oauth2_token_instance
        )
        api_client = ApiClient(configuration)
        
        # Set up token getter and saver decorators
        @api_client.oauth2_token_getter
        def obtain_xero_oauth2_token():
            """Get token from our database storage"""
            credentials = self.get_credentials()
            if not credentials:
                return None
            
            return {
                'access_token': credentials.access_token,
                'refresh_token': credentials.refresh_token,
                'token_type': credentials.token_type,
                'expires_in': int((credentials.expires_at - timezone.now()).total_seconds()) if credentials.expires_at else 1800,
                'scope': credentials.scopes if credentials.scopes else []  # MUST be a list, not string
            }
        
        @api_client.oauth2_token_saver
        def store_xero_oauth2_token(token):
            """Save token to our database storage"""
            logger.info(f"Token saver called with token keys: {list(token.keys()) if token else 'None'}")
            
            if not token:
                logger.error("Token saver called with empty token")
                return
            
            # Validate required fields
            access_token = token.get('access_token')
            if not access_token:
                logger.error(f"Token saver called with empty access_token: {token}")
                return
                
            credentials = self.get_credentials()
            if credentials:
                credentials.access_token = access_token
                credentials.refresh_token = token.get('refresh_token')
                credentials.token_type = token.get('token_type', 'Bearer')
                
                # Handle scope - it might be a string or list
                scope_value = token.get('scope', '')
                if isinstance(scope_value, list):
                    credentials.scopes = scope_value
                elif isinstance(scope_value, str):
                    credentials.scopes = scope_value.split(' ') if scope_value else []
                else:
                    credentials.scopes = []
                
                if token.get('expires_in'):
                    credentials.expires_at = timezone.now() + timezone.timedelta(seconds=int(token['expires_in']))
                
                credentials.last_refreshed_at = timezone.now()
                
                try:
                    credentials.save()
                    logger.info(f"Token saved successfully for integration {self.connection.id}")
                except Exception as e:
                    logger.error(f"Failed to save credentials: {e}")
                    raise
        
        # If we have an existing token, load it into the client
        existing_credentials = self.get_credentials()
        if existing_credentials and existing_credentials.access_token:
            token_dict = {
                'access_token': existing_credentials.access_token,
                'refresh_token': existing_credentials.refresh_token,
                'token_type': existing_credentials.token_type,
                'expires_in': int((existing_credentials.expires_at - timezone.now()).total_seconds()) if existing_credentials.expires_at else 1800,
                'scope': existing_credentials.scopes if existing_credentials.scopes else []  # MUST be a list, not string
            }
            store_xero_oauth2_token(token_dict)
        
        return api_client
    
    def get_auth_url(self, state: Optional[str] = None, **kwargs) -> str:
        """Generate Xero OAuth authorization URL"""
        import urllib.parse
        
        auth_params = {
            'response_type': 'code',
            'client_id': self.config['client_id'],
            'redirect_uri': self.config['redirect_uri'],
            'scope': ' '.join(self.config['scopes']),
            'state': state or str(self.connection.id)
        }
        
        auth_url = f"https://login.xero.com/identity/connect/authorize?{urllib.parse.urlencode(auth_params)}"
        return auth_url
    
    def handle_callback(self, auth_code: str, state: Optional[str] = None) -> Dict[str, Any]:
        """Handle Xero OAuth callback"""
        try:
            # Make direct token exchange request to Xero
            token_url = 'https://identity.xero.com/connect/token'
            token_data = {
                'grant_type': 'authorization_code',
                'client_id': self.config['client_id'],
                'client_secret': self.config['client_secret'],
                'code': auth_code,
                'redirect_uri': self.config['redirect_uri']
            }
            
            response = requests.post(token_url, data=token_data, headers={
                'Content-Type': 'application/x-www-form-urlencoded'
            })
            
            if response.status_code != 200:
                raise Exception(f"Token exchange failed: {response.status_code} {response.text}")
            
            token_data = response.json()
            
            # Create OAuth2Token instance and update it with the received token
            oauth2_token = OAuth2Token(
                client_id=self.config['client_id'],
                client_secret=self.config['client_secret']
            )
            
            oauth2_token.update_token(
                access_token=token_data['access_token'],
                refresh_token=token_data.get('refresh_token'),
                scope=token_data.get('scope', '').split(' ') if isinstance(token_data.get('scope'), str) and token_data.get('scope') else (token_data.get('scope') if isinstance(token_data.get('scope'), list) else []),
                expires_in=token_data.get('expires_in', 1800),
                token_type=token_data.get('token_type', 'Bearer'),
                id_token=token_data.get('id_token')
            )
            
            # Store credentials first
            credentials = self.store_credentials(
                access_token=token_data['access_token'],
                refresh_token=token_data.get('refresh_token'),
                expires_in=token_data.get('expires_in', 1800),
                scopes=token_data.get('scope', '').split(' ') if isinstance(token_data.get('scope'), str) and token_data.get('scope') else (token_data.get('scope') if isinstance(token_data.get('scope'), list) else []),
                additional_data={'token_type': token_data.get('token_type', 'Bearer')}
            )
            
            # Now create API client with proper token management
            api_client = self._create_api_client()
            
            try:
                from xero_python.identity import IdentityApi
                identity_api = IdentityApi(api_client)
                
                # Get connections (tenant IDs)
                connections = identity_api.get_connections()
                if not connections:
                    raise Exception("No Xero connections found")
                
                # Use the first connection
                connection = connections[0]
                tenant_id = connection.tenant_id
                
                # Now get organization details using the tenant ID
                accounting_api = AccountingApi(api_client)
                organizations = accounting_api.get_organisations(xero_tenant_id=tenant_id)
                
                if not organizations.organisations:
                    raise Exception("No organizations found in Xero account")
                
                # Update integration with organization details
                org = organizations.organisations[0]  # Use first org
                self.connection.external_account_id = tenant_id  # Store tenant ID
                self.connection.organization_name = org.name
                self.connection.external_account_name = org.legal_name or org.name
                
                try:
                    self.connection.save()
                except Exception as save_error:
                    # Check if this is a duplicate integration error
                    if 'unique constraint' in str(save_error).lower() or 'duplicate key' in str(save_error).lower():
                        # This Xero organization is already connected to this account
                        logger.warning(f"Attempted to create duplicate integration for Xero org '{org.name}' (tenant: {tenant_id}) for account {self.connection.account.id}")
                        
                        # Clean up the orphaned integration record since it failed to save
                        try:
                            self.connection.delete()
                        except:
                            pass  # Best effort cleanup
                        
                        raise Exception(f"This Xero organization ('{org.name}') is already connected to your account. Please use a different Xero organization.")
                    else:
                        # Some other save error
                        logger.error(f"Error saving integration details: {save_error}")
                        raise Exception(f"Unable to save Xero connection details: {str(save_error)}")
                
                logger.info(f"Successfully connected to Xero org: {org.name} (Tenant ID: {tenant_id})")
                
            except Exception as e:
                logger.error(f"Failed to fetch Xero organizations: {e}")
                raise Exception(f"Failed to verify Xero connection: {str(e)}")
            
            return {
                'success': True,
                'organization_name': self.connection.organization_name,
                'external_account_id': self.connection.external_account_id
            }
            
        except Exception as e:
            self.handle_auth_error(e, "OAuth callback")
            raise
    
    @retry_on_exceptions(
        exceptions=[requests.exceptions.RequestException, xero_exceptions.HTTPStatusException],
        max_retries=3,
        delay=1.0
    )
    def refresh_token(self) -> bool:
        """Refresh Xero access token using proper xero-python SDK pattern"""
        credentials = self.get_credentials()
        if not credentials or not credentials.refresh_token:
            raise TokenRefreshError("No refresh token available")
        
        try:
            # Apply rate limiting
            self.rate_limiter.wait_if_rate_limited()
            
            # Use the standard xero-python pattern
            api_client = self._create_api_client()
            
            logger.info(f"Attempting token refresh for integration {self.connection.id}")
            
            # The key fix: Use the proper xero-python SDK method
            api_client.refresh_oauth2_token()
            
            # Verify the refresh worked by checking if we have a new access token
            refreshed_credentials = self.get_credentials()
            refreshed_credentials.refresh_from_db()  # Reload from DB
            
            if not refreshed_credentials.access_token:
                raise TokenRefreshError("Token refresh succeeded but no access token was saved")
            
            logger.info(f"Token refreshed successfully for integration {self.connection.id}")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during token refresh: {e}")
            raise APIConnectionError(f"Network error: {str(e)}")
        except xero_exceptions.HTTPStatusException as e:
            if e.status in [429, 503]:  # Rate limit or service unavailable
                raise APIRateLimitError(f"API rate limit or service unavailable: {str(e)}")
            elif e.status in [401, 403]:  # Auth errors
                raise TokenRefreshError(f"Authentication failed: {str(e)}")
            else:
                raise APIConnectionError(f"HTTP error {e.status}: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during token refresh: {e}")
            # Don't mark integration as error status for token refresh failures
            # Integration can still work, just needs manual reconnection
            raise TokenRefreshError(f"Token refresh failed: {str(e)}")
    
    def _safe_refresh_token(self) -> bool:
        """Safe wrapper for token refresh that doesn't raise exceptions"""
        try:
            self.refresh_token()
            return True
        except (TokenRefreshError, APIConnectionError, APIRateLimitError) as e:
            logger.error(f"Token refresh failed for integration {self.connection.id}: {e}")
            # Don't mark integration as error - it can still work, just needs manual reconnection
            return False
    
    def _api_call_with_retry(self, api_call_func):
        """Execute API call with automatic token refresh on 401 errors"""
        try:
            return api_call_func()
        except Exception as api_error:
            # Check if this is a 401 Unauthorized error (token expired)
            if ("401" in str(api_error) or 
                "Unauthorized" in str(api_error) or 
                "TokenExpired" in str(api_error) or
                "invalid_token" in str(api_error)):
                
                logger.info("Got 401/token expired error in API call, attempting token refresh...")
                credentials = self.get_credentials()
                
                if credentials and credentials.refresh_token:
                    if self._safe_refresh_token():
                        logger.info("Token refresh successful, retrying API call...")
                        # Retry the API call with refreshed token
                        return api_call_func()
                    else:
                        logger.error("Token refresh failed - user needs to reconnect")
                        raise TokenRefreshError("Token expired and refresh failed. Please reconnect to Xero.")
                else:
                    logger.error("No refresh token available - user needs to reconnect")
                    raise TokenRefreshError("Token expired and no refresh token available. Please reconnect to Xero.")
            else:
                # Re-raise non-authentication errors
                raise api_error
    
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
    
    def get_organizations(self) -> List[Dict[str, Any]]:
        """Fetch client organizations the accountant has access to"""
        credentials = self.get_credentials()
        if not credentials:
            raise Exception("No credentials available")
        
        # Auto-refresh if needed
        if credentials.expires_soon() and credentials.refresh_token:
            logger.info("Token expires soon, attempting proactive refresh...")
            if not self._safe_refresh_token():
                logger.warning("Token expires soon but refresh failed - continuing with current token")
            else:
                credentials.refresh_from_db()
                logger.info("Proactive token refresh successful")
        
        try:
            # Define the API call to get all tenant connections and their organization details
            def fetch_organizations_api():
                from xero_python.identity import IdentityApi
                from xero_python.accounting import AccountingApi
                
                api_client = self._create_api_client()
                identity_api = IdentityApi(api_client)
                accounting_api = AccountingApi(api_client)
                
                # Get all connections (tenant IDs) the user has access to
                connections = identity_api.get_connections()
                
                organizations = []
                for connection in connections:
                    try:
                        # Get organization details for each tenant
                        orgs_response = accounting_api.get_organisations(xero_tenant_id=connection.tenant_id)
                        if orgs_response.organisations:
                            org = orgs_response.organisations[0]  # Each tenant should have one org
                            organizations.append({
                                'tenant_id': connection.tenant_id,
                                'name': org.name,
                                'legal_name': org.legal_name or org.name,
                                'short_code': org.short_code,
                                'country_code': org.country_code,
                                'organisation_id': org.organisation_id,
                                'connection_id': connection.id
                            })
                    except Exception as org_error:
                        logger.warning(f"Failed to get organization details for tenant {connection.tenant_id}: {org_error}")
                        continue
                
                return organizations
            
            # Execute API call with automatic retry on token expiration  
            organizations = self._api_call_with_retry(fetch_organizations_api)
            
            logger.info(f"Successfully fetched {len(organizations)} client organizations")
            return organizations
            
        except TokenRefreshError:
            # Re-raise token refresh errors as-is for proper handling in view
            raise
        except Exception as e:
            logger.error(f"Failed to fetch Xero accounts: {e}")
            raise Exception(f"Failed to fetch accounts: {str(e)}")
    
    def save_selected_organizations(self, selected_tenant_ids: List[str]) -> None:
        """Save selected client organization tenant IDs to integration config"""
        # Update config with selected organizations
        config = self.connection.config.copy()
        config['selected_organizations'] = selected_tenant_ids
        config['organizations_selected_at'] = timezone.now().isoformat()
        
        self.connection.config = config
        self.connection.save()
    
    def save_selected_accounts(self, selected_account_ids: List[str]) -> None:
        """Save selected account IDs to integration config (deprecated - use save_selected_organizations)"""
        # Update config with selected accounts
        config = self.connection.config.copy()
        config['selected_accounts'] = selected_account_ids
        config['accounts_selected_at'] = timezone.now().isoformat()
        
        self.connection.config = config
        self.connection.save()
        
        logger.info(f"Saved {len(selected_account_ids)} selected accounts for integration {self.connection.id}")
    
    def sync_selected_organizations(self, selected_tenant_ids: List[str]) -> Dict[str, Any]:
        """Sync transactions for selected client organizations"""
        logger = logging.getLogger(__name__)
        total_transactions = 0
        
        logger.info(f"Starting sync for {len(selected_tenant_ids)} selected organizations")
        
        try:
            for tenant_id in selected_tenant_ids:
                logger.info(f"Syncing transactions for tenant {tenant_id}")
                
                # Sync transactions for this specific tenant
                result = self._sync_transactions_for_tenant(tenant_id)
                if result.get('success'):
                    transaction_count = result.get('transaction_count', 0)
                    total_transactions += transaction_count
                    logger.info(f"Synced {transaction_count} transactions for tenant {tenant_id}")
                else:
                    logger.warning(f"Failed to sync transactions for tenant {tenant_id}: {result.get('error')}")
                    
            logger.info(f"Total transactions synced: {total_transactions}")
            
            return {
                'success': True,
                'transaction_count': total_transactions
            }
            
        except Exception as e:
            logger.error(f"Failed to sync selected organizations: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _sync_transactions_for_tenant(self, tenant_id: str) -> Dict[str, Any]:
        """Sync transactions for a specific tenant organization"""
        from ..models import TransactionData, TransactionLineItem
        from datetime import datetime, timedelta
        
        logger = logging.getLogger(__name__)
        transactions_synced = 0
        
        try:
            # Define the API call with retry capability
            def fetch_transactions_api():
                api_client = self._create_api_client()
                accounting_api = AccountingApi(api_client)
                
                # Get recent transactions (last 365 days for initial import)
                from_date = (datetime.now() - timedelta(days=365)).date()
                to_date = datetime.now().date()
                
                where_clause = f"Date >= DateTime({from_date.year}, {from_date.month}, {from_date.day}) AND Date <= DateTime({to_date.year}, {to_date.month}, {to_date.day})"
                
                response = accounting_api.get_bank_transactions(
                    xero_tenant_id=tenant_id,
                    where=where_clause,
                    order='Date ASC'
                )
                return response
            
            # Execute API call with automatic retry on token expiration
            response = self._api_call_with_retry(fetch_transactions_api)
            
            if not response.bank_transactions:
                logger.info(f"No transactions found for tenant {tenant_id}")
                return {'success': True, 'transaction_count': 0}
            
            # Process each transaction
            for xero_transaction in response.bank_transactions:
                try:
                    # Create or update transaction record
                    transaction_data, created = TransactionData.objects.get_or_create(
                        integration=self.connection,
                        external_transaction_id=xero_transaction.bank_transaction_id,
                        defaults={
                            'external_account_id': tenant_id,  # Store tenant ID
                            'transaction_type': self._map_transaction_type(xero_transaction.type),
                            'date': xero_transaction.date,
                            'reference': xero_transaction.reference or '',
                            'description': getattr(xero_transaction, 'description', ''),
                            'amount': float(xero_transaction.total or 0),
                            'currency_code': str(self._safe_get_value(xero_transaction.currency_code, 'AUD'))[:3],
                            'status': self._safe_get_value(xero_transaction.status, 'authorised'),
                            'is_reconciled': getattr(xero_transaction, 'is_reconciled', False),
                            'contact_name': xero_transaction.contact.name if xero_transaction.contact else '',
                            'contact_external_id': xero_transaction.contact.contact_id if xero_transaction.contact else '',
                            'external_url': '',  # Use get_xero_url() method instead
                            'raw_data': convert_decimals_for_json({
                                'bank_transaction_id': xero_transaction.bank_transaction_id,
                                'account_id': xero_transaction.bank_account.account_id if xero_transaction.bank_account else '',
                                'type': self._safe_get_value(xero_transaction.type, None),
                                'tenant_id': tenant_id
                            })
                        }
                    )
                    
                    if created:
                        transactions_synced += 1
                        logger.info(f"Created new transaction: {transaction_data.external_transaction_id}")
                    else:
                        logger.debug(f"Transaction already exists: {transaction_data.external_transaction_id}")
                    
                    # Process line items if they exist
                    if xero_transaction.line_items:
                        for line_item in xero_transaction.line_items:
                            TransactionLineItem.objects.get_or_create(
                                transaction=transaction_data,
                                external_line_item_id=getattr(line_item, 'line_item_id', ''),
                                defaults={
                                    'description': line_item.description or '',
                                    'quantity': float(getattr(line_item, 'quantity', 1)),
                                    'unit_amount': float(getattr(line_item, 'unit_amount', 0)),
                                    'line_amount': float(getattr(line_item, 'line_amount', 0)),
                                    'tax_type': getattr(line_item, 'tax_type', ''),
                                    'tax_amount': float(getattr(line_item, 'tax_amount', 0)),
                                    'account_code': getattr(line_item, 'account_code', ''),
                                    'account_name': getattr(line_item.account, 'name', '') if hasattr(line_item, 'account') else '',
                                    'raw_data': {
                                        'line_item_id': getattr(line_item, 'line_item_id', ''),
                                        'tenant_id': tenant_id
                                    }
                                }
                            )
                            
                except Exception as transaction_error:
                    logger.error(f"Failed to process transaction {getattr(xero_transaction, 'bank_transaction_id', 'UNKNOWN')}: {transaction_error}")
                    continue
                    
            logger.info(f"Synced {transactions_synced} new transactions for tenant {tenant_id}")
            
            return {
                'success': True,
                'transaction_count': transactions_synced
            }
            
        except Exception as e:
            logger.error(f"Failed to sync transactions for tenant {tenant_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _safe_get_value(self, obj, default=None):
        """Safely get value from object, handling both enum objects and string values"""
        if not obj:
            return default
        
        # Handle both enum objects and string values
        if hasattr(obj, 'value'):
            return obj.value
        else:
            return obj
    
    def _map_transaction_type(self, xero_type) -> str:
        """Map Xero transaction types to our internal types"""
        if not xero_type:
            return 'other'
        
        # Handle both enum objects and string values
        type_str = self._safe_get_value(xero_type)
        
        type_mapping = {
            'RECEIVE': 'receive',
            'SPEND': 'spend',
            'TRANSFER': 'bank_transfer'
        }
        
        return type_mapping.get(str(type_str), 'other')
    
    def get_selected_accounts(self) -> List[str]:
        """Get list of selected account IDs from config"""
        return self.connection.config.get('selected_accounts', [])
    
    def get_chart_of_accounts(self, tenant_id: str) -> List[dict]:
        """Get chart of accounts from Xero for a specific tenant"""
        credentials = self.get_credentials()
        if not credentials:
            raise Exception("No credentials available")
        
        # Auto-refresh if needed
        if credentials.expires_soon():
            self._safe_refresh_token()
            credentials.refresh_from_db()
        
        # Setup API client
        oauth2_token = OAuth2Token(
            client_id=self.config['client_id'],
            client_secret=self.config['client_secret']
        )
        oauth2_token.access_token = credentials.access_token
        
        api_client = self._create_api_client(oauth2_token)
        accounting_api = AccountingApi(api_client)
        
        # Fetch accounts
        response = accounting_api.get_accounts(
            xero_tenant_id=tenant_id
        )
        
        # Convert to list of dictionaries
        accounts = []
        if response.accounts:
            for account in response.accounts:
                # Convert enum to string
                account_type = account.type
                if hasattr(account_type, 'value'):
                    account_type = account_type.value
                else:
                    account_type = str(account_type)
                    
                accounts.append({
                    'account_id': account.account_id,
                    'name': account.name,
                    'type': account_type,
                    'bank_account_number': getattr(account, 'bank_account_number', None),
                    'code': getattr(account, 'code', None),
                })
        
        return accounts

    def sync_data(self, sync_type: str = 'incremental') -> Sync:
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
                if not self._safe_refresh_token():
                    # Mark integration as needing reconnection instead of failing completely
                    self.connection.status = 'expired'
                    self.connection.last_error = "Token expired and refresh failed. Please reconnect to continue syncing."
                    self.connection.save()
                    raise TokenRefreshError("Token expired and refresh failed. Please reconnect to Xero to continue syncing.")
                credentials.refresh_from_db()
            
            # Setup API client
            oauth2_token = OAuth2Token(
                client_id=self.config['client_id'],
                client_secret=self.config['client_secret']
            )
            oauth2_token.access_token = credentials.access_token
            
            api_client = self._create_api_client(oauth2_token)
            accounting_api = AccountingApi(api_client)
            
            # Fetch and process bank transactions
            transactions_synced = self._sync_bank_transactions(
                accounting_api, 
                sync_type=sync_type,
                sync_record=sync_record
            )
            
            sync_record.status = 'completed'
            sync_record.completed_at = timezone.now()
            sync_record.records_success = transactions_synced
            sync_record.records_processed = transactions_synced
            sync_record.save()
            
            # Update integration last sync time
            self.connection.last_sync_at = timezone.now()
            self.connection.save()
            
            logger.info(f"Sync completed for integration {self.connection.id}: {transactions_synced} transactions")
            
        except Exception as e:
            sync_record.status = 'failed'
            sync_record.error_message = str(e)
            sync_record.completed_at = timezone.now()
            sync_record.save()
            
            logger.error(f"Sync failed for integration {self.connection.id}: {e}")
            raise
        
        return sync_record
    
    def _sync_bank_transactions(self, accounting_api: AccountingApi, 
                                sync_type: str, sync_record: Sync) -> int:
        """Fetch and store bank transactions from Xero"""
        from ..models import TransactionData, TransactionLineItem
        from datetime import datetime, timedelta
        
        # Determine date range for sync
        if sync_type == 'full':
            # Full sync - get last 2 years of data
            from_date = (datetime.now() - timedelta(days=730)).date()
        elif sync_type == 'daily':
            # Daily sync - get only yesterday's transactions
            from_date = (datetime.now() - timedelta(days=1)).date()
        else:
            # Incremental sync - get data since last sync or last 2 years for new integrations
            if self.connection.last_sync_at:
                from_date = self.connection.last_sync_at.date()
            else:
                # For new integrations, get last 2 years of data
                from_date = (datetime.now() - timedelta(days=730)).date()
        
        # Build where clause for filtering
        where_clause = f'Date >= DateTime({from_date.year}, {from_date.month}, {from_date.day})'
        
        # Only sync transactions for selected accounts if configured
        selected_accounts = self.get_selected_accounts()
        logger.info(f"Starting sync with date filter: {where_clause}")
        logger.info(f"Selected accounts filter: {selected_accounts}")
        
        transactions_synced = 0
        page = 1
        page_size = 100
        
        try:
            while True:
                try:
                    # Apply rate limiting before each API call
                    self.rate_limiter.wait_if_rate_limited()
                    
                    # Fetch transactions page by page
                    logger.info(f"Requesting page {page} from Xero API:")
                    logger.info(f"  - Tenant ID: {self.connection.external_account_id}")
                    logger.info(f"  - Where clause: {where_clause}")
                    logger.info(f"  - Page: {page}, Page size: {page_size}")
                    
                    response = accounting_api.get_bank_transactions(
                        xero_tenant_id=self.connection.external_account_id,
                        where=where_clause,
                        page=page,
                        page_size=page_size,
                        order='Date ASC'
                    )
                    
                    logger.info(f"Xero API response received:")
                    logger.info(f"  - Response type: {type(response)}")
                    logger.info(f"  - Has bank_transactions: {hasattr(response, 'bank_transactions')}")
                    if hasattr(response, 'bank_transactions'):
                        logger.info(f"  - Bank transactions count: {len(response.bank_transactions) if response.bank_transactions else 0}")
                except xero_exceptions.HTTPStatusException as e:
                    if e.status == 401:  # Token expired/unauthorized
                        logger.info(f"Got 401 error during sync on page {page}, attempting token refresh...")
                        credentials = self.get_credentials()
                        
                        if credentials and credentials.refresh_token:
                            if self._safe_refresh_token():
                                logger.info("Token refresh successful during sync, retrying page...")
                                # Recreate API client and continue with same page
                                api_client = self._create_api_client()
                                accounting_api = AccountingApi(api_client)
                                continue
                            else:
                                logger.error("Token refresh failed during sync")
                                raise TokenRefreshError("Token expired and refresh failed during sync. Please reconnect to Xero.")
                        else:
                            logger.error("No refresh token available during sync")
                            raise TokenRefreshError("Token expired and no refresh token available during sync. Please reconnect to Xero.")
                    elif e.status == 429:  # Rate limit exceeded
                        logger.warning(f"Rate limit hit on page {page}, waiting 60s...")
                        time.sleep(60)
                        continue
                    elif e.status in [500, 502, 503, 504]:  # Server errors
                        logger.warning(f"Server error on page {page}: {e.status}, retrying...")
                        time.sleep(5)
                        continue
                    else:
                        raise APIConnectionError(f"HTTP {e.status}: {str(e)}")
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Network error on page {page}: {e}, retrying...")
                    time.sleep(5)
                    continue
                
                if not response.bank_transactions:
                    logger.info(f"No transactions returned on page {page}, ending sync")
                    break
                
                logger.info(f"Page {page}: received {len(response.bank_transactions)} transactions from Xero")
                
                for xero_transaction in response.bank_transactions:
                    try:
                        # Skip if not in selected accounts (if configured)
                        if selected_accounts:
                            if xero_transaction.bank_account and \
                               xero_transaction.bank_account.account_id not in selected_accounts:
                                logger.debug(f"Skipping transaction from account {xero_transaction.bank_account.account_id} (not in selected accounts)")
                                continue
                        
                        # Map Xero transaction type to our types
                        transaction_type = self._map_transaction_type(xero_transaction.type)
                        
                        # Validate required fields
                        if not xero_transaction.bank_transaction_id:
                            logger.warning("Skipping transaction without ID")
                            continue
                        
                        # Prepare transaction data with safe field access
                        transaction_data = {
                            'external_transaction_id': xero_transaction.bank_transaction_id,
                            'external_account_id': getattr(xero_transaction.bank_account, 'account_id', '') if xero_transaction.bank_account else '',
                            'transaction_type': transaction_type,
                            'date': xero_transaction.date,
                            'reference': xero_transaction.reference or '',
                            'amount': abs(float(xero_transaction.total or 0)),
                            'currency_code': str(getattr(xero_transaction, 'currency_code', 'USD') or 'USD')[:3],
                            'status': xero_transaction.status.lower() if xero_transaction.status else 'authorised',
                            'is_reconciled': bool(xero_transaction.is_reconciled),
                            'external_url': '',  # Use get_xero_url() method instead
                            'raw_data': convert_decimals_for_json(xero_transaction.to_dict()) if hasattr(xero_transaction, 'to_dict') else {},
                            'last_synced_at': timezone.now()
                        }
                        
                        # Add contact info if available
                        if xero_transaction.contact:
                            transaction_data['contact_name'] = getattr(xero_transaction.contact, 'name', '') or ''
                            transaction_data['contact_external_id'] = getattr(xero_transaction.contact, 'contact_id', '') or ''
                        
                        # Create or update transaction
                        transaction, created = TransactionData.objects.update_or_create(
                            integration=self.connection,
                            external_transaction_id=xero_transaction.bank_transaction_id,
                            defaults=transaction_data
                        )
                        
                        # Process line items
                        if xero_transaction.line_items:
                            try:
                                # Delete existing line items for update case
                                if not created:
                                    transaction.line_items.all().delete()
                                
                                for xero_line in xero_transaction.line_items:
                                    TransactionLineItem.objects.create(
                                        transaction=transaction,
                                        description=getattr(xero_line, 'description', '') or '',
                                        quantity=float(getattr(xero_line, 'quantity', 1) or 1),
                                        unit_amount=float(getattr(xero_line, 'unit_amount', 0) or 0),
                                        line_amount=float(getattr(xero_line, 'line_amount', 0) or 0),
                                        tax_type=getattr(xero_line, 'tax_type', '') or '',
                                        tax_amount=float(getattr(xero_line, 'tax_amount', 0) or 0),
                                        account_code=getattr(xero_line, 'account_code', '') or '',
                                        raw_data=xero_line.to_dict() if hasattr(xero_line, 'to_dict') else {}
                                    )
                            except Exception as line_error:
                                logger.warning(f"Error processing line items for transaction {xero_transaction.bank_transaction_id}: {line_error}")
                                # Continue processing the transaction even if line items fail
                        
                        transactions_synced += 1
                        
                    except Exception as transaction_error:
                        logger.error(f"Error processing transaction {getattr(xero_transaction, 'bank_transaction_id', 'UNKNOWN')}: {transaction_error}")
                        sync_record.records_failed = getattr(sync_record, 'records_failed', 0) + 1
                        sync_record.save()
                        # Continue with next transaction
                
                # Check if there are more pages
                if len(response.bank_transactions) < page_size:
                    break
                
                page += 1
                
                # Update sync record periodically
                if transactions_synced % 500 == 0:
                    sync_record.records_processed = transactions_synced
                    sync_record.save()
                    logger.info(f"Synced {transactions_synced} transactions so far...")
        
        except Exception as e:
            logger.error(f"Error syncing bank transactions: {e}")
            sync_record.error_details = {
                'error': str(e),
                'last_page': page,
                'transactions_synced': transactions_synced
            }
            sync_record.save()
            raise
        
        return transactions_synced
    
    def _map_transaction_type(self, xero_type: str) -> str:
        """Map Xero transaction types to our internal types"""
        type_mapping = {
            'SPEND': 'spend',
            'RECEIVE': 'receive', 
            'TRANSFER': 'bank_transfer',
            'SPEND-OVERPAYMENT': 'spend',
            'SPEND-PREPAYMENT': 'spend',
            'RECEIVE-OVERPAYMENT': 'receive',
            'RECEIVE-PREPAYMENT': 'receive',
        }
        return type_mapping.get(xero_type.upper() if xero_type else '', 'other')
    
    def _build_transaction_url(self, transaction_id: str, account_id: str = None) -> str:
        """Build URL to view transaction in Xero"""
        # Simple Xero URL format: https://go.xero.com/Bank/ViewTransaction.aspx?bankTransactionID={id}
        return f"https://go.xero.com/Bank/ViewTransaction.aspx?bankTransactionID={transaction_id}"


# Register the service
ConnectionServiceRegistry.register('xero', XeroConnectionService)