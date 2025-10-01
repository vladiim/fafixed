# Comprehensive Accounting Integration & Business Context System - Technical Implementation Spec

## 🚧 **CURRENT IMPLEMENTATION STATUS** (Updated: 2025-10-01)

### ✅ **COMPLETED WORK - PHASE 1 FOUNDATION (100% Complete)**

#### **1. Database Models - ALL IMPLEMENTED & MIGRATED ✅**

**Location:** `/Users/vlad/code/fafixed/financial_data/models.py`

All 7 core accounting models have been implemented, tested, and migrated to the database:

1. **`Contact`** (prefix: `cnt_`) - ✅ COMPLETE
   - Customers, suppliers, employees with full contact information
   - Address fields, tax information, payment terms, credit limits
   - Multi-tenant isolation via AccountingData base class
   - Migration: `0004_add_accounting_models.py`

2. **`ChartOfAccountsEntry`** (prefix: `coa_`) - ✅ COMPLETE
   - Complete chart of accounts with account types and business categories
   - Tax handling, system account flags, active/inactive status
   - Unique constraint on (integration, code)
   - Migration: `0004_add_accounting_models.py`

3. **`SalesInvoice`** (prefix: `inv_`) - ✅ COMPLETE
   - Sales invoices with complete financial details
   - Status tracking (draft, sent, paid, overdue, etc.)
   - Date tracking (invoice_date, due_date, payment dates)
   - Currency handling with exchange rates
   - Overdue calculation properties (is_overdue, days_overdue)
   - Migration: `0004_add_accounting_models.py`

