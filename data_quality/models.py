from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from shared.models import PrefixIdMixin


class IssueManager(models.Manager):
    """Custom manager for Issue model with proper aggregation logic"""
    
    def create_or_update_issue(self, connection, validation_result):
        """
        Create a new issue or update an existing one within the proper scope.
        
        Scoping rules:
        1. Issues are scoped to the same Account (via connection.account)
        2. Issues are scoped to the same chart of accounts (via connection.external_account_id)
        3. Issues are grouped by rule name and severity within that scope
        
        Args:
            connection: Connection instance (provides account + chart scope)
            validation_result: ValidationResult from validation rule
            
        Returns:
            Issue: Created or updated issue record
        """
        # Generate issue key for this specific scope
        issue_key = self._generate_issue_key(connection, validation_result)
        
        # Look for existing open issue within the same scope
        existing_issue = self.filter(
            connection__account=connection.account,  # Same account (tenant)
            connection__external_account_id=connection.external_account_id,  # Same chart of accounts
            issue_key=issue_key,  # Same issue type grouping
            status='open'
        ).first()
        
        if existing_issue:
            # Update existing issue with new occurrence
            return self._update_existing_issue(existing_issue, validation_result)
        else:
            # Create new issue
            return self._create_new_issue(connection, validation_result, issue_key)
    
    def _generate_issue_key(self, connection, validation_result):
        """Generate a scoped issue key for grouping similar issues"""
        import hashlib
        
        # Key format: account_id:external_account_id:rule_name:severity
        # This ensures issues are only grouped within the same tenant + chart scope
        full_key = f"{connection.account.id}:{connection.external_account_id}:{validation_result.rule_name}:{validation_result.severity.value}"
        
        # If the key is too long for the database field, hash it
        if len(full_key) > 64:
            # Create a shorter key by hashing the long parts but keeping readable parts
            hash_input = f"{connection.external_account_id}:{validation_result.rule_name}"
            hash_short = hashlib.md5(hash_input.encode()).hexdigest()[:12]
            return f"{connection.account.id}:{hash_short}:{validation_result.severity.value}"
        
        return full_key
    
    def _update_existing_issue(self, issue, validation_result):
        """Update an existing issue with a new occurrence"""
        issue.count += 1
        issue.last_seen = timezone.now()

        # Add this occurrence ID to the list if it exists
        occurrence_id = getattr(validation_result, 'occurrence_id', None)
        if occurrence_id and occurrence_id not in issue.occurrence_ids:
            issue.occurrence_ids.append(occurrence_id)

        # Update latest occurrence details
        issue.latest_occurrence = {
            'rule_name': validation_result.rule_name,
            'severity': validation_result.severity.value if validation_result.severity else None,
            'message': validation_result.description or validation_result.title,
            'occurrence_id': occurrence_id,
            'timestamp': timezone.now().isoformat()
        }
        
        # Update affected transactions
        if hasattr(validation_result, 'transaction_ids'):
            for txn_id in validation_result.transaction_ids:
                if txn_id not in issue.affected_transactions:
                    issue.affected_transactions.append(txn_id)
        
        issue.save()
        return issue
    
    def _create_new_issue(self, connection, validation_result, issue_key):
        """Create a new issue"""
        return self.create(
            connection=connection,
            title=validation_result.title or f"Validation issue: {validation_result.rule_name}",
            description=validation_result.message,
            category=validation_result.rule_name,
            severity=validation_result.severity.value,
            issue_key=issue_key,
            occurrence_ids=[validation_result.occurrence_id] if validation_result.occurrence_id else [],
            latest_occurrence={
                'rule_name': validation_result.rule_name,
                'severity': validation_result.severity.value,
                'message': validation_result.message,
                'occurrence_id': validation_result.occurrence_id,
                'timestamp': timezone.now().isoformat()
            },
            affected_transactions=getattr(validation_result, 'transaction_ids', [])
        )


