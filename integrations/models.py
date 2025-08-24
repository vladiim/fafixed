from django.db import models
from django.contrib.auth.models import User

class Integration(models.Model):
    INTEGRATION_TYPES = [
        ('xero', 'Xero'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='integrations')
    integration_type = models.CharField(max_length=20, choices=INTEGRATION_TYPES, default='xero')
    account_name = models.CharField(max_length=200)
    account_id = models.CharField(max_length=100, unique=True)
    organization_name = models.CharField(max_length=200)
    connected_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.organization_name} - {self.account_name} ({self.get_integration_type_display()})"
    
    class Meta:
        ordering = ['-connected_at']

class Issue(models.Model):
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('resolved', 'Resolved'),
        ('ignored', 'Ignored'),
    ]
    
    CATEGORY_CHOICES = [
        ('duplicate_transactions', 'Duplicate Transactions'),
        ('missing_data', 'Missing Data'),
        ('inconsistent_categories', 'Inconsistent Categories'),
        ('date_anomalies', 'Date Anomalies'),
        ('amount_discrepancies', 'Amount Discrepancies'),
        ('tax_code_errors', 'Tax Code Errors'),
    ]
    
    integration = models.ForeignKey(Integration, on_delete=models.CASCADE, related_name='issues')
    title = models.CharField(max_length=300)
    description = models.TextField()
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    count = models.PositiveIntegerField(default=1)
    affected_transactions = models.JSONField(default=list, blank=True)
    
    def __str__(self):
        return f"{self.title} ({self.integration.organization_name})"
    
    class Meta:
        ordering = ['-last_seen']
