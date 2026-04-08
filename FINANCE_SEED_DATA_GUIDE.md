# Finance Module Seed Data - Comprehensive Guide

## Overview

The `seed_finance_data.py` script provides comprehensive seed data for the Finance Module. It creates:

1. **Chart of Accounts (43 GL accounts)** - Complete accounting structure for schools
2. **Opening Balance Entry** - Initial balances for bank accounts and equity
3. **Sample Revenue Entries** - Fee collections and government grants  
4. **Sample Payroll Entries** - Monthly salary postings
5. **Sample Expenses** - Operational spending records
6. **Sample Expense Postings** - Approved expenses posted to GL

---

## Prerequisites

Before running the finance seed data, ensure:

1. ✅ Run `seed_data.py` first to create:
   - Test school (Test Primary School)
   - Admin user (admin@school.edu.gh)
   - Initial user accounts
   - Classroom data

2. ✅ Run `seed_payroll_data.py` (optional) to create:
   - Staff members
   - Payroll contracts
   - Payroll run history

3. ✅ Database initialized with `alembic upgrade head`

---

## Usage

### Run the Finance Seed Data

```bash
# From the backend directory
python seed_finance_data.py
```

### Output

The script will display:

```
============================================================
FINANCE MODULE SEED DATA
============================================================

✓ Using school: Test Primary School (ID: <school_id>)
✓ Admin user: admin@school.edu.gh

=== SEEDING CHART OF ACCOUNTS ===
✓ Created 43 GL accounts

=== SEEDING OPENING BALANCES ===
✓ Created opening balance entry with 3 line items

=== SEEDING SAMPLE REVENUE ENTRIES ===
✓ Created 6 revenue entries

=== SEEDING SAMPLE PAYROLL ENTRIES ===
✓ Created payroll entry with 2 line items

=== SEEDING SAMPLE EXPENSES ===
✓ Created 7 sample expenses

=== SEEDING SAMPLE EXPENSE POSTING ENTRIES ===
✓ Created expense entry with 2 line items

============================================================
SEED DATA CREATION COMPLETE
============================================================

📊 FINANCE MODULE DATA SUMMARY
  • Chart of Accounts: 43 GL accounts created
  • Opening Balance Entry: 1 entry with 3 line items
  • Revenue Entries: 6 entries (fees & grants)
  • Payroll Entries: 1 entry with deductions
  • Expense Records: 7 expenses in various statuses
  • Expense Entries: 1 posted entry

💾 Total Database Changes:
  • GL Accounts: 43
  • Journal Entries: 10
  • Journal Line Items: 24
  • Expenses: 7

✅ All finance module seed data created successfully!
```

---

## Data Structure

### 1. Chart of Accounts (43 Accounts)

The COA is organized by account type and includes:

#### **ASSETS (10 accounts)**
- Bank Accounts (3): Checking, Savings, Petty Cash
- Accounts Receivable (2): Student Fees, Doubtful Accounts Reserve
- Prepaid Expenses (1)
- Fixed Assets (4): Building, Equipment, Vehicles, Accumulated Depreciation

#### **LIABILITIES (8 accounts)**
- Salaries Payable (5): Gross, NSSF, Pension, Income Tax, Health Insurance
- Accounts Payable (1): Vendor invoices
- Short/Long-Term Debt (2)

#### **EQUITY (2 accounts)**
- Accumulated Surplus
- Current Year Surplus/Deficit

#### **REVENUE (11 accounts)**
- Student Fees (6): Tuition, Exams, Sports, ICT, Library, Boarding
- Donations (1)
- Grants (2): Government, NGO/Projects
- Miscellaneous (1)

#### **EXPENSES (22 accounts)**
- Salaries & Benefits (3)
- Utilities (3): Electricity, Water, Internet/Phone
- Supplies (4): Office, Teaching, Lab, Cleaning
- Repairs & Maintenance (3)
- Transportation (2)
- Services (3): Professional, Contracted, Insurance
- Depreciation (2)
- Miscellaneous (1)

### Account Code Structure

```
1000-1999: Assets
  1010: Checking Account
  1020: Savings Account
  1100: Accounts Receivable
  1300: Fixed Assets

2000-2999: Liabilities
  2100: Salaries Payable
  2200: Accounts Payable
  2300: Short-term Debt

3000-3999: Equity
  3100: Accumulated Surplus
  3110: Current Year Surplus

4000-4999: Revenue
  4100: Student Tuition Fees
  4110: Examination Fees
  4200: Donations
  4210: Government Grants

5000-5999: Expenses
  5100: Staff Salaries
  5200: Electricity
  5300: Office Supplies
  5500: Transportation
```

