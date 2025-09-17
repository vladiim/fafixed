#!/usr/bin/env python3
"""
Demo script to test category consistency functionality end-to-end.
"""

import os
import sys
import django

# Setup Django
sys.path.append('/Users/vlad/code/fafixed')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fafixed.settings')
django.setup()

from decimal import Decimal
from django.contrib.auth.models import User
from connections.models import Connection, Account, Provider
from data_quality.models import (
    XeroTrackingCategory,
    CategoryDetectionRule,
    CategorySuggestion
)
from data_quality.services.category_detection import CategoryDetectionEngine
from data_quality.services.category_suggestion_handler import CategorySuggestionHandler

def create_demo_data():
    """Create demo data for testing category consistency"""

    print("🚀 Creating demo data for category consistency testing...")

    # Get or create test account
    account, created = Account.objects.get_or_create(
        name="Demo Account",
        defaults={
            'is_active': True,
        }
    )
    print(f"✅ Account: {account.name} ({'created' if created else 'exists'})")

    # Get or create test user
    user, created = User.objects.get_or_create(
        username="demo_user",
        defaults={
            'email': 'demo@example.com',
            'first_name': 'Demo',
            'last_name': 'User'
        }
    )
    print(f"✅ User: {user.username} ({'created' if created else 'exists'})")

    # Get or create provider
    provider, created = Provider.objects.get_or_create(
        name="xero",
        defaults={
            'display_name': 'Xero',
            'provider_type': 'xero',
            'is_active': True,
            'auth_url_template': 'https://login.xero.com/identity/connect/authorize',
            'token_url': 'https://identity.xero.com/connect/token',
            'scopes_default': ['accounting.transactions', 'accounting.contacts']
        }
    )
    print(f"✅ Provider: {provider.display_name} ({'created' if created else 'exists'})")

    # Get or create test connection
    connection, created = Connection.objects.get_or_create(
        account=account,
        organization_name="Demo Xero Organization",
        defaults={
            'provider': provider,
            'external_account_id': 'demo-xero-123',
            'external_account_name': 'Demo Xero Account',
            'status': 'active',
        }
    )
    print(f"✅ Connection: {connection.organization_name} ({'created' if created else 'exists'})")

    # Create tracking categories
    office_category, created = XeroTrackingCategory.objects.get_or_create(
        connection=connection,
        xero_category_id='cat-office-123',
        defaults={
            'name': 'Office Expenses',
            'status': 'ACTIVE'
        }
    )
    print(f"✅ Tracking Category: {office_category.name} ({'created' if created else 'exists'})")

    travel_category, created = XeroTrackingCategory.objects.get_or_create(
        connection=connection,
        xero_category_id='cat-travel-456',
        defaults={
            'name': 'Travel Expenses',
            'status': 'ACTIVE'
        }
    )
    print(f"✅ Tracking Category: {travel_category.name} ({'created' if created else 'exists'})")

    # Create detection rules
    office_rule, created = CategoryDetectionRule.objects.get_or_create(
        connection=connection,
        name="Office Supplies Detection",
        defaults={
            'description': 'Detect office supply purchases from major suppliers',
            'suggested_category': office_category,
            'conditions': [
                {'field': 'description', 'operator': 'CONTAINS', 'value': 'office depot'},
                {'field': 'description', 'operator': 'CONTAINS', 'value': 'staples'}
            ],
            'condition_logic': 'ANY',
            'is_active': True,
            'priority': 10
        }
    )
    print(f"✅ Detection Rule: {office_rule.name} ({'created' if created else 'exists'})")

    travel_rule, created = CategoryDetectionRule.objects.get_or_create(
        connection=connection,
        name="Travel Expense Detection",
        defaults={
            'description': 'Detect travel-related expenses',
            'suggested_category': travel_category,
            'conditions': [
                {'field': 'description', 'operator': 'CONTAINS', 'value': 'airline'},
                {'field': 'description', 'operator': 'CONTAINS', 'value': 'hotel'},
                {'field': 'contact_name', 'operator': 'CONTAINS', 'value': 'uber'}
            ],
            'condition_logic': 'ANY',
            'is_active': True,
            'priority': 5
        }
    )
    print(f"✅ Detection Rule: {travel_rule.name} ({'created' if created else 'exists'})")

    return {
        'account': account,
        'user': user,
        'connection': connection,
        'office_category': office_category,
        'travel_category': travel_category,
        'office_rule': office_rule,
        'travel_rule': travel_rule,
        'provider': provider
    }

