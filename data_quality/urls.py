from django.urls import path
from . import views

app_name = 'data_quality'

urlpatterns = [
    # Validation management
    path('transactions/<str:transaction_prefix_id>/run-validations/', views.run_transaction_validations, name='run_transaction_validations'),
    
    # Issue management
    path('issues/', views.issue_list, name='issue_list'),
    path('issues/<str:issue_prefix_id>/', views.issue_detail, name='issue_detail'),
    path('issues/<str:issue_prefix_id>/resolve/', views.resolve_issue, name='resolve_issue'),
    path('issues/bulk-resolve/', views.bulk_resolve_issues, name='bulk_resolve_issues'),
    
    # Agent Checks - validation rules interface
    path('agent-checks/', views.agent_checks, name='agent_checks'),
    path('agent-checks/configure-smart-categorisation/', views.configure_smart_categorisation, name='configure_smart_categorisation'),
    
    # Smart Categorisation CRUD
    path('agent-checks/rules/create/', views.create_categorisation_rule, name='create_categorisation_rule'),
    path('agent-checks/rules/<int:rule_id>/edit/', views.edit_categorisation_rule, name='edit_categorisation_rule'),
    path('agent-checks/rules/<int:rule_id>/delete/', views.delete_categorisation_rule, name='delete_categorisation_rule'),
]