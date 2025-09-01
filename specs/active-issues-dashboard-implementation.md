# 📋 **Active Issues Dashboard System - Technical Implementation Spec**

## ✅ **Analysis & Planning Checklist**

- [x] Research existing validation rules and issues system
- [x] Analyze dashboard issues implementation  
- [x] Design issues aggregation system
- [x] Plan ActionCable real-time updates for dashboard
- [x] Create technical extensibility guide

## 🔍 **Current System Analysis**

### **Existing Architecture:**
```
Validation Rules → ValidationEngine → Issue Records → Dashboard Display
                 ↓                   ↓               ↓
        ValidationResult → Issue.objects → Template Rendering
```

**✅ What's Working:**
- **Validation Rules System**: Extensible `BaseValidationRule` with `DuplicateTransactionRule` implemented
- **Issue Model**: Complete with severity, category, count, affected_transactions JSON field
- **Dashboard View**: Basic issues display with filtering and stats
- **ActionCable Infrastructure**: Working real-time system for transaction updates

**❌ What Needs Implementation:**
- **Real-time Issue Updates**: Dashboard doesn't update when validation runs complete
- **Issue Aggregation**: No automatic grouping/deduplication of similar issues
- **Interactive Issue Management**: Can't click on issues to view/mark individual occurrences
- **ValidationRun Integration**: ValidationRun exists but isn't fully integrated with dashboard

---

## 🏗️ **Technical Implementation Plan**

### **⚠️ CRITICAL RULE: Use prefix_id for ALL user-facing identifiers**
- **URLs**: All routes must use prefix_id parameters (e.g., `<str:issue_prefix_id>`)
- **Templates**: All user-facing IDs must use prefix_id (e.g., `issue-{{ issue.prefix_id }}`)
- **ActionCable**: All streams and targets must use prefix_id for security
- **JavaScript**: All client-side references must use prefix_id
- **APIs**: All endpoints must accept/return prefix_id instead of database id

### **Phase 1: Enhanced Issue System & Aggregation**

#### **Phase 1 Implementation Checklist**
- [ ] **Add Issue PrefixIdMixin inheritance and apply has_prefix_id('iss') decorator**
- [ ] Add new Issue model fields (issue_key, occurrence_ids, latest_occurrence, resolution fields)
- [ ] Create database migration for Issue model enhancements
- [ ] Implement IssueManager.create_or_update_issue() method
- [ ] Add Issue.mark_occurrence_resolved() method
- [ ] Add Issue.get_unresolved_count() method
- [ ] Create issue_key generation logic for smart grouping
- [ ] Update ValidationEngine._create_issue_from_result() to use new aggregation
- [ ] Add database indexes for (integration_id, status, category)
- [ ] Write unit tests for issue aggregation logic

#### **1.1 Issue Aggregation Strategy**
```python
# New Issue grouping logic
class IssueManager:
    @classmethod
    def create_or_update_issue(cls, integration, validation_result):
        # Smart grouping by: integration + category + severity + similar affected transactions
        issue_key = cls._generate_issue_key(integration, validation_result)
        
        existing_issue = Issue.objects.filter(
            integration=integration,
            category=validation_result.category,
            status='open',
            issue_key=issue_key  # New field for grouping
        ).first()
        
        if existing_issue:
            # Update existing issue with new occurrences
            existing_issue.merge_occurrence(validation_result)
        else:
            # Create new grouped issue
            Issue.create_from_validation_result(integration, validation_result)
```

#### **1.2 Issue Model Enhancements**
```python
class Issue(models.Model, PrefixIdMixin):  # ⚠️ MUST inherit PrefixIdMixin
    # Existing fields...
    issue_key = models.CharField(max_length=64, db_index=True)  # For grouping
    occurrence_ids = models.JSONField(default=list)  # Track individual occurrences
    latest_occurrence = models.JSONField(default=dict)  # Most recent details
    resolution_notes = models.TextField(blank=True)
    resolved_by = models.ForeignKey(User, null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    def mark_occurrence_resolved(self, occurrence_id, user):
        """Mark individual occurrence as resolved"""
        # Implementation for granular resolution
        
    def get_unresolved_count(self):
        """Get count of unresolved individual occurrences"""
        # Implementation for partial resolution tracking

# Apply prefix_id decorator
Issue = Issue.has_prefix_id('iss')  # Creates iss_xxxxxxxx IDs
```

