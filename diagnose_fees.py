import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select
from models.fee import Fee, FeeStructure
from models.student import Student, StudentParent
from models.user import User

# Get database URL from .env
database_url = "postgresql+asyncpg://postgres:2211@localhost:5432/school-erp"

async def check_fees():
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Get all fees
        fees_result = await session.execute(select(Fee).limit(5))
        fees = fees_result.scalars().all()
        
        print("=== FEES IN DATABASE ===")
        if fees:
            for fee in fees:
                print(f"\n✓ Fee ID: {fee.id}")
                print(f"  Student ID: {fee.student_id}")
                print(f"  Term ID: {fee.academic_term_id}")
                print(f"  Structure ID: {fee.fee_structure_id}")
                print(f"  Amount Due: {fee.amount_due}")
                print(f"  Amount Paid: {fee.amount_paid}")
                print(f"  Status: {fee.status}")
        else:
            print("❌ No fees found")
        
        # Get fee structures
        print("\n=== FEE STRUCTURES IN DATABASE ===")
        structures_result = await session.execute(select(FeeStructure).limit(5))
        structures = structures_result.scalars().all()
        
        if structures:
            for struct in structures:
                print(f"\n✓ Structure ID: {struct.id}")
                print(f"  Term: {struct.academic_term_id}")
                print(f"  Class Level: {struct.class_level}")
                print(f"  Fee Type: {struct.fee_type}")
                print(f"  Amount: {struct.amount}")
        else:
            print("❌ No fee structures found")
        
    await engine.dispose()

asyncio.run(check_fees())
