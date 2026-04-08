"""
Diagnostic script to inspect message IDs and their types in the database
Shows what receiver_id/sender_id values are actually stored and where they come from
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func
from models.communication import Message
from models.student import Parent, Student
from models.staff import Staff
from models import User

async def diagnose_message_ids():
    from database import async_engine, async_session as session_factory
    
    async with session_factory() as session:
        print("\n" + "="*80)
        print("MESSAGE ID DIAGNOSTIC")
        print("="*80)
        
        # Get all unique receiver_id values
        receiver_query = await session.execute(
            select(Message.receiver_id, func.count(Message.id).label('count'))
            .group_by(Message.receiver_id)
        )
        receiver_ids = receiver_query.all()
        
        print(f"\n✓ Found {len(receiver_ids)} unique receiver_id values in messages:")
        
        for receiver_id, count in receiver_ids:
            print(f"\n  Receiver ID: {receiver_id}")
            print(f"  Message count: {count}")
            
            # Check if it's a User ID
            user_result = await session.execute(select(User).where(User.id == receiver_id))
            user = user_result.scalar_one_or_none()
            if user:
                print(f"  ✓ Found in User table: {user.first_name} {user.last_name} ({user.role})")
            else:
                print(f"  ✗ NOT in User table")
            
            # Check if it's a Parent ID
            parent_result = await session.execute(select(Parent).where(Parent.id == receiver_id))
            parent = parent_result.scalar_one_or_none()
            if parent:
                print(f"  ✓ Found in Parent table: {parent.first_name} {parent.last_name}")
                if parent.user_id:
                    user_result = await session.execute(select(User).where(User.id == parent.user_id))
                    user = user_result.scalar_one_or_none()
                    if user:
                        print(f"    └─ User ID maps to: {user.first_name} {user.last_name}")
            
            # Check if it's a Staff ID
            staff_result = await session.execute(select(Staff).where(Staff.id == receiver_id))
            staff = staff_result.scalar_one_or_none()
            if staff:
                print(f"  ✓ Found in Staff table: {staff.first_name} {staff.last_name}")
                if staff.user_id:
                    user_result = await session.execute(select(User).where(User.id == staff.user_id))
                    user = user_result.scalar_one_or_none()
                    if user:
                        print(f"    └─ User ID maps to: {user.first_name} {user.last_name}")
        
        # Get all unique sender_id values
        sender_query = await session.execute(
            select(Message.sender_id, func.count(Message.id).label('count'))
            .group_by(Message.sender_id)
        )
        sender_ids = sender_query.all()
        
        print(f"\n✓ Found {len(sender_ids)} unique sender_id values in messages:")
        
        for sender_id, count in sender_ids:
            print(f"\n  Sender ID: {sender_id}")
            print(f"  Message count: {count}")
            
            # Check if it's a User ID
            user_result = await session.execute(select(User).where(User.id == sender_id))
            user = user_result.scalar_one_or_none()
            if user:
                print(f"  ✓ Found in User table: {user.first_name} {user.last_name} ({user.role})")
            else:
                print(f"  ✗ NOT in User table")
        
        # Summary
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        total_messages = await session.execute(select(func.count(Message.id)))
        total_count = total_messages.scalar()
        print(f"\nTotal messages in system: {total_count}")
        print(f"Unique receiver IDs: {len(receiver_ids)}")
        print(f"Unique sender IDs: {len(sender_ids)}")
        
        print("\n" + "="*80)

if __name__ == "__main__":
    asyncio.run(diagnose_message_ids())