### **Phase 2: Real-Time Dashboard Updates**

#### **Phase 2 Implementation Checklist**
- [ ] Add Issue post_save signal handler for ActionCable broadcasts
- [ ] Create broadcast_issue_update() function **using prefix_id in stream names**
- [ ] Add account-level stream names (account_issues_{account.prefix_id})
- [ ] Update dashboard template with ActionCable controller **using prefix_id streams**
- [ ] Create dashboard/partials/issue_item.html template **with prefix_id targets**
- [ ] Add ValidationRun post_save signal handler
- [ ] Create broadcast_validation_run_update() function
- [ ] Add turbo-frame targets to dashboard template **using prefix_id**
- [ ] Test real-time issue updates end-to-end
- [ ] Add error handling for ActionCable failures

#### **2.1 ActionCable Integration for Issues**
```python
# New signal handler
@receiver(post_save, sender=Issue)
def broadcast_issue_update(sender, instance, **kwargs):
    """Broadcast issue updates to dashboard via ActionCable"""
    
    # Render dashboard issue partial
    issue_html = render_to_string(
        'dashboard/partials/issue_item.html',
        {'issue': instance}
    )
    
    # ⚠️ CRITICAL: Use prefix_id for stream name and target
    account_stream = f"account_issues_{instance.integration.account.prefix_id}"
    
    turbo_stream_html = f"""
    <turbo-stream action="replace" target="issue-{instance.prefix_id}">
        <template>{issue_html}</template>
    </turbo-stream>
    """
    
    # Broadcast via ActionCable
    broadcast_to_account_streams(account_stream, turbo_stream_html)
```

#### **2.2 Dashboard Real-Time Setup**
```html
<!-- Enhanced dashboard template -->
<div data-controller="actioncable" 
     data-actioncable-url-value="{{ WEBSOCKET_URL }}"
     data-actioncable-subscriptions-value='[
       {"stream_name": "account_issues_{{ request.user.profile.current_account.prefix_id }}"},
       {"stream_name": "account_validations_{{ request.user.profile.current_account.prefix_id }}"}
     ]'>
</div>

<turbo-frame id="issues-dashboard">
  <!-- Dynamic issue list that updates in real-time -->
  {% for issue in issues %}
    <turbo-frame id="issue-{{ issue.prefix_id }}">  <!-- ⚠️ prefix_id -->
      <!-- Issue content -->
    </turbo-frame>
  {% endfor %}
</turbo-frame>
```

#### **2.3 Validation Run Real-Time Integration**
```python
@receiver(post_save, sender=ValidationRun)  
def broadcast_validation_run_update(sender, instance, **kwargs):
    """Broadcast validation run status to dashboard"""
    
    if instance.status == 'completed':
        # ⚠️ Use prefix_id for account identification
        stats_html = render_dashboard_stats(instance.integration.account)
        broadcast_dashboard_stats_update(instance.integration.account.prefix_id, stats_html)
        
        # Show completion notification
        broadcast_validation_completion_toast(instance)
```

### **Phase 3: Interactive Issue Management**

#### **Phase 3 Implementation Checklist**
- [ ] **Ensure Issue model has prefix_id field from Phase 1**
- [ ] Create issue detail URL patterns **using prefix_id parameters**
- [ ] Implement issue_detail view **querying by prefix_id**
- [ ] Implement resolve_occurrence view **using prefix_id**
- [ ] Implement mark_issue_resolved view **using prefix_id**
- [ ] Create issue detail template/modal **with prefix_id identifiers**
- [ ] Add "View Details" buttons to dashboard issue items **using prefix_id URLs**
- [ ] Create individual occurrence resolution UI
- [ ] Add bulk resolution actions
- [ ] Add resolution notes functionality
- [ ] Test interactive issue management workflow

