from django.db import models
from django.utils import timezone
from shared.models import PrefixIdMixin
from core.models import Account


class AccountingDataQuerySet(models.QuerySet):
    """Ensure all accounting data is properly scoped to account"""

    def for_account(self, account: Account):
        return self.filter(account=account)

    def for_user(self, user):
        return self.filter(account__account_users__user=user)


class AccountingDataManager(models.Manager):
    """Custom manager with built-in tenant isolation"""

    def get_queryset(self):
        return AccountingDataQuerySet(self.model, using=self._db)

    def for_account(self, account: Account):
        return self.get_queryset().for_account(account)


class AccountingData(models.Model):
    """Abstract base class for all accounting data with multi-tenant isolation"""
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    integration = models.ForeignKey('integrations.Integration', on_delete=models.CASCADE)

    objects = AccountingDataManager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # Ensure account matches integration.account
        if self.integration.account != self.account:
            from django.core.exceptions import ValidationError
            raise ValidationError("Account mismatch: integration.account must match account")
        super().save(*args, **kwargs)


class Contact(AccountingData, PrefixIdMixin):
    """Comprehensive contact/customer/supplier information"""

    CONTACT_TYPES = [
        ('CUSTOMER', 'Customer'),
        ('SUPPLIER', 'Supplier'),
        ('EMPLOYEE', 'Employee'),
        ('BOTH', 'Customer & Supplier'),
    ]

    TAX_TYPES = [
        ('GST_REGISTERED', 'GST Registered'),
        ('GST_FREE', 'GST Free'),
        ('EXEMPT', 'Exempt'),
        ('UNKNOWN', 'Unknown'),
    ]

    # Basic Information
    name = models.CharField(max_length=200)
    contact_type = models.CharField(max_length=20, choices=CONTACT_TYPES)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)

    # Business Details
    company_number = models.CharField(max_length=100, blank=True)  # ABN, ACN, etc.
    tax_number = models.CharField(max_length=100, blank=True)  # GST/VAT number
    tax_type = models.CharField(max_length=20, choices=TAX_TYPES, default='UNKNOWN')

    # Address Information
    address_line_1 = models.CharField(max_length=200, blank=True)
    address_line_2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True)

    # Payment Terms
    default_payment_terms = models.CharField(max_length=100, blank=True)  # "NET 30", "Due on Receipt"
    credit_limit = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    # Status
    is_active = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)

    # Provider Integration
    external_contact_id = models.CharField(max_length=255)
    external_data = models.JSONField(default=dict)  # Provider-specific fields

    # Sync tracking
    last_synced_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['integration', 'external_contact_id']
        indexes = [
            models.Index(fields=['integration', 'contact_type']),
            models.Index(fields=['integration', 'is_active']),
            models.Index(fields=['account', 'name']),
            models.Index(fields=['email']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_contact_type_display()})"

    @property
    def full_address(self):
        """Get formatted full address"""
        parts = [
            self.address_line_1,
            self.address_line_2,
            self.city,
            self.state,
            self.postal_code,
            self.country
        ]
        return ', '.join(part for part in parts if part)


class ChartOfAccountsEntry(AccountingData, PrefixIdMixin):
    """Standard chart of accounts representation"""

    ACCOUNT_TYPES = [
        ('ASSET', 'Asset'),
        ('LIABILITY', 'Liability'),
        ('EQUITY', 'Equity'),
        ('REVENUE', 'Revenue'),
        ('EXPENSE', 'Expense'),
        ('COST_OF_SALES', 'Cost of Sales'),
    ]

    ACCOUNT_CATEGORIES = [
        ('SALES', 'Sales Income'),
        ('OTHER_INCOME', 'Other Income'),
        ('OFFICE_EXPENSES', 'Office Expenses'),
        ('PAYROLL', 'Payroll Expenses'),
        ('GST_COLLECTED', 'GST Collected'),
        ('GST_PAID', 'GST Paid'),
    ]

    # Core fields
    code = models.CharField(max_length=20, db_index=True)
    name = models.CharField(max_length=200)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)
    category = models.CharField(max_length=50, choices=ACCOUNT_CATEGORIES, blank=True)

    # Tax handling
    default_tax_code = models.CharField(max_length=50, blank=True)
    is_tax_account = models.BooleanField(default=False)

    # Provider-specific data
    external_account_id = models.CharField(max_length=255)
    external_data = models.JSONField(default=dict)

    # Status
    is_active = models.BooleanField(default=True)
    is_system_account = models.BooleanField(default=False)  # Can't be deleted

    class Meta:
        unique_together = ['integration', 'code']
        indexes = [
            models.Index(fields=['integration', 'account_type']),
            models.Index(fields=['integration', 'category']),
            models.Index(fields=['account', 'is_active']),
        ]


