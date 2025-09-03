# Python Style Guide for fafixed
# Following PEP 8 with practical adjustments for Django web applications

"""
This module demonstrates the coding standards and style guide for the fafixed project.
We follow PEP 8 with some practical adjustments for Django development.
"""

from typing import Dict, List, Optional, Any
from django.http import HttpResponse


# =============================================================================
# IMPORTS - PEP 8 Standard Order
# =============================================================================

# 1. Standard library imports
import os
import json
from datetime import datetime

# 2. Related third-party imports
from django.db import models
from django.http import JsonResponse

# 3. Local application/library imports
from core.models import UserProfile
from shared.utils import format_currency


# =============================================================================
# FUNCTIONS - Single-line returns for guard clauses
# =============================================================================

def process_transaction_data(data: Dict[str, Any]) -> Optional[Dict]:
    """
    Process transaction data with validation.
    
    Uses single-line returns for guard clauses (PEP 8 acceptable).
    """
    # Guard clauses - single line returns
    if not data: return None
    if not isinstance(data, dict): return None
    if 'amount' not in data: return None
    
    # Main logic - multi-line for complex operations
    processed_data = {
        'amount': float(data['amount']),
        'currency': data.get('currency', 'AUD'),
        'processed_at': datetime.now()
    }
    
    return processed_data


def validate_user_permissions(user: UserProfile, action: str) -> bool:
    """Validate user can perform action"""
    # Simple guard clauses
    if not user: return False
    if not user.is_active: return False
    if action == 'edit_transactions' and not user.can_edit_transactions(): return False
    
    return True


def format_display_name(first_name: str, last_name: str) -> str:
    """Format user display name"""
    if not first_name and not last_name: return "Unknown User"
    if not first_name: return last_name
    if not last_name: return first_name
    
    return f"{first_name} {last_name}"


# =============================================================================
# CLASSES - PEP 8 Standards
# =============================================================================

class TransactionProcessor:
    """
    Processes financial transactions.
    
    Class names: CapWords (PascalCase)
    Method names: snake_case
    Constants: UPPER_SNAKE_CASE
    """
    
    DEFAULT_CURRENCY = 'AUD'
    MAX_RETRY_ATTEMPTS = 3
    
    def __init__(self, user_profile: UserProfile):
        self.user_profile = user_profile
        self.processed_count = 0
    
    def process_batch(self, transactions: List[Dict]) -> Dict[str, Any]:
        """Process a batch of transactions"""
        # Guard clause
        if not transactions: return {'processed': 0, 'errors': []}
        
        results = {
            'processed': 0,
            'errors': [],
            'total': len(transactions)
        }
        
        for transaction in transactions:
            try:
                self._process_single_transaction(transaction)
                results['processed'] += 1
            except ValueError as e:
                results['errors'].append(str(e))
        
        return results
    
    def _process_single_transaction(self, transaction: Dict) -> None:
        """Process individual transaction (private method)"""
        # Validation with guard clauses
        if not transaction.get('amount'): raise ValueError("Amount required")
        if not transaction.get('account_id'): raise ValueError("Account ID required")
        
        # Main processing logic here
        self.processed_count += 1


# =============================================================================
# DJANGO-SPECIFIC PATTERNS
# =============================================================================

def transaction_list_view(request):
    """
    Django view following our style guide.
    
    - Single-line guard clauses for early returns
    - Clear variable names
    - Type hints where helpful
    """
    # Permission guard clauses
    if not request.user.is_authenticated: return redirect('login')
    if not request.user.profile.is_admin(): return HttpResponse(status=403)
    
    # Get query parameters
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all')
    
    # Build queryset
    transactions = Transaction.objects.select_related('account')
    
    if search_query:
        transactions = transactions.filter(description__icontains=search_query)
    
    if status_filter != 'all':
        transactions = transactions.filter(status=status_filter)
    
    context = {
        'transactions': transactions[:100],  # Limit for performance
        'search_query': search_query,
        'status_filter': status_filter,
    }
    
    return render(request, 'transactions/list.html', context)


# =============================================================================
# STRING FORMATTING - Modern Python
# =============================================================================

def format_transaction_summary(transaction_count: int, total_amount: float) -> str:
    """Format transaction summary using f-strings (preferred in modern Python)"""
    if transaction_count == 0: return "No transactions"
    if transaction_count == 1: return f"1 transaction: {format_currency(total_amount)}"
    
    return f"{transaction_count:,} transactions: {format_currency(total_amount)}"


# =============================================================================
# ERROR HANDLING - Explicit and Clear
# =============================================================================

def safe_json_parse(data: str) -> Optional[Dict]:
    """Safely parse JSON with explicit error handling"""
    if not data: return None
    
    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError):
        # Log error in production, but don't raise
        return None


# =============================================================================
# DOCSTRINGS - Google Style (Django community preference)
# =============================================================================

def calculate_reconciliation_difference(bank_amount: float, xero_amount: float) -> Dict[str, Any]:
    """
    Calculate difference between bank and Xero amounts.
    
    Args:
        bank_amount: Amount from bank statement
        xero_amount: Amount from Xero transaction
        
    Returns:
        Dict containing:
            - difference: Absolute difference between amounts
            - percentage: Percentage difference 
            - is_match: Whether amounts match within tolerance
            
    Raises:
        ValueError: If amounts are not valid numbers
    """
    if bank_amount is None or xero_amount is None:
        raise ValueError("Both amounts must be provided")
    
    difference = abs(bank_amount - xero_amount)
    percentage = (difference / abs(xero_amount)) * 100 if xero_amount != 0 else 100.0
    is_match = difference < 0.01  # 1 cent tolerance
    
    return {
        'difference': difference,
        'percentage': percentage,
        'is_match': is_match
    }


# =============================================================================
# SUMMARY OF STYLE CHOICES
# =============================================================================

"""
Key Style Decisions for fafixed:

1. PEP 8 compliant with practical adjustments
2. Single-line returns for simple guard clauses
3. Multi-line for complex logic and conditions
4. f-strings for string formatting (modern Python)
5. Type hints for function parameters and returns
6. Google-style docstrings (common in Django)
7. Explicit error handling, avoid bare except
8. Clear, descriptive variable names
9. Constants in UPPER_SNAKE_CASE
10. Private methods with leading underscore

Tools to enforce:
- black (code formatting)
- isort (import sorting)  
- flake8 (linting)
- mypy (type checking)
"""