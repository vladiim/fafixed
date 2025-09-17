from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction as db_transaction
from turbo_helper import turbo_stream
from integrations.models import TransactionData, TransactionValidationStatus, Issue
from connections.models import Connection
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
        
        # Parse the affected transactions from issue
        affected_transactions = []
        if issue.affected_transactions:
            transaction_ids = []
            
            # Handle different data structures
            if isinstance(issue.affected_transactions, list):
                # Handle list of complex structures or simple IDs
                for item in issue.affected_transactions:
                    if isinstance(item, dict) and 'transactions' in item:
                        # Extract IDs from complex nested structure
                        transaction_ids.extend([tx['id'] for tx in item['transactions']])
                    elif isinstance(item, (int, str)):
                        # Handle simple ID
                        transaction_ids.append(item)
            elif isinstance(issue.affected_transactions, dict) and 'transactions' in issue.affected_transactions:
                # Handle single dict with transactions
                transaction_ids = [tx['id'] for tx in issue.affected_transactions['transactions']]
            else:
                # Handle simple list of IDs (fallback)
                if isinstance(issue.affected_transactions, (list, tuple)):
                    transaction_ids = list(issue.affected_transactions)
            
            if transaction_ids:
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




@login_required
def agent_checks(request):
    """
    Display Agent Checks - validation rules interface showing all available 
    validation rules and their status, with same issue format as dashboard.
    """
    logger = logging.getLogger(__name__)
    
    # Get user's current account
    current_account = None
    if hasattr(request.user, 'profile') and request.user.profile.current_account:
        current_account = request.user.profile.current_account
    
    if not current_account:
        messages.error(request, "No account selected")
        return redirect('dashboard')
    
    try:
        
        # Get all available validation rules from registry
        from integrations.validation.registry import ValidationRuleRegistry
        all_rules = ValidationRuleRegistry.get_all_rules()
        
        # Get user's integrations
        integrations = current_account.integrations.filter(status='active')
        
        # Build rules information
        validation_rules = []
        for rule_name, rule_class in all_rules.items():
            # For now, all rules are enabled by default (except Smart Categorisation)
            is_enabled = rule_name != 'smart_categorisation'
            
            rule_info = {
                'name': rule_name,
                'display_name': rule_class.description or rule_name.replace('_', ' ').title(),
                'description': getattr(rule_class, 'description', ''),
                'is_enabled': is_enabled,
                'issue_count': 0  # Will be populated below
            }
            
            # Count issues for enabled rules
            if is_enabled:
                rule_info['issue_count'] = Issue.objects.filter(
                    integration__account=current_account,
                    category=rule_name,
                    status='open'
                ).count()
            
            validation_rules.append(rule_info)
        
        # Add Smart Categorisation as a special case (user-configurable)
        smart_cat_enabled = False  # TODO: Check user configuration
        validation_rules.append({
            'name': 'smart_categorisation',
            'display_name': 'Smart Categorisation',
            'description': 'Suggests categorisation for transactions based on user-defined patterns',
            'is_enabled': smart_cat_enabled,
            'issue_count': 0,
            'requires_setup': not smart_cat_enabled
        })
        
        # Get all issues for enabled rules (same format as dashboard)
        if integrations.exists():
            issues = Issue.objects.filter(
                integration__account=current_account,
                status='open',
                integration__in=integrations
            ).select_related('integration').order_by('-first_seen')
        else:
            issues = []
        
        # Calculate summary stats
        total_issues = len(issues)
        critical_issues = sum(1 for issue in issues if issue.severity == 'critical')
        high_issues = sum(1 for issue in issues if issue.severity == 'high')
        
        context = {
            'validation_rules': validation_rules,
            'issues': issues,
            'total_issues': total_issues,
            'critical_issues': critical_issues,
            'high_issues': high_issues,
            'integrations': integrations,
            'has_integrations': integrations.exists()
        }
        
        return render(request, 'data_quality/agent_checks.html', context)
        
    except Exception as e:
        logger.error(f"Error loading Agent Checks: {str(e)}", exc_info=True)
        messages.error(request, "Failed to load Agent Checks")
        return redirect('dashboard')


