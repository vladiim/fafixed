from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from core.models import Account, PrefixIdMixin
from encrypted_model_fields.fields import EncryptedTextField, EncryptedCharField
from datetime import datetime, timedelta
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


class Integration(models.Model, PrefixIdMixin):
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

class IssueManager(models.Manager):
    """Custom manager for Issue model with proper aggregation logic"""
    
    def create_or_update_issue(self, integration, validation_result):
        """
        Create a new issue or update an existing one within the proper scope.
        
        Scoping rules:
        1. Issues are scoped to the same Account (via integration.account)
        2. Issues are scoped to the same chart of accounts (via integration.external_account_id)
        3. Issues are grouped by rule name and severity within that scope
        
        Args:
            integration: Integration instance (provides account + chart scope)
            validation_result: ValidationResult from validation rule
            
        Returns:
            Issue: Created or updated issue record
        """
        # Generate issue key for this specific scope
        issue_key = self._generate_issue_key(integration, validation_result)
        
        # Look for existing open issue within the same scope
        existing_issue = self.filter(
            integration__account=integration.account,  # Same account (tenant)
            integration__external_account_id=integration.external_account_id,  # Same chart of accounts
            issue_key=issue_key,  # Same issue type grouping
            status='open'
        ).first()
        
        if existing_issue:
            # Update existing issue with new occurrence
            return self._update_existing_issue(existing_issue, validation_result)
        else:
            # Create new issue
            return self._create_new_issue(integration, validation_result, issue_key)
    
    def _generate_issue_key(self, integration, validation_result):
        """Generate a scoped issue key for grouping similar issues"""
        import hashlib
        
        # Key format: account_id:external_account_id:rule_name:severity
        # This ensures issues are only grouped within the same tenant + chart scope
        full_key = f"{integration.account.id}:{integration.external_account_id}:{validation_result.rule_name}:{validation_result.severity.value}"
        
        # If the key is too long for the database field, hash it
        if len(full_key) > 64:
            # Create a shorter key by hashing the long parts but keeping readable parts
            hash_input = f"{integration.external_account_id}:{validation_result.rule_name}"
            hash_short = hashlib.md5(hash_input.encode()).hexdigest()[:12]
            return f"{integration.account.id}:{hash_short}:{validation_result.severity.value}"
        
        return full_key
    
    def _update_existing_issue(self, existing_issue, validation_result):
        """Update an existing issue with new occurrence data"""
        from django.utils import timezone
        import uuid
        
        # Generate unique occurrence ID  
        occurrence_id = str(uuid.uuid4())
        
        # Add to occurrence tracking
        existing_issue.occurrence_ids.append(occurrence_id)
        existing_issue.latest_occurrence = {
            'id': occurrence_id,
            'timestamp': timezone.now().isoformat(),
            'metadata': validation_result.metadata or {}
        }
        
        # Update aggregated fields
        existing_issue.count += 1
        existing_issue.last_seen = timezone.now()
        existing_issue.description = validation_result.description  # Update with latest description
        
        # Serialize affected transactions to ensure JSON compatibility
        serialized_transactions = self._serialize_affected_transactions(
            validation_result.affected_transactions
        )
        existing_issue.affected_transactions = serialized_transactions  # Latest affected transactions
        
        existing_issue.save()
        return existing_issue
    
    def _create_new_issue(self, integration, validation_result, issue_key):
        """Create a new issue record"""
        from django.utils import timezone
        import uuid
        
        # Generate unique occurrence ID for first occurrence
        occurrence_id = str(uuid.uuid4())
        
        # Use rule name directly as category - no more duplication!
        category = validation_result.rule_name
        
        # Serialize affected transactions to ensure JSON compatibility
        serialized_transactions = self._serialize_affected_transactions(
            validation_result.affected_transactions
        )
        
        # Create new issue
        issue = self.create(
            integration=integration,
            title=validation_result.title,
            description=validation_result.description,
            category=category,  # Use rule name directly
            severity=validation_result.severity.value,
            status='open',
            count=1,
            affected_transactions=serialized_transactions,
            issue_key=issue_key,
            occurrence_ids=[occurrence_id],
            latest_occurrence={
                'id': occurrence_id,
                'timestamp': timezone.now().isoformat(),
                'metadata': validation_result.metadata or {}
            }
        )
        
        return issue
    
    def get_issues_for_account(self, account):
        """Get all issues scoped to a specific account"""
        return self.filter(integration__account=account)
    
    def get_issues_for_chart(self, integration):
        """Get all issues scoped to a specific chart of accounts"""
        return self.filter(
            integration__account=integration.account,
            integration__external_account_id=integration.external_account_id
        )
    
    def _serialize_affected_transactions(self, affected_transactions):
        """
        Convert affected_transactions data to JSON-serializable format.
        
        Handles Decimal types and other non-serializable data from validation results.
        
        Args:
            affected_transactions: Raw data from ValidationResult
            
        Returns:
            JSON-serializable version of the same data
        """
        if not affected_transactions:
            return []
        
        from decimal import Decimal
        import json
        
        def make_serializable(obj):
            """Recursively convert non-serializable types to serializable ones"""
            if isinstance(obj, Decimal):
                return float(obj)
            elif isinstance(obj, dict):
                return {key: make_serializable(value) for key, value in obj.items()}
            elif isinstance(obj, list):
                return [make_serializable(item) for item in obj]
            else:
                # For other types, try JSON serialization to check if they're already OK
                try:
                    json.dumps(obj)
                    return obj
                except (TypeError, ValueError):
                    # If it fails, convert to string as fallback
                    return str(obj)
        
        return make_serializable(affected_transactions)


