import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select
from models.user import User, UserRole

database_url = "postgresql+asyncpg://postgres:2211@localhost:5432/school-erp"

async def check_parent():
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        parent_result = await session.execute(
            select(User).where(User.role == UserRole.PARENT).limit(1)
        )
        parent = parent_result.scalar_one_or_none()
        
        if parent:
            print(f"Parent: {parent.first_name} {parent.last_name}")
            print(f"Email: {parent.email}")
            print(f"Has password hash: {bool(parent.password_hash)}")
            print(f"Password hash exists: {'yes' if parent.password_hash else 'no'}")
        else:
            print("No parent found")
    
    await engine.dispose()

asyncio.run(check_parent())
