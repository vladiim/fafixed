# 🏗️ **Multi-App Architecture Refactoring Specification**

## 📋 **Executive Summary**

**Current State:** Monolithic `integrations` app containing mixed domain responsibilities  
**Target State:** Clean multi-app architecture with domain-driven design  
**Primary Goal:** Enable rapid extensibility for new data sources and validation rules  

---

## 🎯 **Domain-Driven App Architecture**

### **Current Problem: Mixed Responsibilities**
```
integrations/
├── models.py (837 lines) - EVERYTHING mixed together
├── views.py (1,064 lines) - Fat controller anti-pattern  
├── services/ - Only integration services
└── validation/ - Validation logic buried inside integrations
```

### **Target Architecture: Clean Domain Separation**
```
fafixed/  # Web application with Hotwire/Stimulus architecture
├── core/           # ✅ User/Account Management (existing)
├── connections/    # 🔄 External System Integration (renamed integrations)
├── financial_data/ # 🆕 Transaction Management
├── data_quality/   # 🆕 Validation & Issues  
└── shared/        # 🆕 Common utilities
```

---

## 📂 **Detailed App Specifications**

### **1. `core` App - Foundation** ✅ **EXISTING**
**Domain:** User management, multi-tenancy, authentication

**Models:**
- `UserProfile`, `Account`, `AccountUser`

**Responsibilities:**
- User authentication and authorization
- Multi-tenant account management
- Core infrastructure (PrefixIdMixin, etc.)

**Status:** Already well-designed, minimal changes needed

---

### **2. `connections` App - External Systems** 🔄 **REFACTORED**
**Domain:** Managing connections to external financial systems

**Models:** *(Moved from integrations)*
```python
# connections/models.py
class Provider(models.Model):           # Renamed from IntegrationProvider
class Connection(models.Model):         # Renamed from Integration  
class ConnectionCredential(models.Model)  # Renamed from IntegrationCredential
class OAuthState(models.Model)
class SyncRun(models.Model)            # Renamed from IntegrationSync
```

**Services:**
```python
# connections/services/
├── __init__.py
├── base.py          # BaseConnectionService (renamed)
├── registry.py      # ConnectionServiceRegistry
├── providers/
│   ├── xero.py      # XeroConnectionService
│   ├── quickbooks.py # Future: QuickBooksConnectionService
│   └── sage.py      # Future: SageConnectionService
```

**Web Views & Turbo Streams:**
```python
# connections/views.py - Traditional Django views with Turbo Stream responses
# connections/templates/ - HTML templates with Stimulus controllers
# connections/urls.py - Standard web URLs (no API versioning)
```

**Responsibilities:**
- OAuth flows for external systems
- Connection management and credentials
- Service discovery and registration
- Rate limiting and API communication

---

### **3. `financial_data` App - Transaction Management** 🆕 **NEW**
**Domain:** Financial transaction data storage and processing

**Models:** *(Moved from integrations)*
```python
# financial_data/models.py
class Transaction(models.Model):        # Renamed from TransactionData
class TransactionLineItem(models.Model)
class Account(models.Model)            # Chart of accounts from external systems
class Contact(models.Model)            # Customer/supplier data
```

**Services:**
```python
# financial_data/services/
├── transaction_service.py    # Business logic for transaction processing
├── import_service.py         # Data import from external systems
├── export_service.py         # Data export functionality  
└── reconciliation_service.py # Future: Bank reconciliation
```

**Web Views & Real-time Updates:**
```python
# financial_data/views.py - Transaction list/detail views with Turbo Stream updates
# financial_data/forms.py - Django forms with Stimulus validation
# financial_data/templates/ - HTML templates with data-turbo attributes
# financial_data/channels.py - ActionCable channels for real-time transaction updates
```

**Responsibilities:**
- Transaction data storage and retrieval
- Chart of accounts management
- Contact/customer data management
- Financial data import/export workflows

---

### **4. `data_quality` App - Validation & Issues** 🆕 **NEW**  
**Domain:** Data validation, issue detection, and resolution workflows

