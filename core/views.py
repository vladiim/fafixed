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
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('xero_connect')
    else:
        form = CustomUserCreationForm()
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
