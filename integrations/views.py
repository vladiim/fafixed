from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from turbo_helper import turbo_stream
from django.core.paginator import Paginator
from .models import Integration, Issue, IntegrationProvider, TransactionData, TransactionValidationStatus
from .managers import IntegrationManager
from .services.base import IntegrationServiceRegistry
from .utils import TokenRefreshError
from core.models import Account
from . import services  # Import services to ensure registration
import uuid
from datetime import datetime, timedelta
import random
import json
import time

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
        # Check if any integration already exists for this account/provider combo
        existing_integration = Integration.objects.filter(
            account=current_account,
            provider__name='xero'
        ).first()
        
        if existing_integration:
            if existing_integration.status == 'active':
                logger.info(f"Active Xero integration found: {existing_integration.id}")
                messages.info(request, "Xero integration already exists for this account.")
                return redirect('dashboard')
            else:
                # Reuse existing expired/error integration for reconnection
                logger.info(f"Reusing existing integration for reconnection: {existing_integration.id} (Status: {existing_integration.status})")
                integration = existing_integration
                # Reset integration status for reconnection
                integration.status = 'pending'
                integration.last_error = None
                integration.save()
        else:
            logger.info("Creating new Xero integration...")
            # Create new integration
            integration = IntegrationManager.create_integration(
                account=current_account,
                provider_name='xero',
                created_by=request.user
            )
        
        logger.info(f"Using integration: {integration.id}")
        
        # Create secure OAuth state token
        from .models import OAuthState
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
        from .models import OAuthState
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
            messages.error(request, "Integration is no longer pending authorization")
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