**Models:** *(Moved from integrations)*
```python
# data_quality/models.py  
class Issue(models.Model)                    # Issue tracking
class ValidationRun(models.Model)           # Batch validation execution
class ValidationRuleConfig(models.Model)    # Rule configuration
class IssueResolution(models.Model)         # Resolution tracking
class DataQualityMetric(models.Model)       # Quality scoring
```

**Services:**
```python
# data_quality/services/
├── validation_service.py     # Orchestration of validation runs
├── issue_service.py         # Issue management and resolution
├── metrics_service.py       # Data quality metrics calculation
└── reporting_service.py     # Quality reports and dashboards
```

**Validation Engine:** *(Moved from integrations)*
```python
# data_quality/validation/
├── engine.py                # ValidationEngine (moved)
├── registry.py             # ValidationRuleRegistry (moved)  
├── base.py                 # BaseValidationRule (moved)
├── rules/
│   ├── duplicates.py       # DuplicateTransactionRule (moved)
│   ├── reconciliation.py   # Future: ReconciliationRule
│   ├── compliance.py       # Future: ComplianceRule
│   └── cash_flow.py        # Future: CashFlowRule
```

**Web Views & Live Updates:**
```python
# data_quality/views.py - Issue dashboard with live status updates
# data_quality/forms.py - Resolution forms with Stimulus controllers
# data_quality/templates/ - Issue management UI with Turbo Frame lazy loading  
# data_quality/channels.py - Real-time validation progress via ActionCable
```

**Responsibilities:**
- Data validation rule execution
- Issue detection and tracking  
- Resolution workflow management
- Data quality metrics and reporting

---

### **5. `shared` App - Common Utilities** 🆕 **NEW**
**Domain:** Shared utilities, mixins, and common functionality

**Structure:**
```python
# shared/
├── models.py        # PrefixIdMixin, BaseModel, etc.
├── utils.py         # Common utility functions
├── exceptions.py    # Custom exception classes
├── mixins.py        # Common model/view mixins
├── validators.py    # Custom validators
└── middleware.py    # Shared middleware
```

**Responsibilities:**
- Common model mixins and utilities
- Shared validation logic
- Cross-app exception handling
- Common middleware and decorators

---

## 🧪 **Testing Strategy - Build Coverage As We Go**

### **Testing Philosophy: Hotwire-First Web Application**
**Goal:** Robust test coverage that supports refactoring without breaking constantly

**Testing Principles:**
- ✅ **Test behavior, not implementation** - Focus on inputs/outputs, not internal methods
- ✅ **High coverage for business logic** - Services and validation rules at 90%+
- ✅ **Integration tests for workflows** - End-to-end user scenarios with real browser interactions
- ✅ **Test Turbo Stream responses** - Verify correct HTML partial updates
- ✅ **Stub external dependencies** - Use service interfaces and test implementations
- ✅ **Test against real interfaces** - Use in-memory implementations, not mocks
- ❌ **Avoid mocking** - Use dependency injection and interface stubs instead
- ❌ **No JSON API testing** - All responses are HTML/Turbo Stream
- ❌ **Avoid testing Django internals** - Don't test ORM behavior, just your logic

### **Target Coverage Metrics:**
```python
# Target test coverage by component
Services:        95%    # Core business logic - critical
Models:          80%    # Custom methods and properties  
Views:           85%    # Web views and Turbo Stream responses
Forms:           90%    # Django form validation
Validation Rules: 95%   # Data quality logic - critical  
Utils/Helpers:   90%    # Shared functionality
```

---

## 🔄 **Migration Strategy**

### **Phase 1: Foundation Setup** *(Week 1)* ✅ **COMPLETED**
**Goal:** Establish new app structure without breaking existing functionality