class Issue(models.Model, PrefixIdMixin):
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
    
    # Use custom manager for aggregation logic
    objects = IssueManager()
    
    integration = models.ForeignKey(Integration, on_delete=models.CASCADE, related_name='issues')
    title = models.CharField(max_length=300)
    description = models.TextField()
    category = models.CharField(max_length=50, db_index=True, 
                               help_text="Category based on validation rule name")
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    count = models.PositiveIntegerField(default=1)
    affected_transactions = models.JSONField(default=list, blank=True)
    
    # Enhanced aggregation and resolution tracking fields
    issue_key = models.CharField(max_length=64, db_index=True, blank=True, 
                                help_text="Key for grouping similar issues within account+chart scope")
    occurrence_ids = models.JSONField(default=list, blank=True,
                                     help_text="List of individual occurrence IDs")
    latest_occurrence = models.JSONField(default=dict, blank=True,
                                        help_text="Most recent occurrence details")
    resolution_notes = models.TextField(blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    def mark_occurrence_resolved(self, occurrence_id, user):
        """Mark individual occurrence as resolved"""
        if occurrence_id in self.occurrence_ids:
            self.occurrence_ids.remove(occurrence_id)
            
            # If no more occurrences, mark issue as resolved
            if not self.occurrence_ids:
                self.status = 'resolved'
                self.resolved_by = user
                self.resolved_at = timezone.now()
            
            self.save()
    
    def get_unresolved_count(self):
        """Get count of unresolved individual occurrences"""
        return len(self.occurrence_ids)
    
    def get_category_display_name(self):
        """Get human-readable category name based on validation rule"""
        # Convert rule names to human-readable format
        return self.category.replace('_', ' ').title()
    
    def save(self, *args, **kwargs):
        """Override save to generate issue_key if not provided"""
        if not self.issue_key:
            # Generate scoped issue key: account_id:external_account_id:category:severity
            self.issue_key = f"{self.integration.account.id}:{self.integration.external_account_id}:{self.category}:{self.severity}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.title} ({self.integration.organization_name})"
    
    class Meta:
        ordering = ['-last_seen']
        indexes = [
            models.Index(fields=['integration', 'status', 'category']),
            models.Index(fields=['issue_key']),
            models.Index(fields=['integration', 'category', 'status']),
        ]


# Apply prefix_id decorator to Issue model
Issue = Issue.has_prefix_id('iss')


class TransactionData(models.Model, PrefixIdMixin):
    """Stores transaction data from external systems
    Multi-tenanted through: TransactionData → Integration → Account"""
    
    TRANSACTION_TYPES = [
        ('spend', 'Spend'),
        ('receive', 'Receive'),
        ('bank_transfer', 'Bank Transfer'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('authorised', 'Authorised'),
        ('deleted', 'Deleted'), 
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('pending', 'Pending'),
    ]
    
    # Multi-tenant relationship via Integration
    integration = models.ForeignKey(Integration, on_delete=models.CASCADE, related_name='transactions')
    
    # External system identifiers
    external_transaction_id = models.CharField(max_length=255, db_index=True)
    external_account_id = models.CharField(max_length=255, db_index=True)  # Xero bank account ID
    
    # Transaction details
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    date = models.DateField(db_index=True)
    reference = models.CharField(max_length=500, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    
    # Financial details
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency_code = models.CharField(max_length=3, default='USD')
    
    # Status and reconciliation
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, db_index=True)
    is_reconciled = models.BooleanField(default=False, db_index=True)
    
    # Contact/Supplier information
    contact_name = models.CharField(max_length=500, blank=True, null=True)
    contact_external_id = models.CharField(max_length=255, blank=True, null=True)
    
    # External system URL - direct link to transaction in Xero
    external_url = models.URLField(max_length=500, blank=True, null=True, 
                                   help_text="Direct link to view this transaction in Xero")
    
    # Raw data from external system  
    raw_data = models.JSONField(default=dict, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_synced_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['integration', 'external_transaction_id']
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['integration', 'date']),
            models.Index(fields=['integration', 'status']),
            models.Index(fields=['integration', 'is_reconciled']),
            models.Index(fields=['external_account_id', 'date']),
        ]
    
    def __str__(self):
        return f"{self.reference or self.external_transaction_id} - {self.amount} {self.currency_code}"
    
    @property
    def account(self):
        """Get the account this transaction belongs to (for convenience)"""
        return self.integration.account
    
    def get_available_validation_rules_count(self):
        """Get the count of available validation rules for this transaction's integration"""
        from .validation.registry import ValidationRuleRegistry
        try:
            enabled_rules = ValidationRuleRegistry.get_enabled_rules_for_integration(self.integration)
            return len(enabled_rules)
        except Exception:
            # Fallback to all registered rules if integration-specific lookup fails
            return len(ValidationRuleRegistry.get_rule_names())
    
    def get_validation_status_count(self):
        """Get the count of validation rules that have been run on this transaction"""
        return self.validation_statuses.filter(status='completed').count()
    
    def get_validation_status_display(self):
        """Get the validation status as (x/y) format with CSS class"""
        completed = self.get_validation_status_count()
        total = self.get_available_validation_rules_count()
        
        if completed == 0:
            css_class = 'validation-status-none'
        elif completed == total:
            css_class = 'validation-status-all'
        else:
            css_class = 'validation-status-some'
        
        return {
            'text': f'({completed}/{total})',
            'css_class': css_class,
            'completed': completed,
            'total': total
        }
    
    def get_validation_rule_statuses(self):
        """Get status of individual validation rules for this transaction"""
        from .validation.registry import ValidationRuleRegistry
        
        try:
            # Get enabled rules for this integration
            enabled_rules = ValidationRuleRegistry.get_enabled_rules_for_integration(self.integration)
            rule_names = [rule.name for rule in enabled_rules]
        except Exception:
            # Fallback to all registered rules
            rule_names = ValidationRuleRegistry.get_rule_names()
        
        # Get existing statuses
        existing_statuses = {
            status.rule_name: status 
            for status in self.validation_statuses.all()
        }
        
        # Build status list for all available rules
        rule_statuses = []
        for rule_name in rule_names:
            status = existing_statuses.get(rule_name)
            rule_statuses.append({
                'name': rule_name,
                'display_name': rule_name.replace('_', ' ').title(),
                'status': status.status if status else 'not_run',
                'passed': status.passed if status else None,
                'issues_found': status.issues_found if status else 0,
                'can_view_details': status and status.status == 'completed',
                'status_obj': status
            })
        
        return rule_statuses


class TransactionValidationStatus(models.Model):
    """Tracks which validation rules have been run on each transaction"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    SEVERITY_CHOICES = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical'),
    ]
    
    transaction = models.ForeignKey(TransactionData, on_delete=models.CASCADE, related_name='validation_statuses')
    rule_name = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Execution tracking
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Results
    passed = models.BooleanField(null=True, blank=True)  # None = not run, True = passed, False = failed
    issues_found = models.PositiveIntegerField(default=0)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, null=True, blank=True)
    
    # Details
    result_data = models.JSONField(default=dict, blank=True)  # Stores detailed validation results
    error_message = models.TextField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['transaction', 'rule_name']
        indexes = [
            models.Index(fields=['transaction', 'rule_name']),
            models.Index(fields=['status']),
            models.Index(fields=['completed_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.rule_name} on {self.transaction} - {self.status}"
    
    @property
    def duration(self):
        """Get the duration of the validation run."""
        if self.completed_at and self.started_at:
            return self.completed_at - self.started_at
        return None
    
    def mark_running(self):
        """Mark validation as running"""
        self.status = 'running'
        self.started_at = timezone.now()
        self.save()
    
    def mark_completed(self, passed, issues_found=0, severity=None, result_data=None):
        """Mark validation as completed"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"Marking TransactionValidationStatus {self.id} as completed for transaction {self.transaction_id}")
        
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.passed = passed
        self.issues_found = issues_found
        if severity:
            self.severity = severity
        if result_data:
            self.result_data = result_data
            
        logger.info(f"About to save TransactionValidationStatus {self.id} with status: {self.status}")
        self.save()
        logger.info(f"TransactionValidationStatus {self.id} saved successfully")
    
    def mark_failed(self, error_message):
        """Mark validation as failed"""
        self.status = 'failed'
        self.completed_at = timezone.now()
        self.error_message = error_message
        self.save()
    


class OAuthState(models.Model):
    """Secure OAuth state tokens to prevent CSRF attacks"""
    
    integration = models.ForeignKey(Integration, on_delete=models.CASCADE, related_name='oauth_states')
    state_token = models.CharField(max_length=128, unique=True, db_index=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)
    is_used = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['state_token', 'is_used']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"OAuth State for {self.integration.organization_name} - {self.state_token[:16]}..."
    
    def mark_as_used(self):
        """Mark this state token as used"""
        self.is_used = True
        self.used_at = timezone.now()
        self.save()
    
    @classmethod
    def create_state_token(cls, integration: Integration, user) -> 'OAuthState':
        """Create a new secure state token"""
        import secrets
        import string
        
        # Generate cryptographically secure random token
        alphabet = string.ascii_letters + string.digits
        state_token = ''.join(secrets.choice(alphabet) for _ in range(64))
        
        return cls.objects.create(
            integration=integration,
            state_token=state_token,
            created_by=user
        )
    
    @classmethod
    def cleanup_expired_states(cls, hours=24):
        """Clean up expired OAuth states older than specified hours"""
        from datetime import timedelta
        cutoff_time = timezone.now() - timedelta(hours=hours)
        expired_states = cls.objects.filter(created_at__lt=cutoff_time)
        count = expired_states.count()
        expired_states.delete()
        return count


class TransactionLineItem(models.Model):
    """Line items for transactions (for detailed breakdown)
    Multi-tenanted through: TransactionLineItem → TransactionData → Integration → Account"""
    
    transaction = models.ForeignKey(TransactionData, on_delete=models.CASCADE, related_name='line_items')
    
    # Line item details
    description = models.TextField(blank=True, null=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=4, default=1)
    unit_amount = models.DecimalField(max_digits=15, decimal_places=2)
    line_amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Tax information
    tax_type = models.CharField(max_length=100, blank=True, null=True)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Account classification
    account_code = models.CharField(max_length=20, blank=True, null=True)
    account_name = models.CharField(max_length=200, blank=True, null=True)
    
    # External references
    external_line_item_id = models.CharField(max_length=255, blank=True, null=True)
    
    # Raw data
    raw_data = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['id']


class ValidationRuleConfig(models.Model):
    """Configuration for validation rules per integration."""
    
    integration = models.ForeignKey(Integration, on_delete=models.CASCADE, related_name='validation_configs')
    rule_name = models.CharField(max_length=100, db_index=True)  # e.g., 'duplicate_transactions'
    is_enabled = models.BooleanField(default=True)
    config = models.JSONField(default=dict, blank=True)  # Rule-specific settings
    severity_override = models.CharField(
        max_length=20, 
        choices=[
            ('critical', 'Critical'),
            ('high', 'High'),
            ('medium', 'Medium'),
            ('low', 'Low'),
        ],
        null=True, 
        blank=True,
        help_text="Override the default severity level for this rule"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['integration', 'rule_name']
        ordering = ['rule_name']
    
    def __str__(self):
        return f"{self.integration.organization_name} - {self.rule_name}"


class ValidationRun(models.Model):
    """Track validation rule execution runs."""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    integration = models.ForeignKey(Integration, on_delete=models.CASCADE, related_name='validation_runs')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Run statistics
    total_rules = models.PositiveIntegerField(default=0)
    rules_passed = models.PositiveIntegerField(default=0)
    rules_failed = models.PositiveIntegerField(default=0)
    issues_found = models.PositiveIntegerField(default=0)
    
    # Error handling
    error_message = models.TextField(blank=True, null=True)
    
    # Metadata
    triggered_by = models.CharField(max_length=50, default='manual')  # 'manual', 'sync', 'scheduled'
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['integration', 'status']),
            models.Index(fields=['started_at']),
        ]
    
    def __str__(self):
        return f"Validation run for {self.integration.organization_name} at {self.started_at}"
    
    @property
    def duration(self):
        """Get the duration of the validation run."""
        if self.completed_at and self.started_at:
            return self.completed_at - self.started_at
        return None
    
    def mark_completed(self):
        """Mark the validation run as completed."""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()
    
    def mark_failed(self, error_message: str):
        """Mark the validation run as failed."""
        self.status = 'failed'
        self.error_message = error_message
        self.completed_at = timezone.now()
        self.save()


# Apply prefix_id to Integration model
Integration = Integration.has_prefix_id('int')

# Apply prefix_id to TransactionData model
TransactionData = TransactionData.has_prefix_id('txn')