@login_required
def xero_chart_accounts(request, integration_prefix_id):
    """Display Xero Chart of Accounts for selection (bank accounts, revenue accounts, etc.)"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Xero chart accounts view called for integration {integration_prefix_id} by user {request.user.email}")
    
    try:
        integration = get_object_or_404(
            Integration, 
            prefix_id=integration_prefix_id,
            account__account_users__user=request.user,
            provider__name='xero'
        )
        
        logger.info(f"Found integration: {integration.id} - {integration.organization_name} (Status: {integration.status})")
        
        # Check if integration has completed OAuth (has credentials)
        if not hasattr(integration, 'credentials'):
            logger.error(f"Integration {integration.id} has no credentials")
            messages.error(request, "Integration not properly connected. Please reconnect to Xero.")
            return redirect('dashboard')
        
        logger.info(f"Integration has credentials, expires at: {integration.credentials.expires_at}")
        
        # Get the service for this integration
        logger.info("Getting integration service...")
        service = IntegrationServiceRegistry.get_service(integration)
        logger.info(f"Got service: {service.__class__.__name__}")
        
        # Fetch client organizations from Xero
        logger.info("Fetching client organizations from Xero API...")
        try:
            organizations = service.get_organizations()
            logger.info(f"Successfully fetched {len(organizations)} client organizations from Xero")
            
            # Log first few organizations for debugging
            for i, org in enumerate(organizations[:3]):
                logger.info(f"Organization {i+1}: {org.get('name', 'NO_NAME')} - Legal: {org.get('legal_name', 'NO_LEGAL')} - Tenant: {org.get('tenant_id', 'NO_TENANT')}")
            
            # Auto-select if only one organization available
            if len(organizations) == 1:
                logger.info("Only one client organization available, auto-selecting and importing")
                tenant_id = organizations[0].get('tenant_id')
                if tenant_id:
                    try:
                        service.save_selected_organizations([tenant_id])
                        messages.success(request, f"Successfully imported client organization: {organizations[0].get('name', 'Unknown Organization')}")
                        return redirect('dashboard')
                    except Exception as auto_select_error:
                        logger.error(f"Failed to auto-select organization: {auto_select_error}")
                        # Continue to render template if auto-select fails
                        
        except Exception as api_error:
            logger.error(f"Error fetching client organizations from Xero API: {api_error}", exc_info=True)
            raise
        
        context = {
            'integration': integration,
            'organizations': organizations
        }
        
        logger.info(f"Rendering xero_chart_accounts.html template with {len(organizations)} client organizations")
        return render(request, 'integrations/xero_chart_accounts.html', context)
        
    except TokenRefreshError as e:
        logger.error(f"Token refresh failed for integration {integration_prefix_id}: {str(e)}")
        messages.error(request, "Your Xero connection has expired. Please reconnect to continue.")
        # Mark integration as needing reconnection
        integration.status = 'expired'
        integration.last_error = str(e)
        integration.save()
        return redirect('xero_connect')
    except Exception as e:
        logger.error(f"Failed to fetch Xero client organizations for integration {integration_prefix_id}: {str(e)}", exc_info=True)
        messages.error(request, f"Failed to fetch Xero client organizations: {str(e)}")
        return redirect('dashboard')


@login_required  
def import_chart_accounts(request):
    """Handle client organization selection and import"""
    if request.method != 'POST':
        return redirect('dashboard')
    
    try:
        # Get selected organization tenant IDs from form data (frontend uses 'selected_accounts' field name)
        selected_organizations = request.POST.getlist('selected_accounts')
        
        if not selected_organizations:
            messages.error(request, "Please select at least one client organization to import")
            return redirect(request.META.get('HTTP_REFERER', 'dashboard'))
        
        # Get integration from form or session
        integration_id = request.POST.get('integration_id')
        if not integration_id:
            messages.error(request, "Invalid request")
            return redirect('dashboard')
        
        integration = get_object_or_404(
            Integration,
            id=integration_id,
            account__account_users__user=request.user,
            status='active'
        )
        
        # Save selected organizations using the service
        service = IntegrationServiceRegistry.get_service(integration)
        service.save_selected_organizations(selected_organizations)
        
        # Start syncing transactions for selected organizations
        try:
            sync_record = service.sync_selected_organizations(selected_organizations)
            if sync_record.get('success'):
                transaction_count = sync_record.get('transaction_count', 0)
                messages.success(request, f"Successfully imported {len(selected_organizations)} client organizations and {transaction_count} transactions for analysis")
            else:
                messages.warning(request, f"Imported {len(selected_organizations)} client organizations, but transaction sync had issues: {sync_record.get('error', 'Unknown error')}")
        except Exception as sync_error:
            logger.error(f"Failed to sync transactions: {sync_error}")
            messages.warning(request, f"Successfully imported {len(selected_organizations)} client organizations, but failed to sync transactions. You can manually sync later.")
        
        return redirect('dashboard')
        
    except Exception as e:
        messages.error(request, f"Failed to import client organizations: {str(e)}")
        return redirect('dashboard')


@login_required
def sync_integration(request, integration_id):
    """Manually trigger a sync for an integration"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        integration = get_object_or_404(
            Integration,
            id=integration_id,
            account__account_users__user=request.user,
            status='active'
        )
        
        # Check if we should run sync in background or synchronously
        run_async = request.GET.get('async', 'false').lower() == 'true'
        
        if run_async:
            # Trigger background task
            from .tasks import sync_single_integration
            task = sync_single_integration.delay(integration_id, sync_type='incremental')
            messages.info(request, f"Background sync started for {integration.organization_name}. Task ID: {task.id}")
        else:
            # Run synchronously (for immediate feedback)
            sync_record = IntegrationManager.sync_integration(integration, sync_type='incremental')
            
            if sync_record.status == 'completed':
                messages.success(request, f"Successfully synced {sync_record.records_success} transactions")
            else:
                messages.warning(request, f"Sync completed with issues: {sync_record.error_message}")
            
    except Exception as e:
        messages.error(request, f"Failed to sync: {str(e)}")
        logger.error(f"Manual sync failed for integration {integration_id}", exc_info=True)
    
    return redirect('dashboard')


