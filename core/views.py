from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.contrib import messages
from .forms import CustomUserCreationForm

def home(request):
    return render(request, 'home.html')

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        print(f"Form data: {request.POST}")
        print(f"Form is valid: {form.is_valid()}")
        if not form.is_valid():
            print(f"Form errors: {form.errors}")
            
        if form.is_valid():
            try:
                user = form.save()
                print(f"User created: {user}")
                
                # Create organization account and user profile
                from .models import Account, AccountUser, UserProfile
                
                # Create user profile with prefix_id
                profile, created = UserProfile.objects.get_or_create(user=user)
                print(f"Profile created: {profile}, created: {created}")
                
                # Create organization account
                account = Account.objects.create(
                    name=form.cleaned_data['company_name'],
                    account_type='organization'
                )
                print(f"Account created: {account}")
                
                # Create account-user relationship with owner role
                account_user = AccountUser.objects.create(
                    account=account,
                    user=user,
                    role='owner'
                )
                print(f"AccountUser created: {account_user}")
                
                # Set as current account in profile
                profile.current_account = account
                profile.save()
                print(f"Profile updated with current account")
                
                login(request, user)
                print(f"User logged in, redirecting to xero_connect")
                return redirect('xero_connect')
                
            except ValueError as e:
                print(f"ValueError: {e}")
                form.add_error('company_name', str(e))
            except Exception as e:
                print(f"Unexpected error: {e}")
                form.add_error(None, f"Registration failed: {str(e)}")
    else:
        form = CustomUserCreationForm()
    
    print(f"Rendering form with errors: {form.errors}")
    return render(request, 'registration/register.html', {'form': form})

class CustomLoginView(LoginView):
    template_name = 'registration/login.html'
    success_url = reverse_lazy('dashboard')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Update form field attributes
        form.fields['username'].widget.attrs.update({
            'placeholder': 'Enter your email address',
            'class': 'form-input'
        })
        form.fields['password'].widget.attrs.update({
            'placeholder': 'Enter your password',
            'class': 'form-input'
        })
        return form

def custom_logout(request):
    """
    Custom logout view that properly logs out user and redirects to home
    """
    logout(request)
    messages.success(request, "You have been successfully logged out.")
    return redirect('home')