class Issue(models.Model, PrefixIdMixin):
    """Issue tracking for data quality problems"""
    
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
    
    connection = models.ForeignKey('connections.Connection', on_delete=models.CASCADE, related_name='issues')
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
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_data_quality_issues')
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
    
    def resolve_issue(self, user, notes=""):
        """Mark entire issue as resolved"""
        self.status = 'resolved'
        self.resolved_by = user
        self.resolved_at = timezone.now()
        if notes:
            self.resolution_notes = notes
        self.save()
    
    def ignore_issue(self, user, notes=""):
        """Mark issue as ignored"""
        self.status = 'ignored'
        self.resolved_by = user
        self.resolved_at = timezone.now()
        if notes:
            self.resolution_notes = notes
        self.save()
    
    @property
    def account(self):
        """Get the account this issue belongs to (for convenience)"""
        return self.connection.account
    
    def __str__(self):
        return f"{self.title} ({self.severity})"
    
    class Meta:
        ordering = ['-last_seen']
        indexes = [
            models.Index(fields=['connection', 'status']),
            models.Index(fields=['connection', 'severity']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['issue_key']),
        ]


class ValidationRun(models.Model):
    """Track validation rule execution runs"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    connection = models.ForeignKey('connections.Connection', on_delete=models.CASCADE, related_name='validation_runs')
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
    
    def mark_completed(self, rules_passed=0, rules_failed=0, issues_found=0):
        """Mark validation run as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.rules_passed = rules_passed
        self.rules_failed = rules_failed
        self.issues_found = issues_found
        self.save()
    
    def mark_failed(self, error_message):
        """Mark validation run as failed"""
        self.status = 'failed'
        self.completed_at = timezone.now()
        self.error_message = error_message
        self.save()
    
    @property
    def duration(self):
        """Get the duration of the validation run"""
        if self.completed_at:
            return self.completed_at - self.started_at
        return None
    
    @property
    def success_rate(self):
        """Get success rate as percentage"""
        if self.total_rules == 0:
            return 0
        return (self.rules_passed / self.total_rules) * 100
    
    def __str__(self):
        return f"Validation run for {self.connection.organization_name} - {self.status}"
    
    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['connection', 'status']),
            models.Index(fields=['connection', 'started_at']),
            models.Index(fields=['triggered_by', 'status']),
        ]


class ValidationRuleConfig(models.Model):
    """Configuration for validation rules per connection"""
    
    connection = models.ForeignKey('connections.Connection', on_delete=models.CASCADE, related_name='validation_configs')
    rule_name = models.CharField(max_length=100, db_index=True)
    is_enabled = models.BooleanField(default=True)
    severity_override = models.CharField(max_length=20, blank=True, null=True,
                                        choices=Issue.SEVERITY_CHOICES)
    
    # Rule configuration
    config = models.JSONField(default=dict, blank=True,
                             help_text="Rule-specific configuration parameters")
    
    # Scheduling
    run_on_sync = models.BooleanField(default=True,
                                     help_text="Run this rule when sync completes")
    run_scheduled = models.BooleanField(default=False,
                                       help_text="Run this rule on schedule")
    schedule_frequency = models.CharField(max_length=20, blank=True, null=True,
                                         help_text="Cron-like schedule expression")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    
    def update_last_run(self):
        """Update the last run timestamp"""
        self.last_run_at = timezone.now()
        self.save(update_fields=['last_run_at'])
    
    def __str__(self):
        return f"{self.rule_name} for {self.connection.organization_name} ({'enabled' if self.is_enabled else 'disabled'})"
    
    class Meta:
        unique_together = ['connection', 'rule_name']
        ordering = ['rule_name']
        indexes = [
            models.Index(fields=['connection', 'is_enabled']),
            models.Index(fields=['rule_name', 'is_enabled']),
            models.Index(fields=['run_on_sync']),
            models.Index(fields=['run_scheduled']),
        ]