@login_required
def refresh_sync_integration(request, integration_prefix_id):
    """Trigger refresh sync for an integration - pulls transactions from last sync to now"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        integration = get_object_or_404(
            Integration,
            prefix_id=integration_prefix_id,
            account__account_users__user=request.user,
            status__in=['active', 'expired']  # Allow both active and expired integrations
        )
        
        logger.info(f"Refresh sync triggered for integration {integration.id} ({integration.organization_name}) by user {request.user.email}")
        
        # If integration is expired, redirect directly to reconnect
        if integration.status == 'expired':
            messages.warning(request, f"Your Xero connection for {integration.organization_name} has expired. Redirecting to reconnect...")
            logger.info(f"Integration {integration.id} is expired, redirecting to reconnect")
            return redirect('xero_connect')
        
        # Check if we should run sync in background or synchronously
        run_async = request.GET.get('async', 'false').lower() == 'true'
        
        if run_async:
            # Trigger background task
            from .tasks import sync_single_integration
            task = sync_single_integration.delay(integration.id, sync_type='incremental')
            messages.info(request, f"Background refresh sync started for {integration.organization_name}. Task ID: {task.id}")
            logger.info(f"Background refresh sync task {task.id} started for integration {integration.id}")
        else:
            # Run synchronously for immediate feedback
            sync_record = IntegrationManager.sync_integration(integration, sync_type='incremental')
            
            if sync_record.status == 'completed':
                transaction_count = sync_record.records_success or 0
                if transaction_count > 0:
                    messages.success(request, f"Refresh sync completed: {transaction_count} new transactions synced for {integration.organization_name}")
                else:
                    messages.success(request, f"Refresh sync completed: No new transactions found for {integration.organization_name}. All data is up to date!")
                logger.info(f"Refresh sync completed successfully: {transaction_count} transactions for integration {integration.id}")
            else:
                messages.warning(request, f"Refresh sync completed with issues for {integration.organization_name}: {sync_record.error_message}")
                logger.warning(f"Refresh sync completed with issues for integration {integration.id}: {sync_record.error_message}")
            
    except TokenRefreshError as e:
        messages.warning(request, f"Your Xero connection has expired for {integration.organization_name}. Redirecting to reconnect...")
        logger.error(f"Token refresh failed for integration {integration_prefix_id}: {str(e)}")
        # Automatically redirect to Xero reconnect flow
        return redirect('xero_connect')
    except Exception as e:
        messages.error(request, f"Failed to refresh sync: {str(e)}")
        logger.error(f"Refresh sync failed for integration {integration_prefix_id}", exc_info=True)
    
    return redirect('dashboard')


@login_required
def transaction_list(request, integration_prefix_id):
    """Display paginated list of transactions for an integration"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Transaction list view called for integration {integration_prefix_id} by user {request.user.email}")
    
    try:
        integration = get_object_or_404(
            Integration,
            prefix_id=integration_prefix_id,
            account__account_users__user=request.user,
            status='active'
        )
        
        # Get transactions for this integration, ordered by date (newest first)
        transactions = TransactionData.objects.filter(
            integration=integration
        ).order_by('-date', '-created_at')
        
        # Pagination
        paginator = Paginator(transactions, 25)  # Show 25 transactions per page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'integration': integration,
            'page_obj': page_obj,
            'total_transactions': transactions.count(),
        }
        
        logger.info(f"Rendering transaction list with {transactions.count()} total transactions, showing page {page_obj.number} of {paginator.num_pages}")
        return render(request, 'integrations/transaction_list.html', context)
        
    except Exception as e:
        logger.error(f"Failed to load transaction list for integration {integration_prefix_id}: {str(e)}", exc_info=True)
        messages.error(request, f"Failed to load transactions: {str(e)}")
        return redirect('dashboard')


