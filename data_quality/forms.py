"""
Forms for data quality models.
"""

from django import forms
from .models import CategoryDetectionRule, XeroTrackingCategory, ConditionOperator


class CategoryDetectionRuleForm(forms.ModelForm):
    """
    Form for creating and editing categorisation rules.
    """
    
    connection = forms.ModelChoiceField(
        queryset=None,
        empty_label="Select Xero Organization...",
        help_text="Choose which Xero organization this rule applies to"
    )
    
    class Meta:
        model = CategoryDetectionRule
        fields = [
            'connection',
            'name',
            'description',
            'suggested_category',
            'condition_logic',
            'is_active',
            'priority',
        ]
        widgets = {
            'connection': forms.Select(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand-green focus:border-brand-green sm:text-sm'
            }),
            'name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand-green focus:border-brand-green sm:text-sm',
                'placeholder': 'Enter rule name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand-green focus:border-brand-green sm:text-sm',
                'rows': 3,
                'placeholder': 'Describe what this rule does'
            }),
            'suggested_category': forms.Select(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand-green focus:border-brand-green sm:text-sm'
            }),
            'condition_logic': forms.Select(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand-green focus:border-brand-green sm:text-sm'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-brand-green focus:ring-brand-green border-gray-300 rounded'
            }),
            'priority': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand-green focus:border-brand-green sm:text-sm',
                'min': '0',
                'max': '100',
                'value': '0'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        account = kwargs.pop('account', None)
        super().__init__(*args, **kwargs)
        
        # Set up connections dropdown for the account
        if account:
            from connections.models import Connection
            self.fields['connection'].queryset = Connection.objects.filter(
                account=account,
                status='active'
            ).order_by('organization_name')
        
        # Initially show all categories - will be filtered by JavaScript when connection is selected
        self.fields['suggested_category'].queryset = XeroTrackingCategory.objects.none()
        
        # If editing existing rule, filter categories to the rule's connection
        if self.instance.pk and self.instance.connection:
            self.fields['suggested_category'].queryset = XeroTrackingCategory.objects.filter(
                connection=self.instance.connection
            ).order_by('name')
        
        # Add help text
        self.fields['name'].help_text = "A descriptive name for this rule"
        self.fields['description'].help_text = "Optional description of when this rule should be applied"
        self.fields['suggested_category'].help_text = "The category to suggest when conditions are met"
        self.fields['condition_logic'].help_text = "Whether ALL conditions or ANY condition must match"
        self.fields['priority'].help_text = "Higher priority rules are evaluated first (0-100)"
        
        # Set default values
        if not self.instance.pk:
            self.fields['is_active'].initial = True
            self.fields['condition_logic'].initial = 'ALL'
            self.fields['priority'].initial = 0
    
    def clean_name(self):
        """Validate rule name is unique for the connection"""
        name = self.cleaned_data.get('name')
        if name:
            name = name.strip()
            if len(name) < 3:
                raise forms.ValidationError("Rule name must be at least 3 characters long")
        return name
    
    def clean_priority(self):
        """Validate priority is within range"""
        priority = self.cleaned_data.get('priority')
        if priority is not None:
            if priority < 0 or priority > 100:
                raise forms.ValidationError("Priority must be between 0 and 100")
        return priority
    
    def clean(self):
        """Custom form validation"""
        cleaned_data = super().clean()
        
        # Handle conditions from the hidden input
        conditions_json = self.data.get('conditions', '[]')
        try:
            import json
            conditions = json.loads(conditions_json) if conditions_json else []
            
            # Validate conditions structure
            valid_fields = ['description', 'amount', 'reference', 'contact_name', 'date']
            valid_operators = [choice[0] for choice in ConditionOperator.choices]
            
            for condition in conditions:
                if not isinstance(condition, dict):
                    raise forms.ValidationError("Invalid condition format")
                
                field = condition.get('field')
                operator = condition.get('operator') 
                value = condition.get('value')
                
                if not field or field not in valid_fields:
                    raise forms.ValidationError(f"Invalid field: {field}")
                    
                if not operator:
                    raise forms.ValidationError("Operator is required for all conditions")
                    
                if not value:
                    raise forms.ValidationError("Value is required for all conditions")
            
            # Store parsed conditions for save method
            cleaned_data['parsed_conditions'] = conditions
            
        except (json.JSONDecodeError, ValueError) as e:
            raise forms.ValidationError("Invalid conditions data")
        
        return cleaned_data
    
    def save(self, commit=True):
        """Override save to add conditions"""
        instance = super().save(commit=False)
        
        # Set conditions from cleaned data
        instance.conditions = self.cleaned_data.get('parsed_conditions', [])
        
        if commit:
            instance.save()
        return instance