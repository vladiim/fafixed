from typing import Dict, Any, List, Optional
from django.db import transaction
from django.utils import timezone
from .models import Integration, IntegrationProvider, IntegrationSync
from .services.base import IntegrationServiceRegistry
import logging

logger = logging.getLogger(__name__)


class IntegrationManager:
    """Central manager for integration operations"""
    
    @staticmethod
    def create_integration(account, provider_name: str, created_by, **kwargs) -> Integration:
        """Create a new integration for an account"""
        try:
            provider = IntegrationProvider.objects.get(
                name=provider_name, 
                is_active=True
            )
        except IntegrationProvider.DoesNotExist:
            raise ValueError(f"Provider '{provider_name}' not found or inactive")
        
        with transaction.atomic():
            integration = Integration.objects.create(
                account=account,
                provider=provider,
                created_by=created_by,
                status='pending',
                **kwargs
            )
            
            logger.info(f"Created integration {integration.id} for account {account.id}")
            return integration
    
    @staticmethod
    def initiate_oauth_flow(integration: Integration, **kwargs) -> str:
        """Initiate OAuth flow for an integration"""
        service = IntegrationServiceRegistry.get_service(integration)
        return service.get_auth_url(**kwargs)
    
    @staticmethod
    def complete_oauth_flow(integration: Integration, auth_code: str, **kwargs) -> Dict[str, Any]:
        """Complete OAuth flow and store credentials"""
        service = IntegrationServiceRegistry.get_service(integration)
        return service.handle_callback(auth_code, **kwargs)
    
    @staticmethod
    def test_integration(integration: Integration) -> Dict[str, Any]:
        """Test an integration connection"""
        service = IntegrationServiceRegistry.get_service(integration)
        return service.test_connection()
    
    @staticmethod
    def sync_integration(integration: Integration, sync_type: str = 'incremental') -> IntegrationSync:
        """Sync data for an integration"""
        service = IntegrationServiceRegistry.get_service(integration)
        return service.sync_data(sync_type)
    
    @staticmethod
    def refresh_credentials(integration: Integration) -> bool:
        """Refresh credentials for an integration"""
        service = IntegrationServiceRegistry.get_service(integration)
        return service.refresh_token()
    
    @staticmethod
    def revoke_integration(integration: Integration) -> bool:
        """Revoke and deactivate an integration"""
        try:
            # Try to revoke with the provider first
            service = IntegrationServiceRegistry.get_service(integration)
            
            # If provider supports revocation, call it
            if hasattr(service, 'revoke_access'):
                service.revoke_access()
            
            # Update integration status
            integration.status = 'revoked'
            integration.save()
            
            # Delete credentials
            if hasattr(integration, 'credentials'):
                integration.credentials.delete()
            
            logger.info(f"Revoked integration {integration.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to revoke integration {integration.id}: {e}")
            return False
    
    @staticmethod
    def get_account_integrations(account, provider_name: Optional[str] = None, 
                               status: Optional[str] = None) -> List[Integration]:
        """Get integrations for an account with optional filters"""
        queryset = Integration.objects.filter(account=account)
        
        if provider_name:
            queryset = queryset.filter(provider__name=provider_name)
        
        if status:
            queryset = queryset.filter(status=status)
        
        return list(queryset.select_related('provider', 'created_by'))
    
    @staticmethod
    def check_expired_tokens():
        """Background task to check and refresh expired tokens"""
        expired_integrations = Integration.objects.filter(
            status='active',
            credentials__expires_at__lte=timezone.now()
        )
        
        for integration in expired_integrations:
            try:
                if IntegrationManager.refresh_credentials(integration):
                    logger.info(f"Auto-refreshed token for integration {integration.id}")
                else:
                    integration.status = 'expired'
                    integration.save()
                    logger.warning(f"Failed to refresh token for integration {integration.id}")
            except Exception as e:
                logger.error(f"Error refreshing token for integration {integration.id}: {e}")