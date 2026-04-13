import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select
from models.user import User, UserRole
from models.student import Student, StudentParent

database_url = "postgresql+asyncpg://postgres:2211@localhost:5432/school-erp"

async def diagnose():
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Get all parents
        parents_result = await session.execute(
            select(User).where(User.role == UserRole.PARENT)
        )
        parents = parents_result.scalars().all()
        
        print("="*70)
        print("PARENT PORTAL DIAGNOSTICS")
        print("="*70)
        print(f"\nTotal Parents: {len(parents)}\n")
        
        for i, parent in enumerate(parents, 1):
            print(f"{i}. Parent: {parent.first_name} {parent.last_name}")
            print(f"   Email: {parent.email}")
            print(f"   ID: {parent.id}")
            
            # Get children for this parent
            children_result = await session.execute(
                select(StudentParent).where(StudentParent.parent_id == parent.id)
            )
            children_links = children_result.scalars().all()
            
            if children_links:
                print(f"   Children ({len(children_links)}):")
                for link in children_links:
                    # Get student
                    student_result = await session.execute(
                        select(Student).where(Student.id == link.student_id)
                    )
                    student = student_result.scalar_one_or_none()
                    if student:
                        print(f"     - {student.first_name} {student.last_name} (ID: {student.id})")
                    else:
                        print(f"     - [Orphaned link to ID: {link.student_id}]")
            else:
                print(f"   Children: None")
            
            print()
        
        # Show all students
        print("\nAll Students in System:")
        print("-"*70)
        students_result = await session.execute(select(Student).limit(10))
        students = students_result.scalars().all()
        
        for student in students:
            print(f"\n{student.first_name} {student.last_name} (ID: {student.id})")
            
            # Check if has parent links
            links_result = await session.execute(
                select(StudentParent).where(StudentParent.student_id == student.id)
            )
            links = links_result.scalars().all()
            
            if links:
                for link in links:
                    parent_result = await session.execute(
                        select(User).where(User.id == link.parent_id)
                    )
                    parent = parent_result.scalar_one_or_none()
                    if parent:
                        print(f"  Parent: {parent.first_name} {parent.last_name} ({parent.email})")
                    else:
                        print(f"  Parent: [MISSING ID: {link.parent_id}]")
            else:
                print(f"  Parent: None")
    
    await engine.dispose()

asyncio.run(diagnose())
