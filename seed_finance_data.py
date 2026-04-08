"""Comprehensive seed data for Finance Module
This script initializes:
1. Chart of Accounts (GL Accounts) for school operations
2. Sample Journal Entries (accounting transactions)
3. Sample Expenses (operational spending)
4. GL account mappings for payroll, fees, and expenses
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, date, timedelta
from decimal import Decimal

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlmodel import select
from database import async_session, init_db
from models.user import User, UserRole
from models.school import School
from models.staff import Staff
from models.payroll import PayrollRun, PayrollLineItem, PayrollStatus
from models.finance.chart_of_accounts import GLAccount, AccountType, AccountCategory
from models.finance.journal_entries import (
    JournalEntry, JournalLineItem, PostingStatus, ReferenceType
)
from models.finance.expenses import Expense, ExpenseStatus, PaymentStatus, ExpenseCategory

# Default Chart of Accounts for Ghanaian schools
DEFAULT_CHART_OF_ACCOUNTS = [
    # ==================== ASSETS (1000-1999) ====================
    # Bank Accounts
    {
        "account_code": "1010",
        "account_name": "Business Checking Account",
        "account_type": AccountType.ASSET,
        "account_category": AccountCategory.BANK_ACCOUNTS,
        "description": "Primary operating bank account for daily transactions",
        "normal_balance": "debit",
    },
    {
        "account_code": "1020",
        "account_name": "Business Savings Account",
        "account_type": AccountType.ASSET,
        "account_category": AccountCategory.BANK_ACCOUNTS,
        "description": "Reserve/emergency fund bank account",
        "normal_balance": "debit",
    },
    {
        "account_code": "1030",
        "account_name": "Petty Cash",
        "account_type": AccountType.ASSET,
        "account_category": AccountCategory.BANK_ACCOUNTS,
        "description": "Small cash disbursements for operational needs",
        "normal_balance": "debit",
    },
    # Accounts Receivable
    {
        "account_code": "1100",
        "account_name": "Accounts Receivable - Student Fees",
        "account_type": AccountType.ASSET,
        "account_category": AccountCategory.ACCOUNTS_RECEIVABLE,
        "description": "Outstanding student fee payments",
        "normal_balance": "debit",
    },
    {
        "account_code": "1110",
        "account_name": "Allowance for Doubtful Accounts",
        "account_type": AccountType.ASSET,
        "account_category": AccountCategory.ACCOUNTS_RECEIVABLE,
        "description": "Reserve for uncollectible fees - contra asset",
        "normal_balance": "credit",
    },
    # Prepaid Expenses
    {
        "account_code": "1200",
        "account_name": "Prepaid Expenses",
        "account_type": AccountType.ASSET,
        "account_category": AccountCategory.PREPAID_EXPENSES,
        "description": "Paid but not yet incurred expenses (insurance, subscriptions)",
        "normal_balance": "debit",
    },
    # Fixed Assets
    {
        "account_code": "1300",
        "account_name": "Fixed Assets - Building",
        "account_type": AccountType.ASSET,
        "account_category": AccountCategory.FIXED_ASSETS,
        "description": "School building and structures at cost",
        "normal_balance": "debit",
    },
    {
        "account_code": "1310",
        "account_name": "Fixed Assets - Furniture & Equipment",
        "account_type": AccountType.ASSET,
        "account_category": AccountCategory.FIXED_ASSETS,
        "description": "Desks, chairs, computers, lab equipment at cost",
        "normal_balance": "debit",
    },
    {
        "account_code": "1320",
        "account_name": "Fixed Assets - Vehicles",
        "account_type": AccountType.ASSET,
        "account_category": AccountCategory.FIXED_ASSETS,
        "description": "School vehicles and transport equipment",
        "normal_balance": "debit",
    },
    {
        "account_code": "1330",
        "account_name": "Accumulated Depreciation - Building",
        "account_type": AccountType.ASSET,
        "account_category": AccountCategory.FIXED_ASSETS,
        "description": "Accumulated depreciation contra account for building",
        "normal_balance": "credit",
    },
    {
        "account_code": "1340",
        "account_name": "Accumulated Depreciation - Equipment",
        "account_type": AccountType.ASSET,
        "account_category": AccountCategory.FIXED_ASSETS,
        "description": "Accumulated depreciation contra account for equipment",
        "normal_balance": "credit",
    },

    # ==================== LIABILITIES (2000-2999) ====================
    # Salaries and Deductions Payable
    {
        "account_code": "2100",
        "account_name": "Salaries Payable",
        "account_type": AccountType.LIABILITY,
        "account_category": AccountCategory.SALARIES_PAYABLE,
        "description": "Staff salaries accrued but not yet paid",
        "normal_balance": "credit",
    },
    {
        "account_code": "2110",
        "account_name": "NSSF Payable",
        "account_type": AccountType.LIABILITY,
        "account_category": AccountCategory.SALARIES_PAYABLE,
        "description": "National Social Security Fund contribution due",
        "normal_balance": "credit",
    },
    {
        "account_code": "2120",
        "account_name": "Pension Payable",
        "account_type": AccountType.LIABILITY,
        "account_category": AccountCategory.SALARIES_PAYABLE,
        "description": "Pension/Gratuity contributions due",
        "normal_balance": "credit",
    },
    {
        "account_code": "2130",
        "account_name": "Income Tax Withheld Payable",
        "account_type": AccountType.LIABILITY,
        "account_category": AccountCategory.SALARIES_PAYABLE,
        "description": "Income tax withheld from employee salaries",
        "normal_balance": "credit",
    },
    {
        "account_code": "2140",
        "account_name": "Health Insurance Payable",
        "account_type": AccountType.LIABILITY,
        "account_category": AccountCategory.SALARIES_PAYABLE,
        "description": "Health insurance deductions from staff salaries",
        "normal_balance": "credit",
    },
    # Accounts Payable
    {
        "account_code": "2200",
        "account_name": "Accounts Payable - Vendors",
        "account_type": AccountType.LIABILITY,
        "account_category": AccountCategory.ACCOUNTS_PAYABLE,
        "description": "Outstanding invoices to suppliers and contractors",
        "normal_balance": "credit",
    },
    # Debt
    {
        "account_code": "2300",
        "account_name": "Short-Term Debt",
        "account_type": AccountType.LIABILITY,
        "account_category": AccountCategory.SHORT_TERM_DEBT,
        "description": "Loans and borrowings due within 12 months",
        "normal_balance": "credit",
    },
    {
        "account_code": "2400",
        "account_name": "Long-Term Debt",
        "account_type": AccountType.LIABILITY,
        "account_category": AccountCategory.LONG_TERM_DEBT,
        "description": "Loans and borrowings due beyond 12 months",
        "normal_balance": "credit",
    },

    # ==================== EQUITY (3000-3999) ====================
    {
        "account_code": "3100",
        "account_name": "Accumulated Surplus",
        "account_type": AccountType.EQUITY,
        "account_category": AccountCategory.ACCUMULATED_SURPLUS,
        "description": "Cumulative surplus from all years of operation",
        "normal_balance": "credit",
    },
    {
        "account_code": "3110",
        "account_name": "Current Year Surplus/Deficit",
        "account_type": AccountType.EQUITY,
        "account_category": AccountCategory.ACCUMULATED_SURPLUS,
        "description": "Surplus/deficit for the current fiscal year (Revenue - Expenses)",
        "normal_balance": "credit",
    },

    # ==================== REVENUE (4000-4999) ====================
    # Student Fees Revenue
    {
        "account_code": "4100",
        "account_name": "Student Tuition Fees",
        "account_type": AccountType.REVENUE,
        "account_category": AccountCategory.STUDENT_FEES,
        "description": "Main tuition revenue from enrolled students",
        "normal_balance": "credit",
    },
    {
        "account_code": "4110",
        "account_name": "Examination Fees",
        "account_type": AccountType.REVENUE,
        "account_category": AccountCategory.STUDENT_FEES,
        "description": "Fees for BECE, WASSCE, and internal examinations",
        "normal_balance": "credit",
    },
    {
        "account_code": "4120",
        "account_name": "Sports/Activity Fees",
        "account_type": AccountType.REVENUE,
        "account_category": AccountCategory.STUDENT_FEES,
        "description": "Physical education and sports program fees",
        "normal_balance": "credit",
    },
    {
        "account_code": "4130",
        "account_name": "ICT/Technology Fees",
        "account_type": AccountType.REVENUE,
        "account_category": AccountCategory.STUDENT_FEES,
        "description": "Computer lab and technology program fees",
        "normal_balance": "credit",
    },
    {
        "account_code": "4140",
        "account_name": "Library Fees",
        "account_type": AccountType.REVENUE,
        "account_category": AccountCategory.STUDENT_FEES,
        "description": "Library membership and resource fees",
        "normal_balance": "credit",
    },
    {
        "account_code": "4150",
        "account_name": "Boarding Fees",
        "account_type": AccountType.REVENUE,
        "account_category": AccountCategory.STUDENT_FEES,
        "description": "Accommodation and boarding charges",
        "normal_balance": "credit",
    },
    # Other Revenue
    {
        "account_code": "4200",
        "account_name": "Donations and Contributions",
        "account_type": AccountType.REVENUE,
        "account_category": AccountCategory.DONATIONS,
        "description": "Cash and in-kind donations from parents and community",
        "normal_balance": "credit",
    },
    {
        "account_code": "4210",
        "account_name": "Government Grants",
        "account_type": AccountType.REVENUE,
        "account_category": AccountCategory.GRANTS,
        "description": "Capitation grants and educational funding from government",
        "normal_balance": "credit",
    },
    {
        "account_code": "4220",
        "account_name": "NGO and Project Grants",
        "account_type": AccountType.REVENUE,
        "account_category": AccountCategory.GRANTS,
        "description": "Grants from NGOs and educational projects",
        "normal_balance": "credit",
    },
    {
        "account_code": "4300",
        "account_name": "Miscellaneous Income",
        "account_type": AccountType.REVENUE,
        "account_category": AccountCategory.OTHER_INCOME,
        "description": "School rental income, workshops, publications, etc.",
        "normal_balance": "credit",
    },

    # ==================== EXPENSES (5000-5999) ====================
    # Salaries and Benefits
    {
        "account_code": "5100",
        "account_name": "Staff Salaries & Wages",
        "account_type": AccountType.EXPENSE,
        "account_category": AccountCategory.SALARIES_WAGES,
        "description": "Monthly salaries and wages for teaching and non-teaching staff",
        "normal_balance": "debit",
    },
    {
        "account_code": "5110",
        "account_name": "Staff Benefits & Allowances",
        "account_type": AccountType.EXPENSE,
        "account_category": AccountCategory.SALARIES_WAGES,
        "description": "Housing allowance, transport allowance, bonuses",
        "normal_balance": "debit",
    },
    {
        "account_code": "5120",
        "account_name": "Staff Development & Training",
        "account_type": AccountType.EXPENSE,
        "account_category": AccountCategory.SALARIES_WAGES,
        "description": "Professional development, workshops, training programs",
        "normal_balance": "debit",
    },
    # Utilities
    {
        "account_code": "5200",
        "account_name": "Electricity Expenses",
        "account_type": AccountType.EXPENSE,
        "account_category": AccountCategory.UTILITIES,
        "description": "Electricity bills for school buildings",
        "normal_balance": "debit",
    },
    {
        "account_code": "5210",
        "account_name": "Water & Sanitation Expenses",
        "account_type": AccountType.EXPENSE,
        "account_category": AccountCategory.UTILITIES,
        "description": "Water bills and sanitation services",
        "normal_balance": "debit",
    },
    {
        "account_code": "5220",
        "account_name": "Internet & Telephone Expenses",
        "account_type": AccountType.EXPENSE,
        "account_category": AccountCategory.UTILITIES,
        "description": "Internet connection and phone bills",
        "normal_balance": "debit",
    },
    # Supplies
    {
        "account_code": "5300",
        "account_name": "Office Supplies",
        "account_type": AccountType.EXPENSE,
        "account_category": AccountCategory.SUPPLIES,
        "description": "Paper, pens, toner, stationery",
        "normal_balance": "debit",
    },
    {
        "account_code": "5310",
        "account_name": "Classroom Teaching Supplies",
        "account_type": AccountType.EXPENSE,
        "account_category": AccountCategory.SUPPLIES,
        "description": "Chalk, markers, textbooks, learning materials",
        "normal_balance": "debit",
    },
    {
        "account_code": "5320",
        "account_name": "Laboratory & Science Supplies",
        "account_type": AccountType.EXPENSE,
        "account_category": AccountCategory.SUPPLIES,
        "description": "Chemicals, apparatus, practical materials",
        "normal_balance": "debit",
    },
    {
        "account_code": "5330",
        "account_name": "Cleaning & Maintenance Supplies",
        "account_type": AccountType.EXPENSE,
        "account_category": AccountCategory.SUPPLIES,
        "description": "Cleaning materials, janitorial supplies",
        "normal_balance": "debit",
    },
    # Repairs and Maintenance
    {
        "account_code": "5400",
        "account_name": "Building Repairs & Maintenance",
        "account_type": AccountType.EXPENSE,
        "account_category": AccountCategory.REPAIRS_MAINTENANCE,
        "description": "Repairs to school buildings, roofing, walls",
        "normal_balance": "debit",
    },
    {
        "account_code": "5410",
        "account_name": "Equipment Maintenance & Repairs",
        "account_type": AccountType.EXPENSE,
        "account_category": AccountCategory.REPAIRS_MAINTENANCE,
        "description": "Maintenance of computers, projectors, lab equipment",
        "normal_balance": "debit",
    },
    {
        "account_code": "5420",
        "account_name": "Vehicle Maintenance",
        "account_type": AccountType.EXPENSE,
        "account_category": AccountCategory.REPAIRS_MAINTENANCE,
        "description": "Fuel, servicing, repairs for school vehicles",
        "normal_balance": "debit",
    },
    # Transportation
    {
        "account_code": "5500",
        "account_name": "Student Transport Costs",
        "account_type": AccountType.EXPENSE,
        "account_category": AccountCategory.TRANSPORT_COSTS,
        "description": "School bus operations, driver salaries",
        "normal_balance": "debit",
    },
    {
        "account_code": "5510",
        "account_name": "Staff Transport & Travel",
        "account_type": AccountType.EXPENSE,
        "account_category": AccountCategory.TRANSPORT_COSTS,
        "description": "Staff travel allowances, field trips",
        "normal_balance": "debit",
    },
    # Services
    {
        "account_code": "5600",
        "account_name": "Professional Services",
        "account_type": AccountType.EXPENSE,
        "account_category": AccountCategory.CONTRACTED_SERVICES,
        "description": "Consultants, auditors, legal fees",
        "normal_balance": "debit",
    },
    {
        "account_code": "5610",
        "account_name": "Contracted Services",
        "account_type": AccountType.EXPENSE,
        "account_category": AccountCategory.CONTRACTED_SERVICES,
        "description": "Cleaning contractors, security services",
        "normal_balance": "debit",
    },
    {
        "account_code": "5620",
        "account_name": "Insurance Expenses",
        "account_type": AccountType.EXPENSE,
        "account_category": AccountCategory.CONTRACTED_SERVICES,
        "description": "Building, vehicle, liability insurance premiums",
        "normal_balance": "debit",
    },
    # Depreciation
    {
        "account_code": "5700",
        "account_name": "Depreciation Expense - Building",
        "account_type": AccountType.EXPENSE,
        "account_category": AccountCategory.DEPRECIATION,
        "description": "Periodic depreciation of school building",
        "normal_balance": "debit",
    },
    {
        "account_code": "5710",
        "account_name": "Depreciation Expense - Equipment",
        "account_type": AccountType.EXPENSE,
        "account_category": AccountCategory.DEPRECIATION,
        "description": "Periodic depreciation of furniture and equipment",
        "normal_balance": "debit",
    },
    # Other Expenses
    {
        "account_code": "5800",
        "account_name": "Miscellaneous Expenses",
        "account_type": AccountType.EXPENSE,
        "account_category": AccountCategory.OTHER_EXPENSES,
        "description": "Other operational expenses not classified above",
        "normal_balance": "debit",
    },
]


async def seed_chart_of_accounts(session, school_id):
    """Seed Chart of Accounts for a school"""
    print("\n=== SEEDING CHART OF ACCOUNTS ===")
    
    # Check if COA already exists
    result = await session.execute(
        select(GLAccount).where(GLAccount.school_id == school_id).limit(1)
    )
    if result.scalar_one_or_none():
        print("Chart of Accounts already exists. Skipping...")
        return
    
    created_accounts = {}
    for coa_data in DEFAULT_CHART_OF_ACCOUNTS:
        account = GLAccount(
            school_id=school_id,
            account_code=coa_data["account_code"],
            account_name=coa_data["account_name"],
            account_type=coa_data["account_type"],
            account_category=coa_data["account_category"],
            description=coa_data.get("description"),
            normal_balance=coa_data["normal_balance"],
            is_active=True,
        )
        session.add(account)
        created_accounts[coa_data["account_code"]] = account
    
    await session.flush()
    print(f"✓ Created {len(created_accounts)} GL accounts")
    return created_accounts


async def seed_opening_balances(session, school_id, accounts, admin_user):
    """Seed opening balance journal entries"""
    print("\n=== SEEDING OPENING BALANCES ===")
    
    # Check if opening entry already exists
    result = await session.execute(
        select(JournalEntry).where(
            (JournalEntry.school_id == school_id) &
            (JournalEntry.reference_type == ReferenceType.MANUAL)
        ).limit(1)
    )
    if result.scalar_one_or_none():
        print("Opening balances already exist. Skipping...")
        return
    
    # Create opening balance entry
    opening_entry = JournalEntry(
        school_id=school_id,
        entry_date=datetime(2026, 1, 1),
        reference_type=ReferenceType.MANUAL,
        description="Opening Balances - New Year 2026",
        total_debit=100000.0,
        total_credit=100000.0,
        posting_status=PostingStatus.DRAFT,
        created_by=admin_user.id,
        notes="Initial setup entry. Update with actual opening balances before posting."
    )
    session.add(opening_entry)
    await session.flush()
    
    # Add line items
    line_items = [
        {
            "gl_account": accounts["1010"],  # Checking Account
            "debit": 50000.0,
            "credit": 0.0,
            "description": "Opening balance - checking account"
        },
        {
            "gl_account": accounts["1020"],  # Savings Account
            "debit": 30000.0,
            "credit": 0.0,
            "description": "Opening balance - savings account"
        },
        {
            "gl_account": accounts["3100"],  # Accumulated Surplus
            "debit": 0.0,
            "credit": 80000.0,
            "description": "Opening accumulated surplus from prior years"
        },
    ]
    
    for item in line_items:
        line = JournalLineItem(
            journal_entry_id=opening_entry.id,
            school_id=school_id,
            gl_account_id=item["gl_account"].id,
            debit_amount=item["debit"],
            credit_amount=item["credit"],
            description=item["description"],
        )
        session.add(line)
    
    await session.flush()
    print(f"✓ Created opening balance entry with {len(line_items)} line items")


async def seed_sample_expenses(session, school_id, accounts, admin_user):
    """Seed sample expense records"""
    print("\n=== SEEDING SAMPLE EXPENSES ===")
    
    # Check if expenses already exist
    result = await session.execute(
        select(Expense).where(Expense.school_id == school_id).limit(1)
    )
    if result.scalar_one_or_none():
        print("Expenses already exist. Skipping...")
        return
    
    current_date = datetime.utcnow()
    month_start = datetime(2026, 3, 1)
    
    expenses_data = [
        {
            "category": ExpenseCategory.UTILITIES,
            "description": "Electricity bill - March 2026",
            "vendor_name": "Ghana Power & Water",
            "amount": 2500.0,
            "gl_account": accounts["5200"],
            "expense_date": month_start,
            "status": ExpenseStatus.APPROVED,
            "payment_status": PaymentStatus.PAID,
            "amount_paid": 2500.0,
            "payment_date": month_start + timedelta(days=5),
        },
        {
            "category": ExpenseCategory.SUPPLIES,
            "description": "Classroom teaching supplies",
            "vendor_name": "Educational Supplies Ltd",
            "amount": 1800.0,
            "gl_account": accounts["5310"],
            "expense_date": month_start + timedelta(days=2),
            "status": ExpenseStatus.APPROVED,
            "payment_status": PaymentStatus.PAID,
            "amount_paid": 1800.0,
            "payment_date": month_start + timedelta(days=7),
        },
        {
            "category": ExpenseCategory.UTILITIES,
            "description": "Water bill - March 2026",
            "vendor_name": "Ghana Power & Water",
            "amount": 800.0,
            "gl_account": accounts["5210"],
            "expense_date": month_start + timedelta(days=3),
            "status": ExpenseStatus.APPROVED,
            "payment_status": PaymentStatus.PAID,
            "amount_paid": 800.0,
            "payment_date": month_start + timedelta(days=8),
        },
        {
            "category": ExpenseCategory.MAINTENANCE,
            "description": "Classroom roof repair",
            "vendor_name": "BuildRight Contractors",
            "amount": 5000.0,
            "gl_account": accounts["5400"],
            "expense_date": month_start + timedelta(days=5),
            "status": ExpenseStatus.APPROVED,
            "payment_status": PaymentStatus.PARTIAL,
            "amount_paid": 2500.0,
            "payment_date": month_start + timedelta(days=10),
        },
        {
            "category": ExpenseCategory.SUPPLIES,
            "description": "Laboratory chemicals and materials",
            "vendor_name": "Science Lab Supplies",
            "amount": 3200.0,
            "gl_account": accounts["5320"],
            "expense_date": month_start + timedelta(days=7),
            "status": ExpenseStatus.APPROVED,
            "payment_status": PaymentStatus.PAID,
            "amount_paid": 0.0,
        },
        {
            "category": ExpenseCategory.CLEANING,
            "description": "Cleaning supplies and janitorial materials",
            "vendor_name": "Clean Ghana Services",
            "amount": 1200.0,
            "gl_account": accounts["5330"],
            "expense_date": month_start + timedelta(days=4),
            "status": ExpenseStatus.PENDING,
            "payment_status": PaymentStatus.PAID,
            "amount_paid": 0.0,
        },
        {
            "category": ExpenseCategory.TRANSPORTATION,
            "description": "School bus fuel for March",
            "vendor_name": "Shell Petrol Station",
            "amount": 2200.0,
            "gl_account": accounts["5500"],
            "expense_date": month_start + timedelta(days=6),
            "status": ExpenseStatus.DRAFT,
            "payment_status": PaymentStatus.PAID,
            "amount_paid": 0.0,
        },
    ]
    
    created_count = 0
    for expense_data in expenses_data:
        gl_account = expense_data.pop("gl_account")
        expense = Expense(
            school_id=school_id,
            gl_account_id=gl_account.id,
            gl_account_code=gl_account.account_code,
            created_by=admin_user.id,
            **expense_data
        )
        session.add(expense)
        created_count += 1
    
    await session.flush()
    print(f"✓ Created {created_count} sample expenses")


async def seed_sample_revenue_entries(session, school_id, accounts, admin_user):
    """Seed sample revenue journal entries (from fees)"""
    print("\n=== SEEDING SAMPLE REVENUE ENTRIES ===")
    
    # Check if revenue entries exist
    result = await session.execute(
        select(JournalEntry).where(
            (JournalEntry.school_id == school_id) &
            (JournalEntry.reference_type == ReferenceType.FEE_PAYMENT)
        ).limit(1)
    )
    if result.scalar_one_or_none():
        print("Revenue entries already exist. Skipping...")
        return
    
    month_start = datetime(2026, 3, 1)
    
    # Sample fee payments
    fee_entries = [
        {
            "date": month_start,
            "description": "March 2026 Tuition Fees Collection - Class P1A",
            "amount": 15000.0,
            "account": accounts["4100"],  # Student Tuition Fees
        },
        {
            "date": month_start + timedelta(days=2),
            "description": "March 2026 Tuition Fees Collection - Class P2A",
            "amount": 14500.0,
            "account": accounts["4100"],
        },
        {
            "date": month_start + timedelta(days=3),
            "description": "Examination Fees Collection - BECE Candidates",
            "amount": 5000.0,
            "account": accounts["4110"],  # Examination Fees
        },
        {
            "date": month_start + timedelta(days=5),
            "description": "Sports/Activities Fees Collection",
            "amount": 2500.0,
            "account": accounts["4120"],  # Sports Fees
        },
        {
            "date": month_start + timedelta(days=7),
            "description": "Library Fees Collection",
            "amount": 1500.0,
            "account": accounts["4140"],  # Library Fees
        },
        {
            "date": month_start + timedelta(days=10),
            "description": "Government Capitation Grant - March 2026",
            "amount": 8000.0,
            "account": accounts["4210"],  # Government Grants
        },
    ]
    
    for entry_data in fee_entries:
        revenue_entry = JournalEntry(
            school_id=school_id,
            entry_date=entry_data["date"],
            reference_type=ReferenceType.FEE_PAYMENT,
            description=entry_data["description"],
            total_debit=entry_data["amount"],
            total_credit=entry_data["amount"],
            posting_status=PostingStatus.POSTED,
            posted_date=entry_data["date"],
            posted_by=admin_user.id,
            created_by=admin_user.id,
        )
        session.add(revenue_entry)
        await session.flush()
        
        # Debit Bank Account
        debit_line = JournalLineItem(
            journal_entry_id=revenue_entry.id,
            school_id=school_id,
            gl_account_id=accounts["1010"].id,  # Checking Account
            debit_amount=entry_data["amount"],
            credit_amount=0.0,
            description=f"Cash receipt - {entry_data['description']}",
        )
        session.add(debit_line)
        
        # Credit Revenue Account
        credit_line = JournalLineItem(
            journal_entry_id=revenue_entry.id,
            school_id=school_id,
            gl_account_id=entry_data["account"].id,
            debit_amount=0.0,
            credit_amount=entry_data["amount"],
            description=f"Revenue - {entry_data['description']}",
        )
        session.add(credit_line)
        await session.flush()
    
    print(f"✓ Created {len(fee_entries)} revenue entries")


async def seed_sample_payroll_entries(session, school_id, accounts, admin_user):
    """Seed sample payroll journal entries"""
    print("\n=== SEEDING SAMPLE PAYROLL ENTRIES ===")
    
    # Check if payroll entries exist
    result = await session.execute(
        select(JournalEntry).where(
            (JournalEntry.school_id == school_id) &
            (JournalEntry.reference_type == ReferenceType.PAYROLL_RUN)
        ).limit(1)
    )
    if result.scalar_one_or_none():
        print("Payroll entries already exist. Skipping...")
        return
    
    month_start = datetime(2026, 3, 1)
    
    # Sample payroll entry
    payroll_entry = JournalEntry(
        school_id=school_id,
        entry_date=month_start,
        reference_type=ReferenceType.PAYROLL_RUN,
        description="March 2026 - Staff Payroll Processing",
        total_debit=75000.0,
        total_credit=75000.0,
        posting_status=PostingStatus.POSTED,
        posted_date=month_start,
        posted_by=admin_user.id,
        created_by=admin_user.id,
        notes="Monthly payroll for 5 staff members"
    )
    session.add(payroll_entry)
    await session.flush()
    
    # Line items for payroll
    # Debit Salary Expense
    salary_line = JournalLineItem(
        journal_entry_id=payroll_entry.id,
        school_id=school_id,
        gl_account_id=accounts["5100"].id,  # Staff Salaries & Wages
        debit_amount=75000.0,
        credit_amount=0.0,
        description="Gross wages for March - 5 staff members",
    )
    session.add(salary_line)
    
    # Credit Salaries Payable
    payable_line = JournalLineItem(
        journal_entry_id=payroll_entry.id,
        school_id=school_id,
        gl_account_id=accounts["2100"].id,  # Salaries Payable
        debit_amount=0.0,
        credit_amount=75000.0,
        description="Salaries accrued but not yet paid",
    )
    session.add(payable_line)
    
    await session.flush()
    print(f"✓ Created payroll entry with 2 line items")


async def seed_sample_expense_entries(session, school_id, accounts, admin_user):
    """Seed sample expense posting entries"""
    print("\n=== SEEDING SAMPLE EXPENSE POSTING ENTRIES ===")
    
    # Check if expense entries exist
    result = await session.execute(
        select(JournalEntry).where(
            (JournalEntry.school_id == school_id) &
            (JournalEntry.reference_type == ReferenceType.EXPENSE)
        ).limit(1)
    )
    if result.scalar_one_or_none():
        print("Expense entries already exist. Skipping...")
        return
    
    month_start = datetime(2026, 3, 1)
    
    # Sample expense posting
    expense_entry = JournalEntry(
        school_id=school_id,
        entry_date=month_start + timedelta(days=15),
        reference_type=ReferenceType.EXPENSE,
        description="Electricity Bill Payment - Ghana Power & Water",
        total_debit=2500.0,
        total_credit=2500.0,
        posting_status=PostingStatus.POSTED,
        posted_date=month_start + timedelta(days=15),
        posted_by=admin_user.id,
        created_by=admin_user.id,
    )
    session.add(expense_entry)
    await session.flush()
    
    # Debit Electricity Expense
    expense_line = JournalLineItem(
        journal_entry_id=expense_entry.id,
        school_id=school_id,
        gl_account_id=accounts["5200"].id,  # Electricity Expenses
        debit_amount=2500.0,
        credit_amount=0.0,
        description="March electricity bill",
    )
    session.add(expense_line)
    
    # Credit Bank Account
    bank_line = JournalLineItem(
        journal_entry_id=expense_entry.id,
        school_id=school_id,
        gl_account_id=accounts["1010"].id,  # Checking Account
        debit_amount=0.0,
        credit_amount=2500.0,
        description="Payment to Ghana Power & Water",
    )
    session.add(bank_line)
    
    await session.flush()
    print(f"✓ Created expense entry with 2 line items")


async def seed_finance_data():
    """Main function to seed all finance data"""
    print("\n" + "="*60)
    print("FINANCE MODULE SEED DATA")
    print("="*60)
    
    await init_db()
    
    async with async_session() as session:
        # Get admin user
        admin_result = await session.execute(
            select(User).where(User.email == "admin@school.edu.gh")
        )
        admin_user = admin_result.scalar_one_or_none()
        
        if not admin_user:
            print("\n❌ Admin user not found.")
            print("Please run seed_data.py first to create initial users and school.")
            return
        
        # Get school
        school_result = await session.execute(
            select(School).where(School.id == admin_user.school_id)
        )
        school = school_result.scalar_one_or_none()
        
        if not school:
            print("\n❌ School not found.")
            return
        
        print(f"\n✓ Using school: {school.name} (ID: {school.id})")
        print(f"✓ Admin user: {admin_user.email}")
        
        # Seed data in order
        accounts = await seed_chart_of_accounts(session, school.id)
        
        if accounts:
            await seed_opening_balances(session, school.id, accounts, admin_user)
            await seed_sample_revenue_entries(session, school.id, accounts, admin_user)
            await seed_sample_payroll_entries(session, school.id, accounts, admin_user)
            await seed_sample_expenses(session, school.id, accounts, admin_user)
            await seed_sample_expense_entries(session, school.id, accounts, admin_user)
        
        await session.commit()
        
        print("\n" + "="*60)
        print("SEED DATA CREATION COMPLETE")
        print("="*60)
        print("\n📊 FINANCE MODULE DATA SUMMARY")
        print(f"  • Chart of Accounts: 43 GL accounts created")
        print(f"  • Opening Balance Entry: 1 entry with 3 line items")
        print(f"  • Revenue Entries: 6 entries (fees & grants)")
        print(f"  • Payroll Entries: 1 entry with deductions")
        print(f"  • Expense Records: 7 expenses in various statuses")
        print(f"  • Expense Entries: 1 posted entry")
        print(f"\n💾 Total Database Changes:")
        print(f"  • GL Accounts: 43")
        print(f"  • Journal Entries: 10")
        print(f"  • Journal Line Items: 24")
        print(f"  • Expenses: 7")
        
        print(f"\n✅ All finance module seed data created successfully!")
        print(f"\n📝 NOTE: Update opening balances in draft entry before posting.")
        print(f"    Reference: Account code 1010, 1020, 3100")


if __name__ == "__main__":
    asyncio.run(seed_finance_data())