class IssueResolution(models.Model):
    """Track resolution actions for issues"""
    
    RESOLUTION_TYPES = [
        ('fixed', 'Fixed'),
        ('ignored', 'Ignored'),
        ('false_positive', 'False Positive'),
        ('bulk_action', 'Bulk Action'),
    ]
    
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name='resolutions')
    resolution_type = models.CharField(max_length=20, choices=RESOLUTION_TYPES)
    resolved_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='issue_resolutions')
    resolved_at = models.DateTimeField(auto_now_add=True)
    
    # Resolution details
    notes = models.TextField(blank=True)
    occurrence_ids = models.JSONField(default=list, blank=True,
                                     help_text="Specific occurrence IDs resolved")
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True,
                               help_text="Additional resolution metadata")
    
    def __str__(self):
        return f"{self.resolution_type} resolution for {self.issue.title}"
    
    class Meta:
        ordering = ['-resolved_at']
        indexes = [
            models.Index(fields=['issue', 'resolution_type']),
            models.Index(fields=['resolved_by', 'resolved_at']),
        ]


class DataQualityMetric(models.Model):
    """Track data quality metrics over time"""
    
    connection = models.ForeignKey('connections.Connection', on_delete=models.CASCADE, related_name='quality_metrics')
    date = models.DateField(db_index=True)
    
    # Quality scores (0-100)
    overall_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    completeness_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    accuracy_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    consistency_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Issue counts by severity
    critical_issues = models.PositiveIntegerField(default=0)
    high_issues = models.PositiveIntegerField(default=0)
    medium_issues = models.PositiveIntegerField(default=0)
    low_issues = models.PositiveIntegerField(default=0)
    
    # Transaction coverage
    total_transactions = models.PositiveIntegerField(default=0)
    validated_transactions = models.PositiveIntegerField(default=0)
    
    # Metadata
    calculated_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    @property
    def total_issues(self):
        """Get total number of issues"""
        return self.critical_issues + self.high_issues + self.medium_issues + self.low_issues
    
    @property
    def validation_coverage(self):
        """Get validation coverage percentage"""
        if self.total_transactions == 0:
            return 0
        return (self.validated_transactions / self.total_transactions) * 100
    
    def __str__(self):
        return f"Quality metrics for {self.connection.organization_name} on {self.date}"
    
    class Meta:
        unique_together = ['connection', 'date']
        ordering = ['-date']
        indexes = [
            models.Index(fields=['connection', 'date']),
            models.Index(fields=['date', 'overall_score']),
        ]


class XeroTrackingCategory(models.Model):
    """Cache of Xero tracking categories for local performance"""

    connection = models.ForeignKey(
        'integrations.Integration',
        on_delete=models.CASCADE,
        related_name='tracking_categories'
    )
    xero_category_id = models.CharField(max_length=255, db_index=True)
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=20)  # ACTIVE, ARCHIVED
    last_synced_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['connection', 'xero_category_id']
        ordering = ['name']
        indexes = [
            models.Index(fields=['connection', 'status']),
            models.Index(fields=['xero_category_id']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.connection.organization_name})"


class XeroTrackingOption(models.Model):
    """Cache of Xero tracking options within categories"""
    
    category = models.ForeignKey(
        XeroTrackingCategory, 
        on_delete=models.CASCADE,
        related_name='options'
    )
    xero_option_id = models.CharField(max_length=255, db_index=True)
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=20)  # ACTIVE, ARCHIVED
    
    class Meta:
        unique_together = ['category', 'xero_option_id']
        ordering = ['name']
        indexes = [
            models.Index(fields=['category', 'status']),
            models.Index(fields=['xero_option_id']),
        ]
    
    def __str__(self):
        return f"{self.category.name}: {self.name}"