class SalesInvoice(AccountingData, PrefixIdMixin):
    """Comprehensive sales invoices from accounting system"""

    INVOICE_STATUS = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('SENT', 'Sent'),
        ('PARTIALLY_PAID', 'Partially Paid'),
        ('PAID', 'Paid'),
        ('OVERDUE', 'Overdue'),
        ('VOIDED', 'Voided'),
        ('DELETED', 'Deleted'),
    ]

    INVOICE_TYPES = [
        ('ACCREC', 'Accounts Receivable'), # Sales Invoice
        ('ACCPAY', 'Accounts Payable'),    # Purchase Bill
        ('ACCRECEI', 'Accounts Receivable Item'), # Sales Credit Note
        ('ACCPAYI', 'Accounts Payable Item'),     # Purchase Credit Note
    ]

    # Contact/Customer Information
    contact = models.ForeignKey(Contact, on_delete=models.PROTECT, related_name='invoices')

    # Core invoice data
    invoice_type = models.CharField(max_length=20, choices=INVOICE_TYPES, default='ACCREC')
    invoice_number = models.CharField(max_length=100)
    reference = models.CharField(max_length=255, blank=True)  # Customer reference/PO number

    # Dates
    invoice_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    expected_payment_date = models.DateField(null=True, blank=True)
    fully_paid_on_date = models.DateField(null=True, blank=True)

    # Financial Details
    currency_code = models.CharField(max_length=3, default='AUD')
    currency_rate = models.DecimalField(max_digits=10, decimal_places=6, default=1.0)

    # Amounts (all in invoice currency)
    subtotal = models.DecimalField(max_digits=15, decimal_places=2)
    total_tax = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_discount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    amount_due = models.DecimalField(max_digits=15, decimal_places=2)
    amount_credited = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Payment Terms
    payment_terms = models.CharField(max_length=100, blank=True)

    # Status and Classification
    status = models.CharField(max_length=20, choices=INVOICE_STATUS, default='DRAFT')
    has_attachments = models.BooleanField(default=False)
    has_errors = models.BooleanField(default=False)

    # Line Item Summary
    line_amount_types = models.CharField(max_length=20, default='Exclusive')  # Exclusive, Inclusive, NoTax

    # Branding and Presentation
    branding_theme_id = models.CharField(max_length=255, blank=True)
    url = models.URLField(blank=True)  # Online invoice URL

    # Provider Integration
    external_invoice_id = models.CharField(max_length=255)
    external_data = models.JSONField(default=dict)

    # Tracking
    last_synced_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['integration', 'external_invoice_id']
        indexes = [
            models.Index(fields=['integration', 'status']),
            models.Index(fields=['integration', 'invoice_date']),
            models.Index(fields=['integration', 'invoice_type']),
            models.Index(fields=['contact', 'status']),
            models.Index(fields=['account', 'status', 'due_date']),
            models.Index(fields=['invoice_number']),
        ]

    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.contact.name}"

    @property
    def is_overdue(self):
        """Check if invoice is overdue"""
        if not self.due_date or self.status in ['PAID', 'VOIDED', 'DELETED']:
            return False
        return timezone.now().date() > self.due_date and self.amount_due > 0

    @property
    def days_overdue(self):
        """Calculate days overdue"""
        if not self.is_overdue:
            return 0
        return (timezone.now().date() - self.due_date).days


class InvoiceLineItem(models.Model, PrefixIdMixin):
    """Detailed line items for invoices"""

    invoice = models.ForeignKey(SalesInvoice, on_delete=models.CASCADE, related_name='line_items')

    # Line Item Details
    item_code = models.CharField(max_length=100, blank=True)
    description = models.TextField()

    # Chart of Accounts
    account_code = models.CharField(max_length=20)
    chart_account = models.ForeignKey(ChartOfAccountsEntry, on_delete=models.PROTECT,
                                    null=True, blank=True, related_name='invoice_line_items')

    # Quantities and Pricing
    quantity = models.DecimalField(max_digits=15, decimal_places=4, default=1)
    unit_amount = models.DecimalField(max_digits=15, decimal_places=4)
    discount_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)  # Percentage
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    line_amount = models.DecimalField(max_digits=15, decimal_places=2)  # After discount

    # Tax Information
    tax_type = models.CharField(max_length=50, blank=True)  # GST rate identifier
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Tracking Categories (Xero supports up to 2)
    tracking_category_1_id = models.CharField(max_length=255, blank=True)
    tracking_category_1_name = models.CharField(max_length=200, blank=True)
    tracking_category_1_option = models.CharField(max_length=200, blank=True)
    tracking_category_2_id = models.CharField(max_length=255, blank=True)
    tracking_category_2_name = models.CharField(max_length=200, blank=True)
    tracking_category_2_option = models.CharField(max_length=200, blank=True)

    # Provider Integration
    external_line_item_id = models.CharField(max_length=255, blank=True)
    external_data = models.JSONField(default=dict)

    # Ordering
    line_number = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['line_number']
        indexes = [
            models.Index(fields=['invoice', 'line_number']),
            models.Index(fields=['chart_account']),
            models.Index(fields=['item_code']),
        ]

    def __str__(self):
        return f"{self.invoice.invoice_number} - Line {self.line_number}: {self.description}"


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

    # Tracking categories (Xero supports max 2 tracking categories per line item)
    tracking_category_1_id = models.CharField(max_length=255, blank=True, null=True)
    tracking_category_1_name = models.CharField(max_length=200, blank=True, null=True)
    tracking_category_1_option = models.CharField(max_length=200, blank=True, null=True)
    tracking_category_2_id = models.CharField(max_length=255, blank=True, null=True)
    tracking_category_2_name = models.CharField(max_length=200, blank=True, null=True)
    tracking_category_2_option = models.CharField(max_length=200, blank=True, null=True)

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


# Apply prefix_id decorators
Contact = Contact.has_prefix_id('cnt')
ChartOfAccountsEntry = ChartOfAccountsEntry.has_prefix_id('coa')
SalesInvoice = SalesInvoice.has_prefix_id('inv')
InvoiceLineItem = InvoiceLineItem.has_prefix_id('iln')
Transaction = Transaction.has_prefix_id('txn')


