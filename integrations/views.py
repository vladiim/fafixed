from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import Integration, Issue, IntegrationProvider
from .managers import IntegrationManager
from core.models import Account
from . import services  # Import services to ensure registration
import uuid
from datetime import datetime, timedelta
import random

@login_required
def xero_connect(request):
    """Initiate Xero OAuth flow"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Xero connect initiated by user: {request.user.email}")
    
    # Get user's current account
    if not hasattr(request.user, 'profile'):
        logger.error(f"User {request.user.email} has no profile")
        messages.error(request, "User profile not found. Please contact support.")
        return redirect('dashboard')
        
    if not request.user.profile.current_account:
        logger.error(f"User {request.user.email} has no current account set")
        messages.error(request, "No account selected. Please select an account first.")
        return redirect('dashboard')
    
    current_account = request.user.profile.current_account
    logger.info(f"Current account: {current_account.name} (ID: {current_account.id})")
    
    try:
        # Check if active integration already exists (allow retry for failed/expired ones)
        existing_integration = Integration.objects.filter(
            account=current_account,
            provider__name='xero',
            status='active'
        ).first()
        
        if existing_integration:
            logger.info(f"Active Xero integration found: {existing_integration.id}")
            messages.info(request, "Xero integration already exists for this account.")
            return redirect('dashboard')
        
        logger.info("Creating new Xero integration...")
        
        # Create new integration
        integration = IntegrationManager.create_integration(
            account=current_account,
            provider_name='xero',
            created_by=request.user
        )
        
        logger.info(f"Created integration: {integration.id}")
        
        # Generate OAuth URL
        auth_url = IntegrationManager.initiate_oauth_flow(
            integration, 
            state=str(integration.id)
        )
        
        logger.info(f"Generated OAuth URL: {auth_url}")
        
        return redirect(auth_url)
        
    except Exception as e:
        logger.error(f"Failed to create Xero integration: {str(e)}", exc_info=True)
        messages.error(request, f"Failed to connect to Xero: {str(e)}")
        return redirect('dashboard')

@login_required
def xero_callback(request):
    """Handle Xero OAuth callback"""
    auth_code = request.GET.get('code')
    state = request.GET.get('state')
    error = request.GET.get('error')
    
    if error:
        messages.error(request, f"Xero authentication failed: {error}")
        return redirect('dashboard')
    
    if not auth_code:
        messages.error(request, "No authorization code received from Xero")
        return redirect('dashboard')
    
    if not state:
        messages.error(request, "Invalid authentication state")
        return redirect('dashboard')
    
    try:
        # Get the integration by state (integration ID)
        integration = get_object_or_404(Integration, id=state, status='pending')
        
        # Verify user has access to this integration
        if not request.user.account_memberships.filter(account=integration.account).exists():
            messages.error(request, "Access denied")
            return redirect('dashboard')
        
        # Complete OAuth flow
        result = IntegrationManager.complete_oauth_flow(integration, auth_code, state=state)
        
        if result.get('success'):
            # Create mock issues for this integration (for demo purposes)
            create_mock_issues(integration)
            
            messages.success(request, f"Successfully connected to Xero: {result['organization_name']}")
            return redirect('dashboard')
        else:
            messages.error(request, "Failed to complete Xero authentication")
            return redirect('dashboard')
        
    except Integration.DoesNotExist:
        messages.error(request, "Invalid authentication state")
        return redirect('dashboard')
    except Exception as e:
        messages.error(request, f"Failed to complete Xero authentication: {str(e)}")
        return redirect('dashboard')

@login_required
def test_integration(request, integration_id):
    """Test an existing integration connection"""
    try:
        integration = get_object_or_404(
            Integration, 
            id=integration_id,
            account__account_users__user=request.user
        )
        
        result = IntegrationManager.test_integration(integration)
        
        if result.get('success'):
            messages.success(request, "Integration test successful")
        else:
            messages.error(request, f"Integration test failed: {result.get('error')}")
            
    except Exception as e:
        messages.error(request, f"Failed to test integration: {str(e)}")
    
    return redirect('dashboard')


@login_required
def revoke_integration(request, integration_id):
    """Revoke an integration"""
    try:
        integration = get_object_or_404(
            Integration,
            id=integration_id,
            account__account_users__user=request.user
        )
        
        if IntegrationManager.revoke_integration(integration):
            messages.success(request, "Integration successfully revoked")
        else:
            messages.error(request, "Failed to revoke integration")
            
    except Exception as e:
        messages.error(request, f"Failed to revoke integration: {str(e)}")
    
    return redirect('dashboard')

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
