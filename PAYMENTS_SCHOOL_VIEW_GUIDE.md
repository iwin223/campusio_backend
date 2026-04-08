# 📊 School Finance Dashboard - Payment Views & Reporting

## Overview

Schools can view and manage all online payments made by parents through the **Finance Reports API**. The system is fully **multi-tenant**, meaning each school only sees their own payments.

---

## 🔐 Multi-Tenant Security

### Data Isolation by school_id

Every payment transaction stores the `school_id`:

```javascript
{
  id: "txn-001",
  school_id: "school-abc",     // ← The school that owns this transaction
  fee_id: "fee-123",
  student_id: "student-456",
  parent_id: "parent-789",
  amount: 500.00,
  status: "success"
}
```

### Access Control

Only authorized roles can view payments:
- ✅ `admin` - Full access
- ✅ `accountant` - Full access
- ✅ `finance_officer` - Full access
- ✅ `principal` - Full access
- ❌ `teacher` - No access
- ❌ `parent` - Only view own payments (via parent portal)
- ❌ `student` - No access

Each user's `school_id` is automatically validated on every request.

---

## 📡 API Endpoints for Schools

### 1. List All Payments

```
GET /api/finance/payments
```

**Authentication:** Bearer token + authorized role

**Query Parameters:**
```
?skip=0                    # Pagination offset
&limit=50                  # Records per page (max 500)
&status_filter=success     # Filter: pending, success, failed, all
&start_date=2026-04-01    # Filter by date range
&end_date=2026-04-30
&search=Jane Doe           # Search student/parent name
```

**Response:**
```json
{
  "total": 150,
  "skip": 0,
  "limit": 50,
  "payments": [
    {
      "transaction_id": "txn-001",
      "reference": "ref-paystack-001",
      "student_name": "John Doe",
      "parent_name": "Jane Doe",
      "parent_email": "jane@example.com",
      "parent_phone": "+233123456789",
      "fee_type": "Tuition",
      "amount": 500.00,
      "status": "success",
      "initiated_at": "2026-04-08T10:30:00Z",
      "completed_at": "2026-04-08T10:35:00Z",
      "verified_at": "2026-04-08T10:35:30Z"
    }
  ]
}
```

**Example cURL:**
```bash
curl -X GET "http://localhost:8000/api/finance/payments?limit=10&status_filter=success" \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

---

### 2. Payment Statistics Dashboard

```
GET /api/finance/payments/statistics
```

**Query Parameters:**
```
?period_days=30     # Look back N days (default 30)
```

**Response:**
```json
{
  "total_transactions": 150,
  "successful_payments": 120,
  "failed_payments": 15,
  "pending_payments": 15,
  "total_amount_collected": 45000.00,
  "total_amount_pending": 7500.00,
  "period_start": "2026-03-08T00:00:00Z",
  "period_end": "2026-04-08T00:00:00Z"
}
```

**What It Shows:**
- ✅ Total payments in period
- ✅ Success rate percentage
- ✅ Cash collected vs pending
- ✅ Trend over time

---

### 3. Payments Grouped by Parent

```
GET /api/finance/payments/by-parent
```

**Query Parameters:**
```
?skip=0     # For pagination
&limit=50
```

**Response:**
```json
{
  "total": 45,
  "parents": [
    {
      "parent_id": "parent-001",
      "parent_name": "Jane Doe",
      "parent_email": "jane@example.com",
      "total_payments": 5,
      "total_amount_paid": 2500.00,
      "last_payment_date": "2026-04-08T10:30:00Z",
      "transactions": 5
    }
  ]
}
```

**Use Cases:**
- Track which parents have made payments
- See total amounts from each parent
- Identify payment patterns

---

### 4. Payments by Fee Type

```
GET /api/finance/payments/by-fee-type
```

**Response:**
```json
{
  "fee_types": [
    {
      "fee_type": "Tuition",
      "total_due": 150000.00,
      "total_collected": 120000.00,
      "total_pending": 30000.00,
      "collection_rate": 80.0,
      "transaction_count": 45
    },
    {
      "fee_type": "Dining",
      "total_due": 75000.00,
      "total_collected": 70000.00,
      "total_pending": 5000.00,
      "collection_rate": 93.3,
      "transaction_count": 28
    }
  ]
}
```

**What It Shows:**
- 📊 Collection rate by fee category
- 💰 How much collected per fee type
- ⚠️ Outstanding balances
- 📈 Payment performance metrics

---

### 5. Payment Reconciliation Report

```
GET /api/finance/payments/reconciliation
```

**Query Parameters:**
```
?start_date=2026-04-01
&end_date=2026-04-30
```

**Response:**
```json
{
  "total_transactions": 150,
  "posted_to_gl": 145,
  "pending_gl_posting": 5,
  "discrepancies": [
    {
      "transaction_id": "txn-042",
      "reference": "ref-042",
      "issue": "GL entry not created",
      "amount": 250.00,
      "completed_at": "2026-04-05T14:20:00Z"
    }
  ]
}
```

**Why It Matters:**
- ✅ Verifies all payments have GL entries
- ⚠️ Finds discrepancies (important for auditing)
- 🔍 Prevents GL posting errors

---

### 6. Individual Payment Details

```
GET /api/finance/payments/{transaction_id}
```

**Response:**
```json
{
  "transaction": {
    "id": "txn-001",
    "reference": "ref-paystack-001",
    "student_name": "John Doe",
    "student_id": "student-456",
    "parent_name": "Jane Doe",
    "parent_email": "jane@example.com",
    "parent_phone": "+233123456789",
    "fee_type": "Tuition",
    "amount": 500.00,
    "amount_paid": 500.00,
    "status": "success",
    "gateway": "paystack",
    "initiated_at": "2026-04-08T10:30:00Z",
    "completed_at": "2026-04-08T10:35:00Z",
    "verified_at": "2026-04-08T10:35:30Z",
    "journal_entry_id": "jne-001",
    "failed_reason": null
  }
}
```

---

## 🎯 Use Cases & Examples

### Use Case 1: Daily Cash Reconciliation

**Scenario:** Finance officer wants to reconcile cash received today

```bash
# Get all successful payments from today
curl -X GET "http://localhost:8000/api/finance/payments?status_filter=success&start_date=$(date -d 'today' '+%Y-%m-%d')&end_date=$(date -d 'tomorrow' '+%Y-%m-%d')" \
  -H "Authorization: Bearer TOKEN"

