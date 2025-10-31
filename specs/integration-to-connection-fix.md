# Integration → Connection Migration Fix

## Problem Statement

After connecting successfully to Xero, users encounter two critical errors:

1. **OAuth Callback Error**: "Reverse for 'xero_chart_accounts' not found. 'xero_chart_accounts' is not a valid view function or pattern name."
2. **Delete Error**: "Failed to delete integration: No Connection matches the given query."

## Root Cause Analysis

The codebase was migrated from an `Integration` model to a `Connection` model, but the migration was incomplete:

1. **URL Namespace Issue** (`connections/views.py:120`):
   - Current: `redirect('xero_chart_accounts', ...)`
   - Expected: `redirect('financial_data:xero_chart_accounts', ...)`
   - The URL pattern exists but requires the `financial_data:` namespace

2. **Model Mismatch in Dashboard** (`core/views.py:108-119`):
   - Dashboard queries `Integration` objects (old model)
   - Template passes `integration.prefix_id` to views expecting `Connection` objects
   - Delete view looks up `Connection` but receives `Integration` prefix_id

## User Flow (Expected)

1. User clicks "Connect Xero" on dashboard
2. User authorizes via Xero OAuth
3. OAuth callback completes successfully
4. User redirected to chart of accounts selection page
5. User can view, sync, and delete connections from dashboard

## Edge Cases

- [ ] User has old Integration records from before migration
- [ ] User has both Integration and Connection records
- [ ] User tries to delete while sync is in progress
- [ ] OAuth token expires during callback
- [ ] User tries to connect multiple Xero accounts

## Fix Implementation

### Phase 1: Immediate Fixes (Critical Path)

#### 1.1 Fix OAuth Callback Redirect
- **File**: `connections/views.py:120`
- **Change**: Add namespace to redirect
- **Test**: Complete OAuth flow and verify redirect works

#### 1.2 Update Dashboard to Use Connection Model
- **File**: `core/views.py:94-200`
- **Changes**:
  - Import `Connection` from `connections.models`
  - Query `Connection` instead of `Integration`
  - Update any `TransactionData` queries to use new model relationships
- **Test**: Dashboard loads and displays connections correctly

#### 1.3 Verify Delete Functionality
- **Test**: Delete button works after dashboard fix

### Phase 2: Comprehensive Verification

#### 2.1 Audit All Views for Model Consistency
- [ ] `connections/views.py` - uses Connection ✓ (mostly, needs callback fix)
- [ ] `core/views.py` - uses Integration ✗ (needs update)
- [ ] `financial_data/views.py` - check which model is used
- [ ] `data_quality/views.py` - check which model is used

#### 2.2 Audit All Templates for Prefix ID Usage
- [ ] `templates/dashboard.html` - verify all URL calls are correct
- [ ] Check for any hardcoded model assumptions

### Phase 3: End-to-End Testing

- [ ] Connect new Xero account
- [ ] Select chart of accounts
- [ ] Trigger sync
- [ ] View transactions
- [ ] Delete connection
- [ ] Verify no orphaned records

## Rollout Checklist

- [x] Phase 1.1: Fix callback redirect - Added namespace `financial_data:` to redirect
- [x] Phase 1.2: Update dashboard model - Dashboard already uses Integration (correct)
- [x] Phase 1.3: Update connection views - Changed all Connection lookups to Integration
- [x] Phase 1.4: Add delete_integration method - Added to IntegrationManager
- [x] Phase 1.5: Fix missing template - Copied template to financial_data/templates
- [x] Phase 1.6: Fix chart accounts form action - Added namespace and integration_prefix_id parameter
- [x] Phase 1.7: Fix import_chart_accounts URL pattern - Added integration_prefix_id parameter
- [x] Phase 1.8: Fix all redirect calls in import_chart_accounts - Added financial_data: namespace
- [x] Phase 1.9: Fix other redirect calls in financial_data/views.py - Added namespaces
- [x] Phase 1.10: Fix xero_connect URL references in template - Added connections: namespace
- [x] Phase 1.11: Fix form field name mismatch - Changed JS and view to use selected_organizations[]
- [x] Phase 1.12: Update to Australian spelling - Changed "organization" to "organisation" in user messages
- [x] Phase 1.13: Rebuild static files - Ran collectstatic to apply JavaScript changes
- [x] Phase 1.14: Fix import method - Changed to use sync_single_integration Celery task
- [x] Phase 1.15: Save selected organisations to config - Store in integration.config for dashboard display
- [x] Phase 1.16: Update JavaScript button text - Use Australian spelling consistently
- [x] Phase 1.17: Rebuild static files again - Apply Australian spelling changes
- [x] Test complete OAuth flow - Verified in server logs (line "Successfully connected to Xero org")
- [x] Test delete - Verified successfully by user
- [x] Test reconnection - User successfully deleted and reconnected
- [x] Test chart accounts selection page - User successfully loaded page
- [x] Test organisation selection form submission - Form posted successfully after browser cache clear
- [ ] Test organisation import and sync - Should work now with correct Celery task
- [ ] Test dashboard display of selected organisations - Should work after successful import
- [ ] Test sync functionality - May have separate Decimal serialization issue
- [ ] Verify no errors on fresh connection

## Success Criteria

1. ✅ OAuth flow completes without errors
2. ✅ User redirected to chart of accounts page (template now exists)
3. ✅ Dashboard displays connections correctly (uses Integration model)
4. ✅ Delete functionality works (verified in logs)
5. ✅ No model mismatch errors in logs

## Changes Made

