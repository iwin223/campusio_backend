import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select
from models.user import User, UserRole

database_url = "postgresql+asyncpg://postgres:2211@localhost:5432/school-erp"

async def find_parents():
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Get all parent users
        parents_result = await session.execute(
            select(User).where(User.role == UserRole.PARENT)
        )
        parents = parents_result.scalars().all()
        
        print("=== EXISTING PARENT USERS ===\n")
        for i, parent in enumerate(parents, 1):
            print(f"{i}. ID: {parent.id}")
            print(f"   Name: {parent.first_name} {parent.last_name}")
            print(f"   Email: {parent.email}")
            print(f"   School: {parent.school_id}\n")
        
    await engine.dispose()

asyncio.run(find_parents())
