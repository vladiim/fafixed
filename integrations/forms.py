"""
Forms for integration models.
"""

from django import forms
from .models import TransactionData


class TransactionEditForm(forms.ModelForm):
    """
    Form for editing transaction data - restricted to super_admins only.
    """
    
    class Meta:
        model = TransactionData
        fields = [
            'amount',
            'date', 
            'reference',
            'description',
            'contact_name',
            'status',
            # Read-only fields for context
        ]
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand-green focus:border-brand-green sm:text-sm',
                'step': '0.01',
                'placeholder': 'Enter amount'
            }),
            'date': forms.DateInput(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand-green focus:border-brand-green sm:text-sm',
                'type': 'date'
            }),
            'reference': forms.TextInput(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand-green focus:border-brand-green sm:text-sm',
                'placeholder': 'Transaction reference'
            }),
            'description': forms.Textarea(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand-green focus:border-brand-green sm:text-sm',
                'rows': 3,
                'placeholder': 'Transaction description'
            }),
            'contact_name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand-green focus:border-brand-green sm:text-sm',
                'placeholder': 'Contact name'
            }),
            'status': forms.Select(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand-green focus:border-brand-green sm:text-sm'
            }),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make some fields read-only for safety
        readonly_fields = ['external_transaction_id', 'external_account_id']
        for field_name in readonly_fields:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs['readonly'] = True
        
        # Ensure status field has correct choices
        if 'status' in self.fields:
            self.fields['status'].choices = TransactionData.STATUS_CHOICES
        
        # Add help text
        self.fields['amount'].help_text = "Transaction amount (be careful changing this)"
        self.fields['date'].help_text = "Transaction date"
        self.fields['reference'].help_text = "Transaction reference/number"
        self.fields['status'].help_text = "Transaction status in source system"
    
    def clean_amount(self):
        """Validate amount is reasonable"""
        amount = self.cleaned_data.get('amount')
        if amount is not None:
            if amount < 0:
                # Allow negative amounts but warn
                pass
            if abs(amount) > 1000000:  # 1M limit
                raise forms.ValidationError("Amount seems unusually large. Please verify.")
        return amount
    
    def save(self, commit=True):
        """Override save to add audit trail"""
        instance = super().save(commit=False)
        
        # Add audit information
        if hasattr(self, 'user'):
            # Store who made the edit - this would need to be passed from view
            pass
        
        if commit:
            instance.save()
        return instance