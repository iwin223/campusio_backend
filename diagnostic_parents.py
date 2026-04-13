import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select, func
from models.user import User, UserRole
from models.student import StudentParent
from models.fee import Fee

database_url = "postgresql+asyncpg://postgres:2211@localhost:5432/school-erp"

async def diagnostic():
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Count parents in User table
        parent_count_result = await session.execute(
            select(func.count(User.id)).where(User.role == UserRole.PARENT)
        )
        parent_count = parent_count_result.scalar()
        print(f"Total parent users: {parent_count}")
        
        # Count student-parent links
        link_count_result = await session.execute(
            select(func.count(StudentParent.id))
        )
        link_count = link_count_result.scalar()
        print(f"Total student-parent links: {link_count}")
        
        # Get parent IDs that are linked to students
        linked_parent_ids_result = await session.execute(
            select(StudentParent.parent_id).distinct()
        )
        linked_parent_ids = set(linked_parent_ids_result.scalars().all())
        print(f"Unique parent IDs in links: {len(linked_parent_ids)}")
        
        # Check if linked parent IDs exist in User table
        if linked_parent_ids:
            existing_result = await session.execute(
                select(func.count(User.id)).where(User.id.in_(linked_parent_ids))
            )
            existing_count = existing_result.scalar()
            print(f"Existing parent users: {existing_count}")
            
            if existing_count < len(linked_parent_ids):
                print(f"\n⚠️  FOUND ISSUE: {len(linked_parent_ids) - existing_count} parent IDs in StudentParent table DON'T exist in User table!")
                print("\nThis means the parent-child links are broken or orphaned.")
        
        # List all student-parent links
        print("\n=== ALL STUDENT-PARENT LINKS ===")
        links_result = await session.execute(select(StudentParent))
        links = links_result.scalars().all()
        for link in links[:5]:
            print(f"\nStudent: {link.student_id}")
            print(f"  Parent: {link.parent_id}")
            
            # Check if parent exists
            parent_check = await session.execute(
                select(User).where(User.id == link.parent_id)
            )
            if parent_check.scalar_one_or_none():
                print(f"  ✓ Parent exists")
            else:
                print(f"  ❌ Parent DOES NOT exist!")
        
    await engine.dispose()

asyncio.run(diagnostic())
