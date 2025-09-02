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
from .forms import TransactionEditForm
from core.models import Account
from core.decorators import super_admin_required, check_user_can_edit_transactions
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
        # Always create a new integration to allow multiple integrations per account
        logger.info("Creating new Xero integration...")
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
def revoke_integration(request, integration_prefix_id):
    """Revoke an integration"""
    try:
        integration = get_object_or_404(
            Integration,
            prefix_id=integration_prefix_id,
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
                        
                        # Also auto-select all bank accounts for this organization
                        logger.info("Auto-selecting all bank accounts for the organization")
                        try:
                            bank_accounts = service.get_chart_of_accounts(tenant_id)
                            logger.info(f"Fetched {len(bank_accounts)} total accounts from Xero")
                            
                            # Log all account types to see what's available
                            account_types = {}
                            for acc in bank_accounts:
                                acc_type = acc.get('type')
                                if acc_type not in account_types:
                                    account_types[acc_type] = 0
                                account_types[acc_type] += 1
                            logger.info(f"Account types found: {account_types}")
                            
                            bank_account_ids = [acc.get('account_id') for acc in bank_accounts if acc.get('type') == 'BANK']
                            logger.info(f"Found {len(bank_account_ids)} BANK type accounts: {bank_account_ids}")
                            
                            if bank_account_ids:
                                service.save_selected_accounts(bank_account_ids)
                                logger.info(f"Auto-selected {len(bank_account_ids)} bank accounts: {bank_account_ids}")
                                messages.success(request, f"Successfully imported client organization: {organizations[0].get('name', 'Unknown Organization')} and selected {len(bank_account_ids)} bank accounts for syncing")
                            else:
                                # Try selecting all accounts if no BANK accounts found
                                all_account_ids = [acc.get('account_id') for acc in bank_accounts]
                                if all_account_ids:
                                    service.save_selected_accounts(all_account_ids)
                                    logger.info(f"No BANK accounts found, auto-selected all {len(all_account_ids)} accounts: {all_account_ids}")
                                    messages.success(request, f"Successfully imported client organization: {organizations[0].get('name', 'Unknown Organization')} and selected {len(all_account_ids)} accounts for syncing")
                                else:
                                    logger.warning("No accounts found to select")
                                    messages.success(request, f"Successfully imported client organization: {organizations[0].get('name', 'Unknown Organization')}")
                        except Exception as account_error:
                            logger.error(f"Error fetching or selecting accounts: {account_error}", exc_info=True)
                            messages.success(request, f"Successfully imported client organization: {organizations[0].get('name', 'Unknown Organization')}")
                            
                        return redirect('dashboard')
                    except Exception as auto_select_error:
                        logger.error(f"Failed to auto-select organization or accounts: {auto_select_error}")
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
        
        # Check if integration has selected accounts configured
        selected_accounts = integration.config.get('selected_accounts', [])
        if not selected_accounts:
            messages.info(request, f"Please select bank accounts to sync for {integration.organization_name}")
            logger.info(f"Integration {integration.id} has no selected accounts, redirecting to chart accounts selection")
            return redirect('xero_chart_accounts', integration_prefix_id=integration.prefix_id)
        
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
def transaction_actions(request, transaction_prefix_id):
    """Get current transaction actions state (for Turbo Frame reloads)"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Loading transaction actions for transaction {transaction_prefix_id}")
    
    try:
        # First check if transaction exists at all
        try:
            transaction = TransactionData.objects.get(prefix_id=transaction_prefix_id)
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
        logger.error(f"Error fetching transaction actions for transaction {transaction_prefix_id}: {str(e)}", exc_info=True)
        
        return render(request, 'integrations/partials/transaction_actions.html', {
            'transaction': transaction if 'transaction' in locals() else None,
            'error': f'Failed to load transaction actions: {str(e)}'
        }, status=500)




def run_transaction_validations(request, transaction_prefix_id):
    """Run selected validation rules on a specific transaction"""
    import logging
    logger = logging.getLogger(__name__)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
    
    try:
        # First check if transaction exists at all
        try:
            transaction = TransactionData.objects.get(prefix_id=transaction_prefix_id)
        except TransactionData.DoesNotExist:
            return JsonResponse({'error': 'Transaction not found'}, status=404)
        
        # Then check if user has access to this transaction
        if not transaction.integration.account.account_users.filter(user=request.user).exists():
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Get selected rules from form data
        selected_rules = request.POST.getlist('rules')
        logger.info(f"Running validations for transaction {transaction_prefix_id}: {selected_rules}")
        
        if not selected_rules:
            # Return Turbo Stream with error message
            return turbo_stream.response(
                turbo_stream.replace(
                    f"transaction-{transaction.prefix_id}-actions",
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
            """Background validation work - runs actual validation rules"""
            try:
                from .validation.engine import ValidationEngine
                from .validation.registry import ValidationRuleRegistry
                import time
                
                # Simulate brief loading time
                time.sleep(1)
                
                # Process each validation rule
                for status in validation_statuses:
                    # Mark as running
                    status.mark_running()
                    
                    try:
                        # Get the actual rule and run it on the integration
                        rule_name = status.rule_name
                        integration = transaction.integration
                        
                        logger.info(f"Running actual validation rule {rule_name} on integration {integration.organization_name}")
                        
                        # Run the actual validation rule
                        result = ValidationEngine.run_single_rule(integration, rule_name)
                        
                        # Mark as completed with real results
                        status.mark_completed(
                            passed=result.passed,
                            issues_found=1 if not result.passed else 0,
                            severity=result.severity.value if result.severity else 'info',
                            result_data={
                                'rule_name': result.rule_name,
                                'title': result.title,
                                'description': result.description,
                                'metadata': result.metadata or {}
                            }
                        )
                        
                        logger.info(f"Completed rule {rule_name}: {'PASSED' if result.passed else 'FAILED'}")
                        
                    except Exception as rule_error:
                        logger.error(f"❌ VALIDATION: Failed to run rule {status.rule_name}: {rule_error}")
                        status.mark_failed(str(rule_error))
                
            except Exception as validation_error:
                logger.error(f"❌ VALIDATION: Failed to run background validations: {validation_error}")
        
        # Start background validation work
        validation_thread = threading.Thread(target=run_validations_background)
        validation_thread.daemon = True
        validation_thread.start()
        
        # Return immediate Turbo Stream showing "running" state
        return turbo_stream.response(
            turbo_stream.replace(
                f"transaction-{transaction.prefix_id}-actions",
                template="integrations/partials/transaction_actions.html",
                context={'transaction': transaction, 'task_id': task_id},  # Show running state
                request=request
            )
        )
        
    except Exception as e:
        logger.error(f"Error running validations for transaction {transaction_prefix_id}: {str(e)}", exc_info=True)
        
        # For 404 errors, return proper HTTP response
        from django.http import Http404
        if isinstance(e, Http404):
            return JsonResponse({'error': 'Transaction not found'}, status=404)
        
        return turbo_stream.response(
            turbo_stream.replace(
                f"transaction-{transaction_prefix_id}-actions",
                template="integrations/partials/transaction_actions.html", 
                context={
                    'transaction': transaction if 'transaction' in locals() else None,
                    'error': f'Failed to run validations: {str(e)}'
                },
                request=request
            )
        )





@login_required
def refresh_transaction_status(request, transaction_prefix_id):
    """Refresh transaction status with background job and real-time updates"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Refresh transaction status called for transaction {transaction_prefix_id}")
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
    
    try:
        # Get transaction with user access check
        transaction = get_object_or_404(
            TransactionData,
            prefix_id=transaction_prefix_id,
            integration__account__account_users__user=request.user
        )
        
        logger.info(f"Found transaction {transaction_prefix_id}, updating timestamp")
        
        # Update transaction directly to test WebSocket
        try:
            from django.utils import timezone
            import time
            
            # Simulate the work that would be done
            time.sleep(1)  # Brief delay to simulate processing
            
            # Update the transaction timestamp (this will trigger the signal)
            transaction.updated_at = timezone.now()
            transaction.save()
            
            logger.info(f"Updated transaction {transaction_prefix_id} timestamp")
            
            task_id = "direct_update"  # Fake task ID
        except Exception as update_error:
            logger.error(f"Failed to update transaction: {update_error}")
            task_id = None
        
        # Return Turbo Stream response showing "refreshing" state
        logger.info(f"Returning Turbo Stream response for transaction {transaction_prefix_id}")
        return turbo_stream.response(
            turbo_stream.replace(
                f"transaction-{transaction.prefix_id}-actions",
                template="integrations/partials/transaction_actions.html",
                context={'transaction': transaction, 'refresh_task_id': task_id},
                request=request
            )
        )
        
    except Exception as e:
        logger.error(f"Error refreshing transaction {transaction_prefix_id}: {str(e)}", exc_info=True)
        return turbo_stream.response(
            turbo_stream.replace(
                f"transaction-{transaction_prefix_id}-actions",
                template="integrations/partials/transaction_actions.html", 
                context={
                    'transaction': transaction if 'transaction' in locals() else None,
                    'error': f'Failed to refresh: {str(e)}'
                },
                request=request
            )
        )





