from django.db import models
from shared.models import PrefixIdMixin


class Transaction(models.Model, PrefixIdMixin):
    """Stores transaction data from external systems"""
    
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
    
    # Multi-tenant relationship via Connection
    connection = models.ForeignKey('connections.Connection', on_delete=models.CASCADE, related_name='transactions')
    
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
        unique_together = ['connection', 'external_transaction_id']
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['connection', 'date']),
            models.Index(fields=['connection', 'status']),
            models.Index(fields=['connection', 'is_reconciled']),
            models.Index(fields=['external_account_id', 'date']),
        ]
    
    def __str__(self):
        return f"{self.reference or self.external_transaction_id} - {self.amount} {self.currency_code}"
    
    @property
    def account(self):
        """Get the account this transaction belongs to (for convenience)"""
        return self.connection.account
    
    def get_available_validation_rules_count(self):
        """Get the count of available validation rules for this transaction's connection"""
        # TODO: Update this when validation rules are migrated
        try:
            from data_quality.validation.registry import ValidationRuleRegistry
            enabled_rules = ValidationRuleRegistry.get_enabled_rules_for_connection(self.connection)
            return len(enabled_rules)
        except Exception:
            return 0
    
    def is_spend(self):
        """Check if this is a spend transaction"""
        return self.transaction_type == 'spend'
    
    def is_receive(self):
        """Check if this is a receive transaction"""
        return self.transaction_type == 'receive'
    
    def formatted_amount(self):
        """Get formatted amount with currency"""
        return f"{self.amount:,.2f} {self.currency_code}"
    
    def days_since_transaction(self):
        """Get number of days since transaction date"""
        from django.utils import timezone
        return (timezone.now().date() - self.date).days


class TransactionLineItem(models.Model):
    """Line items for transactions (for detailed breakdown)"""
    
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='line_items')
    
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
    
    def __str__(self):
        return f"{self.description or 'Line Item'} - {self.line_amount}"
    
    def formatted_line_amount(self):
        """Get formatted line amount"""
        return f"{self.line_amount:,.2f}"
    
    @property
    def total_with_tax(self):
        """Calculate total amount including tax"""
        return self.line_amount + self.tax_amount
    
    class Meta:
        ordering = ['id']


# Apply prefix_id to Transaction
Transaction = Transaction.has_prefix_id('txn')
