from django.urls import path
from . import views

app_name = 'connections'

urlpatterns = [
    # OAuth flows
    path('xero/connect/', views.xero_connect, name='xero_connect'),
    path('xero/callback/', views.xero_callback, name='xero_callback'),
    
    # Connection management  
    path('<str:integration_prefix_id>/test/', views.test_integration, name='test_integration'),
    path('<str:integration_prefix_id>/sync/', views.sync_integration, name='sync_integration'),
    path('<str:integration_prefix_id>/refresh-sync/', views.refresh_sync_integration, name='refresh_sync_integration'),
    path('<str:integration_prefix_id>/revoke/', views.revoke_integration, name='revoke_integration'),
    path('<str:integration_prefix_id>/delete/', views.delete_integration, name='delete_integration'),
    
    # Handle callback when accessed directly from /xero/callback/
    path('', views.xero_callback, name='xero_callback_direct_handler'),
]