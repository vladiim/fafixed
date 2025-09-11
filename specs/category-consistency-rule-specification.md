# Category Consistency Rule Specification

## Overview

The Category Consistency Rule allows users to create automated detection rules that identify transactions needing categorization based on user-defined conditions (description, contact, or both). Users then review suggested categorizations and manually approve actions.

**Rule Type**: User-Configurable Detection Rule  
**Plugin Name**: `CategoryConsistencyRule`  
**Display Name**: "Smart Transaction Categorization Detection"  
**Purpose**: Detect transactions that need categorization and suggest appropriate Xero tracking categories for user review

## Business Value

### Problem Statement
- Manual transaction categorization is time-consuming and error-prone
- Users forget to categorize similar transactions consistently
- No way to automatically detect transactions that need specific categories
- Hard to maintain categorization standards across team members

### Solution Benefits
- **Smart Detection**: Rules automatically identify transactions needing categorization
- **User Control**: All categorization changes require manual approval
- **Consistency**: Suggests consistent categories based on user-defined patterns
- **Workflow Integration**: Integrates with existing issue resolution workflow
- **Audit Trail**: Complete history of categorization decisions and rule applications

### User Stories
1. **As an accountant**, I want to be notified when "Office Depot" transactions appear so I can categorize them as "Office Supplies"
2. **As a bookkeeper**, I want transactions containing "fuel" flagged for "Vehicle Expenses" categorization, but I want to review each one first
3. **As a business owner**, I want "Acme Corp" transactions suggested for "Client Work - Acme" but I want to verify the category is correct

## Human-in-the-Loop Workflow

### 1. Rule Detection Phase
- Rules run automatically when transactions are synced
- Matching transactions are flagged for user review
- No automatic changes to Xero or local data
- Creates "Categorization Needed" validation issues

### 2. User Review Phase
Users review flagged transactions and can take three actions:

#### Action 1: Ignore
- **Purpose**: Rule doesn't apply to this specific transaction
- **Result**: Transaction marked as "ignored" for this rule
- **Future Behavior**: This rule will never flag this transaction again
- **Use Case**: Exception to the general pattern

#### Action 2: Mark Done
- **Purpose**: Category already correctly set in Xero
- **Result**: Pull latest transaction data from Xero to verify category
- **Future Behavior**: Rule won't flag this transaction again
- **Use Case**: User already categorized manually in Xero

#### Action 3: Fix in Xero
- **Purpose**: Apply the suggested categorization
- **Result**: 
  1. User clicks to open Xero transaction (external link)
  2. User makes changes in Xero manually
  3. System pulls updated transaction data from Xero
  4. Local database updated with new category information
- **Future Behavior**: Rule won't flag this transaction again
- **Use Case**: Apply the rule's suggested categorization

### 3. Sync Verification Phase
For "Mark Done" and "Fix" actions:
- System calls Xero API to get latest transaction data
- Updates local database with current Xero state
- Verifies categorization was applied correctly
- Marks issue as resolved

## Technical Requirements

### 1. Xero Integration (Read-Only + Verification)

