from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
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

@login_required
def dashboard(request):
    from integrations.models import Integration, Issue
    integrations = Integration.objects.filter(user=request.user, is_active=True)
    all_issues = Issue.objects.filter(integration__user=request.user, status='open')
    
    context = {
        'integrations': integrations,
        'issues': all_issues,
        'total_issues': all_issues.count(),
        'critical_issues': all_issues.filter(severity='critical').count(),
        'high_issues': all_issues.filter(severity='high').count(),
    }
    return render(request, 'dashboard.html', context)