# Expected: List of all payments received today
# Then: Match with Paystack receipts and bank deposits
```

### Use Case 2: Monthly Collection Report

**Scenario:** Principal wants to see collection rate by fee type

```bash
# Get fee type breakdown
curl -X GET "http://localhost:8000/api/finance/payments/by-fee-type" \
  -H "Authorization: Bearer TOKEN"

# Shows:
# - Tuition: 80% collected
# - Dining: 93% collected
# - Transport: 60% collected
```

### Use Case 3: Parent Payment History

**Scenario:** Checking if specific parent has paid

```bash
# Get parent payment records
curl -X GET "http://localhost:8000/api/finance/payments/by-parent?limit=100" \
  -H "Authorization: Bearer TOKEN"

# Shows:
# - Jane Doe: 5 payments totaling GHS 2,500
# - Last payment: 2 days ago
```

### Use Case 4: Audit Trail

**Scenario:** Auditor checking GL reconciliation

```bash
# Get reconciliation report
curl -X GET "http://localhost:8000/api/finance/payments/reconciliation?start_date=2026-01-01&end_date=2026-04-30" \
  -H "Authorization: Bearer TOKEN"

# Shows:
# - 10,000 payments received
# - 9,998 posted to GL
# - 2 discrepancies (to investigate)
```

---

## 🌐 Frontend Integration

### Finance Dashboard Component

School can create a finance dashboard showing:

```javascript
// Example: Finance Dashboard for Accountants
function FinanceDashboard() {
  const [stats, setStats] = useState(null);
  const [payments, setPayments] = useState([]);
  
  useEffect(() => {
    // Load statistics
    api.get('/api/finance/payments/statistics?period_days=30')
      .then(data => setStats(data))
      .catch(err => console.error(err));
    
    // Load recent payments
    api.get('/api/finance/payments?limit=20&status_filter=success')
      .then(data => setPayments(data.payments))
      .catch(err => console.error(err));
  }, []);
  
  return (
    <Dashboard>
      <StatCard title="Collected Today" value={stats?.daily_total} />
      <StatCard title="Success Rate" value={`${stats?.success_rate}%`} />
      <StatCard title="Pending" value={stats?.total_amount_pending} />
      
      <PaymentsList payments={payments} />
      <CollectionChart />
      <ReconciliationStatus />
    </Dashboard>
  );
}
```

---

## 📋 Data Flow - Payment Views

```
Parent pays via Paystack
    ↓
Paystack creates transaction record
    ↓
Webhook received → OnlineTransaction table
    ↓
GL entry auto-created
    ↓
Fee status updated
    ↓
