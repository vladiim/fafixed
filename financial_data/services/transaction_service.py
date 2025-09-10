from typing import List, Dict, Any, Optional
from django.db.models import QuerySet
from django.utils import timezone
from ..models import Transaction, TransactionLineItem
import logging

logger = logging.getLogger(__name__)


class TransactionService:
    """Service for managing transaction business logic"""
    
    @staticmethod
    def get_transactions_for_connection(connection) -> QuerySet:
        """Get all transactions for a connection with optimized queries"""
        return Transaction.objects.filter(connection=connection).select_related(
            'connection', 'connection__account', 'connection__provider'
        ).prefetch_related('line_items')
    
    @staticmethod
    def get_unreconciled_transactions(connection) -> QuerySet:
        """Get unreconciled transactions for a connection"""
        return TransactionService.get_transactions_for_connection(connection).filter(
            is_reconciled=False
        )
    
    @staticmethod
    def get_recent_transactions(connection, days: int = 30) -> QuerySet:
        """Get recent transactions within specified days"""
        cutoff_date = timezone.now().date() - timezone.timedelta(days=days)
        return TransactionService.get_transactions_for_connection(connection).filter(
            date__gte=cutoff_date
        )
    
    @staticmethod
    def get_transactions_by_type(connection, transaction_type: str) -> QuerySet:
        """Get transactions by type (spend, receive, etc.)"""
        return TransactionService.get_transactions_for_connection(connection).filter(
            transaction_type=transaction_type
        )
    
    @staticmethod
    def calculate_totals(transactions: QuerySet) -> Dict[str, Any]:
        """Calculate totals for a set of transactions"""
        from django.db.models import Sum, Count
        from decimal import Decimal
        
        aggregates = transactions.aggregate(
            total_amount=Sum('amount'),
            total_count=Count('id'),
            spend_total=Sum('amount', filter=transactions.filter(transaction_type='spend').query),
            receive_total=Sum('amount', filter=transactions.filter(transaction_type='receive').query)
        )
        
        return {
            'total_amount': aggregates['total_amount'] or Decimal('0'),
            'total_count': aggregates['total_count'] or 0,
            'spend_total': aggregates['spend_total'] or Decimal('0'),
            'receive_total': aggregates['receive_total'] or Decimal('0'),
            'net_total': (aggregates['receive_total'] or Decimal('0')) - (aggregates['spend_total'] or Decimal('0'))
        }
    
    @staticmethod
    def mark_reconciled(transaction_ids: List[str], reconciled: bool = True) -> int:
        """Mark transactions as reconciled/unreconciled"""
        updated = Transaction.objects.filter(
            prefix_id__in=transaction_ids
        ).update(
            is_reconciled=reconciled
        )
        
        logger.info(f"Marked {updated} transactions as {'reconciled' if reconciled else 'unreconciled'}")
        return updated
    
    @staticmethod
    def update_transaction(transaction_prefix_id: str, data: Dict[str, Any]) -> Transaction:
        """Update a transaction with new data"""
        transaction = Transaction.objects.get(prefix_id=transaction_prefix_id)
        
        # Update allowed fields
        allowed_fields = ['reference', 'description', 'is_reconciled']
        for field, value in data.items():
            if field in allowed_fields:
                setattr(transaction, field, value)
        
        transaction.save()
        logger.info(f"Updated transaction {transaction_prefix_id}")
        return transaction
    
    @staticmethod
    def get_transaction_by_prefix_id(prefix_id: str) -> Transaction:
        """Get transaction by prefix ID with related data"""
        return Transaction.objects.select_related(
            'connection', 'connection__account', 'connection__provider'
        ).prefetch_related('line_items').get(prefix_id=prefix_id)
    
    @staticmethod
    def get_duplicate_candidates(connection, reference: str = None, amount: str = None, 
                               date: str = None) -> QuerySet:
        """Find potential duplicate transactions"""
        queryset = TransactionService.get_transactions_for_connection(connection)
        
        if reference:
            queryset = queryset.filter(reference__iexact=reference)
        if amount:
            queryset = queryset.filter(amount=amount)
        if date:
            queryset = queryset.filter(date=date)
            
        return queryset
    
    @staticmethod
    def get_transactions_needing_validation(connection) -> QuerySet:
        """Get transactions that need validation (new or updated)"""
        # This could be enhanced with a last_validated_at field
        return TransactionService.get_transactions_for_connection(connection).filter(
            status='authorised'  # Only validate authorised transactions
        )