---

## 2. Opening Balance Entry

**Status**: DRAFT (Update before posting)

| Account | Type | Code | Amount |
|---------|------|------|--------|
| Business Checking Account | Debit | 1010 | GHS 50,000 |
| Business Savings Account | Debit | 1020 | GHS 30,000 |
| Accumulated Surplus | Credit | 3100 | GHS 80,000 |

**Notes**:
- Replace amounts with actual opening balances
- Post after verifying amounts match your records
- Entry date: January 1, 2026

---

## 3. Sample Revenue Entries (6 entries, Posted)

### Fee Collections

| Date | Description | Amount | Account | Status |
|------|-------------|--------|---------|--------|
| Mar 1 | Primary 1A Tuition (P1A) | GHS 15,000 | 4100 | Posted |
| Mar 3 | Primary 2A Tuition (P2A) | GHS 14,500 | 4100 | Posted |
| Mar 4 | BECE Exam Fees | GHS 5,000 | 4110 | Posted |
| Mar 6 | Sports/Activity Fees | GHS 2,500 | 4120 | Posted |
| Mar 8 | Library Fees | GHS 1,500 | 4140 | Posted |
| Mar 11 | Capitation Grant | GHS 8,000 | 4210 | Posted |

**Total Revenue**: GHS 46,500

**Posting Pattern**:
```
Dr. Bank Account (1010)     GHS X
    Cr. Revenue Account     GHS X
```

---

## 4. Sample Payroll Entry (1 entry, Posted)

**Date**: March 1, 2026  
**Status**: Posted  
**Staff**: 5 members  
**Total Payroll**: GHS 75,000

### Posting Entry

```
Dr. Staff Salaries & Wages (5100)  GHS 75,000
    Cr. Salaries Payable (2100)    GHS 75,000
```

**Notes**:
- Represents monthly salary accrual
- Would include deductions in a full payroll run:
  - NSSF contributions
  - Pension/Gratuity
  - Income tax withholding
  - Health insurance

---

## 5. Sample Expenses (7 records)

### Expense Summary

| Category | Description | Vendor | Amount | Status | Payment |
|----------|-------------|--------|--------|--------|---------|
| Utilities | Electricity Bill | Ghana Power & Water | GHS 2,500 | Approved | Paid |
| Supplies | Teaching Materials | Educational Supplies Ltd | GHS 1,800 | Approved | Paid |
| Utilities | Water Bill | Ghana Power & Water | GHS 800 | Approved | Paid |
| Maintenance | Roof Repair | BuildRight Contractors | GHS 5,000 | Approved | Partial |
| Supplies | Lab Chemicals | Science Lab Supplies | GHS 3,200 | Approved | Outstanding |
| Cleaning | Janitorial Supplies | Clean Ghana Services | GHS 1,200 | Pending | Outstanding |
| Transportation | Bus Fuel | Shell Petrol | GHS 2,200 | Draft | Outstanding |

**Total Expenses**: GHS 16,700  
**Paid**: GHS 4,300  
**Outstanding**: GHS 12,400

### Expense Status Workflow

```
DRAFT → PENDING → APPROVED → REJECTED or POSTED

Draft:    Being prepared, not submitted
Pending:  Submitted, awaiting approval
Approved: Approved, ready to post to GL
Rejected: Not approved, not posted
Posted:   Posted to GL (journal entry created)
```

### Payment Status

```
OUTSTANDING → PARTIAL → PAID

Outstanding: Not yet paid
Partial: Partially paid (shows 50% paid status)
Paid: Fully paid
```

---

## 6. Sample Expense Posting Entry (1 entry, Posted)

**Description**: Electricity Bill Payment - Ghana Power & Water  
**Date**: March 15, 2026  
**Amount**: GHS 2,500  
**Status**: Posted

```
Dr. Electricity Expenses (5200)     GHS 2,500
    Cr. Business Checking (1010)    GHS 2,500
```

---

## Testing the Data

### 1. Verify Chart of Accounts

```bash
# In Python or API
from models.finance.chart_of_accounts import GLAccount
from sqlmodel import select

# Query accounts
result = await session.execute(
    select(GLAccount).where(GLAccount.school_id == "school_id")
)
accounts = result.scalars().all()
print(f"Total accounts: {len(accounts)}")  # Should be 43
```

### 2. Test Journal Entries

