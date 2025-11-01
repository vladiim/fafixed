"""
Tests for CategorySuggestionHandler - TDD implementation for Phase 3.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from datetime import timedelta

from integrations.models import Integration
from connections.models import Provider
from data_quality.models import (
    XeroTrackingCategory, 
    CategoryDetectionRule, 
    CategorySuggestion
)
from data_quality.services.category_suggestion_handler import CategorySuggestionHandler
from core.models import Account


class CategorySuggestionHandlerTest(TestCase):
    """Test CategorySuggestionHandler functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.account = Account.objects.create(
            name='Test Account',
            account_type='organization'
        )
        self.provider = Provider.objects.create(
            name='xero',
            display_name='Xero',
            provider_type='xero',
            auth_url_template='https://api.xero.com/oauth/authorize',
            token_url='https://api.xero.com/oauth/token'
        )
        self.connection = Connection.objects.create(
            account=self.account,
            provider=self.provider,
            external_account_id='test-xero-org-id',
            external_account_name='Test Xero Org',
            organization_name='Test Organization',
            status='active',
            created_by=self.user
        )
        
        # Create test tracking category
        self.office_category = XeroTrackingCategory.objects.create(
            connection=self.connection,
            xero_category_id='office-supplies-cat',
            name='Office Supplies',
            status='ACTIVE'
        )
        
        # Create test detection rule
        self.detection_rule = CategoryDetectionRule.objects.create(
            connection=self.connection,
            name='Office Supplies Rule',
            suggested_category=self.office_category,
            conditions=[
                {
                    'field': 'description',
                    'operator': 'CONTAINS',
                    'value': 'office'
                }
            ]
        )
        
        # Create test suggestion
        self.suggestion = CategorySuggestion.objects.create(
            connection=self.connection,
            detection_rule=self.detection_rule,
            xero_transaction_id='txn-123',
            suggested_category=self.office_category,
            transaction_description='Office Depot - Pens and Paper',
            transaction_contact='Office Depot',
            transaction_amount=Decimal('45.50'),
            status='PENDING'
        )
        
        # Create handler
        self.handler = CategorySuggestionHandler()

    def test_handler_initialization(self):
        """Test handler initializes correctly"""
        handler = CategorySuggestionHandler()
        self.assertIsInstance(handler, CategorySuggestionHandler)

    def test_handle_ignore_action_updates_suggestion(self):
        """Test ignore action updates suggestion status and metadata"""
        # Verify initial state
        self.assertEqual(self.suggestion.status, 'PENDING')
        self.assertIsNone(self.suggestion.decided_by)
        self.assertIsNone(self.suggestion.decided_at)
        
        # Handle ignore action
        result = self.handler.handle_ignore_action(self.suggestion, self.user)
        
        # Verify suggestion updated
        self.suggestion.refresh_from_db()
        self.assertEqual(self.suggestion.status, 'IGNORED')
        self.assertEqual(self.suggestion.decided_by, self.user)
        self.assertIsNotNone(self.suggestion.decided_at)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['action'], 'ignore')
        self.assertEqual(result['suggestion_id'], self.suggestion.id)

    def test_handle_ignore_action_updates_rule_statistics(self):
        """Test ignore action increments rule ignored count"""
        # Get initial rule stats
        initial_ignored_count = self.detection_rule.ignored_count
        
        # Handle ignore action
        self.handler.handle_ignore_action(self.suggestion, self.user)
        
        # Verify rule statistics updated
        self.detection_rule.refresh_from_db()
        self.assertEqual(self.detection_rule.ignored_count, initial_ignored_count + 1)

    def test_handle_ignore_action_creates_audit_trail(self):
        """Test ignore action creates audit trail entry"""
        # Handle ignore action
        result = self.handler.handle_ignore_action(self.suggestion, self.user)
        
        # Verify audit trail created
        self.assertIn('audit_trail', result)
        audit_entry = result['audit_trail']
        self.assertEqual(audit_entry['action'], 'ignore')
        self.assertEqual(audit_entry['user_id'], self.user.id)
        self.assertEqual(audit_entry['suggestion_id'], self.suggestion.id)
        self.assertIsNotNone(audit_entry['timestamp'])

    def test_handle_ignore_action_already_processed(self):
        """Test ignore action on already processed suggestion returns error"""
        # Mark suggestion as already processed
        self.suggestion.status = 'APPLIED'
        self.suggestion.decided_by = self.user
        self.suggestion.decided_at = timezone.now()
        self.suggestion.save()
        
        # Attempt ignore action
        result = self.handler.handle_ignore_action(self.suggestion, self.user)
        
        # Verify error returned
        self.assertFalse(result['success'])
        self.assertIn('already been processed', result['error'].lower())

    @patch('data_quality.services.category_suggestion_handler.verify_transaction_categorization')
    def test_handle_mark_done_action_updates_suggestion(self, mock_verify_task):
        """Test mark done action updates suggestion status"""
        # Mock the Celery task
        mock_task = Mock()
        mock_verify_task.delay.return_value = mock_task
        
        # Handle mark done action
        result = self.handler.handle_mark_done_action(self.suggestion, self.user)
        
        # Verify suggestion updated
        self.suggestion.refresh_from_db()
        self.assertEqual(self.suggestion.status, 'APPLIED')
        self.assertEqual(self.suggestion.decided_by, self.user)
        self.assertIsNotNone(self.suggestion.decided_at)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['action'], 'mark_done')

    @patch('data_quality.services.category_suggestion_handler.verify_transaction_categorization')
    def test_handle_mark_done_action_queues_verification(self, mock_verify_task):
        """Test mark done action queues Xero verification task"""
        # Mock the Celery task
        mock_task = Mock()
        mock_verify_task.delay.return_value = mock_task
        
        # Handle mark done action
        result = self.handler.handle_mark_done_action(self.suggestion, self.user)
        
        # Verify verification task was queued
        mock_verify_task.delay.assert_called_once_with(self.suggestion.id)
        self.assertIn('verification_task_id', result)

    def test_handle_mark_done_action_updates_rule_statistics(self):
        """Test mark done action increments rule applied count"""
        # Get initial rule stats
        initial_applied_count = self.detection_rule.applied_count
        
        # Handle mark done action
        with patch('data_quality.services.category_suggestion_handler.verify_transaction_categorization'):
            self.handler.handle_mark_done_action(self.suggestion, self.user)
        
        # Verify rule statistics updated
        self.detection_rule.refresh_from_db()
        self.assertEqual(self.detection_rule.applied_count, initial_applied_count + 1)

    @patch('data_quality.services.category_suggestion_handler.verify_transaction_categorization')
    def test_handle_fix_action_updates_suggestion(self, mock_verify_task):
        """Test fix action updates suggestion status"""
        # Mock the Celery task
        mock_task = Mock()
        mock_verify_task.delay.return_value = mock_task
        
        # Handle fix action
        result = self.handler.handle_fix_action(self.suggestion, self.user)
        
        # Verify suggestion updated
        self.suggestion.refresh_from_db()
        self.assertEqual(self.suggestion.status, 'APPLIED')
        self.assertEqual(self.suggestion.decided_by, self.user)
        self.assertIsNotNone(self.suggestion.decided_at)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['action'], 'fix')

    @patch('data_quality.services.category_suggestion_handler.verify_transaction_categorization')
    def test_handle_fix_action_queues_verification(self, mock_verify_task):
        """Test fix action queues Xero verification task"""
        # Mock the Celery task
        mock_task = Mock()
        mock_verify_task.delay.return_value = mock_task
        
        # Handle fix action
        result = self.handler.handle_fix_action(self.suggestion, self.user)
        
        # Verify verification task was queued
        mock_verify_task.delay.assert_called_once_with(self.suggestion.id)

    @patch('data_quality.services.category_suggestion_handler.verify_transaction_categorization')
    def test_handle_fix_action_generates_xero_url(self, mock_verify_task):
        """Test fix action generates correct Xero transaction URL"""
        # Mock the Celery task
        mock_task = Mock()
        mock_verify_task.delay.return_value = mock_task
        
        # Handle fix action
        result = self.handler.handle_fix_action(self.suggestion, self.user)
        
        # Verify Xero URL generated
        self.assertIn('xero_url', result)
        expected_url = f"https://go.xero.com/organisationlogin/default.aspx?shortcode={self.connection.external_account_id}&redirecturl=/Bank/ViewTransaction.aspx?bankTransactionID={self.suggestion.xero_transaction_id}"
        self.assertEqual(result['xero_url'], expected_url)

    def test_handle_fix_action_updates_rule_statistics(self):
        """Test fix action increments rule applied count"""
        # Get initial rule stats
        initial_applied_count = self.detection_rule.applied_count
        
        # Handle fix action
        with patch('data_quality.services.category_suggestion_handler.verify_transaction_categorization'):
            self.handler.handle_fix_action(self.suggestion, self.user)
        
        # Verify rule statistics updated
        self.detection_rule.refresh_from_db()
        self.assertEqual(self.detection_rule.applied_count, initial_applied_count + 1)

    def test_bulk_ignore_action_processes_multiple_suggestions(self):
        """Test bulk ignore action processes multiple suggestions"""
        # Create additional suggestions
        suggestion2 = CategorySuggestion.objects.create(
            connection=self.connection,
            detection_rule=self.detection_rule,
            xero_transaction_id='txn-456',
            suggested_category=self.office_category,
            status='PENDING'
        )
        
        suggestion3 = CategorySuggestion.objects.create(
            connection=self.connection,
            detection_rule=self.detection_rule,
            xero_transaction_id='txn-789',
            suggested_category=self.office_category,
            status='PENDING'
        )
        
        # Handle bulk ignore
        suggestions = [self.suggestion, suggestion2, suggestion3]
        result = self.handler.handle_bulk_ignore_action(suggestions, self.user)
        
        # Verify all suggestions updated
        self.suggestion.refresh_from_db()
        suggestion2.refresh_from_db()
        suggestion3.refresh_from_db()
        
        self.assertEqual(self.suggestion.status, 'IGNORED')
        self.assertEqual(suggestion2.status, 'IGNORED')
        self.assertEqual(suggestion3.status, 'IGNORED')
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['processed_count'], 3)
        self.assertEqual(result['failed_count'], 0)

    def test_bulk_action_handles_mixed_success_failure(self):
        """Test bulk action handles mix of successful and failed suggestions"""
        # Create additional suggestion already processed
        suggestion2 = CategorySuggestion.objects.create(
            connection=self.connection,
            detection_rule=self.detection_rule,
            xero_transaction_id='txn-456',
            suggested_category=self.office_category,
            status='APPLIED',  # Already processed
            decided_by=self.user,
            decided_at=timezone.now()
        )
        
        # Handle bulk ignore (one valid, one invalid)
        suggestions = [self.suggestion, suggestion2]
        result = self.handler.handle_bulk_ignore_action(suggestions, self.user)
        
        # Verify partial success
        self.assertEqual(result['processed_count'], 1)
        self.assertEqual(result['failed_count'], 1)
        self.assertEqual(len(result['errors']), 1)

    def test_get_suggestion_status_pending(self):
        """Test getting status of pending suggestion"""
        status = self.handler.get_suggestion_status(self.suggestion)
        
        self.assertEqual(status['status'], 'PENDING')
        self.assertFalse(status['is_processed'])
        self.assertIsNone(status['decided_by'])
        self.assertIsNone(status['decided_at'])

    def test_get_suggestion_status_processed(self):
        """Test getting status of processed suggestion"""
        # Process the suggestion
        self.suggestion.status = 'APPLIED'
        self.suggestion.decided_by = self.user
        self.suggestion.decided_at = timezone.now()
        self.suggestion.save()
        
        status = self.handler.get_suggestion_status(self.suggestion)
        
        self.assertEqual(status['status'], 'APPLIED')
        self.assertTrue(status['is_processed'])
        self.assertEqual(status['decided_by'], self.user.username)
        self.assertIsNotNone(status['decided_at'])

    def test_get_pending_suggestions_for_connection(self):
        """Test getting pending suggestions for a connection"""
        # Create additional suggestions with different statuses
        CategorySuggestion.objects.create(
            connection=self.connection,
            detection_rule=self.detection_rule,
            xero_transaction_id='txn-pending',
            suggested_category=self.office_category,
            status='PENDING'
        )
        
        CategorySuggestion.objects.create(
            connection=self.connection,
            detection_rule=self.detection_rule,
            xero_transaction_id='txn-applied',
            suggested_category=self.office_category,
            status='APPLIED'
        )
        
        # Get pending suggestions
        pending_suggestions = self.handler.get_pending_suggestions_for_connection(self.connection)
        
        # Should return 2 pending suggestions (original + new pending)
        self.assertEqual(len(pending_suggestions), 2)
        for suggestion in pending_suggestions:
            self.assertEqual(suggestion.status, 'PENDING')

    def test_get_suggestion_statistics_for_rule(self):
        """Test getting statistics for a detection rule"""
        # Create suggestions with different statuses
        CategorySuggestion.objects.create(
            connection=self.connection,
            detection_rule=self.detection_rule,
            xero_transaction_id='txn-ignored',
            suggested_category=self.office_category,
            status='IGNORED'
        )
        
        CategorySuggestion.objects.create(
            connection=self.connection,
            detection_rule=self.detection_rule,
            xero_transaction_id='txn-applied',
            suggested_category=self.office_category,
            status='APPLIED'
        )
        
        # Get statistics
        stats = self.handler.get_suggestion_statistics_for_rule(self.detection_rule)
        
        # Verify statistics
        self.assertEqual(stats['total_suggestions'], 3)  # Original + 2 new
        self.assertEqual(stats['pending_count'], 1)      # Original suggestion
        self.assertEqual(stats['applied_count'], 1)      # Applied suggestion
        self.assertEqual(stats['ignored_count'], 1)      # Ignored suggestion
        self.assertEqual(stats['superseded_count'], 0)   # No superseded

    def test_validate_suggestion_for_action_valid(self):
        """Test validation passes for valid pending suggestion"""
        is_valid, error = self.handler._validate_suggestion_for_action(self.suggestion)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_suggestion_for_action_already_processed(self):
        """Test validation fails for already processed suggestion"""
        self.suggestion.status = 'APPLIED'
        self.suggestion.save()
        
        is_valid, error = self.handler._validate_suggestion_for_action(self.suggestion)
        self.assertFalse(is_valid)
        self.assertIn('already been processed', error.lower())

    def test_validate_suggestion_for_action_superseded(self):
        """Test validation fails for superseded suggestion"""
        self.suggestion.status = 'SUPERSEDED'
        self.suggestion.save()
        
        is_valid, error = self.handler._validate_suggestion_for_action(self.suggestion)
        self.assertFalse(is_valid)
        self.assertIn('superseded', error.lower())

    def test_generate_xero_transaction_url(self):
        """Test generating correct Xero transaction URL"""
        url = self.handler._generate_xero_transaction_url(self.suggestion)
        
        expected_url = f"https://go.xero.com/organisationlogin/default.aspx?shortcode={self.connection.external_account_id}&redirecturl=/Bank/ViewTransaction.aspx?bankTransactionID={self.suggestion.xero_transaction_id}"
        self.assertEqual(url, expected_url)

    def test_create_audit_entry(self):
        """Test creating audit trail entry"""
        audit_entry = self.handler._create_audit_entry(
            action='test_action',
            suggestion=self.suggestion,
            user=self.user,
            metadata={'test': 'data'}
        )
        
        self.assertEqual(audit_entry['action'], 'test_action')
        self.assertEqual(audit_entry['suggestion_id'], self.suggestion.id)
        self.assertEqual(audit_entry['user_id'], self.user.id)
        self.assertEqual(audit_entry['user_username'], self.user.username)
        self.assertEqual(audit_entry['metadata']['test'], 'data')
        self.assertIsNotNone(audit_entry['timestamp'])

    def test_error_handling_invalid_suggestion_id(self):
        """Test error handling for invalid suggestion ID"""
        with self.assertRaises(CategorySuggestion.DoesNotExist):
            CategorySuggestion.objects.get(id=99999)

    def test_concurrent_action_handling(self):
        """Test handling concurrent actions on same suggestion"""
        # Simulate concurrent processing by marking as processed
        self.suggestion.status = 'APPLIED'
        self.suggestion.decided_by = self.user
        self.suggestion.decided_at = timezone.now()
        self.suggestion.save()
        
        # Attempt another action
        result = self.handler.handle_ignore_action(self.suggestion, self.user)
        
        # Should fail gracefully
        self.assertFalse(result['success'])
        self.assertIn('already been processed', result['error'].lower())

    def test_rule_statistics_consistency(self):
        """Test that rule statistics remain consistent across actions"""
        # Initial statistics
        initial_applied = self.detection_rule.applied_count
        initial_ignored = self.detection_rule.ignored_count
        
        # Apply one suggestion
        with patch('data_quality.services.category_suggestion_handler.verify_transaction_categorization'):
            self.handler.handle_mark_done_action(self.suggestion, self.user)
        
        # Create and ignore another suggestion
        suggestion2 = CategorySuggestion.objects.create(
            connection=self.connection,
            detection_rule=self.detection_rule,
            xero_transaction_id='txn-456',
            suggested_category=self.office_category,
            status='PENDING'
        )
        self.handler.handle_ignore_action(suggestion2, self.user)
        
        # Verify statistics
        self.detection_rule.refresh_from_db()
        self.assertEqual(self.detection_rule.applied_count, initial_applied + 1)
        self.assertEqual(self.detection_rule.ignored_count, initial_ignored + 1)

    def test_performance_with_many_suggestions(self):
        """Test handler performance with many suggestions"""
        # Create many suggestions
        suggestions = []
        for i in range(50):
            suggestion = CategorySuggestion.objects.create(
                connection=self.connection,
                detection_rule=self.detection_rule,
                xero_transaction_id=f'txn-bulk-{i}',
                suggested_category=self.office_category,
                status='PENDING'
            )
            suggestions.append(suggestion)
        
        # Perform bulk ignore (should complete quickly)
        result = self.handler.handle_bulk_ignore_action(suggestions, self.user)
        
        # Verify all processed
        self.assertTrue(result['success'])
        self.assertEqual(result['processed_count'], 50)
        self.assertEqual(result['failed_count'], 0)