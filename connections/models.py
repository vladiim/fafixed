from django.db import models
from django.contrib.auth.models import User

from core.models import Account
from shared.models import PrefixIdMixin


class Provider(models.Model):
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


class Connection(models.Model, PrefixIdMixin):
    """Connection model linking organization accounts to external provider accounts"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending Authorization'),
        ('active', 'Active'),
        ('expired', 'Token Expired'),
        ('revoked', 'Access Revoked'),
        ('error', 'Error State'),
    ]
    
    # Multi-tenant fields - organization level
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='connections')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_connections')
    
    # Connection details
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)  # NEW: Points to connections.Provider
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

class Credential(models.Model):
    """Secure storage for OAuth tokens and credentials"""
    
    connection = models.OneToOneField(Connection, on_delete=models.CASCADE, related_name='credentials')
    
    # Encrypted OAuth tokens
    access_token = models.TextField()  # Will be encrypted in production
    refresh_token = models.TextField(blank=True, null=True)  # Will be encrypted
    token_type = models.CharField(max_length=20, default='Bearer')
    
    # Token metadata
    expires_at = models.DateTimeField(null=True, blank=True)
    scopes = models.JSONField(default=list)
    
    # Additional encrypted credentials (API keys, secrets, etc.)
    additional_credentials = models.TextField(default='{}')  # JSON stored as encrypted text
    
    # Security tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_refreshed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Credentials for {self.connection.organization_name}"
    
    def is_token_expired(self):
        """Check if the access token is expired"""
        if not self.expires_at:
            return False
        from django.utils import timezone
        return timezone.now() >= self.expires_at
    
    def needs_refresh(self, buffer_minutes=5):
        """Check if token needs refresh (with buffer time)"""
        if not self.expires_at:
            return False
        from django.utils import timezone
        from datetime import timedelta
        buffer_time = timezone.now() + timedelta(minutes=buffer_minutes)
        return buffer_time >= self.expires_at
    
    def update_tokens(self, access_token, refresh_token=None, expires_at=None, scopes=None):
        """Update OAuth tokens"""
        self.access_token = access_token
        if refresh_token is not None:
            self.refresh_token = refresh_token
        if expires_at is not None:
            self.expires_at = expires_at
        if scopes is not None:
            self.scopes = scopes
        
        from django.utils import timezone
        self.last_refreshed_at = timezone.now()
        self.save()
    
    class Meta:
        ordering = ['-created_at']


class OAuthState(models.Model):
    """Temporary storage for OAuth state tokens"""
    
    connection = models.ForeignKey(Connection, on_delete=models.CASCADE, related_name='oauth_states')
    state_token = models.CharField(max_length=255, unique=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='connection_oauth_states')
    
    # State management
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"OAuth State for {self.connection.organization_name} - {self.state_token[:15]}..."
    
    def mark_as_used(self):
        """Mark this state token as used"""
        from django.utils import timezone
        self.is_used = True
        self.used_at = timezone.now()
        self.save()
    
    @classmethod
    def create_state_token(cls, connection, created_by):
        """Create a new state token"""
        import secrets
        import string
        
        # Generate secure random state token
        token = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(64))
        
        return cls.objects.create(
            connection=connection,
            state_token=token,
            created_by=created_by
        )
    
    @classmethod
    def cleanup_expired_states(cls, hours=24):
        """Clean up expired state tokens"""
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_time = timezone.now() - timedelta(hours=hours)
        expired_states = cls.objects.filter(created_at__lt=cutoff_time)
        count = expired_states.count()
        expired_states.delete()
        return count
    
    class Meta:
        ordering = ['-created_at']


class Sync(models.Model):
    """Track synchronization runs between external systems and our database"""
    
    SYNC_TYPES = [
        ('full', 'Full Sync'),
        ('incremental', 'Incremental Sync'),
        ('webhook', 'Webhook Triggered'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    connection = models.ForeignKey(Connection, on_delete=models.CASCADE, related_name='syncs')
    sync_type = models.CharField(max_length=20, choices=SYNC_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Progress tracking
    records_processed = models.IntegerField(default=0)
    records_success = models.IntegerField(default=0)
    records_failed = models.IntegerField(default=0)
    
    # Error handling
    error_message = models.TextField(blank=True, null=True)
    error_details = models.JSONField(default=dict, blank=True)
    
    # Metadata and configuration
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.sync_type.title()} sync for {self.connection.organization_name} - {self.status}"
    
    def mark_completed(self):
        """Mark sync as completed"""
        from django.utils import timezone
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()
    
    def mark_failed(self, error_message, error_details=None):
        """Mark sync as failed with error details"""
        from django.utils import timezone
        self.status = 'failed'
        self.error_message = error_message
        if error_details:
            self.error_details = error_details
        self.completed_at = timezone.now()
        self.save()
    
    def update_progress(self, processed, success=None, failed=None):
        """Update sync progress counters"""
        self.records_processed = processed
        if success is not None:
            self.records_success = success
        if failed is not None:
            self.records_failed = failed
        self.save()
    
    @property
    def duration(self):
        """Calculate sync duration"""
        if not self.completed_at:
            return None
        return self.completed_at - self.started_at
    
    @property
    def success_rate(self):
        """Calculate success rate percentage"""
        if self.records_processed == 0:
            return 0
        return (self.records_success / self.records_processed) * 100
    
    class Meta:
        ordering = ['-started_at']


# Apply prefix_id to Connection  
Connection = Connection.has_prefix_id('con')