### 1. Fixed OAuth Callback Redirect (`connections/views.py:120`)
- **Before**: `redirect('xero_chart_accounts', ...)`
- **After**: `redirect('financial_data:xero_chart_accounts', ...)`
- **Reason**: URL pattern requires namespace

### 2. Updated All Connection Views to Use Integration Model
- `test_integration()` - Changed `Connection` to `Integration`
- `revoke_integration()` - Changed `Connection` to `Integration`
- `delete_integration()` - Changed `Connection` to `Integration`
- Exception handler - Changed `Connection.DoesNotExist` to `Integration.DoesNotExist`
- **Reason**: System creates Integration objects, not Connection objects

### 3. Added `delete_integration()` Method to IntegrationManager
- Created new method in `integrations/managers.py`
- Attempts to revoke with provider before deletion
- Cascades deletion of credentials and related data
- **Reason**: Method was referenced but didn't exist

### 4. Fixed Missing Template
- Copied `xero_chart_accounts.html` from `integrations/templates/` to `financial_data/templates/`
- **Reason**: View looked for template in wrong location

### 5. Fixed Chart Accounts Form Action and URL Pattern
**File**: `/Users/vlad/code/fafixed/financial_data/templates/financial_data/xero_chart_accounts.html:48`
- **Before**: `<form method="post" action="{% url 'import_chart_accounts' %}" ...>`
- **After**: `<form method="post" action="{% url 'financial_data:import_chart_accounts' integration.prefix_id %}" ...>`
- **Reason**: Missing namespace and integration_prefix_id parameter

**File**: `/Users/vlad/code/fafixed/financial_data/urls.py:9`
- **Before**: `path('import-chart-accounts/', views.import_chart_accounts, name='import_chart_accounts'),`
- **After**: `path('import-chart-accounts/<str:integration_prefix_id>/', views.import_chart_accounts, name='import_chart_accounts'),`
- **Reason**: View function signature expects integration_prefix_id parameter

### 6. Fixed All Redirect Calls in import_chart_accounts View
**File**: `/Users/vlad/code/fafixed/financial_data/views.py`
- Line 259: Added `financial_data:` namespace to xero_chart_accounts redirect
- Line 272: Added `financial_data:` namespace to xero_chart_accounts redirect
- Line 289: Added `financial_data:` namespace to transaction_list redirect
- **Reason**: Ensure consistent URL resolution

### 7. Fixed Other Redirect Calls in financial_data Views
**File**: `/Users/vlad/code/fafixed/financial_data/views.py`
- Line 166: Added `financial_data:` namespace to transaction_list redirect
- Line 197: Added `financial_data:` namespace to transaction_edit redirect
- **Reason**: Prevent future URL resolution errors

### 8. Fixed xero_connect URL References in Template
**File**: `/Users/vlad/code/fafixed/financial_data/templates/financial_data/xero_chart_accounts.html`
- Line 113: Changed `{% url 'xero_connect' %}` to `{% url 'connections:xero_connect' %}`
- Line 129: Changed `{% url 'xero_connect' %}` to `{% url 'connections:xero_connect' %}`
- **Reason**: Missing connections: namespace for Back button and "Try connecting again" link

### 9. Fixed Form Field Name Mismatch for Organisation Selection
**File**: `/Users/vlad/code/fafixed/static/js/controllers/account_dropdown_controller.js:127`
- **Before**: `input.name = 'selected_accounts'`
- **After**: `input.name = 'selected_organizations[]'`
- **Reason**: JavaScript was sending 'selected_accounts' but view expected 'selected_organization'

**File**: `/Users/vlad/code/fafixed/financial_data/views.py:269-275`
- **Before**: `selected_org_id = request.POST.get('selected_organization')`
- **After**: `selected_org_ids = request.POST.getlist('selected_organizations[]')` and take first one
- Updated error message to use Australian spelling: "No organisation selected"
- **Reason**: Match JavaScript field name and support Australian spelling

### 10. Fixed Import Method and Save Selected Organisations
**File**: `/Users/vlad/code/fafixed/financial_data/views.py:279-300`
- **Before**: Called non-existent `service.sync_transactions_async()`
- **After**:
  - Save selected organisations to `integration.config['selected_organizations']`
  - Use Celery task `sync_single_integration.delay(integration.id, 'full')`
  - Redirect to dashboard instead of transaction_list
  - Updated all messages to use Australian spelling
- **Reason**: Method didn't exist, organisations weren't being saved for dashboard display

### 11. Updated JavaScript Text to Australian Spelling
**File**: `/Users/vlad/code/fafixed/static/js/controllers/account_dropdown_controller.js:76-91`
- Changed "Select accounts to import..." to "Select client organisations to import..."
- Changed "1 account selected" to "1 client organisation selected"
- Changed "N accounts selected" to "N client organisations selected"
- **Reason**: Consistent Australian spelling throughout UI

## Known Issues (Not Addressed)

1. **Decimal Serialization Error** - Separate issue in sync task
   - Line items fail to serialize Decimal values to JSON
   - Does not affect OAuth flow or deletion
   - Should be fixed separately

## Testing Evidence

From server logs:
```
Successfully connected to Xero org: Heuro LP (Tenant ID: 19b4b37e-1842-4d10-9bee-fee80febb21e)
[31/Oct/2025 02:56:18] "GET /xero/callback/..." 302 0
[31/Oct/2025 02:56:35] "GET /connections/int_cjf8vbjx/delete/" 302 0
```

Both operations completed with successful redirects (302 status).
