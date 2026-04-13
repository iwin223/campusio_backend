import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select
from models.user import User, UserRole
from models.student import Student, StudentParent
from models.fee import Fee

database_url = "postgresql+asyncpg://postgres:2211@localhost:5432/school-erp"

async def check_parent_relationships():
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Get a parent user
        parent_result = await session.execute(
            select(User).where(User.role == UserRole.PARENT).limit(1)
        )
        parent = parent_result.scalar_one_or_none()
        
        if parent:
            print(f"✓ Found parent: {parent.id} ({parent.first_name} {parent.last_name})")
            
            # Get children for this parent
            children_result = await session.execute(
                select(StudentParent).where(StudentParent.parent_id == parent.id)
            )
            children_links = children_result.scalars().all()
            
            if children_links:
                print(f"  Children count: {len(children_links)}")
                
                for child_link in children_links[:3]:
                    # Get student details
                    student_result = await session.execute(
                        select(Student).where(Student.id == child_link.student_id)
                    )
                    student = student_result.scalar_one_or_none()
                    
                    if student:
                        print(f"\n  ✓ Child: {student.id} ({student.first_name} {student.last_name})")
                        
                        # Get fees for this student
                        fees_result = await session.execute(
                            select(Fee).where(Fee.student_id == student.id)
                        )
                        fees = fees_result.scalars().all()
                        
                        print(f"    Fees count: {len(fees)}")
                        for fee in fees[:3]:
                            print(f"      - Fee: {fee.id}, Amount: {fee.amount_due}, Status: {fee.status}")
            else:
                print("  ❌ No children found")
        else:
            print("❌ No parent users found")
        
    await engine.dispose()

asyncio.run(check_parent_relationships())
