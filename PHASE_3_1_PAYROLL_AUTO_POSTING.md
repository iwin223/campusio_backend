"""Phase 3.1 Implementation - Payroll Auto-posting Integration

This document describes the auto-posting integration between the Payroll module
and the General Ledger (Finance module).

## What Was Implemented

When a payroll run is posted (status: APPROVED → POSTED), the system now automatically:

1. Creates a journal entry in DRAFT status
2. Validates GL accounts exist and are active
3. Posts the entry to GL immediately (DRAFT → POSTED)
4. Links the entry to the payroll run via reference_id

## GL Posting Structure

When payroll is posted, the following GL accounts are charged:

**Debit (Expense):**
- 5100 (Salaries and Wages): Full gross salary amount

**Credit (Liabilities):**
- 2100 (Salaries Payable): Net salary amount (what staff receives)
- 2110 (NSSF Payable): NSSF contributions withheld
- 2120 (Pension Payable): Pension contributions withheld
- 2130 (Income Tax Withheld Payable): Income taxes withheld

## Accounting Equation Maintained

The system ensures debits = credits:
  Gross Salary = Net Salary + Deductions
  
Example:
  Gross: 5,000
  Net: 4,000
  NSSF: 500
  Pension: 300
  Tax: 200
  
  Debit: 5,000 (5100)
  Credit: 4,000 + 500 + 300 + 200 = 5,000 (2100, 2110, 2120, 2130)

## Files Modified

1. backend/services/payroll_service.py
   - Added JournalEntryCreate, JournalLineItemCreate imports
   - Modified post_payroll_run() to call _create_payroll_journal_entry()
   - Added _create_payroll_journal_entry() method (210+ lines)
   - Includes comprehensive GL account validation

## Key Features

- **Automatic**: No manual GL entries needed
- **Validated**: Checks GL accounts exist and are active
- **Auditable**: Links to payroll run via reference_id
- **Atomic**: GL posting fails gracefully (payroll still posts, logged for manual reconciliation)
- **Deduction Breakdown**: Separates NSSF, Pension, and Tax into their own GL accounts
- **System-Generated**: Marked as created_by="SYSTEM" and posted_by="SYSTEM"

## Integration Points

The integration happens in:
- Endpoint: POST /api/payroll/runs/{run_id}/post
- Service: PayrollService.post_payroll_run()
- Called from: Payroll router (requires SUPER_ADMIN or SCHOOL_ADMIN)

## GL Account Requirements

The following GL accounts must exist and be active for payroll auto-posting:

- 5100: Salaries and Wages (Expense)
- 2100: Salaries Payable (Liability)
- 2110: NSSF Payable (Liability)
- 2120: Pension Payable (Liability)
- 2130: Income Tax Withheld Payable (Liability)

These are created by default in seed_default_chart_of_accounts()

## Error Handling

If a GL account is not found or is inactive:
- Journal entry creation fails with descriptive error
- Payroll run is still posted (data integrity priority)
- Error is logged for manual reconciliation
- Response includes warning if GL posting failed

## Testing Checklist

- [ ] Create payroll run in DRAFT status
- [ ] Approve payroll run (DRAFT → APPROVED)
- [ ] Post payroll run (APPROVED → POSTED)
  - Check: Journal entry created automatically
  - Check: Entry in POSTED status (not DRAFT)
  - Check: Debits equal credits
  - Check: Reference type = "payroll_run"
  - Check: Reference ID = payroll_run_id
- [ ] Verify GL balances:
  - Get trial balance for school
  - 5100 should have debit = payroll gross
  - 2100 should have credit = payroll net
  - 2110/2120/2130 should have appropriate amounts
- [ ] List journal entries filtered by reference_type=payroll_run
  - Should show the newly created entry

## Next Phase

Phase 3.2 will implement similar auto-posting for Fee Payments:
- When fee payment recorded → Create journal entry
- Dr. Bank Account (1010) / Cr. Fee Revenue (4100)
"""

# ==================== EXAMPLE PAYROLL POSTING ====================

"""
Scenario: Payroll run for January 2026
- 10 staff members
- Total gross: 50,000 GHS
- Total deductions:
  - NSSF: 5,000 GHS
  - Pension: 3,000 GHS
  - Tax: 2,000 GHS
- Total net: 40,000 GHS

Expected GL posting:

Journal Entry #J001
Date: 2026-01-31
Reference: payroll_run_001
Status: POSTED

Line Items:
  1. Dr. 5100 (Salaries and Wages) 50,000 GHS
  2. Cr. 2100 (Salaries Payable) 40,000 GHS
  3. Cr. 2110 (NSSF Payable) 5,000 GHS
  4. Cr. 2120 (Pension Payable) 3,000 GHS
  5. Cr. 2130 (Income Tax) 2,000 GHS

Total Debit: 50,000 GHS
Total Credit: 50,000 GHS
Status: BALANCED ✓

This posting ensures:
- Expense recognized for full salary cost
- Liabilities registered for what's owed
  - To staff (Salaries Payable)
  - To government/pension fund (NSSF/Pension/Tax)
- GL trial balance maintained (debits = credits)
"""
