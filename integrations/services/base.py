from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from django.utils import timezone
from ..models import Integration, IntegrationCredential, IntegrationSync
import logging

logger = logging.getLogger(__name__)


class BaseIntegrationService(ABC):
    """Abstract base class for all integration services"""
    
    def __init__(self, integration: Integration):
        self.integration = integration
        self.account = integration.account
        
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
        """Test the integration connection"""
        pass
    
    @abstractmethod
    def sync_data(self, sync_type: str = 'incremental') -> IntegrationSync:
        """Perform data synchronization"""
        pass
    
    def get_credentials(self) -> Optional[IntegrationCredential]:
        """Get integration credentials"""
        try:
            return self.integration.credentials
        except IntegrationCredential.DoesNotExist:
            return None
    
    def store_credentials(self, 
                         access_token: str,
                         refresh_token: Optional[str] = None,
                         expires_in: Optional[int] = None,
                         scopes: Optional[List[str]] = None,
                         **additional_data) -> IntegrationCredential:
        """Store OAuth credentials securely"""
        
        credentials, created = IntegrationCredential.objects.get_or_create(
            integration=self.integration
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
        
        # Update integration status
        self.integration.status = 'active'
        self.integration.connected_at = timezone.now()
        self.integration.last_error = None
        self.integration.save()
        
        logger.info(f"Credentials stored for integration {self.integration.id}")
        return credentials
    
    def handle_auth_error(self, error: Exception, context: str = ""):
        """Handle authentication errors consistently"""
        error_msg = f"{context}: {str(error)}" if context else str(error)
        
        self.integration.status = 'error'
        self.integration.last_error = error_msg
        self.integration.save()
        
        logger.error(f"Auth error for integration {self.integration.id}: {error_msg}")
        
    def create_sync_record(self, sync_type: str) -> IntegrationSync:
        """Create a new sync record"""
        return IntegrationSync.objects.create(
            integration=self.integration,
            sync_type=sync_type,
            status='pending'
        )


class IntegrationServiceRegistry:
    """Registry for integration services"""
    
    _services = {}
    
    @classmethod
    def register(cls, provider_name: str, service_class):
        """Register a service class for a provider"""
        cls._services[provider_name] = service_class
    
    @classmethod
    def get_service(cls, integration: Integration) -> BaseIntegrationService:
        """Get service instance for an integration"""
        provider_name = integration.provider.name
        
        if provider_name not in cls._services:
            raise ValueError(f"No service registered for provider: {provider_name}")
        
        service_class = cls._services[provider_name]
        return service_class(integration)