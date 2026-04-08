"""Common Journal Entry Examples and Templates

These are example journal entries showing how transactions are recorded
using double-entry bookkeeping for Ghanaian schools.

Each entry maintains the accounting equation:
  Debits = Credits

Templates are provided for common transactions:
1. Student Fee Payment
2. Payroll Processing
3. Expense Recording
4. Bank Transfer
5. Period End Adjustments
"""

# ==================== EXAMPLE 1: Student Fee Payment ====================
# When a student pays GHS 500 in tuition fees in cash

STUDENT_FEE_PAYMENT_EXAMPLE = {
    "entry_date": "2026-04-01",
    "reference_type": "fee_payment",
    "reference_id": "fee_payment_123",
    "description": "Student tuition fee payment - John Doe",
    "line_items": [
        {
            "gl_account_id": "1010",  # Business Checking Account (Asset)
            "debit_amount": 500.0,
            "credit_amount": 0.0,
            "description": "Cash received from student",
            "line_number": 1,
        },
        {
            "gl_account_id": "4100",  # Student Tuition Fees (Revenue)
            "debit_amount": 0.0,
            "credit_amount": 500.0,
            "description": "Tuition fee revenue",
            "line_number": 2,
        },
    ],
    "notes": "Check reference: CHK-2026-0001",
}

# ==================== EXAMPLE 2: Payroll Processing ====================
# When processing payroll for a staff member:
# Gross: GHS 2,000
# Deductions: NSSF GHS 50, Pension GHS 100, Tax GHS 200
# Net: GHS 1,650

PAYROLL_PROCESSING_EXAMPLE = {
    "entry_date": "2026-04-15",
    "reference_type": "payroll_run",
    "reference_id": "payroll_run_202604",
    "description": "Monthly payroll - April 2026",
    "line_items": [
        {
            "gl_account_id": "5100",  # Salaries and Wages (Expense)
            "debit_amount": 2000.0,
            "credit_amount": 0.0,
            "description": "Staff gross salary expense",
            "line_number": 1,
        },
        {
            "gl_account_id": "2100",  # Salaries Payable (Liability)
            "debit_amount": 0.0,
            "credit_amount": 1650.0,
            "description": "Net salary liability to staff",
            "line_number": 2,
        },
        {
            "gl_account_id": "2110",  # NSSF Payable (Liability)
            "debit_amount": 0.0,
            "credit_amount": 50.0,
            "description": "NSSF contribution due",
            "line_number": 3,
        },
        {
            "gl_account_id": "2120",  # Pension Payable (Liability)
            "debit_amount": 0.0,
            "credit_amount": 100.0,
            "description": "Pension contribution due",
            "line_number": 4,
        },
        {
            "gl_account_id": "2130",  # Income Tax Withheld Payable (Liability)
            "debit_amount": 0.0,
            "credit_amount": 200.0,
            "description": "Income tax withholding",
            "line_number": 5,
        },
    ],
}

# ==================== EXAMPLE 3: Operating Expense ====================
# When paying for electricity bill: GHS 2,500 from bank

EXPENSE_PAYMENT_EXAMPLE = {
    "entry_date": "2026-04-05",
    "reference_type": "expense",
    "reference_id": "expense_123",
    "description": "Monthly electricity bill payment",
    "line_items": [
        {
            "gl_account_id": "5200",  # Utilities - Electricity (Expense)
            "debit_amount": 2500.0,
            "credit_amount": 0.0,
            "description": "Electricity expense for April",
            "line_number": 1,
        },
        {
            "gl_account_id": "1010",  # Business Checking Account (Asset)
            "debit_amount": 0.0,
            "credit_amount": 2500.0,
            "description": "Payment from checking account",
            "line_number": 2,
        },
    ],
    "notes": "Invoice: ECG-2026-04-001, Reference: TRNX-12345",
}

# ==================== EXAMPLE 4: Bank Transfer ====================
# Transfer GHS 10,000 from checking to savings account