#### Current State
- ✅ We can read transactions from Xero via existing API integration
- ❌ We do NOT currently pull tracking categories from Xero
- ❌ We do NOT push changes to Xero (and we don't want to!)

#### Required Implementation
1. **Sync Tracking Categories from Xero (Read-Only)**
   - Pull all tracking categories and their options for each connection
   - Cache categories locally for UI dropdown selection
   - Update cache daily via scheduled task
   - Handle category changes and deletions

2. **Verify Transaction Updates (Read-Only)**
   - Fetch specific transaction from Xero to verify changes
   - Update local database with current Xero state
   - No writes to Xero - user makes changes manually

3. **API Endpoints Required**
   ```
   GET /TrackingCategories - Get all tracking categories and options
   GET /BankTransactions/{ID} - Verify transaction current state
   ```

### 2. Rule Configuration System

#### Condition Builder
Users create detection rules with visual interface:

**Field Selection:**
- `description` - Transaction description
- `contact_name` - Contact/supplier name
- `reference` - Transaction reference

**Operator Selection:**
- `equals` - Exact match (case insensitive)
- `contains` - Contains substring (case insensitive)
- `starts_with` - Starts with text (case insensitive)
- `ends_with` - Ends with text (case insensitive)
- `matches_regex` - Regular expression match
- `is_empty` - Field is empty or null

**Logical Operators:**
- `AND` - All conditions must match
- `OR` - Any condition can match
- Support for nested condition groups

#### Suggested Action Configuration
When conditions match, suggest action:
- **Suggested Tracking Category**: Choose from Xero categories and options
- **Suggestion Reason**: Text explaining why this category is suggested

#### Example Rule Configuration
```json
{
  "name": "Office Supplies Detection",
  "description": "Detect office supply purchases for categorization",
  "conditions": {
    "operator": "OR",
    "conditions": [
      {
        "field": "description",
        "operator": "contains", 
        "value": "office depot"
      },
      {
        "field": "contact_name",
        "operator": "equals",
        "value": "Office Works"
      }
    ]
  },
  "suggested_action": {
    "type": "suggest_tracking_category",
    "tracking_category_id": "uuid-from-xero",
    "tracking_option_id": "uuid-from-xero",
    "reason": "Office supply purchases should be categorized as Office Expenses"
  }
}
```

### 3. Database Schema

#### New Models Required

```python
# Xero tracking category cache (read-only)
class XeroTrackingCategory(models.Model):
    connection = models.ForeignKey('connections.Connection')
    xero_category_id = models.CharField(max_length=255)
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=20)  # ACTIVE, ARCHIVED
    last_synced_at = models.DateTimeField(auto_now=True)

class XeroTrackingOption(models.Model):
    category = models.ForeignKey(XeroTrackingCategory, related_name='options')
    xero_option_id = models.CharField(max_length=255)
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=20)  # ACTIVE, ARCHIVED

# User-defined categorization detection rules
class CategoryDetectionRule(models.Model):
    connection = models.ForeignKey('connections.Connection')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_enabled = models.BooleanField(default=True)
    priority_order = models.IntegerField(default=0)
    
    # Rule definition
    conditions = models.JSONField()  # Condition tree
    suggested_action = models.JSONField()  # Suggested categorization
    
    # Statistics
    detection_count = models.IntegerField(default=0)
    applied_count = models.IntegerField(default=0)  # User chose "Fix"
    ignored_count = models.IntegerField(default=0)  # User chose "Ignore"
    last_triggered_at = models.DateTimeField(null=True)
    
    created_by = models.ForeignKey(User)
    created_at = models.DateTimeField(auto_now_add=True)

# Track rule detections and user decisions
class CategorySuggestion(models.Model):
    SUGGESTION_STATUS = [
        ('pending_review', 'Pending User Review'),
        ('ignored', 'User Ignored'),
        ('mark_done', 'User Marked Done'),
        ('fixed', 'User Fixed in Xero'),
    ]
    
    rule = models.ForeignKey(CategoryDetectionRule)
    transaction = models.ForeignKey('financial_data.Transaction')
    status = models.CharField(max_length=20, choices=SUGGESTION_STATUS, default='pending_review')
    
    # Suggestion details
    suggested_category_id = models.CharField(max_length=255)
    suggested_option_id = models.CharField(max_length=255)
    suggestion_reason = models.TextField()
    
    # User decision tracking
    user_decision = models.CharField(max_length=20, blank=True)
    decided_by = models.ForeignKey(User, null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    
    # Sync verification (for mark_done/fixed actions)
    xero_verification_status = models.CharField(max_length=20, default='not_required')
    xero_verified_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['rule', 'transaction']
```

### 4. Detection Engine Architecture

#### Rule Detection Engine
```python
class CategoryDetectionEngine:
    def run_detection(self, connection):
        """Run all enabled detection rules for connection"""
        rules = CategoryDetectionRule.objects.filter(
            connection=connection, 
            is_enabled=True
        ).order_by('priority_order')
        
        transactions = self.get_uncategorized_transactions(connection)
        suggestions = []
        
        for transaction in transactions:
            for rule in rules:
                if self.evaluate_rule(transaction, rule):
                    suggestion = self.create_suggestion(transaction, rule)
                    suggestions.append(suggestion)
                    break  # First match wins
        
        return suggestions
    
    def evaluate_rule(self, transaction, rule):
        """Check if transaction matches rule conditions"""
        return self.evaluate_conditions(transaction, rule.conditions)
    
    def create_suggestion(self, transaction, rule):
        """Create suggestion for user review"""
        return CategorySuggestion.objects.create(
            rule=rule,
            transaction=transaction,
            suggested_category_id=rule.suggested_action['tracking_category_id'],
            suggested_option_id=rule.suggested_action['tracking_option_id'],
            suggestion_reason=rule.suggested_action['reason'],
            status='pending_review'
        )
```

#### User Action Handler
```python
class CategorySuggestionHandler:
    def handle_ignore_action(self, suggestion, user):
        """User chose to ignore this suggestion"""
        suggestion.status = 'ignored'
        suggestion.user_decision = 'ignore'
        suggestion.decided_by = user
        suggestion.decided_at = timezone.now()
        suggestion.save()
        
        # Update rule statistics
        suggestion.rule.ignored_count += 1
        suggestion.rule.save()
    
    def handle_mark_done_action(self, suggestion, user):
        """User says it's already correctly categorized"""
        suggestion.status = 'mark_done'
        suggestion.user_decision = 'mark_done'
        suggestion.decided_by = user
        suggestion.decided_at = timezone.now()
        suggestion.save()
        
        # Queue verification task
        verify_transaction_categorization.delay(suggestion.id)
    
    def handle_fix_action(self, suggestion, user):
        """User will fix categorization in Xero"""
        suggestion.status = 'fixed'
        suggestion.user_decision = 'fix'
        suggestion.decided_by = user
        suggestion.decided_at = timezone.now()
        suggestion.save()
        
        # Update rule statistics
        suggestion.rule.applied_count += 1
        suggestion.rule.save()
        
        # Queue verification task (user will make changes in Xero)
        verify_transaction_categorization.delay(suggestion.id)
```

### 5. User Interface Requirements

#### Categorization Review Dashboard
- **Pending Suggestions List**: All transactions flagged by rules needing review
- **Suggestion Details**: Show rule name, suggested category, reason
- **Action Buttons**: Ignore, Mark Done, Fix in Xero
- **Batch Actions**: Handle multiple suggestions at once
- **Filters**: By rule, date range, suggested category

#### Suggestion Detail View
```html
<div class="suggestion-card border rounded-lg p-4 mb-4">
    <div class="flex justify-between items-start">
        <div class="flex-1">
            <h3 class="font-medium">{{ transaction.description }}</h3>
            <p class="text-sm text-gray-600">
                {{ transaction.contact_name }} • {{ transaction.amount }} • {{ transaction.date }}
            </p>
            <div class="mt-2 p-2 bg-blue-50 rounded">
                <p class="text-sm">
                    <strong>Rule:</strong> {{ suggestion.rule.name }}<br>
                    <strong>Suggested Category:</strong> {{ suggested_category_name }}<br>
                    <strong>Reason:</strong> {{ suggestion.suggestion_reason }}
                </p>
            </div>
        </div>
        <div class="ml-4 flex flex-col space-y-2">
            <button class="btn-secondary" onclick="ignoreTransaction({{ suggestion.id }})">
                Ignore
            </button>
            <button class="btn-secondary" onclick="markDone({{ suggestion.id }})">
                Mark Done
            </button>
            <a href="{{ xero_transaction_url }}" target="_blank" 
               class="btn-primary" onclick="markAsFixed({{ suggestion.id }})">
                Fix in Xero
            </a>
        </div>
    </div>
</div>
```

#### Rule Management Interface
- **Rule List**: All detection rules with statistics
- **Rule Creation**: Visual condition builder + category selector
- **Rule Testing**: Preview which transactions would be flagged
- **Performance Stats**: Detection rate, user action distribution

### 6. Integration with Existing Validation Framework

The Category Detection Rule integrates with the existing validation system:

```python
class CategoryDetectionValidationRule(BaseValidationRule):
    """Integration with existing validation framework"""
    
    name = "category_detection"
    description = "Detect transactions needing categorization"
    
    def validate(self, connection):
        """Run category detection and create validation issues"""
        engine = CategoryDetectionEngine()
        suggestions = engine.run_detection(connection)
        
        if suggestions:
            return ValidationResult.create_issue(
                rule_name=self.name,
                severity=ValidationSeverity.MEDIUM,
                title=f"{len(suggestions)} transactions need categorization review",
                description="Smart categorization rules have identified transactions that may need category assignment",
                affected_transactions=[s.transaction for s in suggestions]
            )
        
        return ValidationResult.success(rule_name=self.name)
```

## Implementation Checklist

### Phase 1: Xero Tracking Categories (Week 1) ✅ COMPLETED
- [x] Research Xero tracking categories API endpoints and response format
- [x] Create `XeroTrackingCategory` and `XeroTrackingOption` models
- [x] Generate and apply database migrations
- [x] Implement Xero tracking categories sync service (read-only)
- [x] Create API integration to pull categories from Xero
- [x] Add error handling for Xero API calls
- [x] Create scheduled Celery task for daily category sync
- [x] Test category sync with development Xero organization
- [x] Add category cache management (create, update, soft delete)
- [x] Create admin interface for debugging category data

**Phase 1 Results:**
- **Database Models**: `XeroTrackingCategory` and `XeroTrackingOption` models implemented with full constraints, indexes, and relationships
- **Sync Service**: `XeroTrackingSyncService` handles create/update/archive operations with connection isolation
- **Celery Tasks**: Three tasks implemented - single connection sync, all connections sync, and cleanup
- **Test Coverage**: 30 comprehensive tests covering models, service, and tasks (all passing ✅)
- **Error Handling**: Robust retry logic, exponential backoff, and comprehensive error scenarios tested
- **Performance**: Connection isolation, efficient querying, and archiving strategy implemented

### Phase 2: Detection Rules Engine (Week 2)
- [ ] Create `CategoryDetectionRule` and `CategorySuggestion` models
- [ ] Generate and apply database migrations
- [ ] Implement `CategoryDetectionEngine` for rule evaluation
- [ ] Build recursive condition tree evaluation (AND/OR logic)
- [ ] Add support for all operators (equals, contains, starts_with, etc.)
- [ ] Create rule suggestion generation system
- [ ] Implement priority-based rule execution (first match wins)
- [ ] Add comprehensive error handling and logging
- [ ] Write unit tests for detection engine
- [ ] Test rule evaluation with sample transaction data

### Phase 3: User Action Handling (Week 3)
- [ ] Create `CategorySuggestionHandler` for user actions
- [ ] Implement "Ignore" action handler
- [ ] Implement "Mark Done" action handler with Xero verification
- [ ] Implement "Fix" action handler with Xero verification
- [ ] Create Celery task for Xero transaction verification
- [ ] Add retry logic for failed Xero API calls during verification
- [ ] Implement rule statistics tracking (detection, applied, ignored counts)
- [ ] Add audit trail for all user decisions
- [ ] Create management command for reprocessing suggestions
- [ ] Test all action handlers with mock Xero responses

### Phase 4: User Interface (Week 4)
- [ ] Create categorization review dashboard template
- [ ] Build suggestion card component with action buttons
- [ ] Implement suggestion detail view with transaction info
- [ ] Add batch action functionality for multiple suggestions
- [ ] Create filters for suggestion list (rule, date, category)
- [ ] Build rule management dashboard
- [ ] Create visual condition builder using jQuery QueryBuilder
- [ ] Implement category selector dropdown using Xero data
- [ ] Add rule testing/preview functionality
- [ ] Style all components with Tailwind CSS
- [ ] Add responsive design for mobile devices
- [ ] Implement real-time updates for suggestion status changes

### Phase 5: Integration & Polish (Week 5)
- [ ] Integrate detection rules with existing validation framework
- [ ] Add rule execution to transaction sync workflow
- [ ] Create integration with issue resolution system
- [ ] Implement suggestion status tracking in transaction list
- [ ] Add rule performance monitoring and alerting
- [ ] Create user documentation and help tooltips
- [ ] Implement comprehensive test suite (unit, integration, E2E)
- [ ] Add accessibility features (ARIA labels, keyboard navigation)
- [ ] Optimize database queries and add appropriate indexes
- [ ] Conduct user acceptance testing with sample rules
- [ ] Create deployment documentation and monitoring setup
- [ ] Deploy to production with feature monitoring

### Phase 6: Validation & Launch (Week 6)
- [ ] Complete end-to-end testing with real Xero connections
- [ ] Validate all user workflows (ignore, mark done, fix)
- [ ] Test Xero API integration under various scenarios
- [ ] Verify rule statistics and performance metrics
- [ ] Confirm proper error handling and recovery
- [ ] Test with large transaction volumes
- [ ] Validate security and data isolation
- [ ] Create operational procedures for support team
- [ ] Monitor system performance and user adoption
- [ ] Collect user feedback and iterate on UX

## Success Metrics

### Technical Metrics
- Rule evaluation time < 50ms per transaction
- Xero API success rate > 99.5%
- Category sync accuracy 100%
- Suggestion generation accuracy > 95%

### Business Metrics
- User action rate > 80% (users act on suggestions vs ignore)
- Categorization time reduced by 60%+
- Rule creation rate > 2 rules per active user
- User satisfaction score > 4.5/5

### Performance Metrics
- Support 1000+ transactions per day per connection
- Handle 20+ detection rules per connection
- Dashboard load time < 2 seconds
- Real-time suggestion updates

## Risk Mitigation

### Technical Risks
- **Xero API Rate Limits**: Implement caching and intelligent request batching
- **Complex Rule Logic**: Start with simple operators, add complexity gradually
- **Performance Issues**: Monitor query performance and optimize indexes
- **User Interface Complexity**: Progressive disclosure, start with simple UI

### Business Risks
- **Low User Adoption**: Provide clear onboarding and rule templates
- **Rule Creation Complexity**: Visual builder with examples and tutorials
- **False Positive Rate**: Allow easy rule refinement and exception handling
- **Support Complexity**: Comprehensive documentation and training materials

## Future Enhancements

### Additional Features
- **Rule Templates**: Industry-specific rule templates
- **Smart Suggestions**: AI-suggested rules based on transaction patterns
- **Bulk Historical Processing**: Apply rules to historical transactions
- **Advanced Operators**: Date ranges, amount comparisons, regex helpers
- **Team Collaboration**: Share rules between team members
- **Reporting**: Analytics on categorization patterns and rule effectiveness

### Integration Opportunities
- **AI Enhancement**: Use ML to suggest rule conditions
- **Workflow Integration**: Connect with approval workflows
- **External Systems**: Integrate with other accounting platforms
- **Mobile App**: Review suggestions on mobile devices

This specification provides a comprehensive roadmap for implementing smart transaction categorization detection with full user control and Xero integration.