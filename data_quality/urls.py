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

    # Suggestion review dashboard
    path('suggestions/', views.suggestion_review_dashboard, name='suggestion_review_dashboard'),

    # Suggestion actions
    path('suggestions/<int:suggestion_id>/ignore/', views.ignore_suggestion, name='ignore_suggestion'),
    path('suggestions/<int:suggestion_id>/mark-done/', views.mark_done_suggestion, name='mark_done_suggestion'),
    path('suggestions/<int:suggestion_id>/fix/', views.fix_suggestion, name='fix_suggestion'),
    path('suggestions/bulk-ignore/', views.bulk_ignore_suggestions, name='bulk_ignore_suggestions'),

    # Turbo frame endpoints
    path('connections/<int:connection_id>/tracking-categories/', views.tracking_categories_dropdown, name='tracking_categories_dropdown'),
]