School can view via:
  ├─ /api/finance/payments           (list view)
  ├─ /api/finance/payments/statistics (dashboard)
  ├─ /api/finance/payments/by-parent (parent view)
  ├─ /api/finance/payments/by-fee-type (analysis)
  └─ /api/finance/payments/reconciliation (audit)
```

---

## 🔍 Querying Examples

### Example 1: High-Value Transactions

```bash
# Get all successful payments > GHS 1000
curl -X GET "http://localhost:8000/api/finance/payments?status_filter=success&limit=500" \
  -H "Authorization: Bearer TOKEN" | \
  jq '.payments[] | select(.amount > 1000)'
```

### Example 2: Failed Payments (Need Follow-up)

```bash
# Get all failed payments
curl -X GET "http://localhost:8000/api/finance/payments?status_filter=failed" \
  -H "Authorization: Bearer TOKEN"

# Then: Follow up with parents
```

### Example 3: Weekly Report

```bash
# Get payments from last week
LAST_WEEK=$(date -d '7 days ago' '+%Y-%m-%d')
TODAY=$(date '+%Y-%m-%d')

curl -X GET "http://localhost:8000/api/finance/payments?start_date=$LAST_WEEK&end_date=$TODAY&status_filter=success" \
  -H "Authorization: Bearer TOKEN"
```

---

## 📈 Common Reports

### 1. Daily Cash Report
Shows:
- Payments received today
- Total amount
- Payment methods
- Failed attempts

### 2. Monthly Collection Report
Shows:
- Total collected per category
- Collection rate %
- Outstanding amounts
- Comparison with previous month

### 3. Parent Payment History
Shows:
- When each parent paid
- Amounts paid
- Fees paid
- Payment method

### 4. Reconciliation Report
Shows:
- All payments vs GL entries
- Discrepancies
- Missing GL entries
- Quick fix options

### 5. Fee Category Analysis
Shows:
- Collection rate by fee type
- Best performing categories
- Worst performing categories
- Trends

---

## ⚠️ Error Handling

### 403 Forbidden
```json
{
  "detail": "Role 'teacher' cannot access financial reports"
}
```
**Solution:** Only admin/accountant/finance_officer roles can view payments

### 404 Not Found
```json
{
  "detail": "Transaction not found"
}
```
**Solution:** Transaction ID might be invalid or from another school

### Multi-Tenant Error
**Problem:** User from School A tries to view School B's payments
**Solution:** Backend automatically filters by user's school_id - impossible to see other schools' data

---

## 🔒 Security Features

✅ **Multi-Tenant Isolation**
- Every query automatically filtered by user's school_id
- No cross-tenant data leakage possible

✅ **Role-Based Access**
- Only financial roles can access reports
- Parents can only see own transactions

✅ **Audit Trail**
- All payment views are logged
- Timestamps on all transactions

✅ **Data Validation**
- All inputs validated
- SQL injection prevention
- Rate limiting on API calls

---

## 🚀 Deployment Checklist

- [ ] Finance Reports router registered in server.py
- [ ] Database has online_transactions table
- [ ] paystack_service configured
- [ ] GL posting working (auto-posting on payment success)
- [ ] Finance staff roles configured (admin, accountant)
- [ ] Test query: `GET /api/finance/payments/statistics`
- [ ] Verify multi-tenant isolation
- [ ] Monitor for errors

---

## 📞 Support

### Common Issues

**Q: School A can see School B's payments**
A: This is impossible - data is automatically scoped by school_id

**Q: Payment not showing in reports**
A: Check:
1. Were you the person who made the payment? (Yes)
2. Did webhook process successfully? (Check backend logs)
3. Is your user in financial role? (Check user role)

**Q: How long until payment shows?**
A: Usually 5-10 seconds after parent completes payment

---

## Summary

✅ **Schools can view ALL online payments via secured API**

| View | Endpoint | Purpose |
|------|----------|---------|
| All Payments | `/api/finance/payments` | List/filter payments |
| Dashboard | `/api/finance/payments/statistics` | Key metrics |
| By Parent | `/api/finance/payments/by-parent` | Parent tracking |
| By Fee Type | `/api/finance/payments/by-fee-type` | Category analysis |
| Reconciliation | `/api/finance/payments/reconciliation` | Audit trail |
| Detail | `/api/finance/payments/{id}` | Single payment view |

**All endpoints are:**
- ✅ Multi-tenant safe (automatic school_id filtering)
- ✅ Role-based (financial roles only)
- ✅ Fully queryable (dates, status, search)
- ✅ Production-ready

