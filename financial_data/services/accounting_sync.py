"""
AccountingSyncService - Orchestrates complete accounting data synchronization

Coordinates XeroAccountingMapper, AccountingRepository, and Xero API
to perform end-to-end sync of accounting data with proper error handling
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from django.utils import timezone
import logging

from financial_data.services.xero_mapper import XeroAccountingMapper
from financial_data.services.accounting_repository import AccountingRepository

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of a sync operation"""
    success: bool = True
    synced_count: int = 0
    created_count: int = 0
    updated_count: int = 0
    error_count: int = 0
    errors: List[str] = field(default_factory=list)

    def add_created(self):
        self.synced_count += 1
        self.created_count += 1

    def add_updated(self):
        self.synced_count += 1
        self.updated_count += 1

    def add_error(self, error: str):
        self.error_count += 1
        self.errors.append(error)
        if self.error_count > 10:  # Prevent memory issues
            self.success = False

    def merge(self, other: 'SyncResult'):
        """Merge another result into this one"""
        self.synced_count += other.synced_count
        self.created_count += other.created_count
        self.updated_count += other.updated_count
        self.error_count += other.error_count
        self.errors.extend(other.errors)
        if not other.success:
            self.success = False


class AccountingSyncService:
    """
    Orchestrates synchronization of accounting data from Xero

    This service coordinates:
    1. Fetching data from Xero API (via XeroIntegrationService)
    2. Transforming data (via XeroAccountingMapper)
    3. Persisting data (via AccountingRepository)
    """

    def __init__(self, integration):
        """
        Initialize sync service

        Args:
            integration: Integration instance
        """
        self.integration = integration
        self.account = integration.account
        self.mapper = XeroAccountingMapper(integration)
        self.repository = AccountingRepository(integration)

    def sync_all_accounting_data(self, sync_type: str = 'incremental') -> SyncResult:
        """
        Complete accounting data sync in proper order

        Order is critical:
        1. Contacts (needed for invoices/bills)
        2. Chart of Accounts (needed for line items)
        3. Sales Invoices (with line items)
        4. Purchase Bills (with line items)

        Args:
            sync_type: 'full' or 'incremental'

        Returns:
            SyncResult with combined results
        """
        result = SyncResult()

        logger.info(f"Starting {sync_type} accounting sync for {self.integration.organization_name}")

        try:
            # 1. Sync contacts first (customers and suppliers)
            logger.info("Syncing contacts...")
            contact_result = self.sync_contacts(sync_type)
            result.merge(contact_result)
            logger.info(f"Contacts: {contact_result.synced_count} synced ({contact_result.created_count} created, {contact_result.updated_count} updated)")

            # 2. Sync chart of accounts
            logger.info("Syncing chart of accounts...")
            coa_result = self.sync_chart_of_accounts()
            result.merge(coa_result)
            logger.info(f"Chart of Accounts: {coa_result.synced_count} synced ({coa_result.created_count} created, {coa_result.updated_count} updated)")

            # 3. Sync sales invoices with line items
            logger.info("Syncing sales invoices...")
            invoice_result = self.sync_sales_invoices(sync_type)
            result.merge(invoice_result)
            logger.info(f"Sales Invoices: {invoice_result.synced_count} synced ({invoice_result.created_count} created, {invoice_result.updated_count} updated)")

            # 4. Sync purchase bills with line items
            logger.info("Syncing purchase bills...")
            bill_result = self.sync_purchase_bills(sync_type)
            result.merge(bill_result)
            logger.info(f"Purchase Bills: {bill_result.synced_count} synced ({bill_result.created_count} created, {bill_result.updated_count} updated)")

            logger.info(f"Accounting sync complete. Total: {result.synced_count} items synced, {result.error_count} errors")

            return result

        except Exception as e:
            logger.error(f"Accounting sync failed: {str(e)}", exc_info=True)
            result.add_error(f"Sync failed: {str(e)}")
            result.success = False
            return result

    def sync_contacts(self, sync_type: str = 'incremental') -> SyncResult:
        """
        Sync contacts (customers and suppliers)

        Args:
            sync_type: 'full' or 'incremental'

        Returns:
            SyncResult
        """
        result = SyncResult()

        try:
            # Note: This method will be called by XeroIntegrationService
            # which will provide the raw contact data from Xero API
            # For now, this is a placeholder that shows the pattern

            # This will be filled in when we extend XeroIntegrationService
            logger.info(f"Contact sync ({sync_type}) ready - awaiting Xero API integration")

            return result

        except Exception as e:
            logger.error(f"Contact sync failed: {str(e)}", exc_info=True)
            result.add_error(f"Contact sync failed: {str(e)}")
            return result

    def process_contact(self, raw_contact: Dict) -> Optional[object]:
        """
        Process single contact from Xero API response

        Args:
            raw_contact: Xero contact dict from API

        Returns:
            Contact instance or None if error
        """
        try:
            # Transform Xero data to our model format
            contact_data = self.mapper.map_contact(raw_contact)

            # Upsert to database
            contact = self.repository.upsert_contact(contact_data)

            return contact

        except Exception as e:
            contact_id = raw_contact.get('ContactID', 'unknown')
            logger.error(f"Failed to process contact {contact_id}: {str(e)}")
            return None

    def sync_chart_of_accounts(self) -> SyncResult:
        """
        Sync complete chart of accounts

        Chart of accounts is always a full sync (not incremental)

        Returns:
            SyncResult
        """
        result = SyncResult()

        try:
            # This will be filled in when we extend XeroIntegrationService
            logger.info("Chart of accounts sync ready - awaiting Xero API integration")

            return result

        except Exception as e:
            logger.error(f"Chart of accounts sync failed: {str(e)}", exc_info=True)
            result.add_error(f"Chart of accounts sync failed: {str(e)}")
            return result

    def process_chart_account(self, raw_account: Dict) -> Optional[object]:
        """
        Process single chart of accounts entry

        Args:
            raw_account: Xero account dict from API

        Returns:
            ChartOfAccountsEntry instance or None if error
        """
        try:
            # Transform
            account_data = self.mapper.map_chart_of_accounts_entry(raw_account)

            # Upsert
            account_entry = self.repository.upsert_account_entry(account_data)

            return account_entry

        except Exception as e:
            account_code = raw_account.get('Code', 'unknown')
            logger.error(f"Failed to process account {account_code}: {str(e)}")
            return None

    def sync_sales_invoices(self, sync_type: str = 'incremental') -> SyncResult:
        """
        Sync sales invoices with line items

        Args:
            sync_type: 'full' or 'incremental'

        Returns:
            SyncResult
        """
        result = SyncResult()

        try:
            # This will be filled in when we extend XeroIntegrationService
            logger.info(f"Sales invoice sync ({sync_type}) ready - awaiting Xero API integration")

            return result

        except Exception as e:
            logger.error(f"Sales invoice sync failed: {str(e)}", exc_info=True)
            result.add_error(f"Sales invoice sync failed: {str(e)}")
            return result

    def process_sales_invoice(self, raw_invoice: Dict) -> Optional[object]:
        """
        Process single sales invoice with line items

        Args:
            raw_invoice: Xero invoice dict from API

        Returns:
            SalesInvoice instance or None if error
        """
        try:
            # 1. Ensure contact exists
            contact_id = raw_invoice.get('Contact', {}).get('ContactID')
            if contact_id:
                contact = self.repository.get_contact_by_external_id(contact_id)
                if not contact:
                    # Contact doesn't exist yet - process it first
                    raw_contact = raw_invoice.get('Contact', {})
                    if raw_contact:
                        contact = self.process_contact(raw_contact)
                        if not contact:
                            raise ValueError(f"Failed to create contact {contact_id}")
            else:
                raise ValueError("Invoice missing contact information")

            # 2. Transform invoice
            invoice_data = self.mapper.map_sales_invoice(raw_invoice)
            invoice_data['contact'] = contact

            # 3. Transform line items
            line_items_data = []
            raw_line_items = raw_invoice.get('LineItems', [])
            for idx, raw_line_item in enumerate(raw_line_items, 1):
                line_item_data = self.mapper.map_invoice_line_item(raw_line_item, line_number=idx)
                line_items_data.append(line_item_data)

            # 4. Upsert invoice with line items (atomic)
            invoice = self.repository.upsert_sales_invoice(invoice_data, line_items_data)

            return invoice

        except Exception as e:
            invoice_number = raw_invoice.get('InvoiceNumber', 'unknown')
            logger.error(f"Failed to process invoice {invoice_number}: {str(e)}")
            return None

    def sync_purchase_bills(self, sync_type: str = 'incremental') -> SyncResult:
        """
        Sync purchase bills with line items

        Args:
            sync_type: 'full' or 'incremental'

        Returns:
            SyncResult
        """
        result = SyncResult()

        try:
            # This will be filled in when we extend XeroIntegrationService
            logger.info(f"Purchase bill sync ({sync_type}) ready - awaiting Xero API integration")

            return result

        except Exception as e:
            logger.error(f"Purchase bill sync failed: {str(e)}", exc_info=True)
            result.add_error(f"Purchase bill sync failed: {str(e)}")
            return result

    def process_purchase_bill(self, raw_bill: Dict) -> Optional[object]:
        """
        Process single purchase bill with line items

        Args:
            raw_bill: Xero bill dict from API (ACCPAY invoice)

        Returns:
            PurchaseBill instance or None if error
        """
        try:
            # 1. Ensure supplier contact exists
            contact_id = raw_bill.get('Contact', {}).get('ContactID')
            if contact_id:
                contact = self.repository.get_contact_by_external_id(contact_id)
                if not contact:
                    raw_contact = raw_bill.get('Contact', {})
                    if raw_contact:
                        contact = self.process_contact(raw_contact)
                        if not contact:
                            raise ValueError(f"Failed to create supplier contact {contact_id}")
            else:
                raise ValueError("Bill missing contact information")

            # 2. Transform bill
            bill_data = self.mapper.map_purchase_bill(raw_bill)
            bill_data['contact'] = contact

            # 3. Transform line items
            line_items_data = []
            raw_line_items = raw_bill.get('LineItems', [])
            for idx, raw_line_item in enumerate(raw_line_items, 1):
                line_item_data = self.mapper.map_bill_line_item(raw_line_item, line_number=idx)
                line_items_data.append(line_item_data)

            # 4. Upsert bill with line items (atomic)
            bill = self.repository.upsert_purchase_bill(bill_data, line_items_data)

            return bill

        except Exception as e:
            bill_number = raw_bill.get('InvoiceNumber', 'unknown')
            logger.error(f"Failed to process bill {bill_number}: {str(e)}")
            return None

    def _get_last_sync_date(self, entity_type: str) -> datetime:
        """
        Get last sync date for incremental syncs

        Args:
            entity_type: Type of entity (contacts, invoices, etc.)

        Returns:
            datetime of last sync, or 30 days ago if never synced
        """
        # For now, default to 30 days ago for incremental syncs
        # Later, we can track this in IntegrationSync model
        return timezone.now() - timedelta(days=30)
