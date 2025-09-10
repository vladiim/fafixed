from typing import Dict, Any, List, Optional
from django.utils import timezone
from django.db import transaction
from ..models import Transaction, TransactionLineItem
from connections.models import Connection
import logging

logger = logging.getLogger(__name__)


class ImportService:
    """Service for importing transaction data from external systems"""
    
    @staticmethod
    def import_transactions(connection: Connection, transaction_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Import transactions from external system data"""
        
        created_count = 0
        updated_count = 0
        error_count = 0
        errors = []
        
        with transaction.atomic():
            for data in transaction_data:
                try:
                    result = ImportService._process_single_transaction(connection, data)
                    if result['created']:
                        created_count += 1
                    else:
                        updated_count += 1
                        
                except Exception as e:
                    error_count += 1
                    error_msg = f"Error processing transaction {data.get('external_transaction_id', 'unknown')}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
        
        return {
            'created': created_count,
            'updated': updated_count,
            'errors': error_count,
            'error_details': errors,
            'total_processed': created_count + updated_count + error_count
        }
    
    @staticmethod
    def _process_single_transaction(connection: Connection, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single transaction record"""
        
        external_id = data.get('external_transaction_id')
        if not external_id:
            raise ValueError("Missing external_transaction_id")
        
        # Try to find existing transaction
        existing_transaction = Transaction.objects.filter(
            connection=connection,
            external_transaction_id=external_id
        ).first()
        
        # Prepare transaction data
        transaction_data = ImportService._prepare_transaction_data(connection, data)
        
        if existing_transaction:
            # Update existing transaction
            for field, value in transaction_data.items():
                if field != 'connection':  # Don't update the connection
                    setattr(existing_transaction, field, value)
            
            existing_transaction.last_synced_at = timezone.now()
            existing_transaction.save()
            
            # Update line items if provided
            if 'line_items' in data:
                ImportService._update_line_items(existing_transaction, data['line_items'])
            
            return {'transaction': existing_transaction, 'created': False}
        
        else:
            # Create new transaction
            new_transaction = Transaction.objects.create(**transaction_data)
            
            # Create line items if provided
            if 'line_items' in data:
                ImportService._create_line_items(new_transaction, data['line_items'])
            
            return {'transaction': new_transaction, 'created': True}
    
    @staticmethod
    def _prepare_transaction_data(connection: Connection, data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare transaction data for database storage"""
        
        # Map external data to our model fields
        transaction_data = {
            'connection': connection,
            'external_transaction_id': data['external_transaction_id'],
            'external_account_id': data.get('external_account_id', ''),
            'transaction_type': ImportService._map_transaction_type(data.get('type', 'other')),
            'date': data['date'],
            'reference': data.get('reference', ''),
            'description': data.get('description', ''),
            'amount': data['amount'],
            'currency_code': data.get('currency_code', 'USD'),
            'status': data.get('status', 'authorised'),
            'is_reconciled': data.get('is_reconciled', False),
            'contact_name': data.get('contact_name', ''),
            'contact_external_id': data.get('contact_external_id', ''),
            'external_url': data.get('external_url', ''),
            'raw_data': data.get('raw_data', {}),
            'last_synced_at': timezone.now()
        }
        
        return transaction_data
    
    @staticmethod
    def _map_transaction_type(external_type: str) -> str:
        """Map external transaction type to our internal types"""
        type_mapping = {
            'SPEND': 'spend',
            'RECEIVE': 'receive', 
            'BANK-TRANSFER': 'bank_transfer',
            'spend': 'spend',
            'receive': 'receive',
            'bank_transfer': 'bank_transfer'
        }
        
        return type_mapping.get(external_type.upper(), 'other')
    
    @staticmethod
    def _create_line_items(transaction: Transaction, line_items_data: List[Dict[str, Any]]):
        """Create line items for a transaction"""
        
        for item_data in line_items_data:
            TransactionLineItem.objects.create(
                transaction=transaction,
                description=item_data.get('description', ''),
                quantity=item_data.get('quantity', 1),
                unit_amount=item_data.get('unit_amount', 0),
                line_amount=item_data.get('line_amount', 0),
                tax_type=item_data.get('tax_type', ''),
                tax_amount=item_data.get('tax_amount', 0),
                account_code=item_data.get('account_code', ''),
                account_name=item_data.get('account_name', ''),
                external_line_item_id=item_data.get('external_line_item_id', ''),
                raw_data=item_data.get('raw_data', {})
            )
    
    @staticmethod
    def _update_line_items(transaction: Transaction, line_items_data: List[Dict[str, Any]]):
        """Update line items for a transaction (replace all)"""
        
        # Delete existing line items
        transaction.line_items.all().delete()
        
        # Create new line items
        ImportService._create_line_items(transaction, line_items_data)
    
    @staticmethod
    def validate_import_data(data: Dict[str, Any]) -> List[str]:
        """Validate transaction data before import"""
        
        errors = []
        
        # Required fields
        required_fields = ['external_transaction_id', 'date', 'amount']
        for field in required_fields:
            if field not in data or data[field] is None:
                errors.append(f"Missing required field: {field}")
        
        # Data type validation
        if 'amount' in data:
            try:
                float(data['amount'])
            except (ValueError, TypeError):
                errors.append("Invalid amount format")
        
        if 'date' in data:
            if not isinstance(data['date'], (str, timezone.datetime)):
                errors.append("Invalid date format")
        
        return errors