@super_admin_required
def transaction_edit(request, transaction_prefix_id):
    """Edit transaction data - super_admin only"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Transaction edit view called for {transaction_prefix_id} by {request.user.email}")
    
    try:
        # Get transaction with user access check
        transaction = get_object_or_404(
            TransactionData,
            prefix_id=transaction_prefix_id,
            integration__account__account_users__user=request.user
        )
        
        if request.method == 'POST':
            logger.info(f"POST request received for transaction {transaction_prefix_id}")
            logger.info(f"POST data: {request.POST}")
            
            form = TransactionEditForm(request.POST, instance=transaction)
            if form.is_valid():
                logger.info("Form is valid, proceeding with save")
                
                # Store original values for audit
                original_data = {
                    'amount': transaction.amount,
                    'date': transaction.date,
                    'reference': transaction.reference,
                    'description': transaction.description,
                    'contact_name': transaction.contact_name,
                    'status': transaction.status,
                }
                
                # Save changes
                form.user = request.user  # For audit trail
                updated_transaction = form.save()
                
                # Log the change
                logger.info(f"Transaction {transaction_prefix_id} updated by {request.user.email}")
                logger.info(f"Original: {original_data}")
                logger.info(f"Updated: amount={updated_transaction.amount}, date={updated_transaction.date}, reference={updated_transaction.reference}")
                
                messages.success(request, f"Transaction {transaction.prefix_id} updated successfully")
                return redirect('transaction_list', integration_prefix_id=transaction.integration.prefix_id)
            else:
                logger.error(f"Form validation failed for transaction {transaction_prefix_id}")
                logger.error(f"Form errors: {form.errors}")
                messages.error(request, "Please correct the errors below")
        else:
            form = TransactionEditForm(instance=transaction)
        
        context = {
            'form': form,
            'transaction': transaction,
            'integration': transaction.integration,
        }
        
        return render(request, 'integrations/transaction_edit.html', context)
        
    except Exception as e:
        logger.error(f"Error editing transaction {transaction_prefix_id}: {str(e)}", exc_info=True)
        messages.error(request, f"Failed to edit transaction: {str(e)}")
        return redirect('dashboard')


@login_required
def transaction_edit_check(request, transaction_prefix_id):
    """Check if user can edit transaction and redirect appropriately"""
    
    # Check user permissions
    if not check_user_can_edit_transactions(request.user):
        messages.warning(request, "Access denied. Only super administrators can edit transactions.")
        return redirect('dashboard')
    
    # Redirect to actual edit view
    return redirect('transaction_edit', transaction_prefix_id=transaction_prefix_id)


@login_required
def delete_integration(request, integration_prefix_id):
    """Delete an integration and all its associated data"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Integration deletion requested for {integration_prefix_id} by {request.user.email}")
    
    try:
        # Get integration with user access check
        integration = get_object_or_404(
            Integration,
            prefix_id=integration_prefix_id,
            account__account_users__user=request.user
        )
        
        if request.method == 'POST':
            # Confirm deletion
            confirmation = request.POST.get('confirmation')
            if confirmation != integration.organization_name:
                messages.error(request, "Organization name confirmation did not match. Deletion cancelled.")
                return redirect('dashboard')
            
            # Get stats before deletion for logging
            transaction_count = integration.transactions.count()
            issue_count = integration.issues.count()
            
            try:
                # Revoke access with provider first (if possible)
                IntegrationManager.revoke_integration(integration)
                
                organization_name = integration.organization_name
                
                # Delete the integration (cascading will handle related data)
                integration.delete()
                
                logger.info(f"Successfully deleted integration {integration_prefix_id} ({organization_name}) "
                           f"with {transaction_count} transactions and {issue_count} issues by {request.user.email}")
                
                messages.success(request, f"Successfully removed {organization_name} and all associated data.")
                return redirect('dashboard')
                
            except Exception as delete_error:
                logger.error(f"Failed to delete integration {integration_prefix_id}: {delete_error}")
                messages.error(request, f"Failed to remove integration: {str(delete_error)}")
                return redirect('dashboard')
        
        # Show confirmation page
        context = {
            'integration': integration,
            'transaction_count': integration.transactions.count(),
            'issue_count': integration.issues.count(),
        }
        
        return render(request, 'integrations/delete_integration.html', context)
        
    except Exception as e:
        logger.error(f"Error accessing integration for deletion {integration_prefix_id}: {str(e)}", exc_info=True)
        messages.error(request, "Integration not found or access denied")
        return redirect('dashboard')