@login_required
def transaction_actions(request, transaction_id):
    """Get current transaction actions state (for Turbo Frame reloads)"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Loading transaction actions for transaction {transaction_id}")
    
    try:
        # First check if transaction exists at all
        try:
            transaction = TransactionData.objects.get(id=transaction_id)
        except TransactionData.DoesNotExist:
            return JsonResponse({'error': 'Transaction not found'}, status=404)
        
        # Then check if user has access to this transaction
        if not transaction.integration.account.account_users.filter(user=request.user).exists():
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Check if there are any pending validation statuses (indicating a task is running)
        pending_statuses = transaction.validation_statuses.filter(status='pending')
        task_id = None
        if pending_statuses.exists():
            # Simulate task_id for UI (we don't track actual celery task IDs in the DB)
            # In a real implementation, you might store the task_id in the TransactionValidationStatus
            task_id = "running"  # Just indicate that tasks are running
        
        # Return Turbo Frame with current state
        return render(request, 'integrations/partials/transaction_actions.html', {
            'transaction': transaction,
            'task_id': task_id
        })
        
    except Exception as e:
        logger.error(f"Error fetching transaction actions for transaction {transaction_id}: {str(e)}", exc_info=True)
        
        return render(request, 'integrations/partials/transaction_actions.html', {
            'transaction': transaction if 'transaction' in locals() else None,
            'error': f'Failed to load transaction actions: {str(e)}'
        }, status=500)




def run_transaction_validations(request, transaction_id):
    """Run selected validation rules on a specific transaction"""
    import logging
    logger = logging.getLogger(__name__)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
    
    try:
        # First check if transaction exists at all
        try:
            transaction = TransactionData.objects.get(id=transaction_id)
        except TransactionData.DoesNotExist:
            return JsonResponse({'error': 'Transaction not found'}, status=404)
        
        # Then check if user has access to this transaction
        if not transaction.integration.account.account_users.filter(user=request.user).exists():
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Get selected rules from form data
        selected_rules = request.POST.getlist('rules')
        logger.info(f"Running validations for transaction {transaction_id}: {selected_rules}")
        
        if not selected_rules:
            # Return Turbo Stream with error message
            return turbo_stream.response(
                turbo_stream.replace(
                    f"transaction-{transaction.id}-actions",
                    template="integrations/partials/transaction_actions.html",
                    context={'transaction': transaction, 'error': 'No validation rules selected'},
                    request=request
                )
            )
        
        # Create pending validation status records for selected rules
        validation_statuses = []
        for rule_name in selected_rules:
            status, created = TransactionValidationStatus.objects.get_or_create(
                transaction=transaction,
                rule_name=rule_name,
                defaults={
                    'status': 'pending'
                }
            )
            # Reset status if it already existed
            if not created:
                status.status = 'pending'
                status.passed = None
                status.issues_found = 0
                status.error_message = None
                status.result_data = {}
                status.save()
            
            validation_statuses.append(status)
        
        # Return immediate "running" state, let Celery job handle completion via ActionCable
        task_id = "direct_validation"  # Show running state
        
        # Start background validation work (simulate Celery)
        import threading
        
        def run_validations_background():
            """Background validation work (simulates Celery task)"""
            try:
                import time
                
                # Simulate validation work
                time.sleep(2)
                
                # Process each validation rule
                for status in validation_statuses:
                    # Mark as running
                    status.mark_running()
                    
                    # Simulate validation result
                    import random
                    passed = random.choice([True, False])
                    issues_found = 0 if passed else random.randint(1, 3)
                    
                    # Mark as completed (this will trigger the validation signal via ActionCable)
                    status.mark_completed(
                        passed=passed,
                        issues_found=issues_found,
                        severity='info' if passed else 'warning',
                        result_data={'simulated': True, 'rule': status.rule_name}
                    )
                
            except Exception as validation_error:
                logger.error(f"❌ VALIDATION: Failed to run background validations: {validation_error}")
        
        # Start background validation work
        validation_thread = threading.Thread(target=run_validations_background)
        validation_thread.daemon = True
        validation_thread.start()
        
        # Return immediate Turbo Stream showing "running" state
        return turbo_stream.response(
            turbo_stream.replace(
                f"transaction-{transaction.id}-actions",
                template="integrations/partials/transaction_actions.html",
                context={'transaction': transaction, 'task_id': task_id},  # Show running state
                request=request
            )
        )
        
    except Exception as e:
        logger.error(f"Error running validations for transaction {transaction_id}: {str(e)}", exc_info=True)
        
        # For 404 errors, return proper HTTP response
        from django.http import Http404
        if isinstance(e, Http404):
            return JsonResponse({'error': 'Transaction not found'}, status=404)
        
        return turbo_stream.response(
            turbo_stream.replace(
                f"transaction-{transaction_id}-actions",
                template="integrations/partials/transaction_actions.html", 
                context={
                    'transaction': transaction if 'transaction' in locals() else None,
                    'error': f'Failed to run validations: {str(e)}'
                },
                request=request
            )
        )





@login_required
def refresh_transaction_status(request, transaction_id):
    """Refresh transaction status with background job and real-time updates"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Refresh transaction status called for transaction {transaction_id}")
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
    
    try:
        # Get transaction with user access check
        transaction = get_object_or_404(
            TransactionData,
            id=transaction_id,
            integration__account__account_users__user=request.user
        )
        
        logger.info(f"Found transaction {transaction_id}, updating timestamp")
        
        # Update transaction directly to test WebSocket
        try:
            from django.utils import timezone
            import time
            
            # Simulate the work that would be done
            time.sleep(1)  # Brief delay to simulate processing
            
            # Update the transaction timestamp (this will trigger the signal)
            transaction.updated_at = timezone.now()
            transaction.save()
            
            logger.info(f"Updated transaction {transaction_id} timestamp")
            
            task_id = "direct_update"  # Fake task ID
        except Exception as update_error:
            logger.error(f"Failed to update transaction: {update_error}")
            task_id = None
        
        # Return Turbo Stream response showing "refreshing" state
        logger.info(f"Returning Turbo Stream response for transaction {transaction_id}")
        return turbo_stream.response(
            turbo_stream.replace(
                f"transaction-{transaction.id}-actions",
                template="integrations/partials/transaction_actions.html",
                context={'transaction': transaction, 'refresh_task_id': task_id},
                request=request
            )
        )
        
    except Exception as e:
        logger.error(f"Error refreshing transaction {transaction_id}: {str(e)}", exc_info=True)
        return turbo_stream.response(
            turbo_stream.replace(
                f"transaction-{transaction_id}-actions",
                template="integrations/partials/transaction_actions.html", 
                context={
                    'transaction': transaction if 'transaction' in locals() else None,
                    'error': f'Failed to refresh: {str(e)}'
                },
                request=request
            )
        )


