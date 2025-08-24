from django.db import models
from django.contrib.auth.models import User
from core.models import Account
from encrypted_model_fields.fields import EncryptedTextField, EncryptedCharField
from datetime import datetime, timezone, timedelta
import json

class IntegrationProvider(models.Model):
    """Registry of available integration providers"""
    
    PROVIDER_TYPES = [
        ('xero', 'Xero'),
    ]
    
    name = models.CharField(max_length=50, unique=True)
    display_name = models.CharField(max_length=100)
    provider_type = models.CharField(max_length=20, choices=PROVIDER_TYPES)
    is_active = models.BooleanField(default=True)
    auth_url_template = models.URLField()
    token_url = models.URLField()
    revoke_url = models.URLField(blank=True, null=True)
    scopes_default = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.display_name


class Integration(models.Model):
    """Integration model linking organization accounts to external provider accounts"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending Authorization'),
        ('active', 'Active'),
        ('expired', 'Token Expired'),
        ('revoked', 'Access Revoked'),
        ('error', 'Error State'),
    ]
    
    # Multi-tenant fields - organization level
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='integrations')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_integrations')
    
    # Integration details
    provider = models.ForeignKey(IntegrationProvider, on_delete=models.CASCADE)
    external_account_id = models.CharField(max_length=255)  # External system's account ID (Xero org ID)
    external_account_name = models.CharField(max_length=200)  # External system's account name
    organization_name = models.CharField(max_length=200)  # External organization name
    
    # Status and lifecycle
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    connected_at = models.DateTimeField(null=True, blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, null=True)
    
    # Metadata
    config = models.JSONField(default=dict, blank=True)  # Provider-specific config
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['account', 'provider', 'external_account_id']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.account.name} - {self.provider.display_name} - {self.organization_name}"


class IntegrationCredential(models.Model):
    """Secure storage for OAuth tokens and credentials"""
    
    integration = models.OneToOneField(Integration, on_delete=models.CASCADE, related_name='credentials')
    
    # Encrypted OAuth tokens
    access_token = EncryptedTextField()
    refresh_token = EncryptedTextField(blank=True, null=True)
    token_type = models.CharField(max_length=20, default='Bearer')
    
    # Token metadata
    expires_at = models.DateTimeField(null=True, blank=True)
    scopes = models.JSONField(default=list)
    
    # Additional encrypted credentials (API keys, secrets, etc.)
    additional_credentials = EncryptedTextField(default='{}')  # JSON stored as encrypted text
    
    # Security tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_refreshed_at = models.DateTimeField(null=True, blank=True)
    
    def is_expired(self):
        """Check if access token is expired"""
        if not self.expires_at:
            return False
        return timezone.now() >= self.expires_at
    
    def expires_soon(self, minutes=30):
        """Check if token expires within specified minutes"""
        if not self.expires_at:
            return False
        return timezone.now() + timedelta(minutes=minutes) >= self.expires_at
    
    def get_additional_credential(self, key):
        """Safely get additional credential"""
        try:
            creds = json.loads(self.additional_credentials)
            return creds.get(key)
        except (json.JSONDecodeError, TypeError):
            return None
    
    def set_additional_credential(self, key, value):
        """Safely set additional credential"""
        try:
            creds = json.loads(self.additional_credentials)
        except (json.JSONDecodeError, TypeError):
            creds = {}
        creds[key] = value
        self.additional_credentials = json.dumps(creds)


class IntegrationSync(models.Model):
    """Track sync operations and their status"""
    
    SYNC_TYPES = [
        ('full', 'Full Sync'),
        ('incremental', 'Incremental Sync'),
        ('webhook', 'Webhook Triggered'),
    ]
    
    SYNC_STATUS = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    integration = models.ForeignKey(Integration, on_delete=models.CASCADE, related_name='syncs')
    sync_type = models.CharField(max_length=20, choices=SYNC_TYPES)
    status = models.CharField(max_length=20, choices=SYNC_STATUS, default='pending')
    
    # Sync details
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    records_processed = models.PositiveIntegerField(default=0)
    records_success = models.PositiveIntegerField(default=0)
    records_failed = models.PositiveIntegerField(default=0)
    
    # Error handling
    error_message = models.TextField(blank=True, null=True)
    error_details = models.JSONField(default=dict, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)  # Sync-specific data
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-started_at']

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
