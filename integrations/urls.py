from django.urls import path
from . import views

# integrations/urls.py
#
# All domain-specific URLs have been moved to their respective apps:
# - OAuth & connection URLs → connections/urls.py  
# - Transaction URLs → financial_data/urls.py
# - Issue management URLs → data_quality/urls.py
#
# This file now contains only shared service endpoints

urlpatterns = [
    # Shared services health check
    path('health/', views.health_check, name='integrations_health'),
    
    # Keep this legacy callback handler for backward compatibility
    # TODO: Remove after confirming all external OAuth configs point to /connections/xero/callback/
    # path('', views.xero_callback, name='xero_callback_legacy_handler'),
]