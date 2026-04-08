# PHASE 4.2: Expense Router & Endpoints

**Status**: ✅ COMPLETE
**Date**: March 2026
**Files Created/Modified**: 3

## Overview

Implemented comprehensive FastAPI router for Expense Management module with 10 REST endpoints exposing the ExpenseService business logic. Full RBAC enforcement and multi-tenant scoping applied across all endpoints.

## Files Created

### 1. `backend/routers/finance/expenses.py` (680+ lines)

**Purpose**: FastAPI router for expense management endpoints

**Endpoints Implemented**:

| Endpoint | Method | Access | Purpose |
|----------|--------|--------|---------|
| `/api/finance/expenses` | POST | HR+ | Create new DRAFT expense |
| `/api/finance/expenses/{id}` | GET | All | Retrieve single expense |
| `/api/finance/expenses` | GET | All | List with filters |
| `/api/finance/expenses/{id}` | PUT | HR+ | Update DRAFT expense |
| `/api/finance/expenses/{id}/submit` | POST | HR+ | Submit for approval |
| `/api/finance/expenses/{id}/approve` | POST | Admin+ | Approve for GL posting |
| `/api/finance/expenses/{id}/reject` | POST | Admin+ | Reject with reason |
| `/api/finance/expenses/{id}/post` | POST | Admin+ | Post to GL (immutable) |
| `/api/finance/expenses/{id}/payment` | POST | Admin+ | Record payment |
| `/api/finance/expenses/summary/stats` | GET | All | Summary analytics |

**Key Features**:

1. **RBAC-based access control**:
   - SUPER_ADMIN: Full access
   - SCHOOL_ADMIN: Full access (approve/post)
   - HR: Create, submit, view
   - Others: Read-only

2. **Comprehensive Documentation**:
   - Docstrings for all endpoints
   - Examples of request/response bodies
   - Clear parameter descriptions
   - Access level markers

3. **Query Parameters**:
   - category: Filter by expense type
   - status: Filter by workflow state
   - start_date/end_date: Date range filtering
   - skip/limit: Pagination

4. **Error Handling**:
   - HTTP 400: Validation errors
   - HTTP 404: Resource not found
   - HTTP 422: Unprocessable entity
   - HTTP 500: Server errors
   - Detailed error messages for debugging

5. **Multi-tenant Scoping**:
   - All endpoints enforce school_id scoping
   - Prevents cross-school data leakage

## Files Modified

### 1. `backend/routers/finance/__init__.py`

**Changes**:
- Added import: `from .expenses import router as expenses_router`
- Added to `__all__`: `"expenses_router"`

**Before**:
```python
from .coa import router as coa_router
from .journal import router as journal_router

__all__ = ["coa_router", "journal_router"]
```

**After**:
```python
from .coa import router as coa_router
from .journal import router as journal_router
from .expenses import router as expenses_router

__all__ = ["coa_router", "journal_router", "expenses_router"]
```

### 2. `backend/server.py`

**Changes**:
- Added import: `from routers.finance.expenses import router as expenses_router` (line 36)
- Added registration: `app.include_router(expenses_router, prefix="/api")` (line 99)

**Impact**: Expenses router now registered and accessible at `/api/finance/expenses/*`

## Endpoint Details

### 1. CREATE EXPENSE
```
POST /api/finance/expenses
{
  "category": "utilities",
  "description": "Monthly electricity bill",
  "vendor_name": "ECG",
  "amount": 5000.00,
  "currency": "GHS",
  "gl_account_id": "uuid",      // Optional
  "expense_date": "2026-04-01T10:00:00",
  "notes": "March bill"
}

Response 201:
{
  "id": "uuid",
  "school_id": "school-uuid",
  "category": "utilities",
  "description": "Monthly electricity bill",
  "amount": 5000.00,
  "amount_paid": 0.00,
  "status": "DRAFT",
  "payment_status": "OUTSTANDING",
  ...
}
```

### 2. GET EXPENSE
```
GET /api/finance/expenses/{expense_id}

Response 200:
{
  "id": "uuid",
  "category": "utilities",
  "status": "DRAFT",
  ...
}

Response 404:
{
  "detail": "Expense {uuid} not found"
}
```

### 3. LIST EXPENSES
```
GET /api/finance/expenses
  ?category=utilities
  &status=pending
  &start_date=2026-03-01
  &end_date=2026-04-01
  &skip=0
  &limit=50

Response 200:
[
  { expense },
  { expense },
  ...
]
```

