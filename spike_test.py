#!/usr/bin/env python
"""
SPIKE TEST: Quick verification that our components are working
Run this with: uv run python spike_test.py
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fafixed.settings')
django.setup()

def test_imports():
    """Test that all our imports work"""
    print("🧪 SPIKE TEST: Testing imports...")
    
    try:
        # Test turbo_helper import
        from turbo_helper.channels.broadcasts import broadcast_render_to
        print("✅ SPIKE TEST: turbo_helper.channels.broadcasts imported successfully")
        
        # Test models
        from integrations.models import TransactionData
        print("✅ SPIKE TEST: TransactionData model imported successfully")
        
        # Test tasks
        from integrations.tasks import refresh_transaction_status_task
        print("✅ SPIKE TEST: refresh_transaction_status_task imported successfully")
        
        # Test views
        from integrations.views import refresh_transaction_status
        print("✅ SPIKE TEST: refresh_transaction_status view imported successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ SPIKE TEST: Import failed: {e}")
        return False

def test_database_connection():
    """Test database connection and find a test transaction"""
    print("\n🧪 SPIKE TEST: Testing database connection...")
    
    try:
        from integrations.models import TransactionData
        
        # Count transactions
        count = TransactionData.objects.count()
        print(f"✅ SPIKE TEST: Found {count} transactions in database")
        
        if count > 0:
            # Get first transaction
            transaction = TransactionData.objects.first()
            print(f"✅ SPIKE TEST: Sample transaction ID: {transaction.id}, Updated: {transaction.updated_at}")
            return transaction.id
        else:
            print("⚠️ SPIKE TEST: No transactions found in database")
            return None
            
    except Exception as e:
        print(f"❌ SPIKE TEST: Database test failed: {e}")
        return None

def test_celery_task():
    """Test that we can import and create the celery task"""
    print("\n🧪 SPIKE TEST: Testing Celery task creation...")
    
    try:
        from integrations.tasks import refresh_transaction_status_task
        
        # Just test that we can reference the task (don't actually run it)
        task_name = refresh_transaction_status_task.name
        print(f"✅ SPIKE TEST: Celery task name: {task_name}")
        return True
        
    except Exception as e:
        print(f"❌ SPIKE TEST: Celery task test failed: {e}")
        return False

def main():
    print("🚀 SPIKE TEST: Starting component verification...\n")
    
    # Run tests
    imports_ok = test_imports()
    transaction_id = test_database_connection()
    celery_ok = test_celery_task()
    
    # Summary
    print(f"\n📊 SPIKE TEST: Results Summary:")
    print(f"   Imports: {'✅' if imports_ok else '❌'}")
    print(f"   Database: {'✅' if transaction_id else '❌'}")  
    print(f"   Celery: {'✅' if celery_ok else '❌'}")
    
    if all([imports_ok, transaction_id, celery_ok]):
        print(f"\n🎉 SPIKE TEST: All components working! Ready to test with transaction ID: {transaction_id}")
        print(f"\n📋 SPIKE TEST: Next steps:")
        print(f"   1. Start: uv run ./bin/dev")
        print(f"   2. Visit transaction list in browser")
        print(f"   3. Click 'Refresh' button on transaction {transaction_id}")
        print(f"   4. Watch logs for SPIKE messages")
    else:
        print(f"\n❌ SPIKE TEST: Some components failed, check errors above")

if __name__ == "__main__":
    main()