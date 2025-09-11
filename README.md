# FAFixed - Financial Data Quality Platform

FAFixed is a Django-based SaaS application for financial accountants that integrates with Xero to pull transaction data and run validation rules to detect data quality issues like duplicate transactions.

## Project Overview

FAFixed helps accountants identify and resolve data quality issues in their clients' financial data by:
1. Integrating with Xero to pull transaction history
2. Running configurable validation rules against the data
3. Presenting issues through an intuitive dashboard interface

## Architecture & Structure

### Domain-Driven App Structure
- **`core/`** - Base models (Account, User profiles) and shared utilities
- **`shared/`** - Common models and utilities shared across domains
- **`connections/`** - OAuth integration and API connection management
- **`financial_data/`** - Transaction storage, Xero sync, and financial data management
- **`data_quality/`** - Validation rules system and data quality checks
- **`fafixed/`** - Django project configuration

### Multi-App Refactoring (95% Complete)
The project has been refactored from a monolithic `integrations/` app into focused domain apps:
- **Phase 1-3**: ✅ Model decomposition, service layer creation, view decomposition
- **Phase 4**: 🔄 Final cleanup and monolith removal

### Key Models

**Integration Flow:**
- `Account` (core) � `Integration` � `IntegrationCredential` (encrypted OAuth tokens)
- `Integration` � `TransactionData` � `TransactionLineItem`
- `Integration` � `ValidationRun` � `Issue`

**Transaction Data Model:**
- Multi-tenant through `Integration` � `Account`
- `TransactionData` stores bank transactions from Xero with rich metadata
- Fields: amount, date, reference, description, contact, status, etc.
- `TransactionLineItem` for detailed breakdowns

**Validation System:**
- `ValidationRuleConfig` - per-integration rule settings  
- `ValidationRun` - tracks validation execution
- `Issue` - stores detected problems

## Xero Integration Implementation

**OAuth Flow:**
1. `xero_connect` creates `Integration` and `OAuthState` token
2. User redirected to Xero OAuth
3. `xero_callback` completes OAuth, saves credentials
4. User selects client organizations to monitor
5. Transactions synced for selected orgs

**Data Sync:**
- `XeroIntegrationService` handles API calls with automatic token refresh
- Syncs bank transactions with full transaction details and line items
- Supports full, incremental, and daily sync modes
- Rate limiting and error handling built-in

## Extensible Validation Rules System

### Plugin-Based Architecture
The validation system uses a plugin architecture to support unlimited rule types:

**Core Components:**
- `ValidationRulePlugin` base class for all rule types
- `ValidationPluginRegistry` for automatic plugin discovery
- `ValidationRuleInstance` model for user-configured rule instances
- Plugin-specific configuration forms and UI templates

### Rule Type Categories

**System Validation Rules** (`data_quality/validation/rule_types/simple/`)
- Duplicate transaction detection
- Missing data validation  
- Suspicious amount patterns
- Data integrity checks

**User-Configurable Rules** (`data_quality/validation/rule_types/user_configurable/`)
- Custom categorization rules with visual condition builder
- Contact matching and assignment rules
- Reference formatting and standardization
- Business logic automation

**AI-Powered Rules** (`data_quality/validation/rule_types/ai_powered/`)
- Agentic expense categorization
- Pattern-based anomaly detection
- Fraud detection algorithms
- Machine learning-based classification

**Integration Rules** (`data_quality/validation/rule_types/integrations/`)
- External service validations
- Compliance checking
- Third-party data enrichment
- Cross-platform synchronization

### Extensibility Features
- **Plugin Interface**: Each rule type defines its own configuration UI, validation logic, and execution behavior
- **Auto-Discovery**: New rule types are automatically registered when added to the rule_types directory
- **Type-Specific UIs**: Simple rules use basic forms, user rules use visual builders, AI rules have model configuration interfaces
- **Scalable Management**: Rules organized by category and capability in the management dashboard
- **Future-Ready**: Architecture supports any validation pattern - from simple checks to complex agentic AI workflows

## Current UI Structure

**Existing Views:**
- `dashboard.html` - Main dashboard showing integrations and issues
- `transaction_list.html` - Paginated transaction table for an integration
- Xero-specific: connect, callback, chart accounts selection

**Dashboard Features:**
- Sidebar with connected accounts and issue summary
- Main area shows active issues with severity badges
- Issues display: title, description, category, affected integration

**Transaction List:**
- Table format with date, description, type, amount, status, contact
- Pagination for large datasets
- Color-coded by transaction type (spend/receive/transfer)

## Data Flow for Validation Rules

1. **Integration Setup**: User connects Xero, selects client orgs
2. **Transaction Sync**: `XeroIntegrationService` pulls transactions into `TransactionData`
3. **Validation Execution**: 
   - Manual or automatic trigger
   - `ValidationEngine` runs enabled rules
   - Rules analyze `TransactionData` for integration
4. **Issue Creation**: Failed validations create `Issue` records
5. **Dashboard Display**: Issues shown on dashboard with details

## Key Implementation Notes

**Security:**
- OAuth tokens encrypted in `IntegrationCredential`
- CSRF protection with `OAuthState` tokens
- Multi-tenant isolation through `Account` relationships

**Performance:**
- Database indexes on key fields (integration, date, status)
- Pagination for large datasets
- Background task support for sync operations

**Extensibility:**
- Plugin system for validation rules
- Service registry for different integration providers
- Configurable rule parameters per integration

## Technical Stack
- Django 5.2.5 with PostgreSQL
- Celery for background tasks
- Xero Python SDK for API integration
- Tailwind CSS for styling
- Stimulus for JavaScript interactions

## Development Setup

1. Install dependencies: `uv sync`
2. Set up environment variables (see `.env.example`)
3. Run migrations: `uv run python manage.py migrate`
4. Start development server: `uv run python manage.py runserver`

## Testing

Run tests with improved output formatting:
```bash
uv run python manage.py test
```

The project uses a custom test runner (`core.test_runner.ColoredTestRunner`) that provides:
- Green dots (.) for passing tests
- Detailed red error output for failures
- Reduced noise from validation messages during test runs

## Key Files & Locations

### Domain Apps
- **Financial Data**: `financial_data/models.py` - Transaction and line item models
- **Connections**: `connections/models.py` - OAuth and API connection management
- **Data Quality**: `data_quality/validation/` - Validation rules system and engine
- **Shared**: `shared/models.py` - Common utilities and base models

### Core Services
- **Xero Integration**: `connections/services/xero_service.py` - Xero API operations
- **Validation Engine**: `data_quality/validation/engine.py` - Rule execution framework
- **Plugin Registry**: `data_quality/validation/registry.py` - Rule type management

### Validation Rules
- **Rule Plugins**: `data_quality/validation/rule_types/` - All validation rule implementations
- **Duplicate Detection**: `data_quality/validation/rule_types/simple/duplicates.py`
- **User Rules**: `data_quality/validation/rule_types/user_configurable/`
- **AI Rules**: `data_quality/validation/rule_types/ai_powered/`

### Views & Templates
- **Domain Views**: Each app has focused views (`connections/views.py`, `financial_data/views.py`, etc.)
- **Templates**: Domain-specific templates in each app's `templates/` directory

This modular foundation supports unlimited validation rule types and provides clean separation of concerns for building sophisticated financial data analysis interfaces.