from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from turbo_helper import turbo_stream
from integrations.models import TransactionData, TransactionValidationStatus, Issue
from django.utils import timezone
import logging
import threading


@login_required
def run_transaction_validations(request, transaction_prefix_id):
    """Run selected validation rules on a specific transaction"""
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
                    template="data_quality/partials/transaction_actions.html",
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
        def run_validations_background():
            """Background validation work - runs actual validation rules"""
            try:
                from data_quality.validation.engine import ValidationEngine
                from data_quality.validation.registry import ValidationRuleRegistry
                
                logger.info(f"Background validation started for transaction {transaction_prefix_id}")
                
                # Initialize validation engine
                engine = ValidationEngine()
                
                # Run each selected rule individually 
                for rule_name in selected_rules:
                    try:
                        logger.info(f"Running validation rule: {rule_name}")
                        
                        # Get the corresponding status record
                        status = TransactionValidationStatus.objects.get(
                            transaction=transaction,
                            rule_name=rule_name,
                            status='pending'
                        )
                        
                        # Mark as running
                        status.status = 'running'
                        status.save()
                        
                        # Get rule class from registry
                        rule_class = ValidationRuleRegistry.get_rule_class(rule_name)
                        
                        if not rule_class:
                            raise Exception(f"Rule class not found for {rule_name}")
                        
                        # Run validation on the single transaction
                        result = engine.run_single_rule(rule_class, [transaction])
                        
                        # Update status based on result
                        if result.passed:
                            status.status = 'completed'
                            status.passed = True
                            status.issues_found = 0
                        else:
                            status.status = 'completed'
                            status.passed = False
                            status.issues_found = len(result.details.get('affected_transactions', []))
                            
                            # Create issue if validation failed
                            if hasattr(result, 'create_issue') and callable(result.create_issue):
                                issue = result.create_issue(transaction.integration)
                                logger.info(f"Created issue {issue.prefix_id} for failed validation")
                        
                        status.result_data = result.details
                        status.save()
                        
                        logger.info(f"Completed validation rule {rule_name}: passed={result.passed}")
                        
                    except Exception as rule_error:
                        logger.error(f"Failed to run validation rule {rule_name}: {str(rule_error)}")
                        
                        # Mark status as failed
                        try:
                            status = TransactionValidationStatus.objects.get(
                                transaction=transaction,
                                rule_name=rule_name
                            )
                            status.status = 'failed'
                            status.error_message = str(rule_error)
                            status.save()
                        except:
                            pass  # Status record might not exist
                        
                logger.info(f"All validation rules completed for transaction {transaction_prefix_id}")
                
            except Exception as e:
                logger.error(f"Background validation failed for transaction {transaction_prefix_id}: {str(e)}")
                
                # Mark all pending statuses as failed
                for rule_name in selected_rules:
                    try:
                        status = TransactionValidationStatus.objects.get(
                            transaction=transaction,
                            rule_name=rule_name,
                            status__in=['pending', 'running']
                        )
                        status.status = 'failed'
                        status.error_message = str(e)
                        status.save()
                    except:
                        pass
        
        # Start background thread
        validation_thread = threading.Thread(target=run_validations_background)
        validation_thread.daemon = True
        validation_thread.start()
        
        # Return Turbo Stream with "running" state
        return turbo_stream.response(
            turbo_stream.replace(
                f"transaction-{transaction.prefix_id}-actions",
                template="data_quality/partials/transaction_actions.html",
                context={'transaction': transaction, 'task_id': task_id},
                request=request
            )
        )
        
    except Exception as e:
        logger.error(f"Failed to start validation for transaction {transaction_prefix_id}: {str(e)}", exc_info=True)
        return JsonResponse({'error': f'Failed to start validation: {str(e)}'}, status=500)


@login_required
def resolve_issue(request, issue_prefix_id):
    """Mark a specific issue as resolved (account multi-tenant)"""
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
    # Get user's current account for multi-tenant filtering
    current_account = None
    if hasattr(request.user, 'profile') and request.user.profile.current_account:
        current_account = request.user.profile.current_account
    
    if not current_account:
        messages.error(request, "No account selected")
        return redirect('dashboard')
    
    # Get the issue, ensuring it belongs to the user's current account
    try:
        issue = get_object_or_404(
            Issue,
            prefix_id=issue_prefix_id,
            integration__account=current_account
        )
        
        # Parse the affected transactions from issue data
        affected_transactions = []
        if issue.data and 'affected_transactions' in issue.data:
            transaction_ids = issue.data['affected_transactions']
            affected_transactions = TransactionData.objects.filter(
                id__in=transaction_ids,
                integration__account=current_account  # Additional security check
            ).order_by('date', 'amount')
        
        context = {
            'issue': issue,
            'affected_transactions': affected_transactions,
            'integration': issue.integration,
        }
        
        return render(request, 'data_quality/issue_detail.html', context)
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error accessing issue detail {issue_prefix_id}: {str(e)}", exc_info=True)
        messages.error(request, "Issue not found or access denied")
        return redirect('dashboard')


@login_required
def issue_list(request):
    """Display list of data quality issues for the current account"""
    logger = logging.getLogger(__name__)
    
    # Get user's current account
    current_account = None
    if hasattr(request.user, 'profile') and request.user.profile.current_account:
        current_account = request.user.profile.current_account
    
    if not current_account:
        messages.error(request, "No account selected")
        return redirect('dashboard')
    
    try:
        # Get issues for current account, ordered by severity and date
        issues = Issue.objects.filter(
            integration__account=current_account
        ).order_by('-severity', '-created_at')
        
        # Filter by status if requested
        status_filter = request.GET.get('status')
        if status_filter in ['open', 'resolved']:
            issues = issues.filter(status=status_filter)
        
        context = {
            'issues': issues,
            'current_account': current_account,
            'status_filter': status_filter,
        }
        
        return render(request, 'data_quality/issue_list.html', context)
        
    except Exception as e:
        logger.error(f"Error loading issue list: {str(e)}", exc_info=True)
        messages.error(request, "Failed to load issues")
        return redirect('dashboard')
