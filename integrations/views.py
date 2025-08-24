from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Integration, Issue
import uuid
from datetime import datetime, timedelta
import random

@login_required
def xero_connect(request):
    return render(request, 'integrations/xero_connect.html')

@login_required
def xero_callback(request):
    # Simulate Xero OAuth callback with mock data
    mock_accounts = [
        {'name': 'Main Trading Account', 'org': 'Smith & Associates Ltd'},
        {'name': 'Investment Portfolio', 'org': 'Smith & Associates Ltd'},
        {'name': 'Primary Business Account', 'org': 'Tech Innovations Pty'},
        {'name': 'Expense Management', 'org': 'Green Energy Solutions'},
    ]
    
    return render(request, 'integrations/xero_accounts.html', {
        'accounts': mock_accounts
    })

@login_required
def import_accounts(request):
    if request.method == 'POST':
        selected_accounts = request.POST.getlist('accounts')
        
        for account_data in selected_accounts:
            # Parse the account data (format: "account_name|org_name")
            account_name, org_name = account_data.split('|')
            
            # Create integration
            integration = Integration.objects.create(
                user=request.user,
                integration_type='xero',
                account_name=account_name,
                account_id=str(uuid.uuid4()),
                organization_name=org_name
            )
            
            # Create mock issues for this integration
            create_mock_issues(integration)
        
        messages.success(request, f'Successfully imported {len(selected_accounts)} account(s)')
        return redirect('dashboard')
    
    return redirect('xero_connect')

def create_mock_issues(integration):
    """Create some mock issues for demonstration"""
    mock_issues = [
        {
            'title': 'Duplicate transaction detected',
            'description': 'Transaction #TXN-2024-001 appears to be duplicated on 2024-01-15',
            'category': 'duplicate_transactions',
            'severity': 'high',
            'count': 3,
        },
        {
            'title': 'Missing tax codes on invoices',
            'description': '15 invoices from Q1 2024 are missing required tax codes',
            'category': 'tax_code_errors',
            'severity': 'medium',
            'count': 15,
        },
        {
            'title': 'Inconsistent supplier categorization',
            'description': 'Office Supplies Ltd categorized differently across transactions',
            'category': 'inconsistent_categories',
            'severity': 'low',
            'count': 8,
        },
        {
            'title': 'Future dated transactions',
            'description': 'Found 2 transactions with dates more than 30 days in the future',
            'category': 'date_anomalies',
            'severity': 'critical',
            'count': 2,
        },
        {
            'title': 'Large amount variance detected',
            'description': 'Transaction amounts significantly different from historical patterns',
            'category': 'amount_discrepancies',
            'severity': 'medium',
            'count': 5,
        }
    ]
    
    for issue_data in random.sample(mock_issues, random.randint(2, 4)):
        Issue.objects.create(
            integration=integration,
            title=issue_data['title'],
            description=issue_data['description'],
            category=issue_data['category'],
            severity=issue_data['severity'],
            count=issue_data['count'],
            first_seen=datetime.now() - timedelta(days=random.randint(1, 30)),
            last_seen=datetime.now() - timedelta(hours=random.randint(1, 24))
        )
