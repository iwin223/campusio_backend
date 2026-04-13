import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select
from models.student import StudentParent
from models.fee import Fee

database_url = "postgresql+asyncpg://postgres:2211@localhost:5432/school-erp"

async def fix_parent_link():
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
        
        # Get the broken link
        link_result = await session.execute(
            select(StudentParent).where(StudentParent.student_id == fee.student_id)
        )
        link = link_result.scalar_one_or_none()
        
        if not link:
            print("❌ No link found")
            await engine.dispose()
            return
        
        # It was broken - fix it to point to Ama Mensah (likely parent)
        correct_parent_id = "455caa68-beff-48c3-959a-a4a732c950ea"
        
        print(f"Fixing broken link...")
        print(f"  Student ID: {fee.student_id}")
        print(f"  Old parent ID: {link.parent_id}")
        print(f"  New parent ID: {correct_parent_id}")
        
        link.parent_id = correct_parent_id
        await session.commit()
        
        print(f"\n✅ Fixed! Student-parent link updated")
        
    await engine.dispose()

asyncio.run(fix_parent_link())
