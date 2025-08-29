from django.urls import path
from . import views

urlpatterns = [
    path('xero/connect/', views.xero_connect, name='xero_connect'),
    path('xero/callback/', views.xero_callback, name='xero_callback'),
    path('xero/chart-accounts/<str:integration_prefix_id>/', views.xero_chart_accounts, name='xero_chart_accounts'),
    path('import-chart-accounts/', views.import_chart_accounts, name='import_chart_accounts'),
    path('test/<str:integration_prefix_id>/', views.test_integration, name='test_integration'),
    path('sync/<str:integration_prefix_id>/', views.sync_integration, name='sync_integration'),
    path('refresh-sync/<str:integration_prefix_id>/', views.refresh_sync_integration, name='refresh_sync_integration'),
    path('revoke/<str:integration_prefix_id>/', views.revoke_integration, name='revoke_integration'),
    path('transactions/<str:integration_prefix_id>/', views.transaction_list, name='transaction_list'),
    path('transactions/<int:transaction_id>/actions/', views.transaction_actions, name='transaction_actions'),
    path('transactions/<int:transaction_id>/run-validations/', views.run_transaction_validations, name='run_transaction_validations'),
    path('transactions/<int:transaction_id>/refresh-status/', views.refresh_transaction_status, name='refresh_transaction_status'),
    
    # Handle callback when accessed directly from /xero/callback/
    path('', views.xero_callback, name='xero_callback_direct_handler'),
]