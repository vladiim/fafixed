from django.urls import path
from . import views

app_name = 'financial_data'

urlpatterns = [
    # Chart of accounts management
    path('xero/chart-accounts/<str:integration_prefix_id>/', views.xero_chart_accounts, name='xero_chart_accounts'),
    path('import-chart-accounts/', views.import_chart_accounts, name='import_chart_accounts'),
    
    # Transaction management
    path('transactions/<str:integration_prefix_id>/', views.transaction_list, name='transaction_list'),
    path('transactions/<str:transaction_prefix_id>/actions/', views.transaction_actions, name='transaction_actions'),
    path('transactions/<str:transaction_prefix_id>/refresh-status/', views.refresh_transaction_status, name='refresh_transaction_status'),
    
    # Transaction editing (super_admin only)
    path('transactions/<str:transaction_prefix_id>/edit/', views.transaction_edit, name='transaction_edit'),
    path('transactions/<str:transaction_prefix_id>/edit-check/', views.transaction_edit_check, name='transaction_edit_check'),
]