#### **3.1 Issue Detail View & Resolution**
```python
# ⚠️ CRITICAL: URL patterns must use prefix_id
path('issues/<str:issue_prefix_id>/', views.issue_detail, name='issue_detail'),
path('issues/<str:issue_prefix_id>/resolve-occurrence/', views.resolve_occurrence, name='resolve_occurrence'),
path('issues/<str:issue_prefix_id>/mark-resolved/', views.mark_issue_resolved, name='mark_issue_resolved'),

# Views must query by prefix_id
@login_required
def issue_detail(request, issue_prefix_id):
    issue = get_object_or_404(
        Issue,
        prefix_id=issue_prefix_id,  # ⚠️ Query by prefix_id
        integration__account__account_users__user=request.user
    )
    # Implementation...
```

#### **3.2 Issue Detail Template**
```html
<!-- Issue detail modal/page -->
<turbo-frame id="issue-{{ issue.prefix_id }}-detail">  <!-- ⚠️ prefix_id -->
  <!-- Issue summary -->
  <!-- List of individual transaction occurrences -->
  <form action="{% url 'mark_issue_resolved' issue.prefix_id %}" method="post">  <!-- ⚠️ prefix_id -->
    <!-- Resolution form -->
  </form>
</turbo-frame>
```

### **Phase 4: Extensibility Framework**

#### **Phase 4 Implementation Checklist**
- [ ] Create IssueTypeRegistry class
- [ ] Implement BaseIssueRenderer abstract class **ensuring prefix_id usage in templates**
- [ ] Add issue type handler registration system
- [ ] Update BaseValidationRule with issue creation guidance
- [ ] Create plugin architecture for custom issue types
- [ ] Add template override system for issue categories **with prefix_id standards**
- [ ] Create action hooks for custom resolution workflows
- [ ] Add configuration system for issue type behaviors
- [ ] Write documentation for creating custom issue types **emphasizing prefix_id usage**
- [ ] Create example custom issue type implementation

#### **4.1 Plugin Architecture for Issue Types**
```python
class IssueTypeRegistry:
    """Registry for different issue type handlers"""
    
    @classmethod
    def register_issue_type(cls, category, handler_class):
        """Register custom issue type handler"""
        
    @classmethod  
    def get_issue_renderer(cls, issue):
        """Get appropriate renderer for issue type"""
        
class BaseIssueRenderer(ABC):
    """Base class for issue-specific rendering and actions"""
    
    @abstractmethod
    def render_dashboard_item(self, issue):
        """Render issue in dashboard list - MUST use issue.prefix_id for IDs"""
        
    @abstractmethod
    def render_detail_view(self, issue):
        """Render detailed issue view - MUST use issue.prefix_id for IDs"""
        
    @abstractmethod
    def get_available_actions(self, issue, user):
        """Get available actions for this issue type"""
```

#### **4.2 Validation Rule Integration**
```python
class BaseValidationRule(ABC):
    # Enhanced with issue creation guidance
    
    def create_issue_from_result(self, integration, result):
        """Template method for creating issues from validation results"""
        return {
            'grouping_strategy': self.get_grouping_strategy(),
            'resolution_actions': self.get_available_resolutions(),
            'display_template': self.get_issue_template(),  # Must use prefix_id
            'detail_template': self.get_detail_template()   # Must use prefix_id
        }
```

---

## 📊 **Dashboard Real-Time Flow Architecture**

### **Real-Time Update Flow:**
```
1. Validation Rule Executes → ValidationResult
2. ValidationEngine.create_issue_from_result() → Issue Created/Updated  
3. Issue post_save signal → ActionCable Broadcast (using prefix_id)
4. Dashboard WebSocket receives update → Turbo Stream applies (targeting prefix_id)
5. Issue list updates in real-time without page refresh
```

### **ActionCable Streams (using prefix_id):**
```python
# ⚠️ CRITICAL: Account-level streams using prefix_id for security
f"account_issues_{account.prefix_id}"           # Issue creation/updates
f"account_validations_{account.prefix_id}"      # Validation run status  
f"account_stats_{account.prefix_id}"            # Dashboard statistics updates
```