@login_required 
def configure_smart_categorisation(request):
    """Display Smart Categorisation configuration interface"""
    logger = logging.getLogger(__name__)
    
    try:
        # Get user's current account
        current_account = None
        if hasattr(request.user, 'profile') and request.user.profile.current_account:
            current_account = request.user.profile.current_account
        
        if not current_account:
            messages.error(request, "No account selected")
            return redirect('dashboard')
        
        # Import the CategoryDetectionRule model
        from data_quality.models import CategoryDetectionRule
        from connections.models import Connection
        
        # Get active connections for this account
        connections = Connection.objects.filter(
            account=current_account,
            status='active'
        )
        
        # Get all category detection rules for this account's connections
        rules = CategoryDetectionRule.objects.filter(
            connection__account=current_account
        ).select_related('connection', 'suggested_category').order_by('-created_at')
        
        # Calculate statistics
        active_rules_count = rules.filter(is_active=True).count()
        total_applied = sum(rule.applied_count for rule in rules)
        total_ignored = sum(rule.ignored_count for rule in rules)
        total_suggestions = total_applied + total_ignored
        success_rate = round((total_applied / total_suggestions * 100) if total_suggestions > 0 else 0)
        
        context = {
            'rules': rules,
            'connections': connections,
            'active_rules_count': active_rules_count,
            'total_applied': total_applied,
            'success_rate': success_rate,
            'current_account': current_account,
        }
        
        logger.info(f"Smart Categorisation configuration accessed by {request.user.email} for account {current_account.id}")
        return render(request, 'data_quality/smart_categorisation_config.html', context)
        
    except Exception as e:
        logger.error(f"Error loading Smart Categorisation configuration: {str(e)}", exc_info=True)
        messages.error(request, "Failed to load Smart Categorisation configuration")
        return redirect('data_quality:agent_checks')


@login_required
def create_categorisation_rule(request):
    """Create a new categorisation rule"""
    logger = logging.getLogger(__name__)
    
    try:
        # Get user's current account
        current_account = None
        if hasattr(request.user, 'profile') and request.user.profile.current_account:
            current_account = request.user.profile.current_account
        
        if not current_account:
            messages.error(request, "No account selected")
            return redirect('data_quality:agent_checks')
        
        # Get all active connections for the account
        connections = Connection.objects.filter(account=current_account, status='active')
        if not connections.exists():
            messages.error(request, "No active Xero connections found")
            return redirect('data_quality:agent_checks')
        
        if request.method == 'POST':
            from .forms import CategoryDetectionRuleForm
            form = CategoryDetectionRuleForm(request.POST, account=current_account)
            
            if form.is_valid():
                rule = form.save()
                
                messages.success(
                    request, 
                    f"Categorisation rule '{rule.name}' created successfully for {rule.connection.organization_name}!"
                )
                logger.info(f"Rule '{rule.name}' created by {request.user.email} for connection {rule.connection.id}")
                return redirect('data_quality:configure_smart_categorisation')
            else:
                messages.error(request, "Please correct the errors below")
        else:
            from .forms import CategoryDetectionRuleForm
            form = CategoryDetectionRuleForm(account=current_account)
        
        # Get existing rules for sidebar display
        from data_quality.models import CategoryDetectionRule, ConditionOperator
        import json
        
        rules = CategoryDetectionRule.objects.filter(
            connection__account=current_account
        ).select_related('connection').order_by('-priority', 'name')
        
        # Prepare condition data for JavaScript
        operators = [{'value': choice[0], 'label': choice[1]} for choice in ConditionOperator.choices]
        fields = [
            {'value': 'description', 'label': 'Description'},
            {'value': 'amount', 'label': 'Amount'},
            {'value': 'reference', 'label': 'Reference'},
            {'value': 'contact_name', 'label': 'Contact Name'},
            {'value': 'date', 'label': 'Date'},
        ]
        
        context = {
            'form': form,
            'connections': connections,
            'current_account': current_account,
            'rules': rules,
            'operators_json': json.dumps(operators),
            'fields_json': json.dumps(fields),
        }
        
        return render(request, 'data_quality/create_categorisation_rule.html', context)
        
    except Exception as e:
        logger.error(f"Error creating categorisation rule: {str(e)}", exc_info=True)
        messages.error(request, "Failed to create categorisation rule")
        return redirect('data_quality:configure_smart_categorisation')


@login_required
def edit_categorisation_rule(request, rule_id):
    """Edit an existing categorisation rule"""
    messages.info(request, f"Rule editing coming soon! (Rule {rule_id})")
    return redirect('data_quality:configure_smart_categorisation')


@login_required
def delete_categorisation_rule(request, rule_id):
    """Delete a categorisation rule"""
    messages.info(request, f"Rule deletion coming soon! (Rule {rule_id})")
    return redirect('data_quality:configure_smart_categorisation')


