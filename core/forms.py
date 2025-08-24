from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    company_name = forms.CharField(max_length=200, required=True)
    
    class Meta:
        model = User
        fields = ("email", "company_name", "password1", "password2")
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove username field since we're using email
        if 'username' in self.fields:
            del self.fields['username']
        
        # Update field attributes
        self.fields['email'].widget.attrs.update({
            'placeholder': 'Enter your email address',
            'class': 'form-input'
        })
        self.fields['company_name'].widget.attrs.update({
            'placeholder': 'Enter your company name',
            'class': 'form-input'
        })
        self.fields['password1'].widget.attrs.update({
            'placeholder': 'Create a strong password',
            'class': 'form-input'
        })
        self.fields['password2'].widget.attrs.update({
            'placeholder': 'Confirm your password',
            'class': 'form-input'
        })
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email address already exists.")
        return email
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.username = self.cleaned_data["email"]  # Use email as username
        if commit:
            user.save()
        return user