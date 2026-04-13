import asyncio
from database import async_session
from models.student import Student
from models.fee import Fee
from models.school import AcademicTerm
from sqlmodel import select

async def fix_fees():
    async with async_session() as session:
        # Get the student
        student_result = await session.execute(
            select(Student).where(Student.id == 'ba00550b-6c63-4322-a119-0a441df8ad47')
        )
        student = student_result.scalar_one_or_none()
        
        if not student:
            print("Student not found")
            return
            
        print(f"Student: {student.first_name} {student.last_name}")
        print(f"School ID: {student.school_id}\n")
        
        # Get terms for this school
        terms_result = await session.execute(
            select(AcademicTerm).where(AcademicTerm.school_id == student.school_id)
        )
        terms = terms_result.scalars().all()
        print(f"Available Terms: {len(terms)}")
        for term in terms:
            print(f"  - {term.term} {term.academic_year} (ID: {term.id})")
        
        if not terms:
            print("\n⚠️  No terms exist! Need to create one first.")
            return
        
        # Get fees for this student
        fees_result = await session.execute(
            select(Fee).where(Fee.student_id == student.id)
        )
        fees = fees_result.scalars().all()
        print(f"\nFees for student: {len(fees)}")
        for fee in fees:
            print(f"  - Amount: {fee.amount_due}, Current Term ID: {fee.academic_term_id}")
        
        # Update all fees to use the first available term
        if fees and terms:
            first_term = terms[0]
            print(f"\nUpdating {len(fees)} fees to use term: {first_term.term} {first_term.academic_year} (ID: {first_term.id})")
            for fee in fees:
                fee.academic_term_id = first_term.id
            
            session.add_all(fees)
            await session.commit()
            print("✅ Fees updated successfully!")

asyncio.run(fix_fees())
