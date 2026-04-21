"""Debug script to check fee_id in database"""
import asyncio
from sqlmodel import select
from database import async_session
from models.fee import Fee

async def check_fee():
    fee_id = "eb18fc81-9657-4466-8f10-7bd4dec30207"
    
    async with async_session() as session:
        # Try to find the fee
        result = await session.execute(
            select(Fee).where(Fee.id == fee_id)
        )
        fee = result.scalar_one_or_none()
        
        if fee:
            print(f"✓ Fee found!")
            print(f"  ID: {fee.id}")
            print(f"  School ID: {fee.school_id}")
            print(f"  Student ID: {fee.student_id}")
            print(f"  Amount Due: {fee.amount_due}")
            print(f"  Amount Paid: {fee.amount_paid}")
            print(f"  Status: {fee.status}")
        else:
            print(f"✗ Fee not found with ID: {fee_id}")
            
            # Show all fees in database
            print("\nAll fees in database:")
            result = await session.execute(select(Fee))
            fees = result.scalars().all()
            if fees:
                for f in fees[:10]:  # Show first 10
                    print(f"  - {f.id} | Student: {f.student_id} | Amount Due: {f.amount_due}")
                if len(fees) > 10:
                    print(f"  ... and {len(fees) - 10} more")
            else:
                print("  No fees found in database!")

if __name__ == "__main__":
    asyncio.run(check_fee())
