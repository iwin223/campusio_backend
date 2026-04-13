import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select
from models.user import User, UserRole
from models.student import Student, StudentParent

database_url = "postgresql+asyncpg://postgres:2211@localhost:5432/school-erp"

async def create_parent_child_links():
    """Create parent-child links for all students"""
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Get parents
        parents_result = await session.execute(
            select(User).where(User.role == UserRole.PARENT)
        )
        parents = parents_result.scalars().all()
        
        if len(parents) < 2:
            print("❌ Need at least 2 parents to create links")
            await engine.dispose()
            return
        
        parent1 = parents[0]  # Ama Mensah
        parent2 = parents[1]  # Sam Marie
        
        print(f"Parent 1: {parent1.first_name} {parent1.last_name} ({parent1.email})")
        print(f"Parent 2: {parent2.first_name} {parent2.last_name} ({parent2.email})\n")
        
        # Get all students
        students_result = await session.execute(select(Student))
        students = students_result.scalars().all()
        
        print(f"Total students: {len(students)}\n")
        
        created_count = 0
        
        # Assign students alternately to parents
        for i, student in enumerate(students):
            # Check if student already has a parent
            existing_link = await session.execute(
                select(StudentParent).where(StudentParent.student_id == student.id)
            )
            if existing_link.scalar_one_or_none():
                print(f"✓ {student.first_name} {student.last_name} - already has parent link")
                continue
            
            # Alternate between two parents
            parent = parent1 if i % 2 == 0 else parent2
            
            link = StudentParent(
                student_id=student.id,
                parent_id=parent.id
            )
            session.add(link)
            created_count += 1
            
            print(f"✓ {student.first_name} {student.last_name} → {parent.first_name} {parent.last_name}")
        
        await session.commit()
        
        print(f"\n✅ Created {created_count} parent-child links")
    
    await engine.dispose()

asyncio.run(create_parent_child_links())
