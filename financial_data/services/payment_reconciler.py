"""
PaymentReconciler - Intelligent payment-to-invoice matching

Uses multiple matching strategies to link bank transactions to invoices
with confidence scoring for automatic vs manual reconciliation
"""

from typing import List, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal
from datetime import date, timedelta
import logging
import re

from financial_data.models import SalesInvoice, Transaction

logger = logging.getLogger(__name__)


@dataclass
class InvoiceMatch:
    """Represents a potential invoice match for a transaction"""
    invoice: SalesInvoice
    confidence: float  # 0.0 to 1.0
    match_reasons: List[str]

    def __repr__(self):
        return f"InvoiceMatch(invoice={self.invoice.invoice_number}, confidence={self.confidence:.2f})"


class PaymentReconciler:
    """
    Intelligent matching of bank transactions to invoices

    Matching strategies (in order of importance):
    1. Exact amount match (weight: 0.5)
    2. Invoice number in description (weight: 0.3)
    3. Customer name in description (weight: 0.2)
    4. Date proximity (weight: 0.2)
    """

    # Confidence thresholds
    AUTO_RECONCILE_THRESHOLD = 0.8  # Auto-reconcile if confidence >= 80%
    SUGGEST_THRESHOLD = 0.3  # Suggest matches if confidence >= 30%

    def __init__(self, repository):
        """
        Initialize reconciler

        Args:
            repository: AccountingRepository instance
        """
        self.repository = repository

    def find_invoice_matches(self, transaction: Transaction,
                           invoices: Optional[List[SalesInvoice]] = None) -> List[InvoiceMatch]:
        """
        Find potential invoice matches for a transaction

        Args:
            transaction: Bank transaction to match
            invoices: List of invoices to search (defaults to all open invoices)

        Returns:
            List of InvoiceMatch objects, sorted by confidence (highest first)
        """
        if invoices is None:
            invoices = self.repository.get_open_invoices()

        matches = []

        for invoice in invoices:
            confidence = self.calculate_match_confidence(transaction, invoice)

            if confidence >= self.SUGGEST_THRESHOLD:
                match_reasons = self._get_match_reasons(transaction, invoice, confidence)
                matches.append(InvoiceMatch(
                    invoice=invoice,
                    confidence=confidence,
                    match_reasons=match_reasons
                ))

        # Sort by confidence (highest first)
        matches.sort(key=lambda m: m.confidence, reverse=True)

        return matches

    def calculate_match_confidence(self, transaction: Transaction, invoice: SalesInvoice) -> float:
        """
        Calculate confidence score for payment-to-invoice match

        Args:
            transaction: Bank transaction
            invoice: Sales invoice

        Returns:
            Confidence score (0.0 to 1.0)
        """
        confidence = 0.0

        # 1. Amount matching (most important) - up to 0.5
        amount_score = self._score_amount_match(transaction.amount, invoice.amount_due)
        confidence += amount_score * 0.5

        # 2. Invoice number in description - up to 0.3
        if self._invoice_number_in_description(invoice.invoice_number, transaction.description):
            confidence += 0.3

        # 3. Customer name in description - up to 0.2
        if self._customer_name_in_description(invoice.contact.name, transaction.description):
            confidence += 0.2

        # 4. Date proximity - up to 0.2
        date_score = self._score_date_proximity(transaction.date, invoice.due_date)
        confidence += date_score * 0.2

        return min(confidence, 1.0)

    def _score_amount_match(self, transaction_amount: Decimal, invoice_amount: Decimal) -> float:
        """
        Score amount matching (0.0 to 1.0)

        Returns:
            1.0 for exact match
            0.8 for within 1% tolerance
            0.5 for within 5% tolerance
            0.0 for no match
        """
        if not invoice_amount or invoice_amount == 0:
            return 0.0

        # Exact match
        if abs(transaction_amount - invoice_amount) < Decimal('0.01'):
            return 1.0

        # Calculate percentage difference
        diff_pct = abs((transaction_amount - invoice_amount) / invoice_amount * 100)

        # Within 1% tolerance (very close)
        if diff_pct <= 1.0:
            return 0.8

        # Within 5% tolerance (reasonably close)
        if diff_pct <= 5.0:
            return 0.5

        # No match
        return 0.0

    def _invoice_number_in_description(self, invoice_number: str, description: Optional[str]) -> bool:
        """
        Check if invoice number appears in transaction description

        Args:
            invoice_number: Invoice number to find
            description: Transaction description

        Returns:
            True if invoice number found
        """
        if not description or not invoice_number:
            return False

        # Normalize: remove spaces, convert to uppercase
        invoice_normalized = re.sub(r'\s+', '', invoice_number.upper())
        description_normalized = re.sub(r'\s+', '', description.upper())

        # Check for exact match
        if invoice_normalized in description_normalized:
            return True

        # Check for partial match (e.g., "INV-001" might appear as "001" in description)
        # Extract numbers from invoice number
        invoice_digits = re.findall(r'\d+', invoice_number)
        if invoice_digits:
            for digit_group in invoice_digits:
                if digit_group in description:
                    return True

        return False

    def _customer_name_in_description(self, customer_name: str, description: Optional[str]) -> bool:
        """
        Check if customer name appears in transaction description

        Args:
            customer_name: Customer name to find
            description: Transaction description

        Returns:
            True if customer name (or significant part) found
        """
        if not description or not customer_name:
            return False

        # Normalize
        customer_lower = customer_name.lower()
        description_lower = description.lower()

        # Check for exact match
        if customer_lower in description_lower:
            return True

        # Check for partial match (first word of company name)
        customer_words = customer_lower.split()
        if customer_words:
            first_word = customer_words[0]
            # Only check if first word is meaningful (> 3 chars)
            if len(first_word) > 3 and first_word in description_lower:
                return True

        return False

    def _score_date_proximity(self, transaction_date: date, invoice_due_date: Optional[date]) -> float:
        """
        Score date proximity (0.0 to 1.0)

        Returns:
            1.0 for within 3 days of due date
            0.5 for within 7 days
            0.3 for within 30 days
            0.0 for beyond 30 days
        """
        if not invoice_due_date:
            return 0.0

        days_diff = abs((transaction_date - invoice_due_date).days)

        if days_diff <= 3:
            return 1.0
        elif days_diff <= 7:
            return 0.5
        elif days_diff <= 30:
            return 0.3
        else:
            return 0.0

    def _get_match_reasons(self, transaction: Transaction, invoice: SalesInvoice,
                          confidence: float) -> List[str]:
        """
        Generate human-readable match reasons

        Args:
            transaction: Bank transaction
            invoice: Sales invoice
            confidence: Calculated confidence score

        Returns:
            List of reason strings
        """
        reasons = []

        # Amount match
        amount_score = self._score_amount_match(transaction.amount, invoice.amount_due)
        if amount_score >= 1.0:
            reasons.append(f"Exact amount match: {transaction.amount}")
        elif amount_score >= 0.8:
            reasons.append(f"Very close amount: {transaction.amount} ≈ {invoice.amount_due}")
        elif amount_score >= 0.5:
            reasons.append(f"Similar amount: {transaction.amount} ≈ {invoice.amount_due}")

        # Invoice number
        if self._invoice_number_in_description(invoice.invoice_number, transaction.description):
            reasons.append(f"Invoice number '{invoice.invoice_number}' in description")

        # Customer name
        if self._customer_name_in_description(invoice.contact.name, transaction.description):
            reasons.append(f"Customer '{invoice.contact.name}' in description")

        # Date proximity
        if invoice.due_date:
            days_diff = abs((transaction.date - invoice.due_date).days)
            if days_diff <= 3:
                reasons.append(f"Payment within 3 days of due date")
            elif days_diff <= 7:
                reasons.append(f"Payment within 7 days of due date")
            elif days_diff <= 30:
                reasons.append(f"Payment within 30 days of due date")

        return reasons

    def should_auto_reconcile(self, confidence: float) -> bool:
        """
        Determine if match should be auto-reconciled

        Args:
            confidence: Match confidence score

        Returns:
            True if confidence is high enough for auto-reconciliation
        """
        return confidence >= self.AUTO_RECONCILE_THRESHOLD

    def reconcile_transaction(self, transaction: Transaction, invoice: SalesInvoice,
                             confidence: float, user=None) -> object:
        """
        Create payment record linking transaction to invoice

        Args:
            transaction: Bank transaction
            invoice: Sales invoice
            confidence: Match confidence score
            user: User performing reconciliation (None for auto)

        Returns:
            InvoicePayment instance
        """
        from django.utils import timezone

        payment_data = {
            'integration': invoice.integration,
            'account': invoice.account,
            'invoice': invoice,
            'transaction': transaction,
            'payment_amount': transaction.amount,
            'payment_date': transaction.date,
            'reconciliation_confidence': confidence,
            'status': 'MATCHED',
        }

        if user:
            payment_data['reconciled_by'] = user
            payment_data['reconciled_at'] = timezone.now()

        payment = self.repository.create_invoice_payment(payment_data)

        # Update transaction reconciliation status
        transaction.is_reconciled = True
        transaction.save(update_fields=['is_reconciled'])

        logger.info(
            f"Reconciled transaction {transaction.prefix_id} to invoice {invoice.invoice_number} "
            f"(confidence: {confidence:.2%}, {'auto' if not user else 'manual'})"
        )

        return payment
