# PARENT PORTAL - FEES TAB ANALYSIS

## 📊 Overview
The Fees tab in the parent portal allows parents to view their child's fee obligations, payment status, and payment history in real-time.

---

## 🔧 API ENDPOINT

**Route**: `GET /api/parent/child/{student_id}/fees`

**Query Parameters** (optional):
- `term_id` - Filter fees by academic term

**Response Format**: JSON object

---

## 📋 DATA STRUCTURE

### Response Format:
```json
{
  "student_name": "Kofi Mensah",
  "summary": {
    "total_due": 20.00,
    "total_paid": 0.00,
    "balance": 20.00,
    "collection_rate": 0.0
  },
  "fees": [
    {
      "id": "fee_uuid",
      "fee_type": "tuition",
      "description": "",
      "amount_due": 20.00,
      "amount_paid": 0.00,
      "balance": 20.00,
      "status": "pending",
      "due_date": "2026-04-08",
      "payments": []
    }
  ]
}
```

---

## 📈 KEY METRICS

| Metric | Type | Purpose |
|--------|------|---------|
| **Total Due** | Float | Total amount owed across all fees |
| **Total Paid** | Float | Total amount already paid |
| **Balance** | Float | Outstanding amount (Due - Paid) |
| **Collection Rate** | Percentage | Percentage of fees collected (Paid/Due * 100) |

---

## 🎯 DISPLAY STRUCTURE

### Summary Section (Header)
- Shows parent's quick view of total fees
- Displays collection rate as percentage
- Highlights outstanding balance

### Fees List Section (Detailed)
Each fee displays:
1. **Fee Type** - Category (e.g., TUITION, SPORTS, LIBRARY)
2. **Description** - Additional details about the fee
3. **Amount Due** - Total fee amount
4. **Amount Paid** - Amount already collected
5. **Balance** - Remaining to pay (calculated: Due - Paid)
6. **Status** - Current status (PENDING, PARTIAL, PAID)
7. **Due Date** - Deadline for payment
8. **Payment History** - List of all payments made:
   - Receipt Number
   - Payment Amount
   - Payment Date
   - Payment Method (CASH, BANK_TRANSFER, PAYSTACK, MOMO)

---

## 💾 DATA SOURCES

### Database Tables Used:
1. **Fee** - Individual fee records per student
2. **FeeStructure** - Fee template (type, amount, description)
3. **FeePayment** - Payment records and receipts
4. **Student** - Student information
5. **StudentParent** - Parent-child relationship validation

---

## 🔐 SECURITY FEATURES

✅ **Authentication Required**: Parent must be logged in
✅ **Authorization**: Parent can only see their own children's fees
✅ **Verification**: `verify_child_access()` ensures parent-child relationship exists
✅ **School Isolation**: Data filtered by school context

---

## ⚙️ BACKEND LOGIC

### 1. Access Verification
```
Check: Is parent logged in? ✓
Check: Is student their child? ✓
Action: Allow data access
```

### 2. Data Aggregation
```
Query: Select all fees for student
Join: With FeeStructure for descriptions
Join: With FeePayment for payment history
```

### 3. Summary Calculation
```
total_due = SUM(fee.amount_due)
total_paid = SUM(fee.amount_paid)
balance = total_due - total_paid
collection_rate = (total_paid / total_due) * 100
```

### 4. Balance Per Fee
```
fee_balance = fee.amount_due - fee.amount_paid - fee.discount
```

---

## 🎛️ FILTERING OPTIONS

### Current Filters Available:
1. **By Academic Term** (optional parameter)
   - Allows parents to view fees for specific term/semester

### Possible Enhancement Filters:
- By Fee Type (tuition, sports, etc.)
- By Payment Status (pending, paid, partial)
- By Due Date Range (overdue, upcoming)

---

## 📊 CURRENT TEST DATA

**Student**: Kofi Mensah (ID: ba00550b-6c63-4322-a119-0a441df8ad47)

### Fees Overview:
| Metric | Value |
|--------|-------|
| Total Due | GHS 20.00 |
| Total Paid | GHS 0.00 |
| Outstanding | GHS 20.00 |
| Collection Rate | 0% |

### Active Fees:
1. **TUITION** - GHS 20.00
   - Status: PENDING
   - Due: 2026-04-08
   - Payments: None

