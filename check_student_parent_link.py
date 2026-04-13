import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select
from models.student import Student, StudentParent
from models.fee import Fee, FeeStructure

database_url = "postgresql+asyncpg://postgres:2211@localhost:5432/school-erp"

async def check_student_parent_links():
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Get the student with fees
        fee_result = await session.execute(select(Fee).limit(1))
        fee = fee_result.scalar_one_or_none()
        
        if fee:
            print(f"✓ Fee found: {fee.id}")
            print(f"  Student ID: {fee.student_id}")
            
            # Get student details
            student_result = await session.execute(
                select(Student).where(Student.id == fee.student_id)
            )
            student = student_result.scalar_one_or_none()
            
            if student:
                print(f"  Student: {student.first_name} {student.last_name}")
                
                # Check if this student has any parent links
                parent_links_result = await session.execute(
                    select(StudentParent).where(StudentParent.student_id == student.id)
                )
                parent_links = parent_links_result.scalars().all()
                
                if parent_links:
                    print(f"  ✓ Parent links found: {len(parent_links)}")
                    for link in parent_links:
                        print(f"    - Parent ID: {link.parent_id}")
                else:
                    print(f"  ❌ NO parent links found for this student!")
                    print(f"     This is the problem: Student has fees but no parent-child relationship")
            else:
                print("❌ Student not found")
        else:
            print("❌ No fees found")
        
    await engine.dispose()

asyncio.run(check_student_parent_links())