@login_required
def resolve_issue(request, issue_prefix_id):
    """Mark a specific issue as resolved (account multi-tenant)"""
    import logging
    from django.utils import timezone
    logger = logging.getLogger(__name__)
    
    if request.method == 'POST':
        try:
            # Get user's current account for proper multi-tenancy
            current_account = request.user.profile.current_account
            
            # Get issue with proper account isolation
            issue = get_object_or_404(
                Issue,
                prefix_id=issue_prefix_id,
                integration__account=current_account,  # Ensure account isolation
                status='open'
            )
            
            # Mark as resolved
            issue.status = 'resolved'
            issue.resolved_by = request.user
            issue.resolved_at = timezone.now()
            issue.save()
            
            logger.info(f"Issue {issue_prefix_id} resolved by {request.user.email} for account {current_account.id}")
            messages.success(request, f"Issue '{issue.title}' marked as resolved")
            
        except Exception as e:
            logger.error(f"Error resolving issue {issue_prefix_id}: {str(e)}", exc_info=True)
            messages.error(request, "Failed to resolve issue or access denied")
    
    return redirect('dashboard')


@login_required  
def bulk_resolve_issues(request):
    """Mark multiple issues as resolved (account multi-tenant)"""
    import logging
    from django.utils import timezone
    logger = logging.getLogger(__name__)
    
    if request.method == 'POST':
        try:
            # Get user's current account for proper multi-tenancy
            current_account = request.user.profile.current_account
            
            issue_ids = request.POST.getlist('issue_ids')
            
            if issue_ids:
                # Get issues with proper account isolation
                issues = Issue.objects.filter(
                    prefix_id__in=issue_ids,
                    integration__account=current_account,  # Ensure account isolation
                    status='open'
                )
                
                # Mark all as resolved
                updated_count = issues.update(
                    status='resolved',
                    resolved_by=request.user,
                    resolved_at=timezone.now()
                )
                
                logger.info(f"Bulk resolved {updated_count} issues by {request.user.email} for account {current_account.id}")
                
                if updated_count > 0:
                    messages.success(request, f"Marked {updated_count} issues as resolved")
                else:
                    messages.info(request, "No open issues found to resolve")
            else:
                messages.info(request, "No issues selected")
                
        except Exception as e:
            logger.error(f"Error bulk resolving issues: {str(e)}", exc_info=True)
            messages.error(request, "Failed to resolve issues")
    
    return redirect('dashboard')