---

## 🚨 POTENTIAL ISSUES & IMPROVEMENTS

### Current Limitations:

1. **No Payment Receipt Viewing**
   - Parents see payment dates but not detailed receipts
   - Recommendation: Add receipt download feature

2. **No Payment Method Initiation**
   - Parents can view balances but cannot directly pay from portal
   - Recommendation: Integrate payment gateway (already supported by PAYSTACK config)

3. **No Discounts Display**
   - Fee discount info not shown in response
   - Recommendation: Add discount details to fee items

4. **Term Filter Not Intuitive**
   - Users must know term_id format
   - Recommendation: Provide dropdown of available terms

5. **No Due Date Warning**
   - Cannot see which fees are overdue at a glance
   - Recommendation: Add "status" field (OVERDUE, UPCOMING, DUE_SOON)

### Recommended Enhancements:

```json
{
  "id": "fee_uuid",
  "fee_type": "tuition",
  "status": "overdue",  // NEW: overdue/pending/paid/partial
  "urgency": "high",    // NEW: normal/medium/high
  "due_days_remaining": -5,  // NEW: days until due
  "discount": 0.00,     // NEW: discount amount
  "discount_reason": null,  // NEW: why discount given
  "amount_due": 20.00,
  "amount_paid": 0.00,
  "balance": 20.00,
  "due_date": "2026-04-08",
  "payments": [
    {
      "receipt_number": "RCP001",
      "amount": 10.00,
      "payment_date": "2026-04-05",
      "payment_method": "CASH",
      "confirmed": true,  // NEW: payment verified
      "receipt_url": "/receipts/RCP001.pdf"  // NEW: digital receipt
    }
  ]
}
```

---

## 📱 UI/UX CONSIDERATIONS

### How Parents Interact:

1. **Dashboard/Overview**
   - See summary card: "You owe GHS X.XX for [Student Name]"
   - Quick status indicator: ✅ Paid / ⚠️ Partial / ❌ Outstanding

2. **Detailed View**
   - Click to expand and see:
     - Breakdown by fee type
     - Payment history timeline
     - Due dates and payment status

3. **Mobile Responsiveness**
   - Summary cards stack vertically
   - Fee items display cleanly
   - Payment details in collapsible sections

4. **Notifications**
   - Alert parents of upcoming due dates
   - Remind of overdue fees
   - Confirm successful payments

---

## 🔄 USER JOURNEY

```
Parent Portal Login
    ↓
Dashboard / Home
    ↓
Click "Fees" Tab
    ↓
See Summary (Total Due, Collection Rate)
    ↓
View Individual Fees
    ↓
[Option 1: Pay Now] → Payment Gateway
[Option 2: View Receipt] → Download/Print
[Option 3: Filter by Term] → Update View
```

---

## 📊 SUMMARY TABLE

| Aspect | Current Status |
|--------|-----------------|
| **Data Access** | ✅ Working - Fees retrieved correctly |
| **Parent Auth** | ✅ Working - Users verified via StudentParent link |
| **CORS** | ✅ Fixed - Headers now sent correctly |
| **Calculations** | ✅ Accurate - Math verified |
| **Payment History** | ✅ Linked - Shows all payments per fee |
| **Multi-fee Support** | ✅ Supported - Can have multiple fee types |
| **Term Filtering** | ✅ Optional - Can filter by term_id |
| **Discount Support** | ⚠️ Partial - Stored but not displayed |
| **Payment Initiation** | ❌ Missing - No direct pay option in portal |
| **Receipt Download** | ❌ Missing - No digital receipt download |
| **Overdue Alerts** | ❌ Missing - No visual urgency indicators |
| **Mobile Responsive** | ⚠️ Depends on Frontend - API supports it |

---

## ✅ VERIFICATION CHECKLIST

- [x] Endpoint exists and responds
- [x] Parent authentication successful
- [x] Child access verified
- [x] Fee data retrieved
- [x] Payment history linked
- [x] Summary calculations accurate
- [x] CORS headers present
- [ ] Payment gateway integrated
- [ ] Digital receipts generated
- [ ] Mobile UI tested
- [ ] Email notifications working
- [ ] SMS reminders configured