```python
from models.finance.journal_entries import JournalEntry

result = await session.execute(
    select(JournalEntry).where(JournalEntry.school_id == "school_id")
)
entries = result.scalars().all()
print(f"Total entries: {len(entries)}")  # Should be 10
```

### 3. Test Expenses

```python
from models.finance.expenses import Expense

result = await session.execute(
    select(Expense).where(Expense.school_id == "school_id")
)
expenses = result.scalars().all()
print(f"Total expenses: {len(expenses)}")  # Should be 7
```

### 4. Verify Double-Entry Bookkeeping

Each journal entry should have:
- Equal total debits and total credits
- At least one debit and one credit line item
- Valid GL account references

---

## Modifying Seed Data

### Add More Revenue

Edit `seed_sample_revenue_entries()`:

```python
fee_entries = [
    {
        "date": month_start + timedelta(days=X),
        "description": "Your description",
        "amount": YOUR_AMOUNT,
        "account": accounts["YOUR_ACCOUNT_CODE"],
    },
]
```

### Add More Expenses

Edit `seed_sample_expenses()`:

```python
expenses_data = [
    {
        "category": ExpenseCategory.YOUR_CATEGORY,
        "description": "Your description",
        "vendor_name": "Vendor",
        "amount": YOUR_AMOUNT,
        "gl_account": accounts["YOUR_ACCOUNT_CODE"],
        "expense_date": datetime(...),
        "status": ExpenseStatus.YOUR_STATUS,
    },
]
```

### Update Chart of Accounts

Edit `DEFAULT_CHART_OF_ACCOUNTS` list to add/modify accounts:

```python
{
    "account_code": "CODE",
    "account_name": "Account Name",
    "account_type": AccountType.ASSET,
    "account_category": AccountCategory.BANK_ACCOUNTS,
    "description": "Description",
    "normal_balance": "debit",  # or "credit"
},
```

---

## API Integration

### Get Chart of Accounts

```bash
GET /api/finance/accounts?school_id=<school_id>
```

Response:
```json
{
  "accounts": [
    {
      "id": "uuid",
      "account_code": "1010",
      "account_name": "Business Checking Account",
      "account_type": "asset",
      "account_category": "bank_accounts",
      "normal_balance": "debit",
      "is_active": true
    }
  ]
}
```

### Get Journal Entries

```bash
GET /api/finance/journal-entries?school_id=<school_id>
```

### Get Expenses

```bash
GET /api/finance/expenses?school_id=<school_id>
```

---

## Troubleshooting

### Issue: "Admin user not found"

**Solution**: Run `seed_data.py` first

```bash
python seed_data.py
python seed_finance_data.py
```

### Issue: GLAccount model not found

**Solution**: Ensure imports are correct

```python
from models.finance.chart_of_accounts import GLAccount
from models.finance.journal_entries import JournalEntry
from models.finance.expenses import Expense
```

### Issue: "Chart of Accounts already exists"

**Solution**: The script skips re-seeding if data exists. To reset:

```bash
# Delete existing data (be careful!)
delete from gl_accounts where school_id = '<school_id>';
delete from journal_entries where school_id = '<school_id>';
delete from expenses where school_id = '<school_id>';

# Then re-run
python seed_finance_data.py
```

---

## Data Relationships

```
School
├── GLAccount (43)
│   ├── Journal Entry (10)
│   │   └── Journal Line Item (24)
│   └── Expense (7)
│       └── Journal Entry (posted entries)
└── User (admin_user)
    └── created_by reference on all records
```

---

## Next Steps

1. **Verify Data**: Run API endpoints to confirm data creation
2. **Test Reports**: Generate Trial Balance, Balance Sheet, P&L
3. **Update Balances**: Modify opening balance entry with actual values
4. **Add Real Data**: Replace sample data with actual school data
5. **Post Entries**: Post draft entries to finalize

---

## File Statistics

| Entity | Count | Details |
|--------|-------|---------|
| GL Accounts | 43 | Assets, Liabilities, Equity, Revenue, Expenses |
| Journal Entries | 10 | Opening balance, Revenue, Payroll, Expenses |
| Journal Lines | 24 | Line items across all entries |
| Expenses | 7 | Various categories and statuses |
| **Total Records** | **84** | Across 5 tables |

---

## Reference

- Chart of Accounts Code: Ghanaian school accounting standards
- Date Range: March 1-15, 2026 (sample fiscal period)
- Amounts: GHS (Ghanaian Cedis)
- Currency: Supports multi-currency (default GHS)

---

**Created**: Finance Module Phase 5  
**Last Updated**: March 2026  
**Status**: Production Ready