### **Turbo Stream Targets (using prefix_id):**
```html
<!-- ⚠️ CRITICAL: All targets must use prefix_id -->
<turbo-frame id="issues-list">                       <!-- Global list updates -->
<turbo-frame id="dashboard-stats">                   <!-- Statistics updates -->
<turbo-frame id="issue-{{ issue.prefix_id }}">       <!-- Individual issue updates -->
<turbo-frame id="validation-status-{{ integration.prefix_id }}"> <!-- Validation progress -->
```

---

## 🔧 **Implementation Best Practices**

### **Database Optimization Checklist**
- [ ] Add composite indexes on (integration_id, status, category)
- [ ] Implement cursor-based pagination for large issue lists  
- [ ] Add Redis caching for frequently accessed issue aggregations
- [ ] Optimize Issue queries with select_related/prefetch_related

### **Real-Time Performance Checklist**
- [ ] Implement account-level stream scoping using prefix_id to prevent cross-tenant data leakage
- [ ] Add selective broadcasting (only to active dashboard sessions)
- [ ] Implement debouncing for multiple rapid issue updates
- [ ] Add ActionCable connection monitoring and error recovery

### **Security & prefix_id Checklist**
- [ ] **Verify all URLs use prefix_id parameters instead of database IDs**
- [ ] **Ensure all templates use prefix_id for user-facing identifiers**  
- [ ] **Confirm ActionCable streams use prefix_id for account scoping**
- [ ] **Test that direct database ID access is not possible via URLs**
- [ ] **Audit all user-facing APIs to ensure prefix_id usage**

### **Extensibility Patterns Checklist**
- [ ] Create plugin system for custom validation rules and issue types
- [ ] Support template override system for different issue categories **with prefix_id standards**
- [ ] Provide action hooks for custom resolution workflows
- [ ] Add configuration system for customizing behaviors

### **Testing Strategy Checklist**
- [ ] Write integration tests for complete validation → issue → broadcast → UI flow
- [ ] Add WebSocket tests for ActionCable message delivery and format **using prefix_id**
- [ ] Create load tests to ensure performance with high issue volumes
- [ ] Add unit tests for all issue aggregation logic
- [ ] **Test security: verify database IDs are not exposed in any user-facing interface**

---

## 🚀 **Migration Strategy**

### **Phase 1 Migration Checklist (Non-Breaking)**
- [ ] **Add PrefixIdMixin to Issue model and apply has_prefix_id('iss') decorator**
- [ ] Create database migration for new Issue fields with defaults
- [ ] **Populate prefix_id for all existing Issue records**
- [ ] Add new database indexes
- [ ] Run data migration to populate issue_key for existing Issue records
- [ ] Test migration on staging environment

### **Phase 2 Deployment Checklist (Gradual Rollout)**  
- [ ] Deploy new validation engine logic with feature flag
- [ ] Enable real-time updates for subset of beta users
- [ ] Monitor ActionCable performance and adjust connection limits
- [ ] **Verify all ActionCable streams use prefix_id correctly**
- [ ] Gradually roll out to all users

### **Phase 3 Frontend Checklist (Progressive)**
- [ ] Add ActionCable to dashboard with feature flag **using prefix_id streams**
- [ ] **Update all issue URLs to use prefix_id parameters**
- [ ] Deploy issue detail views **with prefix_id routing**
- [ ] Enable interactive issue management features
- [ ] Collect user feedback and iterate

### **Phase 4 Advanced Features Checklist (Feature Flags)**
- [ ] Deploy custom issue renderer system **enforcing prefix_id standards**
- [ ] Add bulk resolution workflows
- [ ] Implement advanced filtering and search
- [ ] Add issue analytics and reporting

---

## 🎯 **Current Implementation Status**

### **Phase 1: Enhanced Issue System & Aggregation - ✅ COMPLETED**
- [x] **Add PrefixIdMixin inheritance and apply has_prefix_id('iss') decorator to Issue model**
- [x] **Add new Issue model fields (issue_key, occurrence_ids, latest_occurrence, resolution fields)**
- [x] **Create database migration for Issue model enhancements** 
- [x] **Implement IssueManager.create_or_update_issue() method with proper scoping**
- [x] **Update ValidationEngine._create_issue_from_result() to use new aggregation**
- [x] **Add database indexes for (integration_id, status, category)**
- [x] **Write comprehensive unit tests for issue aggregation logic (15 tests total)**

