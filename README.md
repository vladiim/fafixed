# FAFixed - Financial Data Quality Platform

FAFixed is a Django-based SaaS application for financial accountants that integrates with Xero to pull transaction data and run validation rules to detect data quality issues like duplicate transactions.

## Project Overview

FAFixed helps accountants identify and resolve data quality issues in their clients' financial data by:
1. Integrating with Xero to pull transaction history
2. Running configurable validation rules against the data
3. Presenting issues through an intuitive dashboard interface

## Architecture & Structure

### Core Apps
- **`core/`** - Base models (Account, User profiles) and shared utilities
- **`integrations/`** - Main functionality for external system integrations (Xero)
- **`fafixed/`** - Django project configuration

### Key Models

**Integration Flow:**
- `Account` (core) ’ `Integration` ’ `IntegrationCredential` (encrypted OAuth tokens)
- `Integration` ’ `TransactionData` ’ `TransactionLineItem`
- `Integration` ’ `ValidationRun` ’ `Issue`

**Transaction Data Model:**
- Multi-tenant through `Integration` ’ `Account`
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

## Validation Rules System

**Architecture:**
- Plugin-based system with `ValidationRuleRegistry`
- Base class `BaseValidationRule` for all rules
- Rules auto-discovered from `integrations/validation/rules/`

**Duplicate Transaction Rule:**
- Configurable matching criteria (amount, date, reference, etc.)
- Groups transactions and identifies duplicates
- Creates `Issue` records with detailed affected transaction data
- Located at `integrations/validation/rules/duplicates.py:15`

**Validation Engine:**
- `ValidationEngine.run_validation()` executes rules for an integration
- Creates `ValidationRun` records to track execution
- Converts rule results to `Issue` records
- Supports running specific rules or all enabled rules

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

- **Models**: `integrations/models.py` - Core data models
- **Xero Service**: `integrations/services/xero_service.py` - Xero API integration
- **Validation Engine**: `integrations/validation/engine.py` - Rule execution
- **Duplicate Rule**: `integrations/validation/rules/duplicates.py` - Duplicate detection
- **Views**: `integrations/views.py` - Web interface
- **Templates**: `integrations/templates/` and `templates/` - UI templates

This foundation provides a solid base for extending the validation system and building additional transaction analysis interfaces.