@login_required
def issue_detail(request, issue_prefix_id):
    """
    Display detailed view for a specific issue with resolution workflow.
    
    Designed for accountants to efficiently resolve duplicate transactions
    and other validation issues with full context and external links.
    """
    from django.shortcuts import get_object_or_404
    
    # Get user's current account for multi-tenant filtering
    current_account = None
    if hasattr(request.user, 'profile') and request.user.profile.current_account:
        current_account = request.user.profile.current_account
    
    if not current_account:
        messages.error(request, "No account selected")
        return redirect('dashboard')
    
    # Get the issue, ensuring it belongs to the user's current account
    issue = get_object_or_404(
        Issue, 
        prefix_id=issue_prefix_id,
        integration__account=current_account
    )
    
    # Parse affected transactions data 
    # The affected_transactions field contains duplicate groups with transaction details
    duplicate_groups = issue.affected_transactions if issue.affected_transactions else []
    
    # Add transaction objects for each transaction ID in the groups
    enhanced_groups = []
    for group in duplicate_groups:
        enhanced_group = group.copy()
        
        # Get actual transaction objects for additional context
        transaction_objects = []
        if 'transactions' in group:
            transaction_ids = [txn['id'] for txn in group['transactions']]
            transactions_qs = TransactionData.objects.filter(
                id__in=transaction_ids,
                integration__account=current_account  # Ensure multi-tenant isolation
            ).select_related('integration')
            
            # Create enhanced transaction data combining stored and live data
            for stored_txn in group['transactions']:
                # Find matching live transaction object
                live_txn = None
                for txn_obj in transactions_qs:
                    if txn_obj.id == stored_txn['id']:
                        live_txn = txn_obj
                        break
                
                if live_txn:
                    # Construct specific Xero transaction URL if possible
                    xero_transaction_url = live_txn.external_url  # Default fallback
                    if live_txn.integration.provider.name == 'xero' and live_txn.raw_data:
                        tenant_id = live_txn.raw_data.get('tenant_id')
                        bank_transaction_id = live_txn.raw_data.get('bank_transaction_id')
                        if tenant_id and bank_transaction_id:
                            xero_transaction_url = f"https://go.xero.com/Bank/BankRec.aspx?tenantId={tenant_id}&bankTransactionID={bank_transaction_id}"
                    
                    enhanced_txn = {
                        **stored_txn,  # Use stored data from issue
                        'live_object': live_txn,  # Add live object for additional context
                        'integration_prefix_id': live_txn.integration.prefix_id,
                        'external_url': xero_transaction_url,  # Use specific transaction URL
                        'needs_review': True  # Default status for Phase 1
                    }
                    transaction_objects.append(enhanced_txn)
            
            enhanced_group['enhanced_transactions'] = transaction_objects
            
        enhanced_groups.append(enhanced_group)
    
    # Calculate resolution progress
    total_transactions = sum(len(group.get('transactions', [])) for group in duplicate_groups)
    resolved_transactions = 0  # For Phase 1, none are resolved yet
    
    context = {
        'issue': issue,
        'duplicate_groups': enhanced_groups,
        'total_transactions': total_transactions,
        'resolved_transactions': resolved_transactions,
        'resolution_progress_percent': 0 if total_transactions == 0 else int((resolved_transactions / total_transactions) * 100),
    }
    
    return render(request, 'integrations/issue_detail.html', context)

