from django.urls import path
from . import views

urlpatterns = [
    path('xero/connect/', views.xero_connect, name='xero_connect'),
    path('xero/callback/', views.xero_callback, name='xero_callback'),
    path('xero/chart-accounts/<str:integration_prefix_id>/', views.xero_chart_accounts, name='xero_chart_accounts'),
    path('import-chart-accounts/', views.import_chart_accounts, name='import_chart_accounts'),
    path('test/<str:integration_prefix_id>/', views.test_integration, name='test_integration'),
    path('sync/<str:integration_prefix_id>/', views.sync_integration, name='sync_integration'),
    path('revoke/<str:integration_prefix_id>/', views.revoke_integration, name='revoke_integration'),
    path('transactions/<str:integration_prefix_id>/', views.transaction_list, name='transaction_list'),
    
    # Handle callback when accessed directly from /xero/callback/
    path('', views.xero_callback, name='xero_callback_direct_handler'),
]