### 4. UPDATE EXPENSE
```
PUT /api/finance/expenses/{expense_id}
{
  "category": "supplies",
  "amount": 3500.00,
  "description": "Updated description",
  ...
}

Response 200:
{ updated expense }

Response 400:
{
  "detail": "Expense {uuid} is not in DRAFT status"
}
```

### 5. SUBMIT FOR APPROVAL
```
POST /api/finance/expenses/{expense_id}/submit
{
  "submission_notes": "Ready for review"
}

Response 200:
{
  "id": "uuid",
  "status": "PENDING",
  "submitted_by": "user-uuid",
  "submitted_at": "2026-04-01T10:30:00",
  ...
}

Response 400:
{
  "detail": "Expense is not in DRAFT status"
}
```

### 6. APPROVE EXPENSE
```
POST /api/finance/expenses/{expense_id}/approve
{
  "approval_notes": "Approved - budget OK"
}

Response 200:
{
  "id": "uuid",
  "status": "APPROVED",
  "approved_by": "admin-uuid",
  "approved_date": "2026-04-01T11:00:00",
  ...
}
```

### 7. REJECT EXPENSE
```
POST /api/finance/expenses/{expense_id}/reject
{
  "rejection_reason": "Insufficient budget - Q2 overspent"
}

Response 200:
{
  "id": "uuid",
  "status": "REJECTED",
  "rejected_by": "admin-uuid",
  "rejection_reason": "Insufficient budget - Q2 overspent",
  ...
}
```

### 8. POST TO GL
```
POST /api/finance/expenses/{expense_id}/post

Response 200:
{
  "id": "uuid",
  "status": "POSTED",
  "journal_entry_id": "journal-uuid",
  "posted_date": "2026-04-01T11:15:00",
  ...
}

Response 422:
{
  "detail": "GL account {code} not found or inactive"
}
```

GL Posting Structure:
- Dr. Expense GL Account: $5,000.00
- Cr. 1010 (Bank Account): $5,000.00

### 9. RECORD PAYMENT
```
POST /api/finance/expenses/{expense_id}/payment
{
  "amount_paid": 3000.00,
  "payment_date": "2026-04-02T14:00:00",
  "payment_notes": "Partial payment"
}

Response 200:
{
  "id": "uuid",
  "amount": 5000.00,
  "amount_paid": 3000.00,
  "payment_status": "PARTIAL",
  ...
}
```

### 10. GET SUMMARY
```
GET /api/finance/expenses/summary/stats
  ?start_date=2026-03-01
  &end_date=2026-04-01

Response 200:
{
  "total_expenses": 45,
  "draft_count": 5,
  "pending_count": 8,
  "approved_count": 12,
  "posted_count": 18,
  "rejected_count": 2,
  "total_amount": 125000.00,
  "total_paid": 90000.00,
  "outstanding_amount": 35000.00,
  "by_category": {
    "utilities": 25000.00,
    "supplies": 15000.00,
    "maintenance": 35000.00,
    ...
  }
}
```

## Status Workflow

```
DRAFT
  ↓ /submit
PENDING
  ├─→ /approve → APPROVED
  │              ↓ /post
  │              POSTED
  │              (linked to journal entry)
  │
  └─→ /reject → REJECTED
```

## Integration Points

### 1. Authentication & Authorization
- Uses `get_current_user` for identity verification
- Uses `require_roles` for RBAC enforcement
- JWT token required for all endpoints

### 2. Database Session
- Uses `get_session` for AsyncSession injection
- All operations use async/await patterns
- Multi-tenant scoping via school_id

### 3. Service Layer
- All endpoints delegate to `ExpenseService`
- Service handles business logic and GL integration
- Error handling at service layer with custom exceptions

### 4. GL Integration
- POST endpoint triggers GL posting via service
- Creates journal entry automatically
- Links expense to journal entry for audit trail

## Error Handling Strategy

| Error | HTTP | Scenario |
|-------|------|----------|
| No school context | 400 | User not assigned to school |
| Invalid category | 400 | Category value not in enum |
| Invalid status | 400 | Status filter value invalid |
| Expense not found | 404 | ID doesn't exist or wrong school |
| Validation error | 422 | Amount negative, GL account inactive |
| GL posting failed | 422 | GL account not found |
| Wrong state for action | 400 | E.g., submit when not DRAFT |
| Insufficient permissions | 403 | User role doesn't allow operation |
| Server error | 500 | Unexpected exception |

