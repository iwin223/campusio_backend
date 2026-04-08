"""
DATABASE MIGRATION & FINANCE MODULE SETUP GUIDE

This document explains how to apply database migrations and initialize
the Chart of Accounts for your School ERP Finance Module.

CURRENT MIGRATIONS:
===================

1. 001_payroll - Payroll tables (existing)
2. 002_finance_coa - Chart of Accounts tables (NEW)

RUNNING MIGRATIONS:
===================

Using Alembic CLI:

1. Check migration status:
   $ alembic current
   $ alembic history

2. Apply pending migrations:
   $ alembic upgrade head

3. Revert last migration:
   $ alembic downgrade -1

4. View SQL that will be executed (dry-run):
   $ alembic upgrade head --sql

AUTOMATIC MIGRATION ON STARTUP:
================================

The application runs migrations automatically via SQLModel.metadata.create_all()
called in database.py init_db() function, which is invoked during app startup.

IF YOU NEED EXPLICIT ALEMBIC MIGRATIONS:
- Enable force_create=False in database configuration
- Ensure Alembic environment is properly configured
- Run migrations explicitly before starting the app

INITIALIZING CHART OF ACCOUNTS:
================================

After migrations run, initialize GL accounts for each school:

Option 1: Manual Initialization (In Code/Script)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
```python
from migrations_helper import initialize_school_chart_of_accounts
from database import get_session

async def setup_school():
    async with async_session() as session:
        result = await initialize_school_chart_of_accounts(
            session=session,
            school_id="school_uuid_here",
            created_by="admin_user_id"
        )
        if result['success']:
            print(f"✓ Created {result['accounts_created']} GL accounts")
        else:
            print(f"✗ Failed to initialize CoA")

asyncio.run(setup_school())
```

Option 2: During School Creation (Built into API)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Modify the schools router to automatically seed CoA when a school is created:

```python
# In routers/schools.py create_school endpoint
from migrations_helper import initialize_school_chart_of_accounts

@router.post("/schools")
async def create_school(school_data: SchoolCreate, session: AsyncSession):
    # Create school...
    school = School(**school_data.dict())
    session.add(school)
    await session.commit()
    
    # Initialize Chart of Accounts
    await initialize_school_chart_of_accounts(
        session=session,
        school_id=school.id,
        created_by=current_user.id
    )
    
    return school
```

Option 3: CLI Script
~~~~~~~~~~~~~~~~~~~
Create a management script to initialize existing schools:

```bash
# python scripts/init_finance.py --school-id=<uuid>
```

VERIFICATION:
==============

After initialization, verify the Chart of Accounts:

1. Check table exists:
   SELECT COUNT(*) FROM gl_accounts;

2. Verify accounts for a school:
   SELECT account_code, account_name, account_type 
   FROM gl_accounts 
   WHERE school_id = 'your_school_id'
   ORDER BY account_code;

3. Test API endpoint:
   curl -H "Authorization: Bearer TOKEN" \
     http://localhost:8000/api/finance/coa?active_only=true

4. Validate required accounts:
   curl -X POST -H "Authorization: Bearer TOKEN" \
     http://localhost:8000/api/finance/coa/validate

GL ACCOUNT STRUCTURE:
======================

45 Default Accounts are created per school:

ASSETS (1000-1999):
  - Bank Accounts: Checking (1010), Savings (1020), Petty Cash (1030)
  - Accounts Receivable: Student Fees (1100)
  - Fixed Assets: Building (1300), Equipment (1310), Vehicles (1320)
  - Depreciation Reserves: Building (1330), Equipment (1340)

LIABILITIES (2000-2999):
  - Salaries Payable: Salaries (2100), NSSF (2110), Pension (2120), Tax (2130)
  - Accounts Payable: Vendors (2200)
  - Debt: Short-term (2300), Long-term (2400)

EQUITY (3000-3999):
  - Accumulated Surplus (3100)
  - Current Year Surplus (3110)

REVENUE (4000-4999):
  - Student Fees: Tuition (4100), Exams (4110), Sports (4120), ICT (4130), Library (4140), PTA (4150), Maintenance (4160)
  - Donations (4200)
  - Grants (4300)
  - Other Income: Interest (4400), Miscellaneous (4500)

EXPENSES (5000-5999):
  - Salaries: Salaries & Wages (5100), Taxes & Contributions (5110)
  - Utilities: Electricity (5200), Water (5210), Internet (5220)
  - Supplies: Office (5300), Classroom (5310), Lab (5320)
  - Operations: Repairs (5400), Transport (5500), Services (5600), Cleaning (5610), Security (5620)
  - Other: Depreciation (5700), Insurance (5800), Miscellaneous (5900)

TROUBLESHOOTING:
================

Migration Won't Run:
  1. Check Alembic version: alembic --version
  2. Verify database connection: psql connection_string
  3. Check migration files in alembic/versions/
  4. Review Alembic configuration: alembic.ini

CoA Not Initialized:
  1. Verify gl_accounts table was created
  2. Check for errors in seed_default_chart_of_accounts()
  3. Verify school_id exists in schools table
  4. Check database permissions

Duplicate Account Codes:
  1. Composite unique index enforces (school_id, account_code) uniqueness
  2. Cannot create two accounts with same code in same school
  3. Error: "Account code 'XXXX' already exists for this school"

SUPPORT:
========

For issues or questions:
1. Check migrations_helper.py for initialization functions
2. Review services/coa_initialization.py for seeding logic
3. Check services/coa_service.py for account operations
4. Test endpoints via: http://localhost:8000/api/docs (Swagger UI)
"""
