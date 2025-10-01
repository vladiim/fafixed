"""
XeroAccountingSyncService - Handles accounting data sync for Xero integrations

Separates accounting sync logic from main XeroIntegrationService
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


class XeroAccountingSyncService:
    """Handles accounting data synchronization for Xero"""

    def __init__(self, xero_service):
        """
        Initialize accounting sync service

        Args:
            xero_service: XeroIntegrationService instance for API access
        """
        self.xero_service = xero_service
        self.integration = xero_service.integration

    def sync_all(self, sync_type: str = 'incremental') -> Dict:
        """
        Sync all accounting data (contacts, chart of accounts, invoices, bills)

        Args:
            sync_type: 'full' or 'incremental'

        Returns:
            Dictionary with sync results
        """
        from financial_data.services.accounting_sync import AccountingSyncService

        try:
            sync_service = AccountingSyncService(self.integration)
            tenant_id = self.integration.external_account_id

            # Determine modified_since for incremental sync
            modified_since = None
            if sync_type == 'incremental' and self.integration.last_sync_at:
                modified_since = self.integration.last_sync_at.isoformat()

            result = {
                'status': 'success',
                'contacts': {'synced': 0, 'errors': 0},
                'accounts': {'synced': 0, 'errors': 0},
                'invoices': {'synced': 0, 'errors': 0},
                'bills': {'synced': 0, 'errors': 0},
                'total_synced': 0,
            }

            # Sync in dependency order
            self._sync_contacts(sync_service, tenant_id, modified_since, result)
            self._sync_chart_of_accounts(sync_service, tenant_id, result)
            self._sync_sales_invoices(sync_service, tenant_id, modified_since, result)
            self._sync_purchase_bills(sync_service, tenant_id, modified_since, result)

            # Run payment reconciliation after invoices are synced
            reconciliation_result = self._reconcile_payments(sync_service)
            result['reconciliation'] = reconciliation_result

            # Calculate totals
            result['total_synced'] = (
                result['contacts']['synced'] +
                result['accounts']['synced'] +
                result['invoices']['synced'] +
                result['bills']['synced']
            )

            total_errors = (
                result['contacts']['errors'] +
                result['accounts']['errors'] +
                result['invoices']['errors'] +
                result['bills']['errors']
            )

            if total_errors > 0:
                result['status'] = 'partial'

            logger.info(
                f"Accounting sync complete for integration {self.integration.id}: "
                f"{result['total_synced']} total synced, {total_errors} errors"
            )

            return result

        except Exception as e:
            logger.error(f"Accounting sync failed for integration {self.integration.id}: {str(e)}", exc_info=True)
            return {
                'status': 'failed',
                'error': str(e),
                'total_synced': 0,
            }

    def _sync_contacts(self, sync_service, tenant_id, modified_since, result):
        """Sync contacts (customers/suppliers)"""
        logger.info(f"Syncing contacts for integration {self.integration.id}...")
        try:
            raw_contacts = self.xero_service.fetch_contacts(tenant_id, modified_since=modified_since)
            for raw_contact in raw_contacts:
                if sync_service.process_contact(raw_contact):
                    result['contacts']['synced'] += 1
                else:
                    result['contacts']['errors'] += 1
            logger.info(f"Contacts: {result['contacts']['synced']} synced, {result['contacts']['errors']} errors")
        except Exception as e:
            logger.error(f"Contacts sync failed: {str(e)}")
            result['contacts']['errors'] += 1

    def _sync_chart_of_accounts(self, sync_service, tenant_id, result):
        """Sync chart of accounts"""
        logger.info(f"Syncing chart of accounts for integration {self.integration.id}...")
        try:
            raw_accounts = self.xero_service.fetch_chart_of_accounts(tenant_id)
            for raw_account in raw_accounts:
                if sync_service.process_chart_account(raw_account):
                    result['accounts']['synced'] += 1
                else:
                    result['accounts']['errors'] += 1
            logger.info(f"Accounts: {result['accounts']['synced']} synced, {result['accounts']['errors']} errors")
        except Exception as e:
            logger.error(f"Chart of accounts sync failed: {str(e)}")
            result['accounts']['errors'] += 1

    def _sync_sales_invoices(self, sync_service, tenant_id, modified_since, result):
        """Sync sales invoices"""
        logger.info(f"Syncing sales invoices for integration {self.integration.id}...")
        try:
            raw_invoices = self.xero_service.fetch_invoices(tenant_id, invoice_type='ACCREC', modified_since=modified_since)
            for raw_invoice in raw_invoices:
                if sync_service.process_sales_invoice(raw_invoice):
                    result['invoices']['synced'] += 1
                else:
                    result['invoices']['errors'] += 1
            logger.info(f"Invoices: {result['invoices']['synced']} synced, {result['invoices']['errors']} errors")
        except Exception as e:
            logger.error(f"Sales invoices sync failed: {str(e)}")
            result['invoices']['errors'] += 1

    def _sync_purchase_bills(self, sync_service, tenant_id, modified_since, result):
        """Sync purchase bills"""
        logger.info(f"Syncing purchase bills for integration {self.integration.id}...")
        try:
            raw_bills = self.xero_service.fetch_invoices(tenant_id, invoice_type='ACCPAY', modified_since=modified_since)
            for raw_bill in raw_bills:
                if sync_service.process_purchase_bill(raw_bill):
                    result['bills']['synced'] += 1
                else:
                    result['bills']['errors'] += 1
            logger.info(f"Bills: {result['bills']['synced']} synced, {result['bills']['errors']} errors")
        except Exception as e:
            logger.error(f"Purchase bills sync failed: {str(e)}")
            result['bills']['errors'] += 1

    def _reconcile_payments(self, sync_service) -> Dict:
        """
        Automatically reconcile bank transactions to invoices

        Returns:
            Dictionary with reconciliation results
        """
        from financial_data.services.payment_reconciler import PaymentReconciler
        from financial_data.models import Transaction

        logger.info(f"Running payment reconciliation for integration {self.integration.id}...")

        reconciliation_result = {
            'auto_matched': 0,
            'suggested': 0,
            'no_match': 0,
            'errors': 0,
        }

        try:
            # Get all unreconciled transactions for this integration's connection
            # Note: Transaction uses 'connection' FK, need to map from integration
            from connections.models import Connection

            try:
                connection = Connection.objects.get(
                    external_account_id=self.integration.external_account_id,
                    account=self.integration.account
                )
            except Connection.DoesNotExist:
                logger.warning(f"No connection found for integration {self.integration.id}, skipping reconciliation")
                return reconciliation_result

            unreconciled_transactions = Transaction.objects.filter(
                connection=connection,
                is_reconciled=False,
                transaction_type='receive'  # Only match incoming payments
            ).order_by('-date')[:100]  # Limit to last 100 for performance

            if not unreconciled_transactions:
                logger.info("No unreconciled transactions to process")
                return reconciliation_result

            # Initialize reconciler
            reconciler = PaymentReconciler(sync_service.repository)

            for transaction in unreconciled_transactions:
                try:
                    # Find matches for this transaction
                    matches = reconciler.find_invoice_matches(transaction)

                    if not matches:
                        reconciliation_result['no_match'] += 1
                        continue

                    best_match = matches[0]  # Highest confidence match

                    # Auto-reconcile if confidence is high enough
                    if reconciler.should_auto_reconcile(best_match.confidence):
                        reconciler.reconcile_transaction(
                            transaction,
                            best_match.invoice,
                            best_match.confidence
                        )
                        reconciliation_result['auto_matched'] += 1
                        logger.info(
                            f"Auto-matched transaction {transaction.prefix_id} to "
                            f"invoice {best_match.invoice.invoice_number} "
                            f"(confidence: {best_match.confidence:.2%})"
                        )
                    else:
                        # Low confidence - just log as suggestion
                        reconciliation_result['suggested'] += 1
                        logger.info(
                            f"Suggested match for transaction {transaction.prefix_id}: "
                            f"invoice {best_match.invoice.invoice_number} "
                            f"(confidence: {best_match.confidence:.2%})"
                        )

                except Exception as e:
                    logger.error(f"Error reconciling transaction {transaction.prefix_id}: {str(e)}")
                    reconciliation_result['errors'] += 1

            logger.info(
                f"Reconciliation complete: {reconciliation_result['auto_matched']} auto-matched, "
                f"{reconciliation_result['suggested']} suggested, "
                f"{reconciliation_result['no_match']} no match, "
                f"{reconciliation_result['errors']} errors"
            )

        except Exception as e:
            logger.error(f"Payment reconciliation failed: {str(e)}", exc_info=True)
            reconciliation_result['errors'] += 1

        return reconciliation_result