## Authorization Matrix

| Endpoint | SUPER_ADMIN | SCHOOL_ADMIN | HR | TEACHER | Read-Only |
|----------|-------------|--------------|-------|---------|-----------|
| POST (create) | ✓ | ✓ | ✓ | ✗ | ✗ |
| GET (retrieve) | ✓ | ✓ | ✓ | ✓ | ✓ |
| GET (list) | ✓ | ✓ | ✓ | ✓ | ✓ |
| PUT (update) | ✓ | ✓ | ✓ | ✗ | ✗ |
| POST (submit) | ✓ | ✓ | ✓ | ✗ | ✗ |
| POST (approve) | ✓ | ✓ | ✗ | ✗ | ✗ |
| POST (reject) | ✓ | ✓ | ✗ | ✗ | ✗ |
| POST (post GL) | ✓ | ✓ | ✗ | ✗ | ✗ |
| POST (payment) | ✓ | ✓ | ✗ | ✗ | ✗ |
| GET (summary) | ✓ | ✓ | ✓ | ✓ | ✓ |

## Testing Scenarios

### Create → Submit → Approve → Post Flow
```bash
1. POST /api/finance/expenses          # DRAFT created
2. PUT /api/finance/expenses/{id}      # Edit fields
3. POST /api/finance/expenses/{id}/submit  # PENDING
4. POST /api/finance/expenses/{id}/approve # APPROVED
5. POST /api/finance/expenses/{id}/post    # POSTED + GL entry
```

### Rejection Flow
```bash
1. POST /api/finance/expenses          # DRAFT created
2. POST /api/finance/expenses/{id}/submit  # PENDING
3. POST /api/finance/expenses/{id}/reject  # REJECTED
```

### Payment Tracking
```bash
1. POST /api/finance/expenses/{id}/payment # amount_paid = 3000
2. GET /api/finance/expenses/{id}          # payment_status = PARTIAL
3. POST /api/finance/expenses/{id}/payment # amount_paid += 2000 (now 5000)
   # payment_status = PAID
```

## Technical Details

### Framework: FastAPI
- Async/await patterns throughout
- Dependency injection for auth, session
- Status code specificity for HTTP semantics
- Automatic OpenAPI documentation generation

### Validation
- Enum validation at route level
- Service layer business validation
- GL account existence checks
- State transition enforcement

### Multi-tenancy
- school_id extracted from JWT token
- All queries filtered by school_id
- Cross-school data leakage prevented

### Audit Trail
- created_by/submitted_by/approved_by/rejected_by tracked
- Timestamps for all state changes
- Notes/reasons captured for approvals
- Journal entry linkage for GL audit

## Deployment Notes

1. **Database Migration**: Run alembic migration before deploying
   ```bash
   alembic upgrade head
   ```

2. **Server Restart**: Required to register new router
   ```bash
   docker-compose restart backend
   # or locally: restart FastAPI app
   ```

3. **Testing**: Verify endpoints available
   ```bash
   curl http://localhost:8000/api/finance/expenses
   ```

4. **Documentation**: Auto-generated at `/docs`
   - All endpoints with full parameters
   - Try-it-out functionality
   - Example payloads for testing

## Phase Summary

**Phase 4.2 Completion**:
- ✅ 10 REST endpoints implemented
- ✅ Full RBAC enforcement
- ✅ Multi-tenant scoping
- ✅ Comprehensive error handling
- ✅ GL integration via POST endpoint
- ✅ Payment tracking capability
- ✅ Summary analytics endpoint
- ✅ Complete documentation in docstrings

**Total Finance Module Now**:
- Phase 1: 45 GL accounts (CoA module)
- Phase 2: Journal entry system with 10 endpoints
- Phase 3: Payroll + Fees auto-posting
- Phase 4: Expense management (10 endpoints) + GL integration

**Lines of Code**:
- Router: 680+ lines
- Total Phase 4: 1,650+ lines (models + service + router)
- Total Finance Module: 5,000+ lines across 20+ files

## Next Phase

**Phase 5: Financial Reports** (Ready to Start)
- P&L Statement report
- Balance Sheet report
- Trial Balance report
- Cash Flow Statement
- Query GL accounts and journal entries for period analytics

---

**Created**: March 2026
**By**: AI Assistant
**Status**: Production Ready ✅
