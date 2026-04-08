# Finance Module Seed Data - Quick Reference

## 🚀 Quick Start

```bash
# Prerequisites
python seed_data.py          # Create school and users
python seed_payroll_data.py  # Create staff (optional)

# Seed finance data
python seed_finance_data.py
```

## 📊 What Gets Created

| Entity | Count | Includes |
|--------|-------|----------|
| **GL Accounts** | 43 | Assets, Liabilities, Equity, Revenue, Expenses |
| **Journal Entries** | 10 | Opening balance, revenue, payroll, expenses |
| **Journal Lines** | 24 | Debit/credit line items |
| **Expenses** | 7 | Various categories and statuses |

**Total: 84 records across 5 database tables**

---

## 🏦 Account Codes Reference

### Assets (1000-1999)
```
1010: Checking Account
1020: Savings Account  
1030: Petty Cash
1100: Accounts Receivable - Student Fees
1200: Prepaid Expenses
1300: Fixed Assets - Building
1310: Fixed Assets - Equipment
1320: Fixed Assets - Vehicles
1330: Depreciation Reserve - Building
1340: Depreciation Reserve - Equipment
```

### Liabilities (2000-2999)
```
2100: Salaries Payable
2110: NSSF Payable
2120: Pension Payable
2130: Income Tax Withheld
2140: Health Insurance Payable
2200: Accounts Payable - Vendors
2300: Short-Term Debt
2400: Long-Term Debt
```

### Equity (3000-3999)
```
3100: Accumulated Surplus
3110: Current Year Surplus/Deficit
```

### Revenue (4000-4999)
```
4100: Student Tuition Fees
4110: Examination Fees
4120: Sports/Activity Fees
4130: ICT/Technology Fees
4140: Library Fees
4150: Boarding Fees
4200: Donations & Contributions
4210: Government Grants
4220: NGO & Project Grants
4300: Miscellaneous Income
```

### Expenses (5000-5999)
```
5100: Staff Salaries & Wages
5110: Staff Benefits & Allowances
5120: Staff Development & Training
5200: Electricity Expenses
5210: Water & Sanitation
5220: Internet & Telephone
5300: Office Supplies
5310: Classroom Teaching Supplies
5320: Laboratory & Science Supplies
5330: Cleaning & Maintenance Supplies
5400: Building Repairs & Maintenance
5410: Equipment Maintenance & Repairs
5420: Vehicle Maintenance
5500: Student Transport Costs
5510: Staff Transport & Travel
5600: Professional Services
5610: Contracted Services
5620: Insurance Expenses
5700: Depreciation - Building
5710: Depreciation - Equipment
5800: Miscellaneous Expenses
```

---

## 💰 Sample Data Values

### Opening Balances (DRAFT - Update before posting)
```
Dr. 1010 (Checking)    GHS 50,000
Dr. 1020 (Savings)     GHS 30,000
    Cr. 3100 (Equity)          GHS 80,000
```

### Revenue Entries (POSTED)
```
6 entries created:
- P1A Tuition:      GHS 15,000
- P2A Tuition:      GHS 14,500
- BECE Exam Fees:   GHS 5,000
- Sports Fees:      GHS 2,500
- Library Fees:     GHS 1,500
- Capitation Grant: GHS 8,000
Total:              GHS 46,500
```

### Payroll Entry (POSTED)
```
Dr. 5100 (Salaries)   GHS 75,000
    Cr. 2100 (Payable)        GHS 75,000
(5 staff members, March 2026)
```

### Expenses (Mixed Statuses)
```
Electricity:        GHS 2,500  (Approved, Paid)
Teaching Supplies:  GHS 1,800  (Approved, Paid)
Water:              GHS 800    (Approved, Paid)
Roof Repair:        GHS 5,000  (Approved, Partial)
Lab Chemicals:      GHS 3,200  (Approved, Outstanding)
Cleaning Supplies:  GHS 1,200  (Pending, Outstanding)
Bus Fuel:           GHS 2,200  (Draft, Outstanding)
Total:              GHS 16,700
```

---

## 🔗 Data Relationships

```
School
├── Created 43 GLAccounts
├── Created 10 JournalEntries
│   └── Each with 2-3 JournalLineItems
├── Created 7 Expenses
└── All linked to admin user
```

---

