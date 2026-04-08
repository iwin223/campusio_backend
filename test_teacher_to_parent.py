"""
Test: Verify parent sees messages from teacher (receiver_id = parent_id case)
"""
import asyncio
from sqlalchemy import select, or_
from models.communication import Message
from models.student import Parent
from models.staff import Staff
from models.user import User, UserRole

async def test_teacher_to_parent_message():
    from database import async_session as session_factory
    
    async with session_factory() as session:
        print("\n" + "="*80)
        print("TEST: Teacher-to-Parent Message Resolution")
        print("="*80)
        
        # Get all messages
        all_msgs_result = await session.execute(select(Message))
        all_messages = all_msgs_result.scalars().all()
        
        print(f"\nTotal messages in system: {len(all_messages)}")
        
        for idx, msg in enumerate(all_messages):
            print(f"\n--- Message {idx+1} ---")
            print(f"  Sender ID: {msg.sender_id[:16]}...")
            print(f"  Receiver ID: {msg.receiver_id[:16]}...")
            print(f"  Content: {msg.content[:40]}...")
            
            # Check sender
            sender_as_user = await session.execute(select(User).where(User.id == msg.sender_id))
            sender = sender_as_user.scalar_one_or_none()
            sender_as_staff = await session.execute(select(Staff).where(Staff.id == msg.sender_id))
            sender_staff = sender_as_staff.scalar_one_or_none()
            
            if sender:
                print(f"  Sender is User: {sender.first_name} {sender.last_name} ({sender.role})")
            elif sender_staff:
                print(f"  Sender is Staff: {sender_staff.first_name} {sender_staff.last_name}")
            else:
                print(f"  Sender NOT found in User or Staff tables")
            
            # Check receiver
            receiver_as_user = await session.execute(select(User).where(User.id == msg.receiver_id))
            receiver = receiver_as_user.scalar_one_or_none()
            receiver_as_parent = await session.execute(select(Parent).where(Parent.id == msg.receiver_id))
            receiver_parent = receiver_as_parent.scalar_one_or_none()
            
            if receiver:
                print(f"  Receiver is User: {receiver.first_name} {receiver.last_name} ({receiver.role})")
            elif receiver_parent:
                print(f"  Receiver is Parent (ID): {receiver_parent.first_name} {receiver_parent.last_name}")
                if receiver_parent.user_id:
                    parent_user = await session.execute(select(User).where(User.id == receiver_parent.user_id))
                    parent_user_obj = parent_user.scalar_one_or_none()
                    if parent_user_obj:
                        print(f"    └─ Maps to User: {parent_user_obj.first_name} {parent_user_obj.last_name}")
            else:
                print(f"  Receiver NOT found in User or Parent tables")
            
            # Now test if a parent user would find this message
            print(f"\n  Testing visibility for each parent:")
            
            all_parents_result = await session.execute(select(User).where(User.role == UserRole.PARENT))
            parent_users = all_parents_result.scalars().all()
            
            for parent_user in parent_users:
                search_ids = [parent_user.id]
                
                # Check if parent has a parent_id
                parent_record = await session.execute(select(Parent).where(Parent.user_id == parent_user.id))
                parent_obj = parent_record.scalar_one_or_none()
                if parent_obj:
                    search_ids.append(parent_obj.id)
                
                # Check if message matches
                if msg.sender_id in search_ids or msg.receiver_id in search_ids:
                    print(f"    ✓ {parent_user.first_name} {parent_user.last_name} would see this (search_ids: {[id[:8]+'...' for id in search_ids]})")
                else:
                    print(f"    ✗ {parent_user.first_name} {parent_user.last_name} would NOT see this (search_ids: {[id[:8]+'...' for id in search_ids]})")
        
        print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(test_teacher_to_parent_message())
