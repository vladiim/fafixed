"""
AccountingRepository - Data access layer for accounting entities

Handles CRUD operations, upserts, and common query patterns for accounting data
"""

from typing import Optional, List
from django.db import transaction
import logging

from financial_data.models import (
    Contact,
    ChartOfAccountsEntry,
    SalesInvoice,
    InvoiceLineItem,
    PurchaseBill,
    BillLineItem,
    InvoicePayment,
)

logger = logging.getLogger(__name__)


class AccountingRepository:
    """Repository for accounting data access patterns"""

    def __init__(self, integration):
        """
        Initialize repository with integration context

        Args:
            integration: Integration instance
        """
        self.integration = integration
        self.account = integration.account

    # Contact operations

    def upsert_contact(self, contact_data: dict) -> Contact:
        """
        Create or update contact based on external_contact_id

        Args:
            contact_data: Dict of Contact model fields (from mapper)

        Returns:
            Contact instance (saved)
        """
        external_id = contact_data.get('external_contact_id')

        if not external_id:
            raise ValueError("external_contact_id required for upsert")

        contact, created = Contact.objects.update_or_create(
            integration=self.integration,
            external_contact_id=external_id,
            defaults=contact_data
        )

        if created:
            logger.info(f"Created new contact: {contact.name} ({contact.prefix_id})")
        else:
            logger.info(f"Updated existing contact: {contact.name} ({contact.prefix_id})")

        return contact

    def get_contact_by_external_id(self, external_contact_id: str) -> Optional[Contact]:
        """
        Get contact by Xero ContactID

        Args:
            external_contact_id: Xero contact ID

        Returns:
            Contact instance or None
        """
        try:
            return Contact.objects.get(
                integration=self.integration,
                external_contact_id=external_contact_id
            )
        except Contact.DoesNotExist:
            return None

    def get_all_contacts(self, contact_type: Optional[str] = None) -> List[Contact]:
        """
        Get all contacts for this integration

        Args:
            contact_type: Filter by type (CUSTOMER, SUPPLIER, etc.) - optional

        Returns:
            List of Contact instances
        """
        queryset = Contact.objects.filter(integration=self.integration, is_active=True)

        if contact_type:
            queryset = queryset.filter(contact_type=contact_type)

        return list(queryset.order_by('name'))

    # Chart of Accounts operations

    def upsert_account_entry(self, account_data: dict) -> ChartOfAccountsEntry:
        """
        Create or update chart of accounts entry

        Args:
            account_data: Dict of ChartOfAccountsEntry model fields

        Returns:
            ChartOfAccountsEntry instance (saved)
        """
        code = account_data.get('code')

        if not code:
            raise ValueError("code required for account upsert")

        account_entry, created = ChartOfAccountsEntry.objects.update_or_create(
            integration=self.integration,
            code=code,
            defaults=account_data
        )

        if created:
            logger.info(f"Created account: {code} - {account_entry.name}")
        else:
            logger.info(f"Updated account: {code} - {account_entry.name}")

        return account_entry

    def get_account_by_code(self, code: str) -> Optional[ChartOfAccountsEntry]:
        """
        Get chart of accounts entry by account code

        Args:
            code: Account code (e.g., "200")

        Returns:
            ChartOfAccountsEntry instance or None
        """
        try:
            return ChartOfAccountsEntry.objects.get(
                integration=self.integration,
                code=code
            )
        except ChartOfAccountsEntry.DoesNotExist:
            return None

    def get_chart_of_accounts(self, active_only: bool = True) -> List[ChartOfAccountsEntry]:
        """
        Get complete chart of accounts

        Args:
            active_only: Only return active accounts

        Returns:
            List of ChartOfAccountsEntry instances
        """
        queryset = ChartOfAccountsEntry.objects.filter(integration=self.integration)

        if active_only:
            queryset = queryset.filter(is_active=True)

        return list(queryset.order_by('code'))

    # Sales Invoice operations

    @transaction.atomic
    def upsert_sales_invoice(self, invoice_data: dict, line_items_data: List[dict] = None) -> SalesInvoice:
        """
        Create or update sales invoice with line items

        Args:
            invoice_data: Dict of SalesInvoice model fields
            line_items_data: List of line item dicts (optional)

        Returns:
            SalesInvoice instance (saved with line items)
        """
        external_id = invoice_data.get('external_invoice_id')

        if not external_id:
            raise ValueError("external_invoice_id required for invoice upsert")

        # Remove line items from invoice data if present
        invoice_data_clean = {k: v for k, v in invoice_data.items() if k != 'line_items'}

        invoice, created = SalesInvoice.objects.update_or_create(
            integration=self.integration,
            external_invoice_id=external_id,
            defaults=invoice_data_clean
        )

        if created:
            logger.info(f"Created invoice: {invoice.invoice_number} ({invoice.prefix_id})")
        else:
            logger.info(f"Updated invoice: {invoice.invoice_number} ({invoice.prefix_id})")

        # Handle line items if provided
        if line_items_data:
            # Clear existing line items
            invoice.line_items.all().delete()

            # Create new line items
            for line_item_data in line_items_data:
                self._create_invoice_line_item(invoice, line_item_data)

        return invoice

    def _create_invoice_line_item(self, invoice: SalesInvoice, line_item_data: dict) -> InvoiceLineItem:
        """
        Create invoice line item and link to chart account if possible

        Args:
            invoice: Parent SalesInvoice
            line_item_data: Dict of InvoiceLineItem fields

        Returns:
            InvoiceLineItem instance (saved)
        """
        # Link to chart account if code provided
        account_code = line_item_data.get('account_code')
        if account_code:
            chart_account = self.get_account_by_code(account_code)
            if chart_account:
                line_item_data['chart_account'] = chart_account

        line_item = InvoiceLineItem.objects.create(
            invoice=invoice,
            **line_item_data
        )

        return line_item

    def get_invoice_by_external_id(self, external_invoice_id: str) -> Optional[SalesInvoice]:
        """
        Get invoice by Xero InvoiceID

        Args:
            external_invoice_id: Xero invoice ID

        Returns:
            SalesInvoice instance or None
        """
        try:
            return SalesInvoice.objects.select_related('contact').prefetch_related('line_items').get(
                integration=self.integration,
                external_invoice_id=external_invoice_id
            )
        except SalesInvoice.DoesNotExist:
            return None

    def get_open_invoices(self) -> List[SalesInvoice]:
        """
        Get all invoices with outstanding amounts

        Returns:
            List of SalesInvoice instances with amount_due > 0
        """
        from django.db.models import Q

        return list(
            SalesInvoice.objects
            .filter(integration=self.integration)
            .filter(amount_due__gt=0)
            .exclude(Q(status='VOIDED') | Q(status='DELETED'))
            .select_related('contact')
            .order_by('due_date')
        )

    # Purchase Bill operations

    @transaction.atomic
    def upsert_purchase_bill(self, bill_data: dict, line_items_data: List[dict] = None) -> PurchaseBill:
        """
        Create or update purchase bill with line items

        Args:
            bill_data: Dict of PurchaseBill model fields
            line_items_data: List of line item dicts (optional)

        Returns:
            PurchaseBill instance (saved with line items)
        """
        external_id = bill_data.get('external_bill_id')

        if not external_id:
            raise ValueError("external_bill_id required for bill upsert")

        bill_data_clean = {k: v for k, v in bill_data.items() if k != 'line_items'}

        bill, created = PurchaseBill.objects.update_or_create(
            integration=self.integration,
            external_bill_id=external_id,
            defaults=bill_data_clean
        )

        if created:
            logger.info(f"Created bill: {bill.invoice_number} ({bill.prefix_id})")
        else:
            logger.info(f"Updated bill: {bill.invoice_number} ({bill.prefix_id})")

        # Handle line items if provided
        if line_items_data:
            bill.line_items.all().delete()

            for line_item_data in line_items_data:
                self._create_bill_line_item(bill, line_item_data)

        return bill

    def _create_bill_line_item(self, bill: PurchaseBill, line_item_data: dict) -> BillLineItem:
        """
        Create bill line item and link to chart account if possible

        Args:
            bill: Parent PurchaseBill
            line_item_data: Dict of BillLineItem fields

        Returns:
            BillLineItem instance (saved)
        """
        account_code = line_item_data.get('account_code')
        if account_code:
            chart_account = self.get_account_by_code(account_code)
            if chart_account:
                line_item_data['chart_account'] = chart_account

        line_item = BillLineItem.objects.create(
            bill=bill,
            **line_item_data
        )

        return line_item

    # Payment reconciliation operations

    def get_unreconciled_transactions(self):
        """
        Get bank transactions that haven't been matched to invoices

        Returns:
            QuerySet of Transaction instances
        """
        from financial_data.models import Transaction

        # Get transactions without invoice payments
        return Transaction.objects.filter(
            connection__account=self.account,
            is_reconciled=False,
            transaction_type='receive'  # Focus on incoming payments
        ).order_by('-date')

    def create_invoice_payment(self, payment_data: dict) -> InvoicePayment:
        """
        Create payment record linking transaction to invoice

        Args:
            payment_data: Dict of InvoicePayment fields

        Returns:
            InvoicePayment instance (saved)
        """
        payment = InvoicePayment.objects.create(**payment_data)

        logger.info(f"Created payment record: {payment.prefix_id} - {payment.payment_amount}")

        return payment

    # Query helpers

    def find_invoices_by_amount(self, amount: float, tolerance: float = 0.01) -> List[SalesInvoice]:
        """
        Find invoices matching an amount (within tolerance)

        Args:
            amount: Amount to search for
            tolerance: Allowed difference

        Returns:
            List of matching SalesInvoice instances
        """
        from decimal import Decimal

        amount_decimal = Decimal(str(amount))
        lower_bound = amount_decimal - Decimal(str(tolerance))
        upper_bound = amount_decimal + Decimal(str(tolerance))

        return list(
            SalesInvoice.objects
            .filter(integration=self.integration)
            .filter(amount_due__gte=lower_bound, amount_due__lte=upper_bound)
            .exclude(status__in=['PAID', 'VOIDED', 'DELETED'])
            .select_related('contact')
            .order_by('-invoice_date')
        )