#### **Phase 1 Testing Checklist:**
- [x] **Infrastructure Setup:** ✅ **COMPLETED**
  - [x] Django apps created and added to INSTALLED_APPS
  - [x] UV dependencies installed (pytest-django, pytest-cov, factory-boy, etc.)
  - [x] pytest.ini configuration created
  - [x] Test directory structure with stubs folders
  - [x] Django system check passes with new apps
  - [x] Removed unnecessary API app and DRF dependency
  - [x] Established PEP 8 style guide with single-line returns
- [x] **Unit Tests First:** ✅ **COMPLETED**
  - [x] Test `PrefixIdMixin` behavior in `shared/tests/test_models.py` - 4 tests
  - [x] Test common utilities in `shared/tests/test_utils.py` - 21 tests
  - [x] All tests passing with comprehensive coverage
- [x] **Integration Tests:** ✅ **COMPLETED**
  - [x] Test app discovery and import paths working correctly
  - [x] Django system check passes for all apps
  - [x] Template tag integration verified
- [x] **Coverage Verification:** ✅ **COMPLETED**
  - [x] Shared utilities: 100% coverage - 25/25 tests passing
  - [x] Full test suite integration verified

**Actions:**
1. **✅ Create new Django apps:** *COMPLETED*
   ```bash
   uv run python manage.py startapp connections  
   uv run python manage.py startapp financial_data
   uv run python manage.py startapp data_quality
   uv run python manage.py startapp shared
   # Note: Removed API app - using web-first Hotwire architecture instead
   ```

2. **✅ Set up comprehensive testing infrastructure:** *COMPLETED*
   ```bash
   # Added to pyproject.toml [dependency-groups]
   dev = [
       "pytest-django==4.7.0",
       "pytest-cov==4.0.0", 
       "factory-boy==3.3.0",
       "freezegun==1.2.2", 
       "locust==2.17.0",
       "pytest-xdist==3.5.0",
       # Removed: "djangorestframework==3.14.0" - not needed for web-first architecture
   ]
   
   # Install with UV
   uv sync --group dev
   
   # Created test structure with stubs directories
   mkdir -p {connections,financial_data,data_quality,shared}/tests/stubs
   touch {shared,connections,financial_data,data_quality}/tests/__init__.py
   ```

3. **✅ Move shared utilities to `shared` app with tests:** *COMPLETED*
   - ✅ Move `PrefixIdMixin` from `core/models.py` → `shared/models.py`
   - ✅ Update imports in `core/models.py` and `integrations/models.py`
   - ✅ **Write tests FIRST** - `shared/tests/test_models.py` with 4 focused test cases
   - ✅ All tests passing - PrefixIdMixin working correctly in shared app
   - ✅ Create `shared/utils.py` for common functions with PEP 8 single-line returns
   - ✅ **Write tests** - `shared/tests/test_utils.py` with 21 comprehensive tests

4. **✅ Create shared template utilities and Turbo Stream helpers:** *COMPLETED*
   - ✅ Create common template tags and filters in `shared/templatetags/shared_tags.py`
   - ✅ Set up Turbo Stream response helpers in `shared/utils.py`
   - ✅ Created template components: status badges, progress bars, turbo-frame helpers
   - ✅ **All tests passing** - 25 total tests (4 models + 21 utilities)
   - ✅ Established `specs/styleguide.py` following PEP 8 standards

5. **✅ Architectural refinement:** *COMPLETED*
   - ✅ Removed unnecessary API app - focus on web-first Hotwire architecture
   - ✅ Removed DRF dependency - using Turbo Stream responses instead
   - ✅ Updated specification to reflect web-first approach with Stimulus/ActionCable
   - ✅ All 25 tests passing with clean architecture

### **Phase 2: Model Migration** *(Week 2-3)* 🔄 **READY TO START**
**Goal:** Move models to appropriate apps with database migrations

#### **Phase 2 Testing Checklist:**
- [x] **Unit Tests First (Before Migration):** ✅ **COMPLETED**
  - [x] Test all model methods in `connections/tests/test_models.py` - 33 tests
  - [x] Test model relationships in `financial_data/tests/test_models.py` - 22 tests  
  - [x] Test validation rules in `data_quality/tests/test_models.py` - 37 tests
  - [x] **117 total tests with 96% coverage** - Migration safety net established