@login_required
def tracking_categories_dropdown(request, connection_id):
    """Return category dropdown HTML for Turbo frame"""
    logger = logging.getLogger(__name__)

    try:
        # Get user's current account
        current_account = None
        if hasattr(request.user, 'profile') and request.user.profile.current_account:
            current_account = request.user.profile.current_account

        if not current_account:
            return render(request, 'data_quality/partials/category_dropdown_error.html', {
                'error': 'No account selected'
            })

        # Verify connection belongs to user's account
        from connections.models import Connection
        try:
            connection = Connection.objects.get(
                id=connection_id,
                account=current_account,
                status='active'
            )
        except Connection.DoesNotExist:
            return render(request, 'data_quality/partials/category_dropdown_error.html', {
                'error': 'Connection not found or access denied'
            })

        # Get tracking categories for this connection
        from data_quality.models import XeroTrackingCategory
        categories = XeroTrackingCategory.objects.filter(
            connection=connection,
            status='ACTIVE'
        ).order_by('name')

        return render(request, 'data_quality/partials/category_dropdown.html', {
            'categories': categories,
            'connection': connection,
        })

    except Exception as e:
        logger.error(f"Error loading tracking categories for connection {connection_id}: {str(e)}", exc_info=True)
        return render(request, 'data_quality/partials/category_dropdown_error.html', {
            'error': 'Failed to load tracking categories'
        })


@login_required
def get_tracking_categories_for_connection(request, connection_id):
    """AJAX endpoint to get tracking categories for a specific connection"""
    logger = logging.getLogger(__name__)

    if request.method != 'GET':
        return JsonResponse({'error': 'GET method required'}, status=405)

    try:
        # Get user's current account
        current_account = None
        if hasattr(request.user, 'profile') and request.user.profile.current_account:
            current_account = request.user.profile.current_account

        if not current_account:
            return JsonResponse({'error': 'No account selected'}, status=400)

        # Verify connection belongs to user's account
        from connections.models import Connection
        try:
            connection = Connection.objects.get(
                id=connection_id,
                account=current_account,
                status='active'
            )
        except Connection.DoesNotExist:
            return JsonResponse({'error': 'Connection not found or access denied'}, status=404)

        # Get tracking categories for this connection
        from data_quality.models import XeroTrackingCategory
        categories = XeroTrackingCategory.objects.filter(
            connection=connection,
            status='ACTIVE'
        ).order_by('name')

        # Convert to JSON format for dropdown
        categories_data = [
            {
                'id': category.id,
                'name': category.name,
                'display_name': category.name
            }
            for category in categories
        ]

        return JsonResponse({
            'success': True,
            'categories': categories_data,
            'connection_name': connection.organization_name
        })

    except Exception as e:
        logger.error(f"Error loading tracking categories for connection {connection_id}: {str(e)}", exc_info=True)
        return JsonResponse({'error': 'Failed to load tracking categories'}, status=500)


@login_required
def suggestion_review_dashboard(request):
    """Display suggestion review dashboard"""
    logger = logging.getLogger(__name__)

    try:
        # Get user's current account
        current_account = None
        if hasattr(request.user, 'profile') and request.user.profile.current_account:
            current_account = request.user.profile.current_account

        if not current_account:
            messages.error(request, "No account selected")
            return redirect('dashboard')

        # Get pending suggestions for this account
        from data_quality.models import CategorySuggestion
        suggestions = CategorySuggestion.objects.filter(
            connection__account=current_account,
            status='PENDING'
        ).select_related(
            'detection_rule',
            'suggested_category',
            'connection'
        ).order_by('-created_at')

        # Get statistics
        total_pending = suggestions.count()
        total_rules = CategoryDetectionRule.objects.filter(
            connection__account=current_account,
            is_active=True
        ).count()

        context = {
            'suggestions': suggestions,
            'total_pending': total_pending,
            'total_rules': total_rules,
            'current_account': current_account,
        }

        return render(request, 'data_quality/suggestion_review_dashboard.html', context)

    except Exception as e:
        logger.error(f"Error loading suggestion review dashboard: {str(e)}", exc_info=True)
        messages.error(request, "Failed to load suggestion review dashboard")
        return redirect('data_quality:configure_smart_categorisation')