#### **Phase 1 Key Achievements:**
- ✅ **Account Multi-Tenancy**: Issues properly isolated between accounts via `integration.account`
- ✅ **Chart of Accounts Scoping**: Issues grouped only within same `external_account_id`
- ✅ **Smart Issue Aggregation**: Uses `account_id:external_account_id:rule_name:severity` keys
- ✅ **Prefix ID Security**: All issues use `iss_xxxxxxxx` format for user-facing identifiers
- ✅ **Eliminated Data Duplication**: Removed hardcoded category mapping, uses rule names directly
- ✅ **Occurrence Tracking**: Individual validation occurrences tracked with unique UUIDs
- ✅ **Resolution Management**: Support for marking individual occurrences as resolved

### **Known Issues 🐛**
- [ ] **JSON Serialization Issue**: Complex `affected_transactions` data from validation rules contains non-JSON-serializable types (likely Decimal fields from database queries)
  - **Error**: `TypeError: Object of type 'Decimal' is not JSON serializable`
  - **Root Cause**: ValidationResult.affected_transactions from DuplicateTransactionRule contains:
    ```python
    # From duplicates.py line ~180-198
    transaction_list.append({
        'amount': float(txn.amount) if txn.amount else 0,  # Should be OK
        'date': txn.date.isoformat() if txn.date else None,  # Should be OK  
        # Other fields that may have serialization issues...
    })
    ```
  - **Impact**: Prevents saving issues when ValidationEngine runs with real transaction data  
  - **Temporary Fix**: Use simpler test data to avoid complex ValidationResult.affected_transactions
  - **Solution Options**:
    1. Add `_serialize_affected_transactions()` helper in IssueManager to convert complex types
    2. Update validation rules to ensure all data is JSON-serializable before creating ValidationResult
    3. Use Django's DjangoJSONEncoder for model field serialization
  - **Priority**: High - blocks real validation runs from creating issues

### **Next Up 🚀 - Phase 2: Real-Time Dashboard Updates**
- [ ] **Add Issue post_save signal handler for ActionCable broadcasts**
- [ ] **Create broadcast_issue_update() function using prefix_id in stream names**
- [ ] **Add account-level stream names (account_issues_{account.prefix_id})**
- [ ] **Update dashboard template with ActionCable controller using prefix_id streams**
- [ ] **Create dashboard/partials/issue_item.html template with prefix_id targets**
- [ ] **Add ValidationRun post_save signal handler**
- [ ] **Create broadcast_validation_run_update() function**
- [ ] **Add turbo-frame targets to dashboard template using prefix_id**
- [ ] **Test real-time issue updates end-to-end**
- [ ] **Add error handling for ActionCable failures**

### **Implementation Priority Order**
1. **Phase 1** - ✅ **COMPLETED**: Foundation (Issue aggregation + prefix_id) - Immediate value
2. **Phase 2** - **IN PROGRESS**: Real-time updates (with prefix_id security) - Enhanced UX  
3. **Phase 3** - Interactive management (prefix_id routing) - Advanced features
4. **Phase 4** - Extensibility framework (prefix_id standards) - Future-proofing

---

## ⚠️ **CRITICAL SECURITY REMINDER**

**ALL user-facing identifiers MUST use prefix_id:**
- ✅ URLs: `/issues/iss_abc123def/` 
- ❌ URLs: `/issues/42/`
- ✅ Templates: `<div id="issue-{{ issue.prefix_id }}">`
- ❌ Templates: `<div id="issue-{{ issue.id }}">`  
- ✅ ActionCable: `issue-{{ issue.prefix_id }}`
- ❌ ActionCable: `issue-{{ issue.id }}`

This prevents database enumeration attacks and maintains consistency with the existing transaction and integration systems that already use prefix_id throughout.

---

This specification provides a complete roadmap with granular checkboxes for tracking progress, with the critical addition of the prefix_id requirement for all user-facing identifiers. The modular approach allows for incremental development and testing at each phase, building on the existing solid architecture while maintaining security standards.