- [ ] **Migration Tests:**
  - [ ] Test data migration scripts with realistic data
  - [ ] Test foreign key integrity after migration
  - [ ] Test model queries work with new structure
- [ ] **Integration Tests:**
  - [ ] Test cross-app model relationships
  - [ ] Test admin interface with new models
  - [ ] Test web view integration with moved models
- [ ] **Coverage Verification:**
  - [x] Model custom methods: 96% coverage ✅ (Target: 80%+)
  - [ ] Migration scripts: 95%+ coverage

**Actions:**
1. **Create new models in target apps with comprehensive tests:**
   ```python
   # Example: connections/tests/test_models.py
   class TestConnection(TestCase):
       def test_connection_creation(self): ...
       def test_prefix_id_generation(self): ...
       def test_oauth_flow_methods(self): ...
   ```

2. **Generate database migrations** for new model locations
3. **Data migration scripts with test coverage** to move existing data
4. **Update foreign key references** across apps
5. **Remove old models** after successful migration and test verification

**Migration Order:**
1. `connections` models (least dependent)
2. `financial_data` models (depends on connections)  
3. `data_quality` models (depends on financial_data)

### **Phase 3: Service Layer Extraction** *(Week 4)*
**Goal:** Move business logic to appropriate service layers

**Actions:**
1. **Move integration services** → `connections/services/`
2. **Extract transaction logic** → `financial_data/services/`
3. **Move validation engine** → `data_quality/validation/`
4. **Update import statements** across codebase

### **Phase 4: View Decomposition** *(Week 5-6)*
**Goal:** Break up fat controllers and create clean web views with Turbo Stream support

**Actions:**
1. **Create clean web views** in respective apps with Turbo Stream responses
2. **Decompose `integrations/views.py`:**
   - OAuth views → `connections/views.py`
   - Transaction views → `financial_data/views.py`  
   - Issue views → `data_quality/views.py`
3. **Update URL patterns** to be clean and resource-oriented
4. **Add Turbo Stream support** for real-time updates

### **Phase 5: Testing & Documentation** *(Week 7-8)*
**Goal:** Ensure system integrity and update documentation

**Actions:**
1. **Run full test suite** and fix any issues
2. **Add integration tests** between apps  
3. **Update web interface documentation**
4. **Performance testing** to ensure no regressions
5. **Update deployment scripts** and configurations

---

## 🛤️ **Web-First URL Design**

### **Clean Web URL Patterns:**
```python
# ❌ Current (Mixed patterns)
/integrations/refresh-sync/<integration_id>/
/integrations/transactions/<transaction_id>/actions/

# ✅ Target (Clean web URLs with Turbo Stream actions)  
POST /connections/{connection_id}/sync/
GET  /transactions/{transaction_id}/
POST /transactions/{transaction_id}/validate/
```

### **Resource-Oriented Web Views:**
```python
# connections/urls.py
path('connections/', ConnectionListView.as_view(), name='connection_list')
path('connections/<str:pk>/', ConnectionDetailView.as_view(), name='connection_detail') 
path('connections/<str:pk>/sync/', sync_connection, name='sync_connection')

# financial_data/urls.py  
path('transactions/', TransactionListView.as_view(), name='transaction_list')
path('transactions/<str:pk>/', TransactionDetailView.as_view(), name='transaction_detail')

# data_quality/urls.py
path('issues/', IssueListView.as_view(), name='issue_list')
path('issues/<str:pk>/', IssueDetailView.as_view(), name='issue_detail')
```

### **HTTP Methods & Turbo Stream Responses:**
```python
# Web-first approach with Turbo Stream updates
GET    /transactions/         # List page with Turbo Frames for lazy loading
POST   /transactions/         # Create and return Turbo Stream update
GET    /transactions/{id}/    # Detail page
POST   /transactions/{id}/    # Update and return Turbo Stream partial
DELETE /transactions/{id}/    # Delete and return Turbo Stream removal

# Form actions with Turbo Stream responses
POST   /transactions/{id}/validate/  # Validate and stream status updates
POST   /issues/{id}/resolve/         # Resolve and stream UI updates
```

