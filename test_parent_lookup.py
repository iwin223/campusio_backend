"""
Quick test script to verify Parent/Staff lookup for a given user_id
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from models.student import Parent
from models.staff import Staff
from models import User

# This is a quick debug script - configure with your actual DB connection
async def test_lookup():
    from database import get_async_engine
    
    engine = await get_async_engine()
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    # Test user ID - replace with actual ID from your conversation
    test_user_id = "445c7f3d-a803-49fc-b261-fa13a77758ba"
    
    async with async_session() as session:
        print(f"\n=== Testing Lookup for User ID: {test_user_id} ===\n")
        
        # Test 1: Check if User exists
        print("1. Checking User table...")
        user_result = await session.execute(select(User).where(User.id == test_user_id))
        user = user_result.scalar_one_or_none()
        if user:
            print(f"   ✓ User found: {user.first_name} {user.last_name} (email: {user.email})")
        else:
            print(f"   ✗ User NOT found")
        
        # Test 2: Check if Staff record exists
        print("\n2. Checking Staff table...")
        staff_result = await session.execute(select(Staff).where(Staff.user_id == test_user_id))
        staff = staff_result.scalar_one_or_none()
        if staff:
            print(f"   ✓ Staff found: {staff.first_name} {staff.last_name} (type: {staff.staff_type})")
        else:
            print(f"   ✗ Staff NOT found")
        
        # Test 3: Check if Parent record exists
        print("\n3. Checking Parent table...")
        parent_result = await session.execute(select(Parent).where(Parent.user_id == test_user_id))
        parent = parent_result.scalar_one_or_none()
        if parent:
            print(f"   ✓ Parent found: {parent.first_name} {parent.last_name} (phone: {parent.phone})")
        else:
            print(f"   ✗ Parent NOT found")
        
        # Test 4: List ALL parents to see what exists
        print("\n4. All Parents in system (first 10):")
        all_parents_result = await session.execute(select(Parent).limit(10))
        all_parents = all_parents_result.scalars().all()
        for p in all_parents:
            print(f"   - {p.first_name} {p.last_name} (user_id: {p.user_id})")
        
        # Test 5: List ALL staff to see what exists
        print("\n5. All Staff in system (first 10):")
        all_staff_result = await session.execute(select(Staff).limit(10))
        all_staff = all_staff_result.scalars().all()
        for s in all_staff:
            print(f"   - {s.first_name} {s.last_name} (user_id: {s.user_id})")
        
        print("\n=== Test Complete ===\n")

if __name__ == "__main__":
    asyncio.run(test_lookup())
