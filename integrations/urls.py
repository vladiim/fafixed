from django.urls import path
from . import views

urlpatterns = [
    path('xero/connect/', views.xero_connect, name='xero_connect'),
    path('xero/callback/', views.xero_callback, name='xero_callback'),
    path('xero/accounts/<int:integration_id>/', views.xero_accounts, name='xero_accounts'),
    path('import_accounts/', views.import_accounts, name='import_accounts'),
    path('test/<int:integration_id>/', views.test_integration, name='test_integration'),
    path('revoke/<int:integration_id>/', views.revoke_integration, name='revoke_integration'),
    
    # Handle callback when accessed directly from /xero/callback/
    path('', views.xero_callback, name='xero_callback_direct_handler'),
]