---

## 🔌 **Extensibility Framework**

### **Adding New Data Sources:**
**Target Time: 4 hours** ⚡

```python
# 1. Create new connection service (30 minutes)
# connections/services/providers/sage.py
class SageConnectionService(BaseConnectionService):
    provider_name = "sage"
    
    def get_auth_url(self) -> str: ...
    def handle_callback(self, code: str) -> dict: ...  
    def sync_transactions(self) -> list: ...

# 2. Register the service (5 minutes)  
# connections/services/__init__.py
ConnectionServiceRegistry.register('sage', SageConnectionService)

# 3. Add provider configuration (15 minutes)
# Data migration or admin interface
Provider.objects.create(
    name='sage',
    display_name='Sage Business Cloud',
    provider_type='sage'
)

# 4. Test integration (3+ hours)
# Create integration tests
```

### **Adding New Validation Rules:**
**Target Time: 2 hours** ⚡

```python
# 1. Create new validation rule (90 minutes)
# data_quality/validation/rules/compliance.py  
class ATOComplianceRule(BaseValidationRule):
    rule_name = "ato_compliance_check"
    severity = ValidationSeverity.HIGH
    
    def validate(self, transactions: List[Transaction]) -> ValidationResult:
        # Implementation logic
        pass

# 2. Register the rule (5 minutes)
# data_quality/validation/rules/__init__.py  
ValidationRuleRegistry.register(ATOComplianceRule)

# 3. Add configuration (25 minutes)
# Admin interface or API to enable/configure rule
```

### **Adding New Issue Resolution Workflows:**
**Target Time: 1 hour** ⚡

```python
# 1. Create custom issue handler (45 minutes)  
# data_quality/handlers/custom_handler.py
class CustomIssueHandler(BaseIssueHandler):
    category = "custom_category"
    
    def get_resolution_steps(self, issue: Issue) -> List[ResolutionStep]:
        # Custom resolution workflow
        pass
    
    def auto_resolve(self, issue: Issue) -> bool:
        # Automatic resolution logic  
        pass

# 2. Register handler (15 minutes)
IssueHandlerRegistry.register('custom_category', CustomIssueHandler)
```

---

## 📊 **Success Metrics**

### **Architectural Quality:**
- [x] **App Structure:** 4 clean domain-driven apps created ✅
- [x] **Test Coverage:** 117 tests with 96% coverage ✅ 
- [x] **Code Quality:** Migration-resilient test design ✅
- [ ] **Model Size:** No model file > 200 lines
- [ ] **Service Cohesion:** 95% of business logic in service layer
- [ ] **Web Interface Consistency:** 100% Turbo Stream response compliance

### **Extensibility Metrics:**
- [ ] **New Data Source:** Add in < 4 hours ⚡
- [ ] **New Validation Rule:** Add in < 2 hours ⚡  
- [ ] **New Issue Handler:** Add in < 1 hour ⚡
- [x] **Template Reusability:** Shared components established ✅

### **Development Velocity:**
- [x] **Build Time:** 1.19 seconds for 117 tests ✅ (Target: < 30 seconds)
- [ ] **Deployment:** Zero-downtime database migrations  
- [x] **Test Safety Net:** Complete behavioral validation ✅
- [ ] **Feature Development:** 80% faster than current architecture

### **Quality Assurance:**
- [x] **Migration Readiness:** Comprehensive pre-migration tests ✅
- [x] **Business Logic Preservation:** All model behavior validated ✅  
- [x] **Error Handling:** Database constraints and edge cases tested ✅
- [x] **Fixture-Driven Testing:** Clean, maintainable test code ✅

---

## 🔧 **Technical Implementation Details**

### **Database Migration Strategy:**
```python
# Example: Moving Transaction model
# Step 1: Create new model in financial_data app
# Step 2: Data migration to copy existing data  
# Step 3: Update foreign keys to point to new model
# Step 4: Remove old model

# Migration will be zero-downtime with proper planning
```