@login_required
def dashboard(request):
    from integrations.models import Integration, Issue, TransactionData
    from integrations.services.base import IntegrationServiceRegistry
    from django.db.models import Sum, Count, Q
    from datetime import datetime, timedelta
    from django.contrib import messages
    
    # Get user's current account
    current_account = None
    if hasattr(request.user, 'profile') and request.user.profile.current_account:
        current_account = request.user.profile.current_account
    
    if current_account:
        # Only show active integrations, or if none exist, show the most recent non-revoked one
        active_integrations = Integration.objects.filter(
            account=current_account, 
            status='active'
        ).order_by('-created_at')
        
        if active_integrations.exists():
            integrations = active_integrations
        else:
            # Fallback to most recent non-revoked integration if no active ones
            integrations = Integration.objects.filter(
                account=current_account
            ).exclude(status='revoked').order_by('-created_at')[:1]
        
        # Enhance integrations with selected account info and transaction stats
        enhanced_integrations = []
        for integration in integrations:
            enhanced_integration = integration
            enhanced_integration.selected_accounts_count = 0
            enhanced_integration.has_selected_accounts = False
            
            # Get selected organizations from config (fallback to selected_accounts for backwards compatibility)
            selected_accounts = integration.config.get('selected_organizations', integration.config.get('selected_accounts', []))
            if selected_accounts:
                enhanced_integration.selected_accounts_count = len(selected_accounts)
                enhanced_integration.has_selected_accounts = True
            
            # Get transaction stats
            transaction_stats = TransactionData.objects.filter(
                integration=integration
            ).aggregate(
                total_transactions=Count('id'),
                total_amount=Sum('amount'),
                recent_transactions=Count('id', filter=Q(
                    date__gte=datetime.now().date() - timedelta(days=30)
                ))
            )
            enhanced_integration.transaction_count = transaction_stats['total_transactions'] or 0
            enhanced_integration.recent_transaction_count = transaction_stats['recent_transactions'] or 0
            
            # Check if integration needs reconnection (no refresh token for active integration)
            enhanced_integration.needs_reconnect = False
            if integration.status == 'active' and hasattr(integration, 'credentials'):
                if not integration.credentials.refresh_token:
                    enhanced_integration.needs_reconnect = True
            
            enhanced_integrations.append(enhanced_integration)
        
        # Get issue filter from URL parameter (supports multiple statuses)
        issue_filters = request.GET.getlist('issues')  # e.g. ['active', 'resolved']
        if not issue_filters:
            issue_filters = ['active']  # Default to active issues only
        
        # Map filter names to database statuses and display names
        status_mapping = {
            'active': {'db_status': 'open', 'display': 'Active'},
            'resolved': {'db_status': 'resolved', 'display': 'Resolved'},
            'ignored': {'db_status': 'ignored', 'display': 'Ignored'},
        }
        
        # Build queryset and title based on selected filters
        base_issues = Issue.objects.filter(integration__account=current_account)
        db_statuses = []
        display_names = []
        
        for filter_name in issue_filters:
            if filter_name in status_mapping:
                mapping = status_mapping[filter_name]
                db_statuses.append(mapping['db_status'])
                display_names.append(mapping['display'])
        
        # Filter issues by the selected statuses
        if db_statuses:
            all_issues = base_issues.filter(status__in=db_statuses)
        else:
            # Fallback to active issues if no valid filters
            all_issues = base_issues.filter(status='open')
            display_names = ['Active']
        
        # Generate dynamic title using to_sentence logic
        def to_sentence(items):
            """Convert array to sentence format like Rails' to_sentence"""
            if not items:
                return ""
            elif len(items) == 1:
                return items[0]
            elif len(items) == 2:
                return f"{items[0]} & {items[1]}"
            else:
                return f"{', '.join(items[:-1])} & {items[-1]}"
        
        issues_title = f"{to_sentence(display_names)} Issues"
        
        # Get issue statistics for dropdown options
        issue_stats = base_issues.aggregate(
            active_count=Count('id', filter=Q(status='open')),
            resolved_count=Count('id', filter=Q(status='resolved')),
            ignored_count=Count('id', filter=Q(status='ignored')),
            total_count=Count('id')
        )
        
        # Get additional context for enhanced UX
        from datetime import datetime, timedelta
        thirty_days_ago = datetime.now().date() - timedelta(days=30)
        seven_days_ago = datetime.now().date() - timedelta(days=7)
        
        # Recent resolution stats for progress indicators
        recent_resolutions = base_issues.filter(
            status='resolved',
            resolved_at__gte=thirty_days_ago
        ).count()
        
        # Data freshness indicators
        latest_sync = None
        has_stale_data = False
        total_transactions = 0
        recent_transactions = 0
        
        for integration in enhanced_integrations:
            if hasattr(integration, 'syncs') and integration.syncs.exists():
                last_sync = integration.syncs.filter(status='completed').order_by('-completed_at').first()
                if last_sync:
                    if not latest_sync or last_sync.completed_at > latest_sync:
                        latest_sync = last_sync.completed_at
                    
                    # Check if data is stale (more than 3 days)
                    if last_sync.completed_at.date() < (datetime.now().date() - timedelta(days=3)):
                        has_stale_data = True
            
            # Aggregate transaction stats
            total_transactions += integration.transaction_count
            recent_transactions += integration.recent_transaction_count
        
        # Determine user scenario for contextual messaging
        is_first_time_user = total_transactions == 0
        has_resolved_issues = issue_stats['resolved_count'] > 0
        has_active_issues = issue_stats['active_count'] > 0
        
        # Calculate issue-free streak (days since last open issue)
        issue_free_days = 0
        if not has_active_issues and issue_stats['total_count'] > 0:
            last_active_issue = base_issues.filter(status__in=['resolved', 'ignored']).order_by('-resolved_at', '-last_seen').first()
            if last_active_issue and hasattr(last_active_issue, 'resolved_at') and last_active_issue.resolved_at:
                issue_free_days = (datetime.now().date() - last_active_issue.resolved_at.date()).days
        
        # Get recent transactions across all integrations
        recent_transactions = TransactionData.objects.filter(
            integration__account=current_account
        ).select_related('integration').order_by('-date', '-created_at')[:10]
        
    else:
        enhanced_integrations = []
        all_issues = Issue.objects.none()
        recent_transactions = []
        issues_title = "Issues"
        issue_filters = []
        issue_stats = {
            'active_count': 0,
            'resolved_count': 0,
            'ignored_count': 0,
            'total_count': 0
        }
        # Default values for enhanced UX context
        recent_resolutions = 0
        latest_sync = None
        has_stale_data = False
        total_transactions = 0
        is_first_time_user = True
        has_resolved_issues = False
        has_active_issues = False
        issue_free_days = 0
    
    context = {
        'integrations': enhanced_integrations,
        'issues': all_issues,
        'issues_title': issues_title,
        'current_issue_filters': issue_filters,
        'total_issues': all_issues.count(),
        'critical_issues': all_issues.filter(severity='critical').count(),
        'high_issues': all_issues.filter(severity='high').count(),
        'issue_stats': issue_stats,
        'recent_transactions': recent_transactions,
        # Enhanced UX context
        'recent_resolutions': recent_resolutions,
        'latest_sync': latest_sync,
        'has_stale_data': has_stale_data,
        'total_transactions': total_transactions,
        'is_first_time_user': is_first_time_user,
        'has_resolved_issues': has_resolved_issues,
        'has_active_issues': has_active_issues,
        'issue_free_days': issue_free_days,
        'has_integrations': len(enhanced_integrations) > 0,
    }
    return render(request, 'dashboard.html', context)

