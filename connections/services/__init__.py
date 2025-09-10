# Import services to ensure they get registered
from .base import BaseConnectionService, ConnectionServiceRegistry
from .providers.xero import XeroConnectionService

# Register the Xero service
ConnectionServiceRegistry.register('xero', XeroConnectionService)

__all__ = [
    'BaseConnectionService',
    'ConnectionServiceRegistry', 
    'XeroConnectionService'
]