@login_required
def ignore_suggestion(request, suggestion_id):
    """Handle ignore action for a suggestion"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    logger = logging.getLogger(__name__)

    try:
        # Get user's current account
        current_account = None
        if hasattr(request.user, 'profile') and request.user.profile.current_account:
            current_account = request.user.profile.current_account

        if not current_account:
            return JsonResponse({'error': 'No account selected'}, status=400)

        # Get suggestion
        from data_quality.models import CategorySuggestion
        suggestion = get_object_or_404(
            CategorySuggestion,
            id=suggestion_id,
            connection__account=current_account,
            status='PENDING'
        )

        # Use suggestion handler
        from data_quality.services.category_suggestion_handler import CategorySuggestionHandler
        handler = CategorySuggestionHandler()
        result = handler.handle_ignore_action(suggestion, request.user)

        if result['success']:
            return JsonResponse({
                'success': True,
                'message': 'Suggestion ignored successfully'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result['error']
            }, status=400)

    except Exception as e:
        logger.error(f"Error ignoring suggestion {suggestion_id}: {str(e)}", exc_info=True)
        return JsonResponse({'error': 'Failed to ignore suggestion'}, status=500)


@login_required
def mark_done_suggestion(request, suggestion_id):
    """Handle mark done action for a suggestion"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    logger = logging.getLogger(__name__)

    try:
        # Get user's current account
        current_account = None
        if hasattr(request.user, 'profile') and request.user.profile.current_account:
            current_account = request.user.profile.current_account

        if not current_account:
            return JsonResponse({'error': 'No account selected'}, status=400)

        # Get suggestion
        from data_quality.models import CategorySuggestion
        suggestion = get_object_or_404(
            CategorySuggestion,
            id=suggestion_id,
            connection__account=current_account,
            status='PENDING'
        )

        # Use suggestion handler
        from data_quality.services.category_suggestion_handler import CategorySuggestionHandler
        handler = CategorySuggestionHandler()
        result = handler.handle_mark_done_action(suggestion, request.user)

        if result['success']:
            return JsonResponse({
                'success': True,
                'message': 'Suggestion marked as done successfully'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result['error']
            }, status=400)

    except Exception as e:
        logger.error(f"Error marking suggestion {suggestion_id} as done: {str(e)}", exc_info=True)
        return JsonResponse({'error': 'Failed to mark suggestion as done'}, status=500)


@login_required
def fix_suggestion(request, suggestion_id):
    """Handle fix action for a suggestion"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    logger = logging.getLogger(__name__)

    try:
        # Get user's current account
        current_account = None
        if hasattr(request.user, 'profile') and request.user.profile.current_account:
            current_account = request.user.profile.current_account

        if not current_account:
            return JsonResponse({'error': 'No account selected'}, status=400)

        # Get suggestion
        from data_quality.models import CategorySuggestion
        suggestion = get_object_or_404(
            CategorySuggestion,
            id=suggestion_id,
            connection__account=current_account,
            status='PENDING'
        )

        # Use suggestion handler
        from data_quality.services.category_suggestion_handler import CategorySuggestionHandler
        handler = CategorySuggestionHandler()
        result = handler.handle_fix_action(suggestion, request.user)

        if result['success']:
            return JsonResponse({
                'success': True,
                'message': 'Opening Xero to fix categorization',
                'xero_url': result['xero_url']
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result['error']
            }, status=400)

    except Exception as e:
        logger.error(f"Error fixing suggestion {suggestion_id}: {str(e)}", exc_info=True)
        return JsonResponse({'error': 'Failed to fix suggestion'}, status=500)


@login_required
def bulk_ignore_suggestions(request):
    """Handle bulk ignore action for multiple suggestions"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    logger = logging.getLogger(__name__)

    try:
        # Get user's current account
        current_account = None
        if hasattr(request.user, 'profile') and request.user.profile.current_account:
            current_account = request.user.profile.current_account

        if not current_account:
            return JsonResponse({'error': 'No account selected'}, status=400)

        # Get suggestion IDs from request
        suggestion_ids = request.POST.getlist('suggestion_ids')
        if not suggestion_ids:
            return JsonResponse({'error': 'No suggestions selected'}, status=400)

        # Get suggestions
        from data_quality.models import CategorySuggestion
        suggestions = CategorySuggestion.objects.filter(
            id__in=suggestion_ids,
            connection__account=current_account,
            status='PENDING'
        )

        if not suggestions.exists():
            return JsonResponse({'error': 'No valid suggestions found'}, status=400)

        # Use suggestion handler for bulk operation
        from data_quality.services.category_suggestion_handler import CategorySuggestionHandler
        handler = CategorySuggestionHandler()
        result = handler.handle_bulk_ignore_action(list(suggestions), request.user)

        if result['success']:
            return JsonResponse({
                'success': True,
                'message': f"Ignored {result['processed_count']} suggestions successfully",
                'processed_count': result['processed_count'],
                'failed_count': result['failed_count']
            })
        else:
            return JsonResponse({
                'success': False,
                'error': f"Bulk ignore completed with errors: {result['failed_count']} failed",
                'processed_count': result['processed_count'],
                'failed_count': result['failed_count'],
                'errors': result['errors']
            }, status=400)

    except Exception as e:
        logger.error(f"Error bulk ignoring suggestions: {str(e)}", exc_info=True)
        return JsonResponse({'error': 'Failed to bulk ignore suggestions'}, status=500)