4. **`InvoiceLineItem`** (prefix: `iln_`) - ✅ COMPLETE
   - Detailed invoice line items with quantities, pricing, discounts
   - Tax information per line item
   - Chart of accounts linkage
   - Tracking categories (Xero's 2-category limit supported)
   - Proper ordering by line_number
   - Migration: `0004_add_accounting_models.py`

5. **`PurchaseBill`** (prefix: `pbi_`) - ✅ COMPLETE
   - Purchase bills/invoices from suppliers
   - Similar structure to SalesInvoice but for accounts payable
   - Status tracking and payment management
   - Migration: `0005_add_purchase_bills_and_payment_reconciliation.py`

6. **`BillLineItem`** (prefix: `bln_`) - ✅ COMPLETE
   - Line items for purchase bills
   - Complete pricing, tax, and tracking category support
   - Migration: `0005_add_purchase_bills_and_payment_reconciliation.py`

7. **`InvoicePayment`** (prefix: `pmt_`) - ✅ COMPLETE
   - Links bank transactions to invoices for reconciliation
   - Payment status tracking (pending, matched, partial, overpaid, unmatched)
   - Reconciliation confidence scoring (0.0 to 1.0)
   - User tracking (reconciled_by, reconciled_at)
   - Migration: `0005_add_purchase_bills_and_payment_reconciliation.py`

#### **2. Multi-Tenant Architecture - ✅ COMPLETE**

**Location:** `/Users/vlad/code/fafixed/financial_data/models.py` (lines 7-43)

- ✅ `AccountingDataQuerySet` - Tenant-scoped query filtering
  - `for_account(account)` - Filter by account
  - `for_user(user)` - Filter by user's accounts

- ✅ `AccountingDataManager` - Custom manager with built-in tenant isolation
  - Automatic queryset scoping
  - Security by default

- ✅ `AccountingData` abstract base class
  - Enforces account/integration consistency in save() method
  - Raises ValidationError if account mismatch detected
  - All accounting models inherit from this base

#### **3. Database Migrations - ✅ COMPLETE**

**Location:** `/Users/vlad/code/fafixed/financial_data/migrations/`

- ✅ `0004_add_accounting_models.py` - Contact, ChartOfAccountsEntry, SalesInvoice, InvoiceLineItem
- ✅ `0005_add_purchase_bills_and_payment_reconciliation.py` - PurchaseBill, BillLineItem, InvoicePayment

**All migrations applied successfully to database**

#### **4. Test Suite - ✅ COMPLETE & PASSING**

**Location:** `/Users/vlad/code/fafixed/financial_data/tests/test_accounting_models.py`

**Test Results: 20/20 tests passing ✅**

**Test Coverage:**
- ✅ Contact model tests (7 tests)
  - prefix_id generation and uniqueness
  - Full address formatting with missing fields handling
  - Contact type validation
  - Multi-tenant isolation
  - Account mismatch validation

- ✅ ChartOfAccountsEntry model tests (5 tests)
  - prefix_id generation
  - Account type choices validation
  - Account category choices validation
  - Code uniqueness per integration
  - Multi-tenant isolation

- ✅ SalesInvoice model tests (5 tests)
  - prefix_id generation and relationships
  - Overdue calculation logic
  - Paid invoices never overdue
  - Status choices validation
  - String representation

- ✅ InvoiceLineItem model tests (3 tests)
  - prefix_id generation with tracking categories
  - Line item ordering
  - String representation
  - Amount calculations with discounts and tax

#### **5. Service Layer - XeroAccountingMapper ✅ COMPLETE**

**Location:** `/Users/vlad/code/fafixed/financial_data/services/xero_mapper.py`

Complete Xero API → Internal Model transformation layer:

- ✅ `map_contact()` - Transform Xero contacts to Contact model
  - Contact type detection (CUSTOMER, SUPPLIER, BOTH)
  - Address and phone mapping
  - Tax information and payment terms

- ✅ `map_chart_of_accounts_entry()` - Transform Xero accounts to ChartOfAccountsEntry
  - Account type mapping (15 Xero types → 6 standard types)
  - Automatic category determination based on code ranges
  - Tax code and status mapping

- ✅ `map_sales_invoice()` - Transform Xero invoices to SalesInvoice
  - Date parsing (ISO, /Date()/ formats)
  - Decimal precision handling for financial amounts
  - Status mapping and currency handling

- ✅ `map_invoice_line_item()` - Transform line items with tracking categories
  - Discount rate percentage → decimal conversion
  - Up to 2 tracking categories (Xero limit)
  - Chart account linkage

- ✅ `map_purchase_bill()` & `map_bill_line_item()` - Bill transformations

**Test Coverage:** 18/18 tests passing ✅
- Contact mapping (customer, supplier, both types)
- Chart of accounts with category determination
- Invoice and line item mapping
- Date parsing (multiple formats)
- Tracking category handling

#### **6. Service Layer - AccountingRepository ✅ COMPLETE**

**Location:** `/Users/vlad/code/fafixed/financial_data/services/accounting_repository.py`

Complete data access layer with upsert patterns:

**Contact Operations:**
- ✅ `upsert_contact()` - Create/update by external_contact_id
- ✅ `get_contact_by_external_id()` - Lookup by Xero ID
- ✅ `get_all_contacts()` - List with type filtering

**Chart of Accounts:**
- ✅ `upsert_account_entry()` - Create/update by code
- ✅ `get_account_by_code()` - Fast code lookup
- ✅ `get_chart_of_accounts()` - Complete COA with active filtering

**Invoice Operations:**
- ✅ `upsert_sales_invoice()` - Atomic invoice + line items
- ✅ `get_invoice_by_external_id()` - With prefetch optimization
- ✅ `get_open_invoices()` - Outstanding invoices query

**Bill Operations:**
- ✅ `upsert_purchase_bill()` - Atomic bill + line items
- ✅ Chart account auto-linking for line items

**Reconciliation Helpers:**
- ✅ `get_unreconciled_transactions()` - Unmatched payments
- ✅ `create_invoice_payment()` - Link transaction to invoice
- ✅ `find_invoices_by_amount()` - Amount matching with tolerance

#### **7. Service Layer - AccountingSyncService ✅ COMPLETE**

**Location:** `/Users/vlad/code/fafixed/financial_data/services/accounting_sync.py`

Complete orchestration layer coordinating mapper + repository + Xero API:

**Core Sync Operations:**
- ✅ `sync_all_accounting_data()` - Orchestrates complete sync in proper order
  - Contacts first (needed for invoices/bills)
  - Chart of Accounts second (needed for line items)
  - Sales Invoices with line items
  - Purchase Bills with line items

- ✅ `process_contact()` - Single contact processing pipeline
- ✅ `process_chart_account()` - Single account processing
- ✅ `process_sales_invoice()` - Invoice + line items with contact auto-creation
- ✅ `process_purchase_bill()` - Bill + line items with supplier auto-creation

**Sync Result Tracking:**
- ✅ `SyncResult` dataclass - Tracks created/updated/error counts
- ✅ Error aggregation with limits to prevent memory issues
- ✅ Result merging for combined operations

**Features:**
- Atomic operations (invoice + line items in single transaction)
- Automatic contact creation if missing
- Comprehensive error handling and logging
- Support for incremental and full sync modes

#### **8. Service Layer - PaymentReconciler ✅ COMPLETE**

**Location:** `/Users/vlad/code/fafixed/financial_data/services/payment_reconciler.py`

Intelligent payment-to-invoice matching with confidence scoring:

**Matching Strategies:**
- ✅ Amount matching with tolerance (weight: 0.5)
  - Exact match: 100% confidence
  - Within 1%: 80% confidence
  - Within 5%: 50% confidence

- ✅ Invoice number in description (weight: 0.3)
  - Normalized matching (removes spaces, case-insensitive)
  - Partial number matching (e.g., "001" from "INV-001")

- ✅ Customer name in description (weight: 0.2)
  - Full name or first word matching

- ✅ Date proximity to due date (weight: 0.2)
  - Within 3 days: 100%
  - Within 7 days: 50%
  - Within 30 days: 30%

**Reconciliation Logic:**
- ✅ `find_invoice_matches()` - Returns sorted matches by confidence
- ✅ `should_auto_reconcile()` - Auto at 80%+ confidence
- ✅ `reconcile_transaction()` - Creates InvoicePayment record
- ✅ `InvoiceMatch` dataclass with confidence and reasons

**Thresholds:**
- Auto-reconcile: 80%+ confidence
- Suggest matches: 30%+ confidence

#### **9. Xero API Integration - ✅ COMPLETE**

**Location:** `/Users/vlad/code/fafixed/integrations/services/xero_service.py` (extensions)

Extended XeroIntegrationService with accounting data fetch methods:

**API Methods:**
- ✅ `fetch_contacts()` - Fetch customers/suppliers from Xero
  - Support for incremental sync with `modified_since` parameter
  - Comprehensive contact data including addresses, phones, tax info
  - Proper error handling with retry logic

- ✅ `fetch_chart_of_accounts()` - Fetch complete chart of accounts
  - All account types and categories
  - Active/inactive status filtering
  - Tax code associations

- ✅ `fetch_invoices()` - Fetch invoices (ACCREC) and bills (ACCPAY)
  - Invoice type parameter (ACCREC for sales, ACCPAY for purchases)
  - Complete line item data included
  - Contact information embedded
  - Support for incremental sync with `modified_since` parameter

**Features:**
- Built on existing `_api_call_with_retry()` pattern for reliability
- Proper OAuth2 token management
- Response normalization to dict format
- Multi-tenant isolation via tenant_id parameter

**Code Added:** ~200 lines

#### **10. Background Task Orchestration - ✅ COMPLETE**

**Location:** `/Users/vlad/code/fafixed/integrations/tasks.py` (extensions)

Created comprehensive Celery task for background accounting synchronization:

**Task: `sync_accounting_data(integration_id, sync_type='incremental')`**
- ✅ Coordinates XeroIntegrationService + AccountingSyncService
- ✅ Syncs in proper dependency order:
  1. Contacts (customers/suppliers)
  2. Chart of accounts
  3. Sales invoices with line items
  4. Purchase bills with line items

- ✅ Incremental and full sync support
  - Incremental: Uses `modified_since` to fetch only recent changes
  - Full: Complete data refresh

- ✅ Comprehensive error tracking
  - Counts synced items per entity type
  - Tracks errors per entity type
  - Returns detailed result dictionary

- ✅ Automatic retry configuration
  - Max 3 retries on failure
  - 5-minute countdown between retries
  - Proper error propagation

**Result Format:**
```python
{
    "status": "success" | "partial" | "failed",
    "contacts": {"synced": 42, "errors": 0},
    "accounts": {"synced": 150, "errors": 0},
    "invoices": {"synced": 328, "errors": 2},
    "bills": {"synced": 156, "errors": 0}
}
```

**Code Added:** ~110 lines

### ✅ **COMPLETED WORK - PHASE 2 INTEGRATION (100% Complete)**

All integration components connecting service layer to Xero API are complete:

1. ✅ **XeroIntegrationService Extensions** - 3 new API methods
2. ✅ **Celery Background Task** - Complete sync orchestration
3. ✅ **Error Handling & Retry Logic** - Production-ready reliability
4. ✅ **Incremental Sync Support** - Efficient delta updates
5. ✅ **Multi-Tenant Safety** - Proper isolation throughout

**Total Implementation:** ~310 lines (200 API methods + 110 task code)

### 🎯 **IMPLEMENTATION CHECKLIST - ALL COMPLETE**
1. ✅ ~~Create Database Migration~~ - COMPLETE
2. ✅ ~~Run Migration~~ - COMPLETE
3. ✅ ~~Run Tests~~ - COMPLETE (38/38 passing)
4. ✅ ~~Fix Test Failures~~ - COMPLETE
5. ✅ ~~Add Missing Models~~ - COMPLETE
6. ✅ ~~Run Full Test Suite~~ - COMPLETE (148/148 passing)
7. ✅ ~~Implement XeroAccountingMapper~~ - COMPLETE (18 tests)
8. ✅ ~~Implement AccountingRepository~~ - COMPLETE
9. ✅ ~~Implement AccountingSyncService~~ - COMPLETE
10. ✅ ~~Implement PaymentReconciler~~ - COMPLETE
11. ✅ ~~Extend XeroIntegrationService~~ - COMPLETE (3 API methods)
12. ✅ ~~Create Celery Task~~ - COMPLETE (background sync)

### ⏳ **NEXT STEPS** (Remaining Work)
13. **Integration Testing** - End-to-end validation with real Xero API
14. **UI Layer** - Views and templates for accounting data (Phase 4 from original spec)
15. **Advanced Features** - Analytics, forecasting, anomaly detection (Phase 5 from original spec)

### 📁 **FILES CREATED/MODIFIED - COMPLETE IMPLEMENTATION**

**Models & Migrations:**
- `/Users/vlad/code/fafixed/financial_data/models.py` - ALL 7 accounting models ✅
- `/Users/vlad/code/fafixed/financial_data/migrations/0004_add_accounting_models.py` - Applied ✅
- `/Users/vlad/code/fafixed/financial_data/migrations/0005_add_purchase_bills_and_payment_reconciliation.py` - Applied ✅

**Service Layer:**
- `/Users/vlad/code/fafixed/financial_data/services/xero_mapper.py` - XeroAccountingMapper (450 lines) ✅
- `/Users/vlad/code/fafixed/financial_data/services/accounting_repository.py` - AccountingRepository (350 lines) ✅
- `/Users/vlad/code/fafixed/financial_data/services/accounting_sync.py` - AccountingSyncService (320 lines) ✅
- `/Users/vlad/code/fafixed/financial_data/services/payment_reconciler.py` - PaymentReconciler (280 lines) ✅

**API Integration & Tasks:**
- `/Users/vlad/code/fafixed/integrations/services/xero_service.py` - Extended with 3 accounting API methods (200 lines) ✅
- `/Users/vlad/code/fafixed/integrations/tasks.py` - Added sync_accounting_data task (110 lines) ✅

**Tests:**
- `/Users/vlad/code/fafixed/financial_data/tests/test_accounting_models.py` - Model tests (20 tests) ✅
- `/Users/vlad/code/fafixed/financial_data/tests/test_xero_mapper.py` - Mapper tests (18 tests) ✅

**Total Production Code:** ~2,100 lines
**Total Tests:** 38 tests passing (148 total project tests passing)
**Implementation Progress:** ~90% complete (Core foundation + service layer + API integration done)

### 🏗️ **TECHNICAL ARCHITECTURE - COMPLETE**
- ✅ PrefixIdMixin integration complete (cnt_, coa_, inv_, iln_, pbi_, bln_, pmt_, txn_ prefixes)
- ✅ Multi-tenant isolation via AccountingData base class with validation
- ✅ Comprehensive field definitions for all accounting entities
- ✅ Proper Django model relationships and constraints
- ✅ Database indexes for performance optimization
- ✅ All unique constraints and foreign keys properly defined

## Executive Summary

This specification addresses the critical gap identified in our current transaction system: **we capture cash movements but lack business accounting context**. While we successfully sync bank transactions from Xero, we miss the complete picture of what these transactions represent in terms of sales, purchases, invoices, and proper accounting categorization.

### The Core Problem

**Current State**: Cash-based transaction tracking (when money moves)
**Required State**: Complete accrual accounting context (when obligations are created + when they're paid)

## 🔍 **Current System Analysis & Code Review**

### **✅ What's Working Well**

#### **1. Solid Multi-Tenant Foundation**
- **PrefixIdMixin Pattern**: Excellent security model using `prefix_id` for all user-facing identifiers
- **Account Isolation**: Strong tenant separation at the database level via `Account → Integration → TransactionData`
- **Service Registry Pattern**: Clean abstraction with `IntegrationServiceRegistry` and `BaseIntegrationService`
- **Encrypted Credentials**: Secure OAuth token storage with `EncryptedTextField`

#### **2. Extensible Integration Architecture**
- **Provider Abstraction**: Clean separation with extensible provider interface
- **Service Layer**: Well-defined interfaces for auth, sync, and data operations
- **Task System**: Robust Celery integration for background processing
- **Error Handling**: Comprehensive error tracking and retry logic

#### **3. Validation & Quality Framework**
- **BaseValidationRule**: Extensible pattern for business rule validation
- **Issue Aggregation**: Smart grouping and resolution tracking
- **Real-time Updates**: ActionCable integration for live dashboard updates
- **Category Detection**: AI-powered transaction categorization suggestions

### **❌ Critical Gaps Identified**

#### **1. Missing Chart of Accounts Context**
```python
# Current: Account codes without business meaning
account_code = "882"  # What is this?

# Needed: Full accounting context
account = ChartOfAccountsEntry(
    code="882",
    name="Salary Expenses",
    type="EXPENSE",
    category="PAYROLL",
    tax_code="GST_FREE"
)
```

#### **2. No Invoice Relationship Tracking**
```python
# Current: Bank transactions in isolation
bank_transaction = TransactionData(amount=1000, description="Payment received")

# Needed: Invoice-to-payment relationship
invoice = SalesInvoice(amount=1100, gst=100, customer="ABC Corp")
payment = InvoicePayment(invoice=invoice, bank_transaction=bank_transaction)
```

#### **3. Missing Tax Compliance Data**
```python
# Current: Total amounts only
transaction.amount = 1100.00

# Needed: Tax breakdown for compliance
transaction.net_amount = 1000.00
transaction.gst_amount = 100.00
transaction.total_amount = 1100.00
```

## 🏗️ **Extensible Architecture Design**

### **Design Patterns to Follow**

#### **1. Repository Pattern for Data Access**
```python
class AccountingRepository:
    """Single source of truth for accounting data"""

    def get_chart_of_accounts(self, integration: Integration) -> List[AccountEntry]:
        """Get complete chart of accounts with caching"""

    def get_invoice_by_id(self, invoice_id: str) -> Optional[Invoice]:
        """Get invoice with line items and payments"""

    def find_matching_invoices(self, transaction: TransactionData) -> List[Invoice]:
        """Find invoices that might match this payment"""
```

#### **2. Strategy Pattern for Provider-Specific Logic**
```python
class AccountingDataMapper(ABC):
    """Abstract mapper for provider-specific data transformation"""

    @abstractmethod
    def map_contact(self, raw_data: Dict) -> Contact:
        """Transform provider contact to standard format"""

    @abstractmethod
    def map_chart_of_accounts_entry(self, raw_data: Dict) -> ChartOfAccountsEntry:
        """Transform provider account to standard format"""

    @abstractmethod
    def map_sales_invoice(self, raw_data: Dict) -> SalesInvoice:
        """Transform provider sales invoice to standard format"""

    @abstractmethod
    def map_purchase_bill(self, raw_data: Dict) -> PurchaseBill:
        """Transform provider purchase bill to standard format"""

    @abstractmethod
    def map_invoice_line_item(self, raw_data: Dict) -> InvoiceLineItem:
        """Transform provider invoice line item to standard format"""

    @abstractmethod
    def map_bill_line_item(self, raw_data: Dict) -> BillLineItem:
        """Transform provider bill line item to standard format"""

class XeroAccountingMapper(AccountingDataMapper):
    """Xero-specific implementation with comprehensive mapping"""

    def __init__(self, integration: Integration):
        self.integration = integration

    def map_contact(self, raw_contact: Dict) -> Contact:
        """Map Xero contact to internal Contact model"""

        contact_data = {
            'integration': self.integration,
            'account': self.integration.account,
            'name': raw_contact.get('Name', ''),
            'email': raw_contact.get('EmailAddress', ''),
            'external_contact_id': raw_contact.get('ContactID', ''),
            'external_data': raw_contact,
        }

        # Determine contact type
        if raw_contact.get('IsSupplier') and raw_contact.get('IsCustomer'):
            contact_data['contact_type'] = 'BOTH'
        elif raw_contact.get('IsSupplier'):
            contact_data['contact_type'] = 'SUPPLIER'
        elif raw_contact.get('IsCustomer'):
            contact_data['contact_type'] = 'CUSTOMER'
        else:
            contact_data['contact_type'] = 'CUSTOMER'  # Default

        # Map address information
        if 'Addresses' in raw_contact and raw_contact['Addresses']:
            address = raw_contact['Addresses'][0]  # Use first address
            contact_data.update({
                'address_line_1': address.get('AddressLine1', ''),
                'address_line_2': address.get('AddressLine2', ''),
                'city': address.get('City', ''),
                'state': address.get('Region', ''),
                'postal_code': address.get('PostalCode', ''),
                'country': address.get('Country', ''),
            })

        # Map phone numbers
        if 'Phones' in raw_contact and raw_contact['Phones']:
            phone = raw_contact['Phones'][0]  # Use first phone
            contact_data['phone'] = phone.get('PhoneNumber', '')

        # Map tax information
        contact_data['tax_number'] = raw_contact.get('TaxNumber', '')

        # Map payment terms
        if 'PaymentTerms' in raw_contact:
            payment_terms = raw_contact['PaymentTerms']
            if 'Bills' in payment_terms:
                contact_data['default_payment_terms'] = payment_terms['Bills'].get('Day', '')
            elif 'Sales' in payment_terms:
                contact_data['default_payment_terms'] = payment_terms['Sales'].get('Day', '')

        return Contact(**contact_data)

    def map_chart_of_accounts_entry(self, raw_account: Dict) -> ChartOfAccountsEntry:
        """Map Xero account to internal ChartOfAccountsEntry model"""

        # Map Xero account types to our standard types
        type_mapping = {
            'BANK': 'ASSET',
            'CURRENT': 'ASSET',
            'CURRLIAB': 'LIABILITY',
            'DEPRECIATN': 'ASSET',
            'DIRECTCOSTS': 'COST_OF_SALES',
            'EQUITY': 'EQUITY',
            'EXPENSE': 'EXPENSE',
            'FIXED': 'ASSET',
            'INVENTORY': 'ASSET',
            'LIABILITY': 'LIABILITY',
            'NONCURRENT': 'ASSET',
            'OTHERINCOME': 'REVENUE',
            'OVERHEADS': 'EXPENSE',
            'PREPAYMENT': 'ASSET',
            'REVENUE': 'REVENUE',
            'SALES': 'REVENUE',
            'TERMLIAB': 'LIABILITY',
        }

        account_data = {
            'integration': self.integration,
            'account': self.integration.account,
            'code': raw_account.get('Code', ''),
            'name': raw_account.get('Name', ''),
            'account_type': type_mapping.get(raw_account.get('Type'), 'EXPENSE'),
            'external_account_id': raw_account.get('AccountID', ''),
            'external_data': raw_account,
            'is_active': raw_account.get('Status') == 'ACTIVE',
            'is_system_account': raw_account.get('SystemAccount', False),
        }

        # Map to business category based on account type and code
        account_data['category'] = self._determine_account_category(
            account_data['account_type'],
            raw_account.get('Code', ''),
            raw_account.get('Name', '')
        )

        # Map tax information
        if 'TaxType' in raw_account:
            account_data['default_tax_code'] = raw_account['TaxType']

        return ChartOfAccountsEntry(**account_data)

    def map_sales_invoice(self, raw_invoice: Dict) -> SalesInvoice:
        """Map Xero sales invoice to internal SalesInvoice model"""

        # Find or create contact
        contact = self._get_or_create_contact(raw_invoice.get('Contact', {}))

        invoice_data = {
            'integration': self.integration,
            'account': self.integration.account,
            'contact': contact,
            'invoice_type': raw_invoice.get('Type', 'ACCREC'),
            'invoice_number': raw_invoice.get('InvoiceNumber', ''),
            'reference': raw_invoice.get('Reference', ''),
            'external_invoice_id': raw_invoice.get('InvoiceID', ''),
            'external_data': raw_invoice,
        }

        # Map dates
        if 'Date' in raw_invoice:
            invoice_data['invoice_date'] = self._parse_date(raw_invoice['Date'])
        if 'DueDate' in raw_invoice:
            invoice_data['due_date'] = self._parse_date(raw_invoice['DueDate'])
        if 'ExpectedPaymentDate' in raw_invoice:
            invoice_data['expected_payment_date'] = self._parse_date(raw_invoice['ExpectedPaymentDate'])
        if 'FullyPaidOnDate' in raw_invoice:
            invoice_data['fully_paid_on_date'] = self._parse_date(raw_invoice['FullyPaidOnDate'])

        # Map financial details
        invoice_data.update({
            'currency_code': raw_invoice.get('CurrencyCode', 'AUD'),
            'currency_rate': Decimal(str(raw_invoice.get('CurrencyRate', 1.0))),
            'subtotal': Decimal(str(raw_invoice.get('SubTotal', 0))),
            'total_tax': Decimal(str(raw_invoice.get('TotalTax', 0))),
            'total_discount': Decimal(str(raw_invoice.get('TotalDiscount', 0))),
            'total_amount': Decimal(str(raw_invoice.get('Total', 0))),
            'amount_paid': Decimal(str(raw_invoice.get('AmountPaid', 0))),
            'amount_due': Decimal(str(raw_invoice.get('AmountDue', 0))),
            'amount_credited': Decimal(str(raw_invoice.get('AmountCredited', 0))),
        })

        # Map status
        status_mapping = {
            'DRAFT': 'DRAFT',
            'SUBMITTED': 'SUBMITTED',
            'AUTHORISED': 'SENT',
            'PAID': 'PAID',
            'VOIDED': 'VOIDED',
            'DELETED': 'DELETED',
        }
        invoice_data['status'] = status_mapping.get(raw_invoice.get('Status'), 'DRAFT')

        # Additional fields
        invoice_data.update({
            'line_amount_types': raw_invoice.get('LineAmountTypes', 'Exclusive'),
            'has_attachments': raw_invoice.get('HasAttachments', False),
            'has_errors': raw_invoice.get('HasErrors', False),
            'url': raw_invoice.get('Url', ''),
            'branding_theme_id': raw_invoice.get('BrandingThemeID', ''),
        })

        return SalesInvoice(**invoice_data)

    def map_invoice_line_item(self, raw_line_item: Dict) -> InvoiceLineItem:
        """Map Xero invoice line item to internal InvoiceLineItem model"""

        line_item_data = {
            'item_code': raw_line_item.get('ItemCode', ''),
            'description': raw_line_item.get('Description', ''),
            'account_code': raw_line_item.get('AccountCode', ''),
            'quantity': Decimal(str(raw_line_item.get('Quantity', 1))),
            'unit_amount': Decimal(str(raw_line_item.get('UnitAmount', 0))),
            'discount_rate': Decimal(str(raw_line_item.get('DiscountRate', 0))),
            'discount_amount': Decimal(str(raw_line_item.get('DiscountAmount', 0))),
            'line_amount': Decimal(str(raw_line_item.get('LineAmount', 0))),
            'tax_type': raw_line_item.get('TaxType', ''),
            'tax_amount': Decimal(str(raw_line_item.get('TaxAmount', 0))),
            'external_line_item_id': raw_line_item.get('LineItemID', ''),
            'external_data': raw_line_item,
        }

        # Map tracking categories
        if 'Tracking' in raw_line_item:
            tracking = raw_line_item['Tracking']
            if len(tracking) >= 1:
                track1 = tracking[0]
                line_item_data.update({
                    'tracking_category_1_id': track1.get('TrackingCategoryID', ''),
                    'tracking_category_1_name': track1.get('Name', ''),
                    'tracking_category_1_option': track1.get('Option', ''),
                })
            if len(tracking) >= 2:
                track2 = tracking[1]
                line_item_data.update({
                    'tracking_category_2_id': track2.get('TrackingCategoryID', ''),
                    'tracking_category_2_name': track2.get('Name', ''),
                    'tracking_category_2_option': track2.get('Option', ''),
                })

        return InvoiceLineItem(**line_item_data)

    def _determine_account_category(self, account_type: str, code: str, name: str) -> str:
        """Determine business category based on account details"""

        code_int = int(code) if code.isdigit() else 0

        if account_type == 'REVENUE':
            if 200 <= code_int <= 299:
                return 'SALES'
            else:
                return 'OTHER_INCOME'
        elif account_type == 'EXPENSE':
            if 300 <= code_int <= 399:
                return 'COST_OF_SALES'
            elif 'office' in name.lower():
                return 'OFFICE_EXPENSES'
            elif 'salary' in name.lower() or 'payroll' in name.lower():
                return 'PAYROLL'
            else:
                return 'GENERAL_EXPENSES'

        return account_type.upper()

    def _get_or_create_contact(self, raw_contact: Dict) -> Contact:
        """Get existing contact or create new one"""

        contact_id = raw_contact.get('ContactID')
        if not contact_id:
            # Create a basic contact if no ContactID provided
            return Contact.objects.create(
                integration=self.integration,
                account=self.integration.account,
                name=raw_contact.get('Name', 'Unknown Contact'),
                external_contact_id='',
                contact_type='CUSTOMER'
            )

        try:
            return Contact.objects.get(
                integration=self.integration,
                external_contact_id=contact_id
            )
        except Contact.DoesNotExist:
            # Contact doesn't exist yet, create it
            return Contact.objects.create(
                integration=self.integration,
                account=self.integration.account,
                name=raw_contact.get('Name', 'Unknown Contact'),
                external_contact_id=contact_id,
                contact_type='CUSTOMER'
            )

# Future providers can implement AccountingDataMapper interface
```

#### **3. Domain Event Pattern for Business Logic**
```python
class InvoicePaymentReconciled(DomainEvent):
    """Event fired when payment matches invoice"""
    invoice_id: str
    payment_id: str
    reconciliation_confidence: float

class ChartOfAccountsUpdated(DomainEvent):
    """Event fired when COA changes"""
    integration_id: str
    changed_accounts: List[str]
```

#### **4. CQRS Pattern for Read/Write Separation**
```python
# Command Side: Business operations
class ReconcileInvoicePaymentCommand:
    invoice_id: str
    payment_id: str
    user_id: str

# Query Side: Optimized reporting
class AccountingReportQuery:
    def get_sales_summary(self, integration: Integration, period: DateRange):
        """Optimized read model for sales reporting"""
```

### **Multi-Tenant Architecture Enhancements**

#### **Account-Level Data Isolation**
```python
class AccountingData(models.Model):
    """Base class for all accounting data"""
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    integration = models.ForeignKey(Integration, on_delete=models.CASCADE)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # Ensure account matches integration.account
        if self.integration.account != self.account:
            raise ValidationError("Account mismatch")
        super().save(*args, **kwargs)
```

#### **Provider Abstraction Layer**
```python
class AccountingProvider(ABC):
    """Universal interface for accounting systems"""

    @abstractmethod
    def sync_chart_of_accounts(self) -> ChartOfAccountsSync:
        """Sync complete chart of accounts"""

    @abstractmethod
    def sync_invoices(self, since: datetime) -> InvoiceSync:
        """Sync sales/purchase invoices"""

    @abstractmethod
    def sync_payments(self, since: datetime) -> PaymentSync:
        """Sync invoice payments"""

    @abstractmethod
    def reconcile_payment(self, invoice_id: str, payment_id: str) -> ReconciliationResult:
        """Link payment to invoice"""
```

## 📊 **Database Schema Design**

### **Core Accounting Models**

```python
@has_prefix_id('acc')
class ChartOfAccountsEntry(models.Model, PrefixIdMixin, AccountingData):
    """Standard chart of accounts representation"""

    ACCOUNT_TYPES = [
        ('ASSET', 'Asset'),
        ('LIABILITY', 'Liability'),
        ('EQUITY', 'Equity'),
        ('REVENUE', 'Revenue'),
        ('EXPENSE', 'Expense'),
        ('COST_OF_SALES', 'Cost of Sales'),
    ]

    ACCOUNT_CATEGORIES = [
        ('SALES', 'Sales Income'),
        ('OTHER_INCOME', 'Other Income'),
        ('OFFICE_EXPENSES', 'Office Expenses'),
        ('PAYROLL', 'Payroll Expenses'),
        ('GST_COLLECTED', 'GST Collected'),
        ('GST_PAID', 'GST Paid'),
        # ... more categories
    ]

    # Core fields
    code = models.CharField(max_length=20, db_index=True)
    name = models.CharField(max_length=200)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)
    category = models.CharField(max_length=50, choices=ACCOUNT_CATEGORIES)

    # Tax handling
    default_tax_code = models.CharField(max_length=50, blank=True)
    is_tax_account = models.BooleanField(default=False)

    # Provider-specific data
    external_account_id = models.CharField(max_length=255)
    external_data = models.JSONField(default=dict)

    # Status
    is_active = models.BooleanField(default=True)
    is_system_account = models.BooleanField(default=False)  # Can't be deleted

    class Meta:
        unique_together = ['integration', 'code']
        indexes = [
            models.Index(fields=['integration', 'account_type']),
            models.Index(fields=['integration', 'category']),
            models.Index(fields=['account', 'is_active']),
        ]

@has_prefix_id('con')
class Contact(models.Model, PrefixIdMixin, AccountingData):
    """Comprehensive contact/customer/supplier information"""

    CONTACT_TYPES = [
        ('CUSTOMER', 'Customer'),
        ('SUPPLIER', 'Supplier'),
        ('EMPLOYEE', 'Employee'),
        ('BOTH', 'Customer & Supplier'),
    ]

    TAX_TYPES = [
        ('GST_REGISTERED', 'GST Registered'),
        ('GST_FREE', 'GST Free'),
        ('EXEMPT', 'Exempt'),
        ('UNKNOWN', 'Unknown'),
    ]

    # Basic Information
    name = models.CharField(max_length=200)
    contact_type = models.CharField(max_length=20, choices=CONTACT_TYPES)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)

    # Business Details
    company_number = models.CharField(max_length=100, blank=True)  # ABN, ACN, etc.
    tax_number = models.CharField(max_length=100, blank=True)  # GST/VAT number
    tax_type = models.CharField(max_length=20, choices=TAX_TYPES, default='UNKNOWN')

    # Address Information
    address_line_1 = models.CharField(max_length=200, blank=True)
    address_line_2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True)

    # Payment Terms
    default_payment_terms = models.CharField(max_length=100, blank=True)  # "NET 30", "Due on Receipt"
    credit_limit = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    # Status
    is_active = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)

    # Provider Integration
    external_contact_id = models.CharField(max_length=255)
    external_data = models.JSONField(default=dict)  # Provider-specific fields

    # Sync tracking
    last_synced_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['integration', 'external_contact_id']
        indexes = [
            models.Index(fields=['integration', 'contact_type']),
            models.Index(fields=['integration', 'is_active']),
            models.Index(fields=['account', 'name']),
            models.Index(fields=['email']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_contact_type_display()})"

    @property
    def full_address(self):
        """Get formatted full address"""
        parts = [
            self.address_line_1,
            self.address_line_2,
            self.city,
            self.state,
            self.postal_code,
            self.country
        ]
        return ', '.join(part for part in parts if part)

@has_prefix_id('inv')
class SalesInvoice(models.Model, PrefixIdMixin, AccountingData):
    """Comprehensive sales invoices from accounting system"""

    INVOICE_STATUS = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('SENT', 'Sent'),
        ('PARTIALLY_PAID', 'Partially Paid'),
        ('PAID', 'Paid'),
        ('OVERDUE', 'Overdue'),
        ('VOIDED', 'Voided'),
        ('DELETED', 'Deleted'),
    ]

    INVOICE_TYPES = [
        ('ACCREC', 'Accounts Receivable'), # Sales Invoice
        ('ACCPAY', 'Accounts Payable'),    # Purchase Bill
        ('ACCRECEI', 'Accounts Receivable Item'), # Sales Credit Note
        ('ACCPAYI', 'Accounts Payable Item'),     # Purchase Credit Note
    ]

    # Contact/Customer Information
    contact = models.ForeignKey(Contact, on_delete=models.PROTECT, related_name='invoices')

    # Core invoice data
    invoice_type = models.CharField(max_length=20, choices=INVOICE_TYPES, default='ACCREC')
    invoice_number = models.CharField(max_length=100)
    reference = models.CharField(max_length=255, blank=True)  # Customer reference/PO number

    # Dates
    invoice_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    expected_payment_date = models.DateField(null=True, blank=True)
    fully_paid_on_date = models.DateField(null=True, blank=True)

    # Financial Details
    currency_code = models.CharField(max_length=3, default='AUD')
    currency_rate = models.DecimalField(max_digits=10, decimal_places=6, default=1.0)

    # Amounts (all in invoice currency)
    subtotal = models.DecimalField(max_digits=15, decimal_places=2)
    total_tax = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_discount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    amount_due = models.DecimalField(max_digits=15, decimal_places=2)
    amount_credited = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Payment Terms
    payment_terms = models.CharField(max_length=100, blank=True)

    # Status and Classification
    status = models.CharField(max_length=20, choices=INVOICE_STATUS, default='DRAFT')
    has_attachments = models.BooleanField(default=False)
    has_errors = models.BooleanField(default=False)

    # Line Item Summary
    line_amount_types = models.CharField(max_length=20, default='Exclusive')  # Exclusive, Inclusive, NoTax

    # Branding and Presentation
    branding_theme_id = models.CharField(max_length=255, blank=True)
    url = models.URLField(blank=True)  # Online invoice URL

    # Provider Integration
    external_invoice_id = models.CharField(max_length=255)
    external_data = models.JSONField(default=dict)

    # Tracking
    last_synced_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['integration', 'external_invoice_id']
        indexes = [
            models.Index(fields=['integration', 'status']),
            models.Index(fields=['integration', 'invoice_date']),
            models.Index(fields=['integration', 'invoice_type']),
            models.Index(fields=['contact', 'status']),
            models.Index(fields=['account', 'status', 'due_date']),
            models.Index(fields=['invoice_number']),
        ]

    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.contact.name}"

    @property
    def is_overdue(self):
        """Check if invoice is overdue"""
        if not self.due_date or self.status in ['PAID', 'VOIDED', 'DELETED']:
            return False
        return timezone.now().date() > self.due_date and self.amount_due > 0

    @property
    def days_overdue(self):
        """Calculate days overdue"""
        if not self.is_overdue:
            return 0
        return (timezone.now().date() - self.due_date).days

@has_prefix_id('iln')
class InvoiceLineItem(models.Model, PrefixIdMixin):
    """Detailed line items for invoices"""

    invoice = models.ForeignKey(SalesInvoice, on_delete=models.CASCADE, related_name='line_items')

    # Line Item Details
    item_code = models.CharField(max_length=100, blank=True)
    description = models.TextField()

    # Chart of Accounts
    account_code = models.CharField(max_length=20)
    chart_account = models.ForeignKey(ChartOfAccountsEntry, on_delete=models.PROTECT,
                                    null=True, blank=True, related_name='invoice_line_items')

    # Quantities and Pricing
    quantity = models.DecimalField(max_digits=15, decimal_places=4, default=1)
    unit_amount = models.DecimalField(max_digits=15, decimal_places=4)
    discount_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)  # Percentage
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    line_amount = models.DecimalField(max_digits=15, decimal_places=2)  # After discount

    # Tax Information
    tax_type = models.CharField(max_length=50, blank=True)  # GST rate identifier
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Tracking Categories (Xero supports up to 2)
    tracking_category_1_id = models.CharField(max_length=255, blank=True)
    tracking_category_1_name = models.CharField(max_length=200, blank=True)
    tracking_category_1_option = models.CharField(max_length=200, blank=True)
    tracking_category_2_id = models.CharField(max_length=255, blank=True)
    tracking_category_2_name = models.CharField(max_length=200, blank=True)
    tracking_category_2_option = models.CharField(max_length=200, blank=True)

    # Provider Integration
    external_line_item_id = models.CharField(max_length=255, blank=True)
    external_data = models.JSONField(default=dict)

    # Ordering
    line_number = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['line_number']
        indexes = [
            models.Index(fields=['invoice', 'line_number']),
            models.Index(fields=['chart_account']),
            models.Index(fields=['item_code']),
        ]

    def __str__(self):
        return f"{self.invoice.invoice_number} - Line {self.line_number}: {self.description}"

@has_prefix_id('pbi')
class PurchaseBill(models.Model, PrefixIdMixin, AccountingData):
    """Purchase bills/invoices from suppliers"""

    BILL_STATUS = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('AUTHORISED', 'Authorised'),
        ('PAID', 'Paid'),
        ('VOIDED', 'Voided'),
        ('DELETED', 'Deleted'),
    ]

    # Supplier Information
    contact = models.ForeignKey(Contact, on_delete=models.PROTECT, related_name='purchase_bills')

    # Core bill data
    bill_number = models.CharField(max_length=100, blank=True)  # Our internal number
    invoice_number = models.CharField(max_length=100)  # Supplier's invoice number
    reference = models.CharField(max_length=255, blank=True)

    # Dates
    invoice_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    expected_payment_date = models.DateField(null=True, blank=True)
    fully_paid_on_date = models.DateField(null=True, blank=True)

    # Financial Details
    currency_code = models.CharField(max_length=3, default='AUD')
    currency_rate = models.DecimalField(max_digits=10, decimal_places=6, default=1.0)

    # Amounts
    subtotal = models.DecimalField(max_digits=15, decimal_places=2)
    total_tax = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    amount_due = models.DecimalField(max_digits=15, decimal_places=2)

    # Status
    status = models.CharField(max_length=20, choices=BILL_STATUS, default='DRAFT')
    has_attachments = models.BooleanField(default=False)

    # Provider Integration
    external_bill_id = models.CharField(max_length=255)
    external_data = models.JSONField(default=dict)

    # Tracking
    last_synced_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['integration', 'external_bill_id']
        indexes = [
            models.Index(fields=['integration', 'status']),
            models.Index(fields=['integration', 'invoice_date']),
            models.Index(fields=['contact', 'status']),
            models.Index(fields=['account', 'status', 'due_date']),
        ]

@has_prefix_id('bln')
class BillLineItem(models.Model, PrefixIdMixin):
    """Line items for purchase bills"""

    bill = models.ForeignKey(PurchaseBill, on_delete=models.CASCADE, related_name='line_items')

    # Line Item Details
    item_code = models.CharField(max_length=100, blank=True)
    description = models.TextField()

    # Chart of Accounts
    account_code = models.CharField(max_length=20)
    chart_account = models.ForeignKey(ChartOfAccountsEntry, on_delete=models.PROTECT,
                                    null=True, blank=True, related_name='bill_line_items')

    # Quantities and Pricing
    quantity = models.DecimalField(max_digits=15, decimal_places=4, default=1)
    unit_amount = models.DecimalField(max_digits=15, decimal_places=4)
    discount_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    line_amount = models.DecimalField(max_digits=15, decimal_places=2)

    # Tax Information
    tax_type = models.CharField(max_length=50, blank=True)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Tracking Categories
    tracking_category_1_id = models.CharField(max_length=255, blank=True)
    tracking_category_1_name = models.CharField(max_length=200, blank=True)
    tracking_category_1_option = models.CharField(max_length=200, blank=True)
    tracking_category_2_id = models.CharField(max_length=255, blank=True)
    tracking_category_2_name = models.CharField(max_length=200, blank=True)
    tracking_category_2_option = models.CharField(max_length=200, blank=True)

    # Provider Integration
    external_line_item_id = models.CharField(max_length=255, blank=True)
    external_data = models.JSONField(default=dict)

    # Ordering
    line_number = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['line_number']
        indexes = [
            models.Index(fields=['bill', 'line_number']),
            models.Index(fields=['chart_account']),
        ]

@has_prefix_id('pmt')
class InvoicePayment(models.Model, PrefixIdMixin, AccountingData):
    """Links bank transactions to invoices"""

    PAYMENT_STATUS = [
        ('PENDING', 'Pending Reconciliation'),
        ('MATCHED', 'Matched to Invoice'),
        ('PARTIAL', 'Partial Payment'),
        ('OVERPAID', 'Overpayment'),
        ('UNMATCHED', 'No Invoice Match'),
    ]

    # Relationships
    invoice = models.ForeignKey(SalesInvoice, on_delete=models.CASCADE,
                               related_name='payments', null=True, blank=True)
    bank_transaction = models.ForeignKey(TransactionData, on_delete=models.CASCADE,
                                       related_name='invoice_payments')

    # Payment details
    payment_amount = models.DecimalField(max_digits=15, decimal_places=2)
    payment_date = models.DateField()

    # Reconciliation
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='PENDING')
    reconciliation_confidence = models.FloatField(default=0.0)  # 0.0 to 1.0
    reconciled_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    reconciled_at = models.DateTimeField(null=True, blank=True)

    # Provider-specific
    external_payment_id = models.CharField(max_length=255, blank=True)
    external_data = models.JSONField(default=dict)

    class Meta:
        unique_together = ['integration', 'external_payment_id']
        indexes = [
            models.Index(fields=['integration', 'status']),
            models.Index(fields=['account', 'payment_date']),
            models.Index(fields=['bank_transaction']),
        ]

# Enhanced TransactionData with accounting context
class TransactionData(models.Model, PrefixIdMixin):
    # ... existing fields ...

    # NEW: Accounting context
    chart_account = models.ForeignKey(ChartOfAccountsEntry, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='transactions')

    # NEW: Tax breakdown
    net_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    tax_code = models.CharField(max_length=50, blank=True)

    # NEW: Business classification
    business_category = models.CharField(max_length=50, blank=True)  # SALES, PURCHASES, EXPENSES
    transaction_purpose = models.CharField(max_length=100, blank=True)  # More specific description
```

### **Enhanced Line Items with Accounting Detail**

```python
class TransactionLineItem(models.Model):
    # ... existing fields ...

    # NEW: Account mapping
    chart_account = models.ForeignKey(ChartOfAccountsEntry, null=True, blank=True,
                                    on_delete=models.SET_NULL)

    # NEW: Tax details
    net_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    tax_code = models.CharField(max_length=50, blank=True)

    # NEW: Item classification
    item_type = models.CharField(max_length=50, blank=True)  # GOODS, SERVICES, FEES
    business_purpose = models.CharField(max_length=200, blank=True)
```

## 🔄 **Service Layer Architecture**

### **Accounting Data Sync Service**

```python
class AccountingSyncService:
    """Orchestrates complete accounting data synchronization"""

    def __init__(self, integration: Integration):
        self.integration = integration
        self.provider = AccountingProviderFactory.get_provider(integration)
        self.repository = AccountingRepository(integration)
        self.mapper = self.provider.get_mapper()

    def sync_all_accounting_data(self, sync_type: str = 'incremental') -> AccountingSyncResult:
        """Complete accounting data sync in proper order"""

        result = AccountingSyncResult()

        try:
            # 1. Contacts (customers/suppliers - foundation for invoices)
            contact_result = self.sync_contacts(sync_type)
            result.merge(contact_result)

            # 2. Chart of Accounts (foundation for line items)
            coa_result = self.sync_chart_of_accounts()
            result.merge(coa_result)

            # 3. Sales Invoices (business transactions)
            invoice_result = self.sync_sales_invoices(sync_type)
            result.merge(invoice_result)

            # 4. Purchase Bills (supplier invoices)
            bill_result = self.sync_purchase_bills(sync_type)
            result.merge(bill_result)

            # 5. Bank transactions (cash movements)
            bank_result = self.sync_bank_transactions(sync_type)
            result.merge(bank_result)

            # 6. Payment reconciliation (link cash to invoices)
            reconcile_result = self.reconcile_payments()
            result.merge(reconcile_result)

            # 7. Update transaction context
            context_result = self.enhance_transaction_context()
            result.merge(context_result)

            return result

        except Exception as e:
            result.add_error(f"Sync failed: {str(e)}")
            return result

    def sync_contacts(self, sync_type: str = 'incremental') -> ContactSyncResult:
        """Sync all contacts (customers/suppliers)"""

        result = ContactSyncResult()

        try:
            # Determine sync scope
            if sync_type == 'full':
                raw_contacts = self.provider.fetch_all_contacts()
            else:
                since_date = self._get_last_sync_date('contacts')
                raw_contacts = self.provider.fetch_contacts_since(since_date)

            for raw_contact in raw_contacts:
                try:
                    contact = self.mapper.map_contact(raw_contact)
                    saved_contact = self.repository.upsert_contact(contact)
                    result.add_synced(saved_contact)

                except Exception as e:
                    result.add_error(f"Failed to sync contact {raw_contact.get('ContactID', 'unknown')}: {e}")

            return result

        except Exception as e:
            result.add_error(f"Contact sync failed: {str(e)}")
            return result

    def sync_chart_of_accounts(self) -> ChartOfAccountsSyncResult:
        """Sync complete chart of accounts structure"""

        result = ChartOfAccountsSyncResult()

        try:
            raw_accounts = self.provider.fetch_chart_of_accounts()

            for raw_account in raw_accounts:
                try:
                    account_entry = self.mapper.map_chart_of_accounts_entry(raw_account)
                    saved_account = self.repository.upsert_account_entry(account_entry)
                    result.add_synced(saved_account)

                except Exception as e:
                    result.add_error(f"Failed to sync account {raw_account.get('Code', 'unknown')}: {e}")

            return result

        except Exception as e:
            result.add_error(f"Chart of accounts sync failed: {str(e)}")
            return result

    def sync_sales_invoices(self, sync_type: str = 'incremental') -> InvoiceSyncResult:
        """Sync sales invoices with complete line item detail"""

        result = InvoiceSyncResult()

        try:
            # Determine sync scope
            if sync_type == 'full':
                raw_invoices = self.provider.fetch_all_sales_invoices()
            else:
                since_date = self._get_last_sync_date('sales_invoices')
                raw_invoices = self.provider.fetch_sales_invoices_since(since_date)

            for raw_invoice in raw_invoices:
                try:
                    # Map invoice header
                    invoice = self.mapper.map_sales_invoice(raw_invoice)
                    saved_invoice = self.repository.upsert_sales_invoice(invoice)

                    # Map and save line items
                    if 'LineItems' in raw_invoice:
                        self._sync_invoice_line_items(saved_invoice, raw_invoice['LineItems'])

                    result.add_synced(saved_invoice)

                except Exception as e:
                    result.add_error(f"Failed to sync invoice {raw_invoice.get('InvoiceNumber', 'unknown')}: {e}")

            return result

        except Exception as e:
            result.add_error(f"Sales invoice sync failed: {str(e)}")
            return result

    def sync_purchase_bills(self, sync_type: str = 'incremental') -> BillSyncResult:
        """Sync purchase bills/invoices from suppliers"""

        result = BillSyncResult()

        try:
            # Determine sync scope
            if sync_type == 'full':
                raw_bills = self.provider.fetch_all_purchase_bills()
            else:
                since_date = self._get_last_sync_date('purchase_bills')
                raw_bills = self.provider.fetch_purchase_bills_since(since_date)

            for raw_bill in raw_bills:
                try:
                    # Map bill header
                    bill = self.mapper.map_purchase_bill(raw_bill)
                    saved_bill = self.repository.upsert_purchase_bill(bill)

                    # Map and save line items
                    if 'LineItems' in raw_bill:
                        self._sync_bill_line_items(saved_bill, raw_bill['LineItems'])

                    result.add_synced(saved_bill)

                except Exception as e:
                    result.add_error(f"Failed to sync bill {raw_bill.get('InvoiceNumber', 'unknown')}: {e}")

            return result

        except Exception as e:
            result.add_error(f"Purchase bill sync failed: {str(e)}")
            return result

    def _sync_invoice_line_items(self, invoice: SalesInvoice, raw_line_items: List[Dict]):
        """Sync detailed invoice line items"""

        # Clear existing line items to ensure sync accuracy
        invoice.line_items.all().delete()

        for index, raw_line_item in enumerate(raw_line_items, 1):
            try:
                line_item = self.mapper.map_invoice_line_item(raw_line_item)
                line_item.invoice = invoice
                line_item.line_number = index

                # Link to chart of accounts
                if line_item.account_code:
                    chart_account = self.repository.get_account_by_code(line_item.account_code)
                    if chart_account:
                        line_item.chart_account = chart_account

                line_item.save()

            except Exception as e:
                logger.error(f"Failed to sync line item {index} for invoice {invoice.invoice_number}: {e}")

    def _sync_bill_line_items(self, bill: PurchaseBill, raw_line_items: List[Dict]):
        """Sync detailed bill line items"""

        # Clear existing line items to ensure sync accuracy
        bill.line_items.all().delete()

        for index, raw_line_item in enumerate(raw_line_items, 1):
            try:
                line_item = self.mapper.map_bill_line_item(raw_line_item)
                line_item.bill = bill
                line_item.line_number = index

                # Link to chart of accounts
                if line_item.account_code:
                    chart_account = self.repository.get_account_by_code(line_item.account_code)
                    if chart_account:
                        line_item.chart_account = chart_account

                line_item.save()

            except Exception as e:
                logger.error(f"Failed to sync line item {index} for bill {bill.invoice_number}: {e}")

    def reconcile_payments(self) -> PaymentReconciliationResult:
        """Automatically match payments to invoices"""

        unmatched_transactions = self.repository.get_unmatched_transactions()
        open_invoices = self.repository.get_open_invoices()

        reconciler = PaymentReconciler()

        for transaction in unmatched_transactions:
            matches = reconciler.find_invoice_matches(transaction, open_invoices)

            for match in matches:
                if match.confidence > 0.8:  # Auto-reconcile high confidence
                    self.create_payment_record(transaction, match.invoice, match.confidence)
                else:  # Flag for manual review
                    self.flag_for_manual_reconciliation(transaction, match.invoice, match.confidence)
```

### **Payment Reconciliation Engine**

```python
class PaymentReconciler:
    """Intelligent matching of payments to invoices"""

    def find_invoice_matches(self, transaction: TransactionData,
                           invoices: List[SalesInvoice]) -> List[InvoiceMatch]:
        """Find potential invoice matches for a transaction"""

        matches = []

        for invoice in invoices:
            confidence = self.calculate_match_confidence(transaction, invoice)

            if confidence > 0.3:  # Minimum threshold
                matches.append(InvoiceMatch(
                    invoice=invoice,
                    confidence=confidence,
                    match_reasons=self.get_match_reasons(transaction, invoice)
                ))

        return sorted(matches, key=lambda m: m.confidence, reverse=True)

    def calculate_match_confidence(self, transaction: TransactionData,
                                  invoice: SalesInvoice) -> float:
        """Calculate confidence score for payment-to-invoice match"""

        confidence = 0.0

        # Amount matching (most important)
        if abs(transaction.amount - invoice.amount_due) < 0.01:
            confidence += 0.5  # Exact amount match
        elif abs(transaction.amount - invoice.total_amount) < 0.01:
            confidence += 0.4  # Full amount match
        elif 0.8 <= transaction.amount / invoice.amount_due <= 1.2:
            confidence += 0.3  # Close amount match

        # Date proximity
        days_diff = abs((transaction.date - invoice.due_date).days)
        if days_diff <= 7:
            confidence += 0.2
        elif days_diff <= 30:
            confidence += 0.1

        # Customer name matching
        if invoice.customer_name.lower() in transaction.description.lower():
            confidence += 0.2

        # Invoice number in description
        if invoice.invoice_number in transaction.description:
            confidence += 0.3

        return min(confidence, 1.0)
```

## 📊 **Business Intelligence & Reporting Layer**

### **Accounting Insights Service**

```python
class AccountingInsightsService:
    """Generate business insights from accounting data"""

    def __init__(self, account: Account):
        self.account = account
        self.repository = AccountingRepository()

    def get_sales_summary(self, period: DateRange) -> SalesSummary:
        """Get comprehensive sales analysis"""

        invoices = self.repository.get_invoices_in_period(self.account, period)
        payments = self.repository.get_payments_in_period(self.account, period)

        return SalesSummary(
            total_invoiced=sum(inv.total_amount for inv in invoices),
            total_collected=sum(pmt.payment_amount for pmt in payments),
            outstanding_amount=sum(inv.amount_due for inv in invoices if inv.amount_due > 0),
            overdue_amount=sum(inv.amount_due for inv in invoices if inv.is_overdue()),
            average_payment_days=self.calculate_average_payment_days(invoices, payments),
            top_customers=self.get_top_customers(invoices),
            sales_by_category=self.group_sales_by_category(invoices),
        )

    def get_cash_flow_analysis(self, period: DateRange) -> CashFlowAnalysis:
        """Analyze cash in vs cash out"""

        transactions = self.repository.get_transactions_in_period(self.account, period)

        cash_in = sum(txn.amount for txn in transactions
                     if txn.transaction_type == 'receive')
        cash_out = sum(txn.amount for txn in transactions
                      if txn.transaction_type == 'spend')

        return CashFlowAnalysis(
            total_cash_in=cash_in,
            total_cash_out=cash_out,
            net_cash_flow=cash_in - cash_out,
            cash_in_by_category=self.group_by_category(transactions, 'receive'),
            cash_out_by_category=self.group_by_category(transactions, 'spend'),
            largest_transactions=self.get_largest_transactions(transactions),
        )
```

## 🚀 **Implementation Strategy**

### **Phase 1: Foundation (Weeks 1-2)**
```markdown
## Database Schema & Models
- [ ] Create ChartOfAccountsEntry model with PrefixIdMixin
- [ ] Create SalesInvoice model with complete invoice structure
- [ ] Create InvoicePayment model for transaction-to-invoice linking
- [ ] Enhance TransactionData with accounting context fields
- [ ] Generate and apply database migrations
- [ ] Add indexes for performance optimization

## Core Services
- [ ] Implement AccountingRepository for data access patterns
- [ ] Create AccountingSyncService for orchestrated sync
- [ ] Build XeroAccountingMapper for data transformation
- [ ] Implement PaymentReconciler for automatic matching
- [ ] Add comprehensive error handling and logging
```

### **Phase 2: Data Synchronization (Weeks 3-4)**
```markdown
## Chart of Accounts Integration
- [ ] Implement Xero Chart of Accounts API integration
- [ ] Create account mapping and categorization logic
- [ ] Build account hierarchy and relationship tracking
- [ ] Add account status management (active/inactive)

## Invoice Data Integration
- [ ] Implement Xero Sales Invoice API integration
- [ ] Create invoice line item mapping
- [ ] Build customer data synchronization
- [ ] Add invoice status tracking and updates

## Payment Reconciliation
- [ ] Implement automatic payment-to-invoice matching
- [ ] Create confidence scoring algorithm
- [ ] Build manual reconciliation interface
- [ ] Add reconciliation audit trail
```

### **Phase 3: Business Intelligence (Weeks 5-6)**
```markdown
## Enhanced Transaction Context
- [ ] Update existing transactions with chart of accounts mapping
- [ ] Add tax breakdown calculation from raw data
- [ ] Implement business categorization rules
- [ ] Create transaction purpose classification

## Reporting & Analytics
- [ ] Build AccountingInsightsService for business metrics
- [ ] Create sales summary and analysis reports
- [ ] Implement cash flow analysis and forecasting
- [ ] Add customer payment behavior analytics
```

### **Phase 4: User Interface (Weeks 7-8)**
```markdown
## Chart of Accounts Management
- [ ] Create chart of accounts viewing interface
- [ ] Build account mapping configuration UI
- [ ] Add account categorization management
- [ ] Implement account sync status monitoring

## Invoice & Payment Management
- [ ] Create invoice list and detail views
- [ ] Build payment reconciliation dashboard
- [ ] Add manual reconciliation interface
- [ ] Implement reconciliation approval workflow

## Enhanced Transaction Views
- [ ] Update transaction list with accounting context
- [ ] Add chart of accounts information display
- [ ] Show tax breakdown in transaction details
- [ ] Display invoice relationships where applicable
```

### **Phase 5: Advanced Features (Weeks 9-10)**
```markdown
## Automated Workflows
- [ ] Implement scheduled reconciliation tasks
- [ ] Create intelligent matching improvements
- [ ] Add batch reconciliation operations
- [ ] Build reconciliation confidence learning

## Multi-Provider Support
- [ ] Create provider abstraction framework
- [ ] Document extensible provider framework for future use
- [ ] Implement provider-agnostic data models
- [ ] Build provider migration capabilities

## Advanced Analytics
- [ ] Create cash flow forecasting models
- [ ] Build customer payment prediction
- [ ] Add seasonal analysis capabilities
- [ ] Implement anomaly detection for transactions
```

## 🔐 **Security & Compliance Considerations**

### **Multi-Tenant Data Isolation**
```python
class AccountingDataQuerySet(models.QuerySet):
    """Ensure all accounting data is properly scoped to account"""

    def for_account(self, account: Account):
        return self.filter(account=account)

    def for_user(self, user: User):
        return self.filter(account__account_users__user=user)

class AccountingDataManager(models.Manager):
    """Custom manager with built-in tenant isolation"""

    def get_queryset(self):
        return AccountingDataQuerySet(self.model, using=self._db)

    def for_account(self, account: Account):
        return self.get_queryset().for_account(account)
```

### **Audit Trail Requirements**
```python
class AccountingAuditLog(models.Model, PrefixIdMixin):
    """Complete audit trail for all accounting operations"""

    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    operation = models.CharField(max_length=50)  # CREATE, UPDATE, DELETE, RECONCILE
    entity_type = models.CharField(max_length=50)  # INVOICE, PAYMENT, ACCOUNT
    entity_id = models.CharField(max_length=50)  # prefix_id of affected entity

    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)

    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
```

## 🧪 **Comprehensive Testing Strategy**

### **Unit Test Coverage Requirements**

#### **Model Tests (`tests/test_models.py`)**
```python
class ContactModelTest(TestCase):
    """Test Contact model functionality"""

    def setUp(self):
        self.account = Account.objects.create(name="Test Account")
        self.integration = Integration.objects.create(
            account=self.account,
            provider_id=1,
            external_account_id="test_org",
            organization_name="Test Org"
        )

    def test_contact_creation_with_prefix_id(self):
        """Test that contacts are created with proper prefix_id"""
        contact = Contact.objects.create(
            integration=self.integration,
            account=self.account,
            name="Test Customer",
            external_contact_id="xero_123",
            contact_type="CUSTOMER"
        )

        self.assertTrue(contact.prefix_id.startswith('con_'))
        self.assertEqual(len(contact.prefix_id), 12)  # con_ + 8 chars

    def test_contact_full_address_property(self):
        """Test full address formatting"""
        contact = Contact.objects.create(
            integration=self.integration,
            account=self.account,
            name="Test Customer",
            address_line_1="123 Business St",
            city="Sydney",
            state="NSW",
            postal_code="2000",
            country="Australia"
        )

        expected = "123 Business St, Sydney, NSW, 2000, Australia"
        self.assertEqual(contact.full_address, expected)

    def test_multi_tenant_isolation(self):
        """Test that contacts are properly isolated by account"""
        other_account = Account.objects.create(name="Other Account")
        other_integration = Integration.objects.create(
            account=other_account,
            provider_id=1,
            external_account_id="other_org",
            organization_name="Other Org"
        )

        # Create contacts in different accounts
        contact1 = Contact.objects.create(
            integration=self.integration,
            account=self.account,
            name="Account 1 Customer"
        )
        contact2 = Contact.objects.create(
            integration=other_integration,
            account=other_account,
            name="Account 2 Customer"
        )

        # Verify isolation
        account1_contacts = Contact.objects.for_account(self.account)
        account2_contacts = Contact.objects.for_account(other_account)

        self.assertIn(contact1, account1_contacts)
        self.assertNotIn(contact2, account1_contacts)
        self.assertIn(contact2, account2_contacts)
        self.assertNotIn(contact1, account2_contacts)

class SalesInvoiceModelTest(TestCase):
    """Test SalesInvoice model functionality"""

    def setUp(self):
        self.account = Account.objects.create(name="Test Account")
        self.integration = Integration.objects.create(
            account=self.account,
            provider_id=1,
            external_account_id="test_org"
        )
        self.contact = Contact.objects.create(
            integration=self.integration,
            account=self.account,
            name="Test Customer",
            external_contact_id="cust_123"
        )

    def test_invoice_creation_with_relationships(self):
        """Test invoice creation with proper relationships"""
        invoice = SalesInvoice.objects.create(
            integration=self.integration,
            account=self.account,
            contact=self.contact,
            invoice_number="INV-001",
            external_invoice_id="xero_inv_123",
            subtotal=Decimal('1000.00'),
            total_tax=Decimal('100.00'),
            total_amount=Decimal('1100.00'),
            amount_due=Decimal('1100.00'),
            invoice_date=date.today()
        )

        self.assertTrue(invoice.prefix_id.startswith('inv_'))
        self.assertEqual(invoice.contact, self.contact)
        self.assertEqual(invoice.integration.account, self.account)

    def test_invoice_overdue_calculation(self):
        """Test overdue date calculation"""
        # Create overdue invoice
        overdue_invoice = SalesInvoice.objects.create(
            integration=self.integration,
            account=self.account,
            contact=self.contact,
            invoice_number="INV-OVERDUE",
            due_date=date.today() - timedelta(days=30),
            amount_due=Decimal('500.00'),
            status='SENT'
        )

        # Create current invoice
        current_invoice = SalesInvoice.objects.create(
            integration=self.integration,
            account=self.account,
            contact=self.contact,
            invoice_number="INV-CURRENT",
            due_date=date.today() + timedelta(days=30),
            amount_due=Decimal('500.00'),
            status='SENT'
        )

        self.assertTrue(overdue_invoice.is_overdue)
        self.assertEqual(overdue_invoice.days_overdue, 30)
        self.assertFalse(current_invoice.is_overdue)
        self.assertEqual(current_invoice.days_overdue, 0)

    def test_paid_invoice_not_overdue(self):
        """Test that paid invoices are never considered overdue"""
        paid_invoice = SalesInvoice.objects.create(
            integration=self.integration,
            account=self.account,
            contact=self.contact,
            invoice_number="INV-PAID",
            due_date=date.today() - timedelta(days=30),
            amount_due=Decimal('0.00'),
            status='PAID'
        )

        self.assertFalse(paid_invoice.is_overdue)

class InvoiceLineItemModelTest(TestCase):
    """Test InvoiceLineItem model functionality"""

    def setUp(self):
        self.account = Account.objects.create(name="Test Account")
        self.integration = Integration.objects.create(
            account=self.account,
            provider_id=1,
            external_account_id="test_org"
        )
        self.contact = Contact.objects.create(
            integration=self.integration,
            account=self.account,
            name="Test Customer"
        )
        self.invoice = SalesInvoice.objects.create(
            integration=self.integration,
            account=self.account,
            contact=self.contact,
            invoice_number="INV-001",
            subtotal=Decimal('1000.00'),
            total_amount=Decimal('1100.00')
        )
        self.chart_account = ChartOfAccountsEntry.objects.create(
            integration=self.integration,
            account=self.account,
            code="200",
            name="Sales Income",
            account_type="REVENUE",
            external_account_id="acc_123"
        )

    def test_line_item_creation_with_tracking(self):
        """Test line item creation with tracking categories"""
        line_item = InvoiceLineItem.objects.create(
            invoice=self.invoice,
            description="Professional Services",
            account_code="200",
            chart_account=self.chart_account,
            quantity=Decimal('10.0'),
            unit_amount=Decimal('100.00'),
            line_amount=Decimal('1000.00'),
            tracking_category_1_name="Department",
            tracking_category_1_option="Consulting",
            line_number=1
        )

        self.assertTrue(line_item.prefix_id.startswith('iln_'))
        self.assertEqual(line_item.invoice, self.invoice)
        self.assertEqual(line_item.chart_account, self.chart_account)
        self.assertEqual(line_item.tracking_category_1_name, "Department")

    def test_line_item_ordering(self):
        """Test that line items maintain proper ordering"""
        line1 = InvoiceLineItem.objects.create(
            invoice=self.invoice,
            description="Item 1",
            line_number=1,
            line_amount=Decimal('500.00')
        )
        line2 = InvoiceLineItem.objects.create(
            invoice=self.invoice,
            description="Item 2",
            line_number=2,
            line_amount=Decimal('500.00')
        )

        ordered_items = list(self.invoice.line_items.all())
        self.assertEqual(ordered_items[0], line1)
        self.assertEqual(ordered_items[1], line2)
```

#### **Service Tests (`tests/test_services.py`)**
```python
class XeroAccountingMapperTest(TestCase):
    """Test Xero data mapping functionality"""

    def setUp(self):
        self.account = Account.objects.create(name="Test Account")
        self.integration = Integration.objects.create(
            account=self.account,
            provider_id=1,
            external_account_id="test_org"
        )
        self.mapper = XeroAccountingMapper(self.integration)

    def test_contact_mapping_customer(self):
        """Test mapping Xero customer contact data"""
        raw_contact = {
            'ContactID': 'xero_123',
            'Name': 'ABC Corporation',
            'EmailAddress': 'contact@abc.com',
            'IsCustomer': True,
            'IsSupplier': False,
            'TaxNumber': '12-345-678-901',
            'Addresses': [{
                'AddressType': 'STREET',
                'AddressLine1': '123 Business St',
                'City': 'Sydney',
                'Region': 'NSW',
                'PostalCode': '2000',
                'Country': 'Australia'
            }],
            'Phones': [{
                'PhoneType': 'DEFAULT',
                'PhoneNumber': '+61 2 1234 5678'
            }]
        }

        contact = self.mapper.map_contact(raw_contact)

        self.assertEqual(contact.name, 'ABC Corporation')
        self.assertEqual(contact.email, 'contact@abc.com')
        self.assertEqual(contact.contact_type, 'CUSTOMER')
        self.assertEqual(contact.tax_number, '12-345-678-901')
        self.assertEqual(contact.address_line_1, '123 Business St')
        self.assertEqual(contact.city, 'Sydney')
        self.assertEqual(contact.phone, '+61 2 1234 5678')

    def test_contact_mapping_supplier(self):
        """Test mapping Xero supplier contact data"""
        raw_contact = {
            'ContactID': 'supplier_456',
            'Name': 'Office Supplies Ltd',
            'IsCustomer': False,
            'IsSupplier': True
        }

        contact = self.mapper.map_contact(raw_contact)
        self.assertEqual(contact.contact_type, 'SUPPLIER')

    def test_contact_mapping_both_customer_supplier(self):
        """Test mapping contact that is both customer and supplier"""
        raw_contact = {
            'ContactID': 'both_789',
            'Name': 'Dual Purpose Corp',
            'IsCustomer': True,
            'IsSupplier': True
        }

        contact = self.mapper.map_contact(raw_contact)
        self.assertEqual(contact.contact_type, 'BOTH')

    def test_chart_of_accounts_mapping(self):
        """Test mapping Xero chart of accounts data"""
        raw_account = {
            'AccountID': 'acc_123',
            'Code': '200',
            'Name': 'Sales Income',
            'Type': 'REVENUE',
            'Status': 'ACTIVE',
            'TaxType': 'OUTPUT',
            'SystemAccount': False
        }

        account = self.mapper.map_chart_of_accounts_entry(raw_account)

        self.assertEqual(account.code, '200')
        self.assertEqual(account.name, 'Sales Income')
        self.assertEqual(account.account_type, 'REVENUE')
        self.assertEqual(account.category, 'SALES')
        self.assertTrue(account.is_active)
        self.assertFalse(account.is_system_account)

    def test_sales_invoice_mapping(self):
        """Test mapping Xero sales invoice data"""
        # Create contact first
        contact = Contact.objects.create(
            integration=self.integration,
            account=self.account,
            name="Test Customer",
            external_contact_id="cust_123"
        )

        raw_invoice = {
            'InvoiceID': 'inv_456',
            'InvoiceNumber': 'INV-001',
            'Type': 'ACCREC',
            'Contact': {'ContactID': 'cust_123'},
            'Date': '/Date(1640995200000)/',  # 2022-01-01
            'DueDate': '/Date(1643673600000)/',  # 2022-02-01
            'SubTotal': 1000.00,
            'TotalTax': 100.00,
            'Total': 1100.00,
            'AmountDue': 1100.00,
            'Status': 'AUTHORISED',
            'CurrencyCode': 'AUD',
            'LineAmountTypes': 'Exclusive'
        }

        invoice = self.mapper.map_sales_invoice(raw_invoice)

        self.assertEqual(invoice.invoice_number, 'INV-001')
        self.assertEqual(invoice.contact, contact)
        self.assertEqual(invoice.subtotal, Decimal('1000.00'))
        self.assertEqual(invoice.total_tax, Decimal('100.00'))
        self.assertEqual(invoice.total_amount, Decimal('1100.00'))
        self.assertEqual(invoice.status, 'SENT')  # AUTHORISED maps to SENT

    def test_invoice_line_item_mapping(self):
        """Test mapping Xero invoice line item data"""
        raw_line_item = {
            'LineItemID': 'line_123',
            'Description': 'Professional Services',
            'Quantity': 10.0,
            'UnitAmount': 100.00,
            'LineAmount': 1000.00,
            'AccountCode': '200',
            'TaxType': 'OUTPUT',
            'TaxAmount': 100.00,
            'ItemCode': 'PROF_SERV',
            'Tracking': [
                {
                    'TrackingCategoryID': 'track1_123',
                    'Name': 'Department',
                    'Option': 'Consulting'
                },
                {
                    'TrackingCategoryID': 'track2_456',
                    'Name': 'Project',
                    'Option': 'Internal'
                }
            ]
        }

        line_item = self.mapper.map_invoice_line_item(raw_line_item)

        self.assertEqual(line_item.description, 'Professional Services')
        self.assertEqual(line_item.quantity, Decimal('10.0'))
        self.assertEqual(line_item.unit_amount, Decimal('100.00'))
        self.assertEqual(line_item.line_amount, Decimal('1000.00'))
        self.assertEqual(line_item.account_code, '200')
        self.assertEqual(line_item.tracking_category_1_name, 'Department')
        self.assertEqual(line_item.tracking_category_1_option, 'Consulting')
        self.assertEqual(line_item.tracking_category_2_name, 'Project')
        self.assertEqual(line_item.tracking_category_2_option, 'Internal')

class AccountingSyncServiceTest(TestCase):
    """Test AccountingSyncService functionality"""

    def setUp(self):
        self.account = Account.objects.create(name="Test Account")
        self.integration = Integration.objects.create(
            account=self.account,
            provider_id=1,
            external_account_id="test_org"
        )

    @patch('accounting.services.sync.AccountingProviderFactory.get_provider')
    def test_sync_contacts_success(self, mock_provider_factory):
        """Test successful contact synchronization"""
        # Mock provider and its methods
        mock_provider = Mock()
        mock_provider.fetch_all_contacts.return_value = [
            {
                'ContactID': 'contact_1',
                'Name': 'Customer 1',
                'IsCustomer': True
            },
            {
                'ContactID': 'contact_2',
                'Name': 'Supplier 1',
                'IsSupplier': True
            }
        ]
        mock_provider.get_mapper.return_value = XeroAccountingMapper(self.integration)
        mock_provider_factory.return_value = mock_provider

        service = AccountingSyncService(self.integration)
        result = service.sync_contacts('full')

        self.assertTrue(result.success)
        self.assertEqual(result.synced_count, 2)
        self.assertEqual(Contact.objects.filter(integration=self.integration).count(), 2)

    @patch('accounting.services.sync.AccountingProviderFactory.get_provider')
    def test_sync_chart_of_accounts_success(self, mock_provider_factory):
        """Test successful chart of accounts synchronization"""
        mock_provider = Mock()
        mock_provider.fetch_chart_of_accounts.return_value = [
            {
                'AccountID': 'acc_1',
                'Code': '200',
                'Name': 'Sales',
                'Type': 'REVENUE',
                'Status': 'ACTIVE'
            },
            {
                'AccountID': 'acc_2',
                'Code': '400',
                'Name': 'Office Expenses',
                'Type': 'EXPENSE',
                'Status': 'ACTIVE'
            }
        ]
        mock_provider.get_mapper.return_value = XeroAccountingMapper(self.integration)
        mock_provider_factory.return_value = mock_provider

        service = AccountingSyncService(self.integration)
        result = service.sync_chart_of_accounts()

        self.assertTrue(result.success)
        self.assertEqual(result.synced_count, 2)
        self.assertEqual(ChartOfAccountsEntry.objects.filter(integration=self.integration).count(), 2)

    @patch('accounting.services.sync.AccountingProviderFactory.get_provider')
    def test_sync_sales_invoices_with_line_items(self, mock_provider_factory):
        """Test sales invoice sync with line items"""
        # Create contact first
        contact = Contact.objects.create(
            integration=self.integration,
            account=self.account,
            name="Test Customer",
            external_contact_id="cust_123"
        )

        mock_provider = Mock()
        mock_provider.fetch_all_sales_invoices.return_value = [
            {
                'InvoiceID': 'inv_1',
                'InvoiceNumber': 'INV-001',
                'Contact': {'ContactID': 'cust_123'},
                'SubTotal': 1000.00,
                'Total': 1100.00,
                'Status': 'PAID',
                'LineItems': [
                    {
                        'Description': 'Service 1',
                        'LineAmount': 500.00,
                        'AccountCode': '200'
                    },
                    {
                        'Description': 'Service 2',
                        'LineAmount': 500.00,
                        'AccountCode': '200'
                    }
                ]
            }
        ]
        mock_provider.get_mapper.return_value = XeroAccountingMapper(self.integration)
        mock_provider_factory.return_value = mock_provider

        service = AccountingSyncService(self.integration)
        result = service.sync_sales_invoices('full')

        self.assertTrue(result.success)
        self.assertEqual(result.synced_count, 1)

        invoice = SalesInvoice.objects.get(integration=self.integration)
        self.assertEqual(invoice.line_items.count(), 2)
        self.assertEqual(invoice.line_items.first().description, 'Service 1')

class PaymentReconcilerTest(TestCase):
    """Test payment reconciliation functionality"""

    def setUp(self):
        self.account = Account.objects.create(name="Test Account")
        self.integration = Integration.objects.create(
            account=self.account,
            provider_id=1,
            external_account_id="test_org"
        )
        self.contact = Contact.objects.create(
            integration=self.integration,
            account=self.account,
            name="Test Customer"
        )
        self.reconciler = PaymentReconciler()

    def test_exact_amount_match_high_confidence(self):
        """Test that exact amount matches get high confidence"""
        invoice = SalesInvoice.objects.create(
            integration=self.integration,
            account=self.account,
            contact=self.contact,
            invoice_number="INV-001",
            total_amount=Decimal('1100.00'),
            amount_due=Decimal('1100.00'),
            due_date=date.today()
        )

        transaction = TransactionData.objects.create(
            integration=self.integration,
            amount=Decimal('1100.00'),
            date=date.today(),
            description="Payment from customer"
        )

        confidence = self.reconciler.calculate_match_confidence(transaction, invoice)
        self.assertGreaterEqual(confidence, 0.5)  # Should get points for exact amount

    def test_invoice_number_in_description_boosts_confidence(self):
        """Test that invoice number in description increases confidence"""
        invoice = SalesInvoice.objects.create(
            integration=self.integration,
            account=self.account,
            contact=self.contact,
            invoice_number="INV-001",
            total_amount=Decimal('1100.00'),
            amount_due=Decimal('1100.00')
        )

        transaction = TransactionData.objects.create(
            integration=self.integration,
            amount=Decimal('1100.00'),
            date=date.today(),
            description="Payment for INV-001"
        )

        confidence = self.reconciler.calculate_match_confidence(transaction, invoice)
        self.assertGreaterEqual(confidence, 0.8)  # Amount + invoice number = high confidence

    def test_customer_name_matching(self):
        """Test customer name matching in transaction description"""
        self.contact.name = "ABC Corporation"
        self.contact.save()

        invoice = SalesInvoice.objects.create(
            integration=self.integration,
            account=self.account,
            contact=self.contact,
            invoice_number="INV-001",
            total_amount=Decimal('1100.00'),
            amount_due=Decimal('1100.00')
        )

        transaction = TransactionData.objects.create(
            integration=self.integration,
            amount=Decimal('1100.00'),
            date=date.today(),
            description="Payment from ABC Corporation"
        )

        confidence = self.reconciler.calculate_match_confidence(transaction, invoice)
        self.assertGreaterEqual(confidence, 0.7)  # Amount + customer name

    def test_date_proximity_affects_confidence(self):
        """Test that date proximity affects confidence scoring"""
        invoice = SalesInvoice.objects.create(
            integration=self.integration,
            account=self.account,
            contact=self.contact,
            invoice_number="INV-001",
            total_amount=Decimal('1100.00'),
            amount_due=Decimal('1100.00'),
            due_date=date.today()
        )

        # Payment on due date
        transaction_on_time = TransactionData.objects.create(
            integration=self.integration,
            amount=Decimal('1100.00'),
            date=date.today(),
            description="Payment"
        )

        # Payment 30 days late
        transaction_late = TransactionData.objects.create(
            integration=self.integration,
            amount=Decimal('1100.00'),
            date=date.today() + timedelta(days=30),
            description="Payment"
        )

        confidence_on_time = self.reconciler.calculate_match_confidence(transaction_on_time, invoice)
        confidence_late = self.reconciler.calculate_match_confidence(transaction_late, invoice)

        self.assertGreater(confidence_on_time, confidence_late)
```

#### **Integration Tests (`tests/test_integration.py`)**
```python
class AccountingIntegrationTest(TransactionTestCase):
    """End-to-end integration tests"""

    def setUp(self):
        self.account = Account.objects.create(name="Test Account")
        self.user = User.objects.create_user('testuser', 'test@example.com', 'password')
        self.integration = Integration.objects.create(
            account=self.account,
            provider_id=1,
            external_account_id="test_org",
            created_by=self.user
        )

    @patch('accounting.providers.xero.XeroProvider.fetch_all_contacts')
    @patch('accounting.providers.xero.XeroProvider.fetch_chart_of_accounts')
    @patch('accounting.providers.xero.XeroProvider.fetch_all_sales_invoices')
    def test_complete_accounting_sync_workflow(self, mock_invoices, mock_accounts, mock_contacts):
        """Test complete end-to-end sync workflow"""
        # Mock Xero API responses
        mock_contacts.return_value = [
            {
                'ContactID': 'cust_1',
                'Name': 'Customer One',
                'IsCustomer': True,
                'EmailAddress': 'customer@example.com'
            }
        ]

        mock_accounts.return_value = [
            {
                'AccountID': 'acc_1',
                'Code': '200',
                'Name': 'Sales Income',
                'Type': 'REVENUE',
                'Status': 'ACTIVE'
            }
        ]

        mock_invoices.return_value = [
            {
                'InvoiceID': 'inv_1',
                'InvoiceNumber': 'INV-001',
                'Contact': {'ContactID': 'cust_1'},
                'SubTotal': 1000.00,
                'TotalTax': 100.00,
                'Total': 1100.00,
                'Status': 'PAID',
                'LineItems': [
                    {
                        'Description': 'Consulting Services',
                        'LineAmount': 1000.00,
                        'AccountCode': '200',
                        'TaxAmount': 100.00
                    }
                ]
            }
        ]

        # Run sync
        service = AccountingSyncService(self.integration)
        result = service.sync_all_accounting_data('full')

        # Verify results
        self.assertTrue(result.success)

        # Check contacts
        self.assertEqual(Contact.objects.filter(integration=self.integration).count(), 1)
        contact = Contact.objects.get(integration=self.integration)
        self.assertEqual(contact.name, 'Customer One')

        # Check chart of accounts
        self.assertEqual(ChartOfAccountsEntry.objects.filter(integration=self.integration).count(), 1)
        account = ChartOfAccountsEntry.objects.get(integration=self.integration)
        self.assertEqual(account.code, '200')

        # Check invoices
        self.assertEqual(SalesInvoice.objects.filter(integration=self.integration).count(), 1)
        invoice = SalesInvoice.objects.get(integration=self.integration)
        self.assertEqual(invoice.invoice_number, 'INV-001')
        self.assertEqual(invoice.contact, contact)

        # Check line items
        self.assertEqual(invoice.line_items.count(), 1)
        line_item = invoice.line_items.first()
        self.assertEqual(line_item.chart_account, account)
        self.assertEqual(line_item.description, 'Consulting Services')

    def test_payment_reconciliation_workflow(self):
        """Test complete payment reconciliation workflow"""
        # Create test data
        contact = Contact.objects.create(
            integration=self.integration,
            account=self.account,
            name="Test Customer"
        )

        invoice = SalesInvoice.objects.create(
            integration=self.integration,
            account=self.account,
            contact=contact,
            invoice_number="INV-001",
            total_amount=Decimal('1100.00'),
            amount_due=Decimal('1100.00'),
            due_date=date.today()
        )

        transaction = TransactionData.objects.create(
            integration=self.integration,
            amount=Decimal('1100.00'),
            date=date.today(),
            description="Payment for INV-001",
            transaction_type='receive'
        )

        # Run reconciliation
        service = AccountingSyncService(self.integration)
        result = service.reconcile_payments()

        # Verify payment was created
        self.assertTrue(result.success)
        payment = InvoicePayment.objects.get(
            invoice=invoice,
            bank_transaction=transaction
        )
        self.assertEqual(payment.status, 'MATCHED')
        self.assertGreater(payment.reconciliation_confidence, 0.8)

### **Performance Tests (`tests/test_performance.py`)**
```python
class AccountingPerformanceTest(TestCase):
    """Performance and scalability tests"""

    def setUp(self):
        self.account = Account.objects.create(name="Performance Test Account")
        self.integration = Integration.objects.create(
            account=self.account,
            provider_id=1,
            external_account_id="perf_test_org"
        )

    def test_bulk_contact_sync_performance(self):
        """Test performance with large number of contacts"""
        start_time = time.time()

        # Create 1000 contacts
        contacts_data = []
        for i in range(1000):
            contacts_data.append({
                'ContactID': f'contact_{i}',
                'Name': f'Customer {i}',
                'IsCustomer': True,
                'EmailAddress': f'customer{i}@example.com'
            })

        mapper = XeroAccountingMapper(self.integration)
        for contact_data in contacts_data:
            contact = mapper.map_contact(contact_data)
            contact.save()

        end_time = time.time()
        sync_time = end_time - start_time

        # Should complete in reasonable time (adjust threshold as needed)
        self.assertLess(sync_time, 30.0, "Bulk contact sync took too long")
        self.assertEqual(Contact.objects.filter(integration=self.integration).count(), 1000)

    def test_invoice_with_many_line_items_performance(self):
        """Test performance with invoices containing many line items"""
        contact = Contact.objects.create(
            integration=self.integration,
            account=self.account,
            name="Performance Test Customer"
        )

        invoice = SalesInvoice.objects.create(
            integration=self.integration,
            account=self.account,
            contact=contact,
            invoice_number="PERF-001",
            total_amount=Decimal('10000.00')
        )

        start_time = time.time()

        # Create 100 line items
        for i in range(100):
            InvoiceLineItem.objects.create(
                invoice=invoice,
                description=f"Line item {i}",
                line_number=i+1,
                quantity=Decimal('1.0'),
                unit_amount=Decimal('100.00'),
                line_amount=Decimal('100.00')
            )

        end_time = time.time()
        creation_time = end_time - start_time

        self.assertLess(creation_time, 5.0, "Line item creation took too long")
        self.assertEqual(invoice.line_items.count(), 100)

### **Test Coverage Requirements**
- **Minimum 95% code coverage** for all core accounting models
- **100% coverage** for data mapping functions
- **90% coverage** for service layer methods
- **Integration tests** for complete workflows
- **Performance benchmarks** for bulk operations
- **Multi-tenancy isolation tests** for all models
- **Security tests** for prefix_id generation and data access
```

## 📈 **Performance & Scalability**

### **Caching Strategy**
```python
class AccountingDataCache:
    """Redis-based caching for accounting data"""

    @staticmethod
    def get_chart_of_accounts(integration: Integration) -> List[ChartOfAccountsEntry]:
        cache_key = f"coa:{integration.prefix_id}"
        cached = cache.get(cache_key)

        if not cached:
            accounts = ChartOfAccountsEntry.objects.filter(integration=integration)
            cache.set(cache_key, accounts, timeout=3600)  # 1 hour
            return accounts

        return cached

    @staticmethod
    def invalidate_chart_of_accounts(integration: Integration):
        cache_key = f"coa:{integration.prefix_id}"
        cache.delete(cache_key)
```

### **Background Processing**
```python
@shared_task(bind=True, max_retries=3)
def sync_accounting_data_task(self, integration_id: int, sync_type: str = 'incremental'):
    """Celery task for background accounting data sync"""

    try:
        integration = Integration.objects.get(id=integration_id)
        service = AccountingSyncService(integration)

        result = service.sync_all_accounting_data(sync_type)

        if result.has_errors():
            self.retry(countdown=60 * (self.request.retries + 1))

        return result.to_dict()

    except Exception as exc:
        logger.error(f"Accounting sync failed for integration {integration_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)
```

## 🎯 **Success Metrics & KPIs**

### **Technical Metrics**
- **Data Sync Accuracy**: >99.5% successful sync operations
- **Reconciliation Accuracy**: >95% automatic payment matching success
- **Performance**: <500ms for chart of accounts queries
- **Availability**: >99.9% uptime for accounting data APIs

### **Business Metrics**
- **Complete Transaction Context**: 100% of transactions mapped to chart of accounts
- **Invoice Visibility**: All sales/purchase invoices tracked with payment status
- **Tax Compliance**: Complete GST breakdown for all applicable transactions
- **Reconciliation Efficiency**: 80% reduction in manual reconciliation time

### **User Experience Metrics**
- **Dashboard Load Time**: <2 seconds for accounting insights
- **Search Performance**: <100ms for transaction/invoice search
- **Data Freshness**: <15 minutes for accounting data sync
- **User Adoption**: >90% of users actively using accounting insights

---

## 🏁 **Migration Strategy**

### **Zero-Downtime Deployment**
1. **Phase 1**: Deploy new models with feature flags disabled
2. **Phase 2**: Backfill chart of accounts data in background
3. **Phase 3**: Enable invoice sync for new integrations only
4. **Phase 4**: Gradually enable for existing integrations
5. **Phase 5**: Enable payment reconciliation features
6. **Phase 6**: Full rollout with monitoring

### **Data Migration Plan**
```python
class AccountingDataMigration:
    """Safe migration of existing transaction data"""

    def migrate_chart_of_accounts(self, integration: Integration):
        """Extract and create chart of accounts from existing raw_data"""

        # Find unique account codes in existing transactions
        unique_accounts = TransactionData.objects.filter(
            integration=integration
        ).values('raw_data__line_items__account_code').distinct()

        # Create chart of accounts entries
        for account_data in unique_accounts:
            ChartOfAccountsEntry.objects.get_or_create(
                integration=integration,
                code=account_data['account_code'],
                defaults={'name': f"Account {account_data['account_code']}"}
            )

    def enhance_existing_transactions(self, integration: Integration):
        """Add accounting context to existing transactions"""

        transactions = TransactionData.objects.filter(integration=integration)

        for transaction in transactions:
            if transaction.raw_data and 'line_items' in transaction.raw_data:
                line_item = transaction.raw_data['line_items'][0]
                account_code = line_item.get('account_code')

                if account_code:
                    chart_account = ChartOfAccountsEntry.objects.filter(
                        integration=integration, code=account_code
                    ).first()

                    if chart_account:
                        transaction.chart_account = chart_account
                        transaction.save()
```

This comprehensive specification provides a complete roadmap for transforming the current cash-based transaction system into a full-featured accounting integration that captures the complete business context of every financial transaction.

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"content": "Review existing specs for current architecture patterns", "status": "completed", "activeForm": "Reviewing existing specs for current architecture patterns"}, {"content": "Analyze current codebase for design patterns and extensibility", "status": "completed", "activeForm": "Analyzing current codebase for design patterns and extensibility"}, {"content": "Research accounting software integration best practices", "status": "completed", "activeForm": "Researching accounting software integration best practices"}, {"content": "Design extensible architecture for chart of accounts and invoice integration", "status": "completed", "activeForm": "Designing extensible architecture for chart of accounts and invoice integration"}, {"content": "Create comprehensive implementation specification", "status": "completed", "activeForm": "Creating comprehensive implementation specification"}]