class ConditionOperator(models.TextChoices):
    """Operators for rule conditions"""
    EQUALS = 'EQUALS', 'Equals'
    NOT_EQUALS = 'NOT_EQUALS', 'Not Equals'
    CONTAINS = 'CONTAINS', 'Contains'
    NOT_CONTAINS = 'NOT_CONTAINS', 'Does Not Contain'
    STARTS_WITH = 'STARTS_WITH', 'Starts With'
    ENDS_WITH = 'ENDS_WITH', 'Ends With'
    REGEX = 'REGEX', 'Regular Expression'
    GREATER_THAN = 'GREATER_THAN', 'Greater Than'
    LESS_THAN = 'LESS_THAN', 'Less Than'
    GREATER_THAN_OR_EQUAL = 'GREATER_THAN_OR_EQUAL', 'Greater Than or Equal'
    LESS_THAN_OR_EQUAL = 'LESS_THAN_OR_EQUAL', 'Less Than or Equal'


class CategoryDetectionRule(models.Model):
    """User-configurable rules for detecting transaction categories"""

    CONDITION_LOGIC_CHOICES = [
        ('ALL', 'All conditions must match'),
        ('ANY', 'Any condition can match'),
    ]

    connection = models.ForeignKey(
        'integrations.Integration',
        on_delete=models.CASCADE,
        related_name='category_detection_rules'
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    suggested_category = models.ForeignKey(
        XeroTrackingCategory,
        on_delete=models.PROTECT,
        related_name='detection_rules'
    )
    
    # Rule conditions stored as JSON
    conditions = models.JSONField(
        help_text="List of condition dictionaries with field, operator, value"
    )
    condition_logic = models.CharField(
        max_length=3,
        choices=CONDITION_LOGIC_CHOICES,
        default='ALL'
    )
    
    # Rule management
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=0, help_text="Higher numbers = higher priority")
    
    # Rule statistics
    applied_count = models.IntegerField(
        default=0, 
        help_text="Number of suggestions that were applied by users"
    )
    ignored_count = models.IntegerField(
        default=0, 
        help_text="Number of suggestions that were ignored by users"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['connection', 'name']
        ordering = ['-priority', 'name']
        indexes = [
            models.Index(fields=['connection', 'is_active']),
            models.Index(fields=['connection', 'priority']),
            models.Index(fields=['suggested_category']),
        ]
    
    def __str__(self):
        return f"{self.name} -> {self.suggested_category.name}"


class CategorySuggestion(models.Model):
    """Suggestions generated by detection rules for manual review"""
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('APPLIED', 'Applied to Xero'),
        ('IGNORED', 'Ignored'),
        ('SUPERSEDED', 'Superseded by newer suggestion'),
    ]
    
    connection = models.ForeignKey(
        'connections.Connection',
        on_delete=models.CASCADE,
        related_name='category_suggestions'
    )
    detection_rule = models.ForeignKey(
        CategoryDetectionRule,
        on_delete=models.CASCADE,
        related_name='suggestions'
    )
    
    # Transaction details
    xero_transaction_id = models.CharField(max_length=255, db_index=True)
    transaction_description = models.TextField(blank=True, null=True)
    transaction_contact = models.CharField(max_length=200, blank=True, null=True)
    transaction_amount = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        blank=True, 
        null=True
    )
    
    # Suggestion details
    suggested_category = models.ForeignKey(
        XeroTrackingCategory,
        on_delete=models.PROTECT,
        related_name='suggestions'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # User decision tracking
    decided_by = models.ForeignKey(
        'auth.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='category_decisions'
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['detection_rule', 'xero_transaction_id']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['connection', 'status']),
            models.Index(fields=['xero_transaction_id']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['detection_rule', 'status']),
        ]
    
    def __str__(self):
        return f"{self.xero_transaction_id} -> {self.suggested_category.name} ({self.status})"


# Apply prefix_id to Issue model
Issue = Issue.has_prefix_id('iss')