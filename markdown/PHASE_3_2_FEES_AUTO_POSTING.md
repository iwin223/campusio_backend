"""Phase 3.2 Implementation - Fees Auto-posting Integration

This document describes the auto-posting integration between the Fees module
and the General Ledger (Finance module).

## What Was Implemented

When a fee payment is recorded in the system, the system now automatically:

1. Creates a journal entry in DRAFT status
2. Validates GL accounts exist and are active
3. Posts the entry to GL immediately (DRAFT → POSTED)
4. Links the entry to the fee payment via reference_id

## GL Posting Structure

When a fee payment is recorded, the following GL accounts are charged:

**Debit (Asset):**
- 1010 (Business Checking Account): Payment amount received

**Credit (Revenue) - Based on Fee Type:**
- 4100 (Student Tuition Fees): For tuition fees
- 4110 (Examination Fees): For examination fees
- 4120 (Sports Fees): For sports fees
- 4130 (ICT Fees): For ICT/computer fees
- 4140 (Library Fees): For library fees
- 4150 (PTA Levy): For PTA contributions
- 4160 (Maintenance Fees): For maintenance fees
- 4100 (default): For other fee types

## Accounting Equation Maintained

The system ensures debits = credits:
  Payment Received = Revenue Recognized
  
Example:
  Student submits 500 GHS for tuition fee
  
  Debit: 500 (1010 - Business Checking Account)
  Credit: 500 (4100 - Student Tuition Fees)
  
  Net effect: School has 500 GHS more cash and 500 GHS more revenue

## Files Modified

1. backend/routers/fees.py
   - Added JournalEntryCreate, JournalLineItemCreate, ReferenceType imports
   - Modified record_payment() to call _create_fee_journal_entry()
   - Added _create_fee_journal_entry() helper function (160+ lines)
   - Includes GL account mapping by fee type
   - Includes comprehensive GL account validation

## Key Features

- **Automatic**: No manual GL entries needed
- **Fee Type Mapping**: Different revenue accounts by fee type
- **Validated**: Checks GL accounts exist and are active
- **Auditable**: Links to fee payment via reference_id
- **Atomic**: GL posting fails gracefully (payment still recorded, logged for reconciliation)
- **Payment Method Tracking**: Captures payment method in audit trail
- **System-Generated**: Marked as created_by="SYSTEM" and posted_by="SYSTEM"

## Integration Points

The integration happens in:
- Endpoint: POST /api/fees/payments
- Service: record_payment() endpoint
- Called from: Fees router (requires SUPER_ADMIN or SCHOOL_ADMIN)

## GL Account Requirements

The following GL accounts must exist and be active for fee auto-posting:

- 1010: Business Checking Account (Asset)
- 4100: Student Tuition Fees (Revenue)
- 4110: Examination Fees (Revenue)
- 4120: Sports Fees (Revenue)
- 4130: ICT Fees (Revenue)
- 4140: Library Fees (Revenue)
- 4150: PTA Levy (Revenue)
- 4160: Maintenance Fees (Revenue)

These are created by default in seed_default_chart_of_accounts()

## Fee Type Mapping

| Fee Type | GL Account | Account Name |
|----------|-----------|--------------|
| tuition | 4100 | Student Tuition Fees |
| examination | 4110 | Examination Fees |
| sports | 4120 | Sports Fees |
| ict | 4130 | ICT Fees |
| library | 4140 | Library Fees |
| pta | 4150 | PTA Levy |
| maintenance | 4160 | Maintenance Fees |
| other | 4100 | Student Tuition Fees (default) |

## Error Handling

If a GL account is not found or is inactive:
- Journal entry creation fails with descriptive error
- Fee payment is still recorded (data integrity priority)
- Error is logged for manual reconciliation
- Response includes warning if GL posting failed

## Testing Checklist

- [ ] Create fee structure (e.g., tuition)
- [ ] Assign fee to student
- [ ] Record fee payment
  - Check: Journal entry created automatically
  - Check: Entry in POSTED status (not DRAFT)
  - Check: Debits equal credits
  - Check: Reference type = "fee_payment"
  - Check: Reference ID = payment_id
  - Check: Revenue account matches fee type (4100 for tuition, etc.)
- [ ] Verify GL balances:
  - Get trial balance for school
  - 1010 should have debit = total payments received
  - 4100 should have credit = total tuition collected
  - 4110/4120/etc. should have appropriate amounts
- [ ] List journal entries filtered by reference_type=fee_payment
  - Should show the newly created entry
- [ ] Test partial payment
  - Record partial payment
  - Record final payment
  - Verify separate GL entries for each payment

## Next Phase

Phase 4.1 will implement Expense Models & Router:
- Track school expenses (utilities, supplies, maintenance, etc.)
- Link expenses to GL accounts
- Potential Phase 4.2: Auto-posting expenses to GL

## Reference Data

### Fee Types Supported
- tuition: Main school fees for academic instruction
- examination: Fees for mid-term and end-of-term exams
- sports: Sports and physical education activities
- ict: Computer lab and IT resources
- library: Library access and resources
- maintenance: School facilities maintenance
- pta: Parent-Teacher Association contributions
- other: Miscellaneous fees

### Payment Methods Tracked
- cash: Cash payment
- bank_transfer: Bank transfer
- mobile_money: Mobile money transfer
- cheque: Cheque payment
"""

# ==================== EXAMPLE FEE POSTING ====================

"""
Scenario: Multiple fee payments received
Date: 2026-04-01

Payment 1: Student John (Tuition)
Amount: 3,000 GHS
Receipt: RCP-20260401-A1B2C3D4

Journal Entry #J002
Line Items:
  1. Dr. 1010 (Business Checking Account) 3,000 GHS
  2. Cr. 4100 (Student Tuition Fees) 3,000 GHS

Status: POSTED

---

Payment 2: Student Jane (Examination)
Amount: 500 GHS  
Receipt: RCP-20260401-E5F6G7H8

Journal Entry #J003
Line Items:
  1. Dr. 1010 (Business Checking Account) 500 GHS
  2. Cr. 4110 (Examination Fees) 500 GHS

Status: POSTED

---

Trial Balance Check:
- 1010 (Debit): 3,500 GHS (total deposits)
- 4100 (Credit): 3,000 GHS (tuition revenue)
- 4110 (Credit): 500 GHS (exam revenue)

Total Debit: 3,500
Total Credit: 3,500
Status: BALANCED ✓
"""
