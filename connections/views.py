from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from turbo_helper import turbo_stream
from integrations.models import Integration, IntegrationProvider, OAuthState
from .models import Connection
from integrations.services.base import IntegrationServiceRegistry
from integrations.managers import IntegrationManager
from core.models import Account
from core.decorators import super_admin_required
import uuid
from datetime import datetime, timedelta
import logging


@login_required
def xero_connect(request):
    """Initiate Xero OAuth flow"""
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
        # Always create a new integration to allow multiple integrations per account
        logger.info("Creating new Xero integration...")
        integration = IntegrationManager.create_integration(
            account=current_account,
            provider_name='xero',
            created_by=request.user
        )
        
        logger.info(f"Using integration: {integration.id}")
        
        # Create secure OAuth state token
        oauth_state = OAuthState.create_state_token(integration, request.user)
        
        # Generate OAuth URL with secure state
        auth_url = IntegrationManager.initiate_oauth_flow(
            integration, 
            state=oauth_state.state_token
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
        # Validate OAuth state token
        try:
            oauth_state = OAuthState.objects.get(
                state_token=state,
                is_used=False,
                created_by=request.user
            )
        except OAuthState.DoesNotExist:
            messages.error(request, "Invalid or expired authentication state")
            return redirect('dashboard')
        
        integration = oauth_state.integration
        
        # Verify integration is still pending
        if integration.status != 'pending':
            messages.error(request, "Connection is no longer pending authorization")
            return redirect('dashboard')
        
        # Verify user still has access to this integration
        if not request.user.account_memberships.filter(account=integration.account).exists():
            messages.error(request, "Access denied")
            return redirect('dashboard')
        
        # Mark state token as used to prevent replay attacks
        oauth_state.mark_as_used()
        
        # Complete OAuth flow
        result = IntegrationManager.complete_oauth_flow(integration, auth_code, state=state)
        
        if result.get('success'):
            messages.success(request, f"Successfully connected to Xero: {result['organization_name']}")
            # Redirect to client organisation selection instead of dashboard
            return redirect('xero_chart_accounts', integration_prefix_id=integration.prefix_id)
        else:
            messages.error(request, "Failed to complete Xero authentication")
            return redirect('dashboard')
        
    except Connection.DoesNotExist:
        messages.error(request, "Invalid authentication state")
        return redirect('dashboard')
    except Exception as e:
        messages.error(request, f"Failed to complete Xero authentication: {str(e)}")
        return redirect('dashboard')


@login_required
def test_integration(request, integration_id):
    """Test an existing integration"""
    try:
        integration = get_object_or_404(
            Connection, 
            id=integration_id,
            account__account_users__user=request.user
        )
        
        result = IntegrationManager.test_integration(integration)
        
        if result.get('success'):
            messages.success(request, "Connection test successful")
        else:
            messages.error(request, f"Connection test failed: {result.get('error')}")
            
    except Exception as e:
        messages.error(request, f"Failed to test integration: {str(e)}")
    
    return redirect('dashboard')


@login_required
def revoke_integration(request, integration_prefix_id):
    """Revoke a integration"""
    try:
        integration = get_object_or_404(
            Connection,
            prefix_id=integration_prefix_id,
            account__account_users__user=request.user
        )
        
        if IntegrationManager.revoke_integration(integration):
            messages.success(request, "Connection successfully revoked")
        else:
            messages.error(request, "Failed to revoke integration")
            
    except Exception as e:
        messages.error(request, f"Failed to revoke integration: {str(e)}")
    
    return redirect('dashboard')


@login_required
def delete_integration(request, integration_prefix_id):
    """Delete a integration"""
    try:
        integration = get_object_or_404(
            Connection,
            prefix_id=integration_prefix_id,
            account__account_users__user=request.user
        )
        
        if IntegrationManager.delete_integration(integration):
            messages.success(request, "Connection successfully deleted")
        else:
            messages.error(request, "Failed to delete integration")
            
    except Exception as e:
        messages.error(request, f"Failed to delete integration: {str(e)}")
    
    return redirect('dashboard')


@login_required  
def sync_integration(request, integration_prefix_id):
    """Trigger data sync for a integration"""
    logger = logging.getLogger(__name__)

    # Get sync type from query parameters (default to incremental)
    sync_type = request.GET.get('sync_type', 'incremental')

    try:
        from integrations.models import Integration
        integration = get_object_or_404(
            Integration,
            prefix_id=integration_prefix_id,
            account__account_users__user=request.user
        )

        logger.info(f"Syncing integration {integration.prefix_id} with sync_type: {sync_type}")

        # Trigger sync with specified type using the Integration model directly
        from integrations.tasks import sync_single_integration
        result = sync_single_integration.delay(integration.id, sync_type)

        if result:
            if sync_type == 'full':
                messages.success(request, "Full data resync started successfully. This will fetch all transaction data including tracking categories.")
            else:
                messages.success(request, "Data sync started successfully")
        else:
            messages.error(request, f"Failed to start sync")

    except Exception as e:
        logger.error(f"Failed to sync integration: {str(e)}", exc_info=True)
        messages.error(request, f"Failed to sync integration: {str(e)}")

    # Redirect back to transaction list if we came from there
    if 'transaction_list' in request.META.get('HTTP_REFERER', ''):
        return redirect('financial_data:transaction_list', integration_prefix_id=integration_prefix_id)

    return redirect('dashboard')


@login_required
def refresh_sync_integration(request, integration_prefix_id):
    """Refresh sync status for a integration - just redirect back to dashboard"""
    try:
        integration = get_object_or_404(
            Integration,
            prefix_id=integration_prefix_id,
            account__account_users__user=request.user
        )

        # For now, just redirect back to dashboard
        # The sync status will be refreshed when the page loads
        messages.success(request, "Sync status refreshed")

    except Exception as e:
        messages.error(request, f"Failed to refresh sync: {str(e)}")

    return redirect('dashboard')
