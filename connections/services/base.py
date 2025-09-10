from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from django.utils import timezone
from ..models import Connection, Credential, Sync
import logging

logger = logging.getLogger(__name__)


class BaseConnectionService(ABC):
    """Abstract base class for all connection services"""
    
    def __init__(self, connection: Connection):
        self.connection = connection
        self.account = connection.account
        
    @abstractmethod
    def get_auth_url(self, state: Optional[str] = None, **kwargs) -> str:
        """Generate OAuth authorization URL"""
        pass
    
    @abstractmethod
    def handle_callback(self, auth_code: str, state: Optional[str] = None) -> Dict[str, Any]:
        """Handle OAuth callback and store credentials"""
        pass
    
    @abstractmethod
    def refresh_token(self) -> bool:
        """Refresh access token using refresh token"""
        pass
    
    @abstractmethod
    def test_connection(self) -> Dict[str, Any]:
        """Test the connection"""
        pass
    
    @abstractmethod
    def sync_data(self, sync_type: str = 'incremental') -> Sync:
        """Perform data synchronization"""
        pass
    
    def get_credentials(self) -> Optional[Credential]:
        """Get connection credentials"""
        try:
            return self.connection.credentials
        except Credential.DoesNotExist:
            return None
    
    def store_credentials(self, 
                         access_token: str,
                         refresh_token: Optional[str] = None,
                         expires_in: Optional[int] = None,
                         scopes: Optional[List[str]] = None,
                         **additional_data) -> Credential:
        """Store OAuth credentials securely"""
        
        credentials, created = Credential.objects.get_or_create(
            connection=self.connection
        )
        
        credentials.access_token = access_token
        if refresh_token:
            credentials.refresh_token = refresh_token
            
        if expires_in:
            credentials.expires_at = timezone.now() + timezone.timedelta(seconds=expires_in)
        
        if scopes:
            credentials.scopes = scopes
            
        # Store additional provider-specific data
        if additional_data:
            import json
            current_additional = {}
            try:
                if credentials.additional_credentials:
                    current_additional = json.loads(credentials.additional_credentials)
            except (json.JSONDecodeError, TypeError):
                pass
                
            current_additional.update(additional_data)
            credentials.additional_credentials = json.dumps(current_additional)
        
        credentials.save()
        
        # Update connection status
        self.connection.status = 'active'
        self.connection.connected_at = timezone.now()
        self.connection.last_error = None
        self.connection.save()
        
        logger.info(f"Credentials stored for connection {self.connection.prefix_id}")
        return credentials
    
    def handle_auth_error(self, error: Exception, context: str = ""):
        """Handle authentication errors consistently"""
        error_msg = f"{context}: {str(error)}" if context else str(error)
        
        self.connection.status = 'error'
        self.connection.last_error = error_msg
        self.connection.save()
        
        logger.error(f"Auth error for connection {self.connection.prefix_id}: {error_msg}")
        
    def create_sync_record(self, sync_type: str) -> Sync:
        """Create a new sync record"""
        return Sync.objects.create(
            connection=self.connection,
            sync_type=sync_type,
            status='pending'
        )


class ConnectionServiceRegistry:
    """Registry for connection services"""
    
    _services = {}
    
    @classmethod
    def register(cls, provider_name: str, service_class):
        """Register a service class for a provider"""
        cls._services[provider_name] = service_class
    
    @classmethod
    def get_service(cls, connection: Connection) -> BaseConnectionService:
        """Get service instance for a connection"""
        provider_name = connection.provider.name
        
        if provider_name not in cls._services:
            raise ValueError(f"No service registered for provider: {provider_name}")
        
        service_class = cls._services[provider_name]
        return service_class(connection)