## ⚙️ Double-Entry Bookkeeping Rules

All journal entries follow:
```
Total Debits = Total Credits

Every entry has:
- At least 1 debit line
- At least 1 credit line
- Balanced amounts
- Valid GL account references
```

**Example**:
```
Dr. 1010 (Asset)      GHS 2,500
    Cr. 5200 (Expense)     GHS 2,500
```

---

## 📝 Expense Lifecycle

### Status Flow
```
DRAFT → PENDING → APPROVED → POSTED
                    ↓
                 REJECTED
```

### Payment Status
```
OUTSTANDING → PARTIAL → PAID
```

### Example Entry
```
Category:      Utilities
Vendor:        Ghana Power & Water
Amount:        GHS 2,500
GL Account:    5200 (Electricity)
Status:        Approved
Payment:       Paid
Posted Date:   March 2026
```

---

## 🧪 Testing Endpoints

After seeding, test these API endpoints:

### List Accounts
```bash
GET /api/finance/accounts?school_id=<school_id>
```

### Get Single Account
```bash
GET /api/finance/accounts/<account_id>
```

### List Journal Entries
```bash
GET /api/finance/journal-entries?school_id=<school_id>
```

### Get Trial Balance
```bash
GET /api/finance/reports/trial-balance?school_id=<school_id>
```

### Get Balance Sheet
```bash
GET /api/finance/reports/balance-sheet?school_id=<school_id>
```

### Get P&L Statement
```bash
GET /api/finance/reports/income-statement?school_id=<school_id>
```

### List Expenses
```bash
GET /api/finance/expenses?school_id=<school_id>
```

---

## 🐛 Common Issues & Fixes

| Issue | Cause | Solution |
|-------|-------|----------|
| Admin user not found | `seed_data.py` not run | Run `python seed_data.py` first |
| GL Account import errors | Missing model file | Check `models/finance/` exists |
| COA already exists | Script re-run | Data is idempotent, safe to re-run |
| Journal entry imbalance | Code error | Report bug with entry details |

---

## 📚 File Mapping

```
backend/
├── seed_data.py                    # Run 1st: Creates school & users
├── seed_payroll_data.py            # Run 2nd (optional): Creates staff
├── seed_finance_data.py            # Run 3rd: Creates finance data
├── FINANCE_SEED_DATA_GUIDE.md      # Detailed documentation
├── FINANCE_SEED_DATA_QUICK_REF.md  # This file
└── models/finance/
    ├── chart_of_accounts.py        # GLAccount model
    ├── journal_entries.py          # JournalEntry model
    └── expenses.py                 # Expense model
```

---

## 🎯 Execution Order

```
1. python seed_data.py
   Creates: School, Users (admin, teacher, student, parent)
   
2. python seed_payroll_data.py (optional)
   Creates: Staff, Payroll contracts
   
3. python seed_finance_data.py
   Creates: GL Accounts, Journal Entries, Expenses
```

---

## 💡 Key Features Seeded

✅ **Complete Chart of Accounts** (43 accounts)  
✅ **Opening Balance Template** (DRAFT, ready to customize)  
✅ **Revenue Entries** (fee collections, grants)  
✅ **Payroll Integration** (salary postings)  
✅ **Expense Management** (7 sample expenses)  
✅ **Audit Trail** (all records timestamped, created_by tracked)  
✅ **Double-Entry Verified** (balanced entries)  
✅ **Multi-Tenant Ready** (school_id scoped)  

---

## 🔐 Security

- All entries tied to admin user
- School isolation via school_id
- Role-based access ready (RBAC)
- Audit timestamp on all records
- No sensitive data in seed

---

## 📈 Next Steps

1. ✅ Run seed scripts
2. ✅ Verify data in database
3. ⚠️ **Update opening balances** with real values
4. ⚠️ **Post draft entry** after verification
5. Test API endpoints
6. Generate reports
7. Add real school data

---

## ℹ️ Notes

- **School**: Test Primary School
- **Admin**: admin@school.edu.gh
- **Currency**: GHS (Ghanaian Cedis)
- **Period**: March 2026 (sample data)
- **Idempotent**: Safe to run multiple times

---

**Status**: ✅ Production Ready  
**Last Updated**: March 2026  
**Finance Module**: Phase 5 Complete
