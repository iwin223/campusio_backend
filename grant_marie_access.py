import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select
from models.user import User
from models.student import Student, StudentParent

database_url = "postgresql+asyncpg://postgres:2211@localhost:5432/school-erp"

async def grant_access():
    """Grant Sam Marie access to Kofi Mensah"""
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Get Sam Marie
        sam_result = await session.execute(
            select(User).where(User.first_name == "Sam", User.last_name == "Marie")
        )
        sam = sam_result.scalar_one_or_none()
        
        if not sam:
            print("❌ Sam Marie not found")
            await engine.dispose()
            return
        
        # Get Kofi Mensah
        kofi_result = await session.execute(
            select(Student).where(Student.first_name == "Kofi", Student.last_name == "Mensah")
        )
        kofi = kofi_result.scalar_one_or_none()
        
        if not kofi:
            print("❌ Kofi Mensah not found")
            await engine.dispose()
            return
        
        # Check if link already exists
        existing = await session.execute(
            select(StudentParent).where(
                StudentParent.parent_id == sam.id,
                StudentParent.student_id == kofi.id
            )
        )
        
        if existing.scalar_one_or_none():
            print(f"✓ {sam.first_name} {sam.last_name} already has access to {kofi.first_name} {kofi.last_name}")
            await engine.dispose()
            return
        
        # Create link
        link = StudentParent(
            parent_id=sam.id,
            student_id=kofi.id
        )
        session.add(link)
        await session.commit()
        
        print(f"✅ Grant access successful!")
        print(f"   {sam.first_name} {sam.last_name} ({sam.email})")
        print(f"   can now access")
        print(f"   {kofi.first_name} {kofi.last_name}")
    
    await engine.dispose()

asyncio.run(grant_access())