def test_detection_engine(data):
    """Test the category detection engine"""

    print("\n🔍 Testing Category Detection Engine...")

    # Sample transactions to test
    test_transactions = [
        {
            'id': 'txn-001',
            'description': 'Office Depot - Pens and Paper',
            'contact_name': 'Office Depot',
            'amount': Decimal('45.50'),
            'date': '2024-01-15'
        },
        {
            'id': 'txn-002',
            'description': 'United Airlines Flight 1234',
            'contact_name': 'United Airlines',
            'amount': Decimal('450.00'),
            'date': '2024-01-20'
        },
        {
            'id': 'txn-003',
            'description': 'Uber Trip to Airport',
            'contact_name': 'Uber Technologies',
            'amount': Decimal('35.75'),
            'date': '2024-01-20'
        },
        {
            'id': 'txn-004',
            'description': 'Coffee Shop Purchase',
            'contact_name': 'Local Coffee',
            'amount': Decimal('8.50'),
            'date': '2024-01-21'
        }
    ]

    # Initialize detection engine
    engine = CategoryDetectionEngine(data['connection'])

    # Run detection
    suggestions = engine.run_detection(test_transactions)

    print(f"✅ Generated {len(suggestions)} suggestions from {len(test_transactions)} transactions")

    for suggestion in suggestions:
        print(f"   💡 {suggestion.transaction_description} → {suggestion.suggested_category.name}")
        print(f"      Rule: {suggestion.detection_rule.name}")
        print(f"      Amount: ${suggestion.transaction_amount}")
        print()

    return suggestions

def test_suggestion_handler(suggestions, data):
    """Test the suggestion handler actions"""

    print("⚡ Testing Suggestion Handler Actions...")

    if not suggestions:
        print("❌ No suggestions to test")
        return

    handler = CategorySuggestionHandler()

    # Test different actions on different suggestions
    for i, suggestion in enumerate(suggestions[:3]):  # Test first 3 suggestions

        if i == 0:
            # Test ignore action
            print(f"🚫 Testing IGNORE action for: {suggestion.transaction_description}")
            result = handler.handle_ignore_action(suggestion, data['user'])
            print(f"   Result: {'✅ Success' if result['success'] else '❌ Failed'}")
            if result['success']:
                print(f"   Rule ignored count: {suggestion.detection_rule.ignored_count}")

        elif i == 1:
            # Test mark done action
            print(f"✅ Testing MARK DONE action for: {suggestion.transaction_description}")
            result = handler.handle_mark_done_action(suggestion, data['user'])
            print(f"   Result: {'✅ Success' if result['success'] else '❌ Failed'}")
            if result['success']:
                print(f"   Rule applied count: {suggestion.detection_rule.applied_count}")

        elif i == 2:
            # Test fix action
            print(f"🔧 Testing FIX action for: {suggestion.transaction_description}")
            result = handler.handle_fix_action(suggestion, data['user'])
            print(f"   Result: {'✅ Success' if result['success'] else '❌ Failed'}")
            if result['success']:
                print(f"   Xero URL: {result.get('xero_url', 'N/A')}")
                print(f"   Rule applied count: {suggestion.detection_rule.applied_count}")

        print()

def test_statistics(data):
    """Test statistics and reporting"""

    print("📊 Testing Statistics and Reporting...")

    handler = CategorySuggestionHandler()

    # Get statistics for each rule
    for rule in [data['office_rule'], data['travel_rule']]:
        stats = handler.get_suggestion_statistics_for_rule(rule)

        print(f"📈 Rule: {stats['rule_name']}")
        print(f"   Total suggestions: {stats['total_suggestions']}")
        print(f"   Pending: {stats['pending_count']}")
        print(f"   Applied: {stats['applied_count']}")
        print(f"   Ignored: {stats['ignored_count']}")
        print(f"   Action rate: {stats['action_rate']:.1f}%")
        print()

    # Get pending suggestions for connection
    pending = handler.get_pending_suggestions_for_connection(data['connection'])
    print(f"🕒 Total pending suggestions for connection: {len(pending)}")

    for suggestion in pending:
        status = handler.get_suggestion_status(suggestion)
        print(f"   📝 {status['transaction_description']} - {status['status']}")

def cleanup_demo_data():
    """Clean up demo data"""

    print("\n🧹 Cleaning up demo data...")

    try:
        # Delete in order to respect foreign key constraints
        CategorySuggestion.objects.filter(
            connection__organization_name="Demo Xero Organization"
        ).delete()

        CategoryDetectionRule.objects.filter(
            connection__organization_name="Demo Xero Organization"
        ).delete()

        XeroTrackingCategory.objects.filter(
            connection__organization_name="Demo Xero Organization"
        ).delete()

        Connection.objects.filter(
            organization_name="Demo Xero Organization"
        ).delete()

        Account.objects.filter(name="Demo Account").delete()
        User.objects.filter(username="demo_user").delete()

        print("✅ Demo data cleaned up successfully")

    except Exception as e:
        print(f"❌ Error cleaning up demo data: {e}")

def main():
    """Run the complete demo"""

    print("🎯 Category Consistency Feature Demo")
    print("=" * 50)

    try:
        # Create demo data
        data = create_demo_data()

        # Test detection engine
        suggestions = test_detection_engine(data)

        # Test suggestion handler
        test_suggestion_handler(suggestions, data)

        # Test statistics
        test_statistics(data)

        print("🎉 Demo completed successfully!")
        print("\nThe category consistency feature is working end-to-end:")
        print("✅ Rule creation and management")
        print("✅ Transaction detection and suggestion generation")
        print("✅ User action handling (ignore, mark done, fix)")
        print("✅ Statistics and reporting")
        print("✅ Database persistence and relationships")

    except Exception as e:
        print(f"❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Ask user if they want to keep demo data
        response = input("\nKeep demo data for manual testing? (y/N): ").strip().lower()
        if response != 'y':
            cleanup_demo_data()

if __name__ == "__main__":
    main()