import asyncio
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select
from models.user import User
from models.fee import Fee

database_url = "postgresql+asyncpg://postgres:2211@localhost:5432/school-erp"

async def test_parent_fees_endpoint():
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Get the fee to find the student
        fee_result = await session.execute(select(Fee).limit(1))
        fee = fee_result.scalar_one_or_none()
        
        if not fee:
            print("❌ No fees found")
            await engine.dispose()
            return
        
        # Get the parent who should have access
        from models.student import StudentParent
        parent_link_result = await session.execute(
            select(StudentParent).where(StudentParent.student_id == fee.student_id).limit(1)
        )
        parent_link = parent_link_result.scalar_one_or_none()
        
        if not parent_link:
            print("❌ No parent link found")
            await engine.dispose()
            return
        
        # Get parent details
        parent_result = await session.execute(
            select(User).where(User.id == parent_link.parent_id)
        )
        parent = parent_result.scalar_one_or_none()
        
        if not parent:
            print("❌ Parent user not found")
            await engine.dispose()
            return
        
        print(f"✓ Parent: {parent.first_name} {parent.last_name} ({parent.id})")
        print(f"  Email: {parent.email}")
        print(f"  Student ID: {fee.student_id}")
        print(f"\n📌 To test, you need to:")
        print(f"   1. Get JWT token for parent: {parent.email}")
        print(f"   2. Call: GET /api/parent/child/{fee.student_id}/fees")
        print(f"   3. Include Bearer token in header")
        
    await engine.dispose()

asyncio.run(test_parent_fees_endpoint())
