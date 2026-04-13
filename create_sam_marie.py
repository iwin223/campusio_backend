import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select
from models.user import User
from auth import get_password_hash

database_url = "postgresql+asyncpg://postgres:2211@localhost:5432/school-erp"

async def set_password():
    """Set password for Sam Marie"""
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Get Sam Marie
        sam_result = await session.execute(
            select(User).where(User.first_name == "Sam", User.last_name == "Marie")
        )
        sam = sam_result.scalar_one_or_none()
        
        if not sam:
            print("❌ Sam Marie not found in database")
            print("   Creating Sam Marie with default password...")
            
            # Create Sam Marie
            sam = User(
                email="sam.marie@tps001.school.edu.gh",
                password_hash=get_password_hash("sam123"),
                first_name="Sam",
                last_name="Marie",
                phone="+233 20 666 6666",
                role="parent",  # Assuming PARENT role
                school_id="a2615ecf-a7e4-43f8-881b-e79000edfec0"  # Use the first school
            )
            session.add(sam)
            await session.commit()
            print("✅ Sam Marie created with password: sam123")
        else:
            # Update password
            sam.password_hash = get_password_hash("sam123")
            await session.commit()
            print("✅ Sam Marie password set to: sam123")
    
    await engine.dispose()

asyncio.run(set_password())