BANK_TRANSFER_EXAMPLE = {
    "entry_date": "2026-04-10",
    "reference_type": "manual",
    "reference_id": None,
    "description": "Transfer funds from checking to savings",
    "line_items": [
        {
            "gl_account_id": "1020",  # Business Savings Account (Asset)
            "debit_amount": 10000.0,
            "credit_amount": 0.0,
            "description": "Deposit to savings",
            "line_number": 1,
        },
        {
            "gl_account_id": "1010",  # Business Checking Account (Asset)
            "debit_amount": 0.0,
            "credit_amount": 10000.0,
            "description": "Withdrawal from checking",
            "line_number": 2,
        },
    ],
    "notes": "Reserve fund buildup",
}

# ==================== EXAMPLE 5: Period End Depreciation ====================
# Monthly depreciation on building: GHS 500

DEPRECIATION_POSTING_EXAMPLE = {
    "entry_date": "2026-04-30",
    "reference_type": "depreciation",
    "reference_id": None,
    "description": "April 2026 depreciation expense",
    "line_items": [
        {
            "gl_account_id": "5700",  # Depreciation Expense (Expense)
            "debit_amount": 500.0,
            "credit_amount": 0.0,
            "description": "Monthly building depreciation",
            "line_number": 1,
        },
        {
            "gl_account_id": "1330",  # Accumulated Depreciation - Building (Asset contra)
            "debit_amount": 0.0,
            "credit_amount": 500.0,
            "description": "Accumulated depreciation reserve",
            "line_number": 2,
        },
    ],
}

# ==================== EXAMPLE 6: Donation Receipt ====================
# School receives cash donation: GHS 5,000

DONATION_RECEIPT_EXAMPLE = {
    "entry_date": "2026-04-12",
    "reference_type": "manual",
    "reference_id": None,
    "description": "Cash donation received",
    "line_items": [
        {
            "gl_account_id": "1010",  # Business Checking Account (Asset)
            "debit_amount": 5000.0,
            "credit_amount": 0.0,
            "description": "Donation cash received",
            "line_number": 1,
        },
        {
            "gl_account_id": "4200",  # Donations (Revenue)
            "debit_amount": 0.0,
            "credit_amount": 5000.0,
            "description": "Unrestricted donation",
            "line_number": 2,
        },
    ],
    "notes": "Donor: ABC Company Ltd",
}

# ==================== EXAMPLE 7: Expense Reversal (Correction) ====================
# Wrong entry was posted, now creating the reverse (contra-entry)
# This shows how corrections are handled

REVERSAL_ENTRY_EXAMPLE = {
    "entry_date": "2026-04-15",
    "reference_type": "adjustment",
    "reference_id": "journal_entry_456",  # Link to entry being reversed
    "description": "Reversal of incorrect posting - See reference",
    "line_items": [
        # Exactly opposite of the original entry
        {
            "gl_account_id": "5200",  # Utilities - Electricity (Expense)
            "debit_amount": 0.0,
            "credit_amount": 2500.0,  # Credit instead of debit
            "description": "Reversal of incorrect electricity charge",
            "line_number": 1,
        },
        {
            "gl_account_id": "1010",  # Business Checking Account (Asset)
            "debit_amount": 2500.0,  # Debit instead of credit
            "credit_amount": 0.0,
            "description": "Reversal of incorrect payment",
            "line_number": 2,
        },
    ],
    "notes": "Reversing duplicate entry - correct amount was already paid",
}

# ==================== Common Posting Patterns ====================
# These patterns show typical uses of GL accounts

COMMON_POSTING_PATTERNS = {
    "fee_collection": {
        "description": "Fee collection always increases cash (debit) and fee revenue (credit)",
        "accounts": [
            ("1010", "debit", "Cash in"),
            ("4100-4160", "credit", "Revenue recognition"),
        ],
    },
    "expense_payment": {
        "description": "Expense payment increases expense account (debit) and decreases cash (credit)",
        "accounts": [
            ("5000-5999", "debit", "Expense account"),
            ("1010", "credit", "Cash out"),
        ],
    },
    "payroll_accrual": {
        "description": "Payroll accrual increases expense (debit) and liability (credit)",
        "accounts": [
            ("5100-5110", "debit", "Salary expense"),
            ("2100-2130", "credit", "Payroll liabilities"),
        ],
    },
    "payroll_payment": {
        "description": "Payroll payment decreases liability (debit) and cash (credit)",
        "accounts": [
            ("2100-2130", "debit", "Pay down liability"),
            ("1010", "credit", "Cash disbursement"),
        ],
    },
}
