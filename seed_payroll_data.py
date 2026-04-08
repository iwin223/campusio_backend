"""Seed payroll data for School ERP System"""
import asyncio
import sys
from pathlib import Path
from datetime import date, datetime, timedelta

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlmodel import select
from database import async_session, init_db
from models.user import User, UserRole
from models.school import School
from models.staff import Staff, StaffStatus, StaffType
from models.payroll import PayrollContract, PayrollRun, PayrollLineItem, PayrollStatus
from auth import get_password_hash


async def seed_payroll_data():
    """Seed payroll data including contracts and test runs"""
    
    await init_db()
    
    async with async_session() as session:
        # Get admin user and their school
        admin_result = await session.execute(
            select(User).where(User.email == "admin@school.edu.gh")
        )
        admin_user = admin_result.scalar_one_or_none()
        
        if not admin_user:
            print("Admin user not found. Please run seed_data.py first.")
            return
        
        # Get the admin's school
        school_result = await session.execute(
            select(School).where(School.id == admin_user.school_id)
        )
        school = school_result.scalar_one_or_none()
        
        if not school:
            print("School not found. Please run seed_data.py first.")
            return
        
        print(f"Using school: {school.name} (ID: {school.id})")
        
        # Check if payroll contracts already exist
        contract_result = await session.execute(
            select(PayrollContract).where(PayrollContract.school_id == school.id)
        )
        if contract_result.scalars().first():
            print("Payroll data already exists. Skipping...")
            return
        
        # Get or create staff members
        staff_list = []
        
        # First, ensure staff exist
        staff_result = await session.execute(
            select(Staff).where(Staff.school_id == school.id).limit(5)
        )
        existing_staff = staff_result.scalars().all()
        
        if not existing_staff:
            # Create 5 test staff members
            staff_data = [
                {
                    "staff_id": "TPS2024101",
                    "first_name": "John",
                    "last_name": "Amissah",
                    "email": "john.amissah@school.edu.gh",
                    "phone": "+233 20 100 0001",
                    "position": "Mathematics Teacher",
                    "staff_type": StaffType.TEACHING,
                    "date_of_birth": "1985-03-15",
                    "gender": "male",
                    "qualification": "B.Sc Mathematics",
                    "date_joined": "2020-01-08",
                    "status": StaffStatus.ACTIVE
                },
                {
                    "staff_id": "TPS2024102",
                    "first_name": "Ama",
                    "last_name": "Boateng",
                    "email": "ama.boateng@school.edu.gh",
                    "phone": "+233 20 100 0002",
                    "position": "English Teacher",
                    "staff_type": StaffType.TEACHING,
                    "date_of_birth": "1988-07-22",
                    "gender": "female",
                    "qualification": "B.A English",
                    "date_joined": "2019-08-05",
                    "status": StaffStatus.ACTIVE
                },
                {
                    "staff_id": "TPS2024103",
                    "first_name": "Kwesi",
                    "last_name": "Mensah",
                    "email": "kwesi.mensah@school.edu.gh",
                    "phone": "+233 20 100 0003",
                    "position": "Science Teacher",
                    "staff_type": StaffType.TEACHING,
                    "date_of_birth": "1990-11-08",
                    "gender": "male",
                    "qualification": "B.Sc Physics",
                    "date_joined": "2021-01-15",
                    "status": StaffStatus.ACTIVE
                },
                {
                    "staff_id": "TPS2024104",
                    "first_name": "Abena",
                    "last_name": "Owusu",
                    "email": "abena.owusu@school.edu.gh",
                    "phone": "+233 20 100 0004",
                    "position": "Social Studies Teacher",
                    "staff_type": StaffType.TEACHING,
                    "date_of_birth": "1987-09-30",
                    "gender": "female",
                    "qualification": "B.A Social Studies",
                    "date_joined": "2020-08-22",
                    "status": StaffStatus.ACTIVE
                },
                {
                    "staff_id": "TPS2024105",
                    "first_name": "Yaw",
                    "last_name": "Adomako",
                    "email": "yaw.adomako@school.edu.gh",
                    "phone": "+233 20 100 0005",
                    "position": "ICT Coordinator",
                    "staff_type": StaffType.NON_TEACHING,
                    "date_of_birth": "1992-02-14",
                    "gender": "male",
                    "qualification": "HND ICT",
                    "date_joined": "2022-03-01",
                    "status": StaffStatus.ACTIVE
                }
            ]
            
            for staff_data_item in staff_data:
                # Keep dates as strings (ISO format) for PostgreSQL
                staff = Staff(school_id=school.id, **staff_data_item)
                session.add(staff)
                staff_list.append(staff_data_item["first_name"] + " " + staff_data_item["last_name"])
            
            await session.flush()
            print(f"Created 5 new staff members: {', '.join(staff_list)}")
        else:
            staff_list = [f"{s.first_name} {s.last_name}" for s in existing_staff]
            print(f"Using existing {len(existing_staff)} staff members")
        
        # Get all active staff
        staff_result = await session.execute(
            select(Staff).where(Staff.school_id == school.id, Staff.status == StaffStatus.ACTIVE)
        )
        all_staff = staff_result.scalars().all()
        
        print(f"Found {len(all_staff)} active staff members")
        
        # Create payroll contracts for each staff
        contracts_created = 0
        for staff in all_staff:
            # Varied salary structures
            if staff.position in ["Mathematics Teacher", "English Teacher", "Science Teacher"]:
                basic_salary = 8000
                allowance_housing = 2000
                allowance_transport = 500
                allowance_meals = 400
                tax_rate = 15
                pension_rate = 5
                nssf_rate = 3
            elif staff.position == "Social Studies Teacher":
                basic_salary = 7500
                allowance_housing = 1800
                allowance_transport = 450
                allowance_meals = 350
                tax_rate = 14
                pension_rate = 5
                nssf_rate = 3
            else:  # ICT Coordinator
                basic_salary = 6500
                allowance_housing = 1500
                allowance_transport = 400
                allowance_meals = 300
                tax_rate = 12
                pension_rate = 5
                nssf_rate = 3
            
            contract = PayrollContract(
                school_id=school.id,
                staff_id=staff.id,
                basic_salary=basic_salary,
                pay_schedule="monthly",
                allowance_housing=allowance_housing,
                allowance_transport=allowance_transport,
                allowance_meals=allowance_meals,
                allowance_utilities=0,
                allowance_other=0,
                tax_rate_percent=tax_rate,
                pension_rate_percent=pension_rate,
                nssf_rate_percent=nssf_rate,
                other_deduction=0,
                effective_from=date.today(),
                effective_to=None,
                status="active",
                created_by=admin_user.id,
                notes=f"Standard contract for {staff.position}"
            )
            session.add(contract)
            contracts_created += 1
        
        await session.flush()
        print(f"✓ Created {contracts_created} payroll contracts")
        
        # Create a sample payroll run for March 2026
        period_year = 2026
        period_month = 3
        
        # Calculate totals based on staff salary structures
        total_basic = 8000 + 8000 + 8000 + 7500 + 6500  # Sum of basic salaries
        total_allowances = (2900 + 2900 + 2900 + 2600 + 2200)  # Sum of all allowances
        total_gross = total_basic + total_allowances
        
        # Approximate deductions: tax, pension, nssf
        total_deductions = (total_gross * 0.15 * (3/5)) + (total_gross * 0.14 * (1/5)) + (total_gross * 0.12 * (1/5)) + (total_gross * 0.05) + (total_gross * 0.03)
        total_net = total_gross - total_deductions
        
        payroll_run = PayrollRun(
            school_id=school.id,
            period_year=period_year,
            period_month=period_month,
            period_name=f"March {period_year}",
            status=PayrollStatus.GENERATED,
            staff_count=len(all_staff),
            total_allowances=total_allowances,
            total_gross=total_gross,
            total_deductions=total_deductions,
            total_net=total_net,
            generated_by=admin_user.id,
            notes="Sample payroll run for testing"
        )
        
        session.add(payroll_run)
        await session.flush()
        
        # Create line items for each staff
        line_items_created = 0
        for i, staff in enumerate(all_staff):
            # Get corresponding contract
            contract_result = await session.execute(
                select(PayrollContract).where(PayrollContract.staff_id == staff.id)
            )
            contract = contract_result.scalar_one_or_none()
            
            if not contract:
                continue
            
            # Calculate payroll amounts
            allowances = (contract.allowance_housing or 0) + (contract.allowance_transport or 0) + \
                        (contract.allowance_meals or 0) + (contract.allowance_utilities or 0) + \
                        (contract.allowance_other or 0)
            
            gross = contract.basic_salary + allowances
            tax = gross * (contract.tax_rate_percent or 0) / 100
            pension = gross * (contract.pension_rate_percent or 0) / 100
            nssf = gross * (contract.nssf_rate_percent or 0) / 100
            other_ded = contract.other_deduction or 0
            net = gross - tax - pension - nssf - other_ded
            
            line_item = PayrollLineItem(
                payroll_run_id=payroll_run.id,
                school_id=school.id,
                staff_id=staff.id,
                basic_salary=contract.basic_salary,
                total_allowances=allowances,
                gross_amount=gross,
                tax_amount=tax,
                pension_amount=pension,
                nssf_amount=nssf,
                other_deductions=other_ded,
                total_deductions=tax + pension + nssf + other_ded,
                net_amount=max(net, 0),  # Ensure net is never negative
                breakdown=str({
                    "allowances": {
                        "housing": contract.allowance_housing or 0,
                        "transport": contract.allowance_transport or 0,
                        "meals": contract.allowance_meals or 0,
                        "utilities": contract.allowance_utilities or 0,
                        "other": contract.allowance_other or 0
                    },
                    "deductions": {
                        "tax": tax,
                        "pension": pension,
                        "nssf": nssf,
                        "other": other_ded
                    }
                })
            )
            session.add(line_item)
            line_items_created += 1
        
        await session.flush()
        await session.commit()
        
        print(f"✓ Created sample payroll run for March 2026")
        print(f"✓ Created {line_items_created} payroll line items")
        
        print("\n=== Payroll Seed Data Summary ===")
        print(f"✓ {contracts_created} payroll contracts created")
        print(f"✓ 1 payroll run created (March 2026)")
        print(f"✓ {line_items_created} line items created")
        print(f"\nTotal Gross Salary: GHS {total_gross:,.2f}")
        print(f"Total Deductions: GHS {total_deductions:,.2f}")
        print(f"Total Net: GHS {total_net:,.2f}")
        
        print("\n=== Staff Contracts ===")
        for i, staff in enumerate(all_staff):
            contract_result = await session.execute(
                select(PayrollContract).where(PayrollContract.staff_id == staff.id)
            )
            contract = contract_result.scalar_one_or_none()
            if contract:
                total_allow = (contract.allowance_housing or 0) + (contract.allowance_transport or 0) + \
                             (contract.allowance_meals or 0)
                print(f"{i+1}. {staff.first_name} {staff.last_name} - {staff.position}")
                print(f"   Basic: GHS {contract.basic_salary:,} | Allowances: GHS {total_allow:,}")


if __name__ == "__main__":
    asyncio.run(seed_payroll_data())
