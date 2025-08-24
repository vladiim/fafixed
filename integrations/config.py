import os
from typing import Dict, Any
from django.conf import settings


class BaseIntegrationConfig:
    """Base class for integration configurations"""
    
    def __init__(self):
        self.validate_config()
    
    def validate_config(self):
        """Override in subclasses to validate required configuration"""
        pass
    
    def get_config(self) -> Dict[str, Any]:
        """Override in subclasses to return configuration dict"""
        raise NotImplementedError


class XeroConfig(BaseIntegrationConfig):
    """Xero integration configuration"""
    
    def __init__(self):
        self.client_id = os.getenv('XERO_CLIENT_ID')
        self.client_secret = os.getenv('XERO_CLIENT_SECRET')
        self.redirect_uri = self._get_redirect_uri()
        self.scopes = ['accounting.transactions', 'accounting.contacts', 'accounting.settings']
        super().__init__()
    
    def _get_redirect_uri(self) -> str:
        """Get redirect URI based on environment"""
        # Check if explicitly set in environment
        if os.getenv('XERO_REDIRECT_URI'):
            return os.getenv('XERO_REDIRECT_URI')
        
        # Determine base URL based on environment
        if settings.DEBUG:
            base_url = 'http://localhost:8000'
        else:
            base_url = 'https://fafixed.com'
        
        return f'{base_url}/xero/callback/'
    
    def validate_config(self):
        """Validate that required Xero configuration is present"""
        if not self.client_id:
            raise ValueError("XERO_CLIENT_ID environment variable is required")
        if not self.client_secret:
            raise ValueError("XERO_CLIENT_SECRET environment variable is required")
    
    def get_config(self) -> Dict[str, Any]:
        """Return Xero configuration dictionary"""
        return {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': self.redirect_uri,
            'scopes': self.scopes
        }


class IntegrationConfigManager:
    """Manager class for all integration configurations"""
    
    _configs = {
        'xero': XeroConfig,
    }
    
    @classmethod
    def get_config(cls, integration_type: str) -> BaseIntegrationConfig:
        """Get configuration for a specific integration type"""
        if integration_type not in cls._configs:
            raise ValueError(f"Unknown integration type: {integration_type}")
        
        return cls._configs[integration_type]()
    
    @classmethod
    def register_integration(cls, integration_type: str, config_class: type):
        """Register a new integration configuration class"""
        cls._configs[integration_type] = config_class