### **Backwards Compatibility:**
```python  
# API versioning ensures existing integrations continue working
# /api/v1/ endpoints maintained during transition
# Legacy URLs redirect to new structure with deprecation warnings
```

### **Inter-App Communication:**
```python
# Clean dependency chain: connections → financial_data → data_quality
# Use Django signals for loose coupling between apps
# Shared utilities in `shared` app to prevent circular imports
```

---

## 🚀 **Implementation Timeline**

| Phase | Duration | Key Deliverables |
|-------|----------|-----------------|  
| **Phase 1** | Week 1 | New app structure, API foundation |
| **Phase 2** | Week 2-3 | Model migrations, database restructure |
| **Phase 3** | Week 4 | Service layer extraction |  
| **Phase 4** | Week 5-6 | View decomposition, RESTful APIs |
| **Phase 5** | Week 7-8 | Testing, documentation, go-live |

**Total Duration:** 8 weeks  
**Risk Level:** Medium (well-planned migrations reduce risk)  
**Business Impact:** Minimal (phased approach with backwards compatibility)

---

## 📋 **Current Implementation Status**

### **✅ Phase 1: Foundation Setup - COMPLETED** 
- **Duration:** Completed in 1 session
- **Status:** All infrastructure tests passing ✅
- **Key Deliverables:**
  - ✅ 4 domain-driven Django apps created (connections, financial_data, data_quality, shared)
  - ✅ Web-first architecture with Hotwire/Turbo Stream support
  - ✅ Comprehensive shared utilities with PEP 8 style guide
  - ✅ Template tags and filters for common UI patterns
  - ✅ 100% test coverage for shared utilities

### **✅ Phase 1.5: Comprehensive Model Testing - COMPLETED**
- **Duration:** Completed in 1 session  
- **Status:** All 117 tests passing with 96% coverage ✅
- **Key Deliverables:**
  - ✅ **33 connection model tests** - Provider, Connection, ConnectionCredential, OAuthState, SyncRun
  - ✅ **22 financial_data model tests** - Transaction, TransactionLineItem  
  - ✅ **37 data_quality model tests** - Issue (+ custom manager), ValidationRun, ValidationRuleConfig, TransactionValidationStatus
  - ✅ **Migration-resilient test design** - Focus on behavior, not implementation
  - ✅ **Comprehensive fixture usage** - Clean, maintainable test code
  - ✅ **Business logic validation** - All model methods, properties, and constraints tested
  - ✅ **Error condition handling** - Database constraints, edge cases, transaction management

### **🔄 Phase 2: Model Migration - READY TO START**
- **Status:** Comprehensive test safety net established ✅  
- **Next:** Move models from integrations app to appropriate domain apps
- **Focus:** Test-driven migration with database integrity
- **Timeline:** 2-3 weeks
- **Confidence Level:** HIGH - Complete test coverage ensures migration safety

### **📊 Test Coverage Summary**
```bash
# Phase 1: Infrastructure Tests
✅ shared/tests/test_models.py     - 4 tests   (PrefixIdMixin)
✅ shared/tests/test_utils.py      - 21 tests  (Utilities & Turbo Stream)

# Phase 1.5: Comprehensive Model Tests  
✅ connections/tests/test_models.py    - 33 tests (Provider, Connection, Credential, OAuth, Sync)
✅ financial_data/tests/test_models.py - 22 tests (Transaction, LineItem)
✅ data_quality/tests/test_models.py   - 37 tests (Issue, ValidationRun, Config, Status)

# Overall Status
✅ Total Test Suite                - 117 tests passing
✅ Code Coverage                   - 96% across all new apps
✅ Django System Check            - No issues
✅ Migration Safety Net           - Complete behavioral validation
```

**Next Steps:** Begin Phase 2 model migration with confidence - comprehensive test coverage ensures all business logic will continue working correctly after models are moved to their new domain-driven locations.