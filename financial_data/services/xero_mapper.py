"""
XeroAccountingMapper - Transforms Xero API responses to internal accounting models

This mapper handles the conversion of Xero-specific data structures into our
standardized accounting models, following the Strategy pattern for provider-specific logic.
"""

from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime, date
from django.utils import timezone
import logging

from financial_data.models import (
    Contact,
    ChartOfAccountsEntry,
    SalesInvoice,
    InvoiceLineItem,
    PurchaseBill,
    BillLineItem,
)

logger = logging.getLogger(__name__)


class XeroAccountingMapper:
    """Xero-specific implementation for transforming API data to internal models"""

    def __init__(self, integration):
        """
        Initialize mapper with integration context

        Args:
            integration: Integration instance (connections.Integration)
        """
        self.integration = integration
        self.account = integration.account

    def map_contact(self, raw_contact: Dict) -> Dict:
        """
        Map Xero contact to internal Contact model data

        Args:
            raw_contact: Xero contact API response dict

        Returns:
            Dict of Contact model field values (not saved to DB)
        """
        contact_data = {
            'integration': self.integration,
            'account': self.account,
            'name': raw_contact.get('Name', ''),
            'email': raw_contact.get('EmailAddress', ''),
            'external_contact_id': raw_contact.get('ContactID', ''),
            'external_data': raw_contact,
        }

        # Determine contact type
        is_supplier = raw_contact.get('IsSupplier', False)
        is_customer = raw_contact.get('IsCustomer', False)

        if is_supplier and is_customer:
            contact_data['contact_type'] = 'BOTH'
        elif is_supplier:
            contact_data['contact_type'] = 'SUPPLIER'
        elif is_customer:
            contact_data['contact_type'] = 'CUSTOMER'
        else:
            contact_data['contact_type'] = 'CUSTOMER'  # Default

        # Map address information (use first address)
        addresses = raw_contact.get('Addresses', [])
        if addresses:
            address = addresses[0]
            contact_data.update({
                'address_line_1': address.get('AddressLine1', ''),
                'address_line_2': address.get('AddressLine2', ''),
                'city': address.get('City', ''),
                'state': address.get('Region', ''),
                'postal_code': address.get('PostalCode', ''),
                'country': address.get('Country', ''),
            })

        # Map phone numbers (use first phone)
        phones = raw_contact.get('Phones', [])
        if phones:
            phone = phones[0]
            contact_data['phone'] = phone.get('PhoneNumber', '')

        # Map tax information
        contact_data['tax_number'] = raw_contact.get('TaxNumber', '')

        # Map payment terms
        payment_terms = raw_contact.get('PaymentTerms', {})
        if payment_terms:
            if 'Bills' in payment_terms:
                contact_data['default_payment_terms'] = f"NET {payment_terms['Bills'].get('Day', '')}"
            elif 'Sales' in payment_terms:
                contact_data['default_payment_terms'] = f"NET {payment_terms['Sales'].get('Day', '')}"

        return contact_data

    def map_chart_of_accounts_entry(self, raw_account: Dict) -> Dict:
        """
        Map Xero account to internal ChartOfAccountsEntry model data

        Args:
            raw_account: Xero account API response dict

        Returns:
            Dict of ChartOfAccountsEntry model field values
        """
        # Map Xero account types to our standard types
        type_mapping = {
            'BANK': 'ASSET',
            'CURRENT': 'ASSET',
            'CURRLIAB': 'LIABILITY',
            'DEPRECIATN': 'ASSET',
            'DIRECTCOSTS': 'COST_OF_SALES',
            'EQUITY': 'EQUITY',
            'EXPENSE': 'EXPENSE',
            'FIXED': 'ASSET',
            'INVENTORY': 'ASSET',
            'LIABILITY': 'LIABILITY',
            'NONCURRENT': 'ASSET',
            'OTHERINCOME': 'REVENUE',
            'OVERHEADS': 'EXPENSE',
            'PREPAYMENT': 'ASSET',
            'REVENUE': 'REVENUE',
            'SALES': 'REVENUE',
            'TERMLIAB': 'LIABILITY',
        }

        xero_type = raw_account.get('Type', 'EXPENSE')
        account_type = type_mapping.get(xero_type, 'EXPENSE')

        account_data = {
            'integration': self.integration,
            'account': self.account,
            'code': raw_account.get('Code', ''),
            'name': raw_account.get('Name', ''),
            'account_type': account_type,
            'external_account_id': raw_account.get('AccountID', ''),
            'external_data': raw_account,
            'is_active': raw_account.get('Status') == 'ACTIVE',
            'is_system_account': raw_account.get('SystemAccount', False),
        }

        # Map to business category based on account type and code
        account_data['category'] = self._determine_account_category(
            account_type,
            raw_account.get('Code', ''),
            raw_account.get('Name', '')
        )

        # Map tax information
        if 'TaxType' in raw_account:
            account_data['default_tax_code'] = raw_account['TaxType']

        return account_data

    def map_sales_invoice(self, raw_invoice: Dict) -> Dict:
        """
        Map Xero sales invoice to internal SalesInvoice model data

        Args:
            raw_invoice: Xero invoice API response dict

        Returns:
            Dict of SalesInvoice model field values

        Note: Does not create Contact - assumes contact exists or will be created separately
        """
        invoice_data = {
            'integration': self.integration,
            'account': self.account,
            'invoice_type': raw_invoice.get('Type', 'ACCREC'),
            'invoice_number': raw_invoice.get('InvoiceNumber', ''),
            'reference': raw_invoice.get('Reference', ''),
            'external_invoice_id': raw_invoice.get('InvoiceID', ''),
            'external_data': raw_invoice,
        }

        # Map dates
        if 'Date' in raw_invoice:
            invoice_data['invoice_date'] = self._parse_date(raw_invoice['Date'])
        if 'DueDate' in raw_invoice:
            invoice_data['due_date'] = self._parse_date(raw_invoice['DueDate'])
        if 'ExpectedPaymentDate' in raw_invoice:
            invoice_data['expected_payment_date'] = self._parse_date(raw_invoice['ExpectedPaymentDate'])
        if 'FullyPaidOnDate' in raw_invoice:
            invoice_data['fully_paid_on_date'] = self._parse_date(raw_invoice['FullyPaidOnDate'])

        # Map financial details
        invoice_data.update({
            'currency_code': raw_invoice.get('CurrencyCode', 'AUD'),
            'currency_rate': Decimal(str(raw_invoice.get('CurrencyRate', 1.0))),
            'subtotal': Decimal(str(raw_invoice.get('SubTotal', 0))),
            'total_tax': Decimal(str(raw_invoice.get('TotalTax', 0))),
            'total_discount': Decimal(str(raw_invoice.get('TotalDiscount', 0))),
            'total_amount': Decimal(str(raw_invoice.get('Total', 0))),
            'amount_paid': Decimal(str(raw_invoice.get('AmountPaid', 0))),
            'amount_due': Decimal(str(raw_invoice.get('AmountDue', 0))),
            'amount_credited': Decimal(str(raw_invoice.get('AmountCredited', 0))),
        })

        # Map status
        status_mapping = {
            'DRAFT': 'DRAFT',
            'SUBMITTED': 'SUBMITTED',
            'AUTHORISED': 'SENT',
            'PAID': 'PAID',
            'VOIDED': 'VOIDED',
            'DELETED': 'DELETED',
        }
        invoice_data['status'] = status_mapping.get(raw_invoice.get('Status'), 'DRAFT')

        # Additional fields
        invoice_data.update({
            'line_amount_types': raw_invoice.get('LineAmountTypes', 'Exclusive'),
            'has_attachments': raw_invoice.get('HasAttachments', False),
            'has_errors': raw_invoice.get('HasErrors', False),
            'url': raw_invoice.get('Url', ''),
            'branding_theme_id': raw_invoice.get('BrandingThemeID', ''),
        })

        return invoice_data

    def map_invoice_line_item(self, raw_line_item: Dict, line_number: int = 1) -> Dict:
        """
        Map Xero invoice line item to internal InvoiceLineItem model data

        Args:
            raw_line_item: Xero line item dict from invoice
            line_number: Position in invoice (1-indexed)

        Returns:
            Dict of InvoiceLineItem model field values
        """
        line_item_data = {
            'item_code': raw_line_item.get('ItemCode', ''),
            'description': raw_line_item.get('Description', ''),
            'account_code': raw_line_item.get('AccountCode', ''),
            'quantity': Decimal(str(raw_line_item.get('Quantity', 1))),
            'unit_amount': Decimal(str(raw_line_item.get('UnitAmount', 0))),
            'discount_rate': Decimal(str(raw_line_item.get('DiscountRate', 0))) / Decimal('100'),  # Convert percentage to decimal
            'discount_amount': Decimal(str(raw_line_item.get('DiscountAmount', 0))),
            'line_amount': Decimal(str(raw_line_item.get('LineAmount', 0))),
            'tax_type': raw_line_item.get('TaxType', ''),
            'tax_amount': Decimal(str(raw_line_item.get('TaxAmount', 0))),
            'external_line_item_id': raw_line_item.get('LineItemID', ''),
            'external_data': raw_line_item,
            'line_number': line_number,
        }

        # Map tracking categories
        tracking = raw_line_item.get('Tracking', [])
        if len(tracking) >= 1:
            track1 = tracking[0]
            line_item_data.update({
                'tracking_category_1_id': track1.get('TrackingCategoryID', ''),
                'tracking_category_1_name': track1.get('Name', ''),
                'tracking_category_1_option': track1.get('Option', ''),
            })
        if len(tracking) >= 2:
            track2 = tracking[1]
            line_item_data.update({
                'tracking_category_2_id': track2.get('TrackingCategoryID', ''),
                'tracking_category_2_name': track2.get('Name', ''),
                'tracking_category_2_option': track2.get('Option', ''),
            })

        return line_item_data

    def map_purchase_bill(self, raw_bill: Dict) -> Dict:
        """
        Map Xero purchase bill to internal PurchaseBill model data

        Args:
            raw_bill: Xero bill API response dict (ACCPAY type invoice)

        Returns:
            Dict of PurchaseBill model field values
        """
        bill_data = {
            'integration': self.integration,
            'account': self.account,
            'bill_number': raw_bill.get('InvoiceNumber', ''),  # Xero uses same field
            'invoice_number': raw_bill.get('InvoiceNumber', ''),  # Supplier's invoice number
            'reference': raw_bill.get('Reference', ''),
            'external_bill_id': raw_bill.get('InvoiceID', ''),
            'external_data': raw_bill,
        }

        # Map dates
        if 'Date' in raw_bill:
            bill_data['invoice_date'] = self._parse_date(raw_bill['Date'])
        if 'DueDate' in raw_bill:
            bill_data['due_date'] = self._parse_date(raw_bill['DueDate'])
        if 'ExpectedPaymentDate' in raw_bill:
            bill_data['expected_payment_date'] = self._parse_date(raw_bill['ExpectedPaymentDate'])
        if 'FullyPaidOnDate' in raw_bill:
            bill_data['fully_paid_on_date'] = self._parse_date(raw_bill['FullyPaidOnDate'])

        # Map financial details
        bill_data.update({
            'currency_code': raw_bill.get('CurrencyCode', 'AUD'),
            'currency_rate': Decimal(str(raw_bill.get('CurrencyRate', 1.0))),
            'subtotal': Decimal(str(raw_bill.get('SubTotal', 0))),
            'total_tax': Decimal(str(raw_bill.get('TotalTax', 0))),
            'total_amount': Decimal(str(raw_bill.get('Total', 0))),
            'amount_paid': Decimal(str(raw_bill.get('AmountPaid', 0))),
            'amount_due': Decimal(str(raw_bill.get('AmountDue', 0))),
        })

        # Map status
        status_mapping = {
            'DRAFT': 'DRAFT',
            'SUBMITTED': 'SUBMITTED',
            'AUTHORISED': 'AUTHORISED',
            'PAID': 'PAID',
            'VOIDED': 'VOIDED',
            'DELETED': 'DELETED',
        }
        bill_data['status'] = status_mapping.get(raw_bill.get('Status'), 'DRAFT')

        # Additional fields
        bill_data['has_attachments'] = raw_bill.get('HasAttachments', False)

        return bill_data

    def map_bill_line_item(self, raw_line_item: Dict, line_number: int = 1) -> Dict:
        """
        Map Xero bill line item to internal BillLineItem model data

        Args:
            raw_line_item: Xero line item dict from bill
            line_number: Position in bill (1-indexed)

        Returns:
            Dict of BillLineItem model field values
        """
        # Bills use same line item structure as invoices
        line_item_data = {
            'item_code': raw_line_item.get('ItemCode', ''),
            'description': raw_line_item.get('Description', ''),
            'account_code': raw_line_item.get('AccountCode', ''),
            'quantity': Decimal(str(raw_line_item.get('Quantity', 1))),
            'unit_amount': Decimal(str(raw_line_item.get('UnitAmount', 0))),
            'discount_rate': Decimal(str(raw_line_item.get('DiscountRate', 0))) / Decimal('100'),
            'discount_amount': Decimal(str(raw_line_item.get('DiscountAmount', 0))),
            'line_amount': Decimal(str(raw_line_item.get('LineAmount', 0))),
            'tax_type': raw_line_item.get('TaxType', ''),
            'tax_amount': Decimal(str(raw_line_item.get('TaxAmount', 0))),
            'external_line_item_id': raw_line_item.get('LineItemID', ''),
            'external_data': raw_line_item,
            'line_number': line_number,
        }

        # Map tracking categories
        tracking = raw_line_item.get('Tracking', [])
        if len(tracking) >= 1:
            track1 = tracking[0]
            line_item_data.update({
                'tracking_category_1_id': track1.get('TrackingCategoryID', ''),
                'tracking_category_1_name': track1.get('Name', ''),
                'tracking_category_1_option': track1.get('Option', ''),
            })
        if len(tracking) >= 2:
            track2 = tracking[1]
            line_item_data.update({
                'tracking_category_2_id': track2.get('TrackingCategoryID', ''),
                'tracking_category_2_name': track2.get('Name', ''),
                'tracking_category_2_option': track2.get('Option', ''),
            })

        return line_item_data

    # Helper methods

    def _determine_account_category(self, account_type: str, code: str, name: str) -> str:
        """
        Determine business category based on account details

        Args:
            account_type: Our standardized account type
            code: Account code (e.g., "200")
            name: Account name

        Returns:
            Business category string
        """
        code_int = int(code) if code.isdigit() else 0

        if account_type == 'REVENUE':
            # Primary sales accounts: 200-249
            if 200 <= code_int <= 249:
                return 'SALES'
            # Other income: 250-299
            else:
                return 'OTHER_INCOME'
        elif account_type == 'EXPENSE':
            if 300 <= code_int <= 399:
                return 'COST_OF_SALES'
            elif 'office' in name.lower():
                return 'OFFICE_EXPENSES'
            elif 'salary' in name.lower() or 'payroll' in name.lower():
                return 'PAYROLL'
            else:
                return ''  # No specific category
        elif account_type == 'LIABILITY':
            if 'gst' in name.lower():
                return 'GST_COLLECTED'
        elif account_type == 'ASSET':
            if 'gst' in name.lower():
                return 'GST_PAID'

        return ''  # Default: no category

    def _parse_date(self, date_str: str) -> Optional[date]:
        """
        Parse Xero date string to Python date

        Args:
            date_str: Date string from Xero API (ISO format or /Date()/ format)

        Returns:
            date object or None
        """
        if not date_str:
            return None

        try:
            # Handle ISO format: "2024-01-15T00:00:00"
            if 'T' in date_str:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()

            # Handle /Date(timestamp)/ format
            if date_str.startswith('/Date('):
                timestamp = int(date_str[6:-2]) / 1000  # Convert ms to seconds
                return datetime.fromtimestamp(timestamp).date()

            # Handle simple date format
            return datetime.strptime(date_str, '%Y-%m-%d').date()

        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse date '{date_str}': {e}")
            return None
