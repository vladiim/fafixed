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
        
        all_issues = Issue.objects.filter(integration__account=current_account, status='open')
        
        # Get recent transactions across all integrations
        recent_transactions = TransactionData.objects.filter(
            integration__account=current_account
        ).select_related('integration').order_by('-date', '-created_at')[:10]
        
    else:
        enhanced_integrations = []
        all_issues = Issue.objects.none()
        recent_transactions = []
    
    context = {
        'integrations': enhanced_integrations,
        'issues': all_issues,
        'total_issues': all_issues.count(),
        'critical_issues': all_issues.filter(severity='critical').count(),
        'high_issues': all_issues.filter(severity='high').count(),
        'recent_transactions': recent_transactions,
    }
    return render(request, 'dashboard.html', context)

