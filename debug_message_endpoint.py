"""
Debug script to check what /api/communication/conversations/with/{id} returns
"""
import asyncio
import json
from sqlalchemy import select
from models.communication import Message
from models.user import User, UserRole
from models.student import Parent
from models.staff import Staff

async def debug_message_endpoint():
    from database import async_session as session_factory
    
    async with session_factory() as session:
        print("\n" + "="*80)
        print("DEBUG: Message Endpoint Response")
        print("="*80)
        
        # Get a parent user
        parent_user_result = await session.execute(
            select(User).where(User.role == UserRole.PARENT).limit(1)
        )
        parent_user = parent_user_result.scalar_one_or_none()
        
        if not parent_user:
            print("\n✗ No parent users found")
            return
        
        print(f"\n✓ Parent User: {parent_user.first_name} {parent_user.last_name}")
        print(f"  ID: {parent_user.id}")
        
        # Get parent's parent_id
        parent_record = await session.execute(
            select(Parent).where(Parent.user_id == parent_user.id)
        )
        parent_obj = parent_record.scalar_one_or_none()
        
        if parent_obj:
            print(f"  Parent ID: {parent_obj.id}")
        else:
            print(f"  ✗ No Parent record")
        
        # Get all conversations for this parent
        search_ids = [parent_user.id]
        if parent_obj:
            search_ids.append(parent_obj.id)
        
        all_msg_result = await session.execute(
            select(Message).where(
                (Message.sender_id.in_(search_ids)) | (Message.receiver_id.in_(search_ids))
            )
        )
        all_messages = all_msg_result.scalars().all()
        
        print(f"\n✓ Parent has {len(all_messages)} messages total")
        
        if len(all_messages) == 0:
            print("  No messages found!")
            return
        
        # Get unique conversation partners
        partners = set()
        for msg in all_messages:
            if msg.sender_id in search_ids:
                partners.add(msg.receiver_id)
            else:
                partners.add(msg.sender_id)
        
        print(f"  Unique conversation partners: {len(partners)}")
        
        # Test fetching messages for first conversation
        if partners:
            other_user_id = list(partners)[0]
            print(f"\n  Testing endpoint for conversation_id: {other_user_id[:16]}...")
            
            # Simulate the backend query
            current_user_search_ids = search_ids
            other_user_search_ids = [other_user_id]
            
            # Check if other_user_id is parent_id
            other_parent = await session.execute(
                select(Parent).where(Parent.id == other_user_id)
            )
            other_parent_obj = other_parent.scalar_one_or_none()
            if other_parent_obj and other_parent_obj.user_id:
                other_user_search_ids.append(other_parent_obj.user_id)
                print(f"\n  Other user is Parent with user_id: {other_parent_obj.user_id[:16]}...")
            
            # Check if other_user_id is staff_id
            other_staff = await session.execute(
                select(Staff).where(Staff.id == other_user_id)
            )
            other_staff_obj = other_staff.scalar_one_or_none()
            if other_staff_obj and other_staff_obj.user_id:
                other_user_search_ids.append(other_staff_obj.user_id)
                print(f"\n  Other user is Staff with user_id: {other_staff_obj.user_id[:16]}...")
            
            # Get messages
            msg_result = await session.execute(
                select(Message).where(
                    (
                        Message.sender_id.in_(current_user_search_ids) & 
                        Message.receiver_id.in_(other_user_search_ids)
                    ) |
                    (
                        Message.sender_id.in_(other_user_search_ids) & 
                        Message.receiver_id.in_(current_user_search_ids)
                    )
                )
            )
            messages = msg_result.scalars().all()
            
            print(f"\n  ✓ Endpoint would return {len(messages)} messages")
            
            # Show structure like the endpoint returns
            print(f"\n  Response structure (first 2 messages):")
            
            for idx, msg in enumerate(messages[:2]):
                sender_user = await session.execute(select(User).where(User.id == msg.sender_id))
                sender = sender_user.scalar_one_or_none()
                
                print(f"\n    Message {idx+1}:")
                print(f"      id: {msg.id[:16]}...")
                print(f"      sender_id: {msg.sender_id[:16]}...")
                print(f"      sender_name: {sender.first_name if sender else 'UNKNOWN'} {sender.last_name if sender else ''}")
                print(f"      content: {msg.content[:40]}...")
                print(f"      message_type: {msg.message_type}")
                print(f"      is_read: {msg.is_read}")
                print(f"      created_at: {msg.created_at}")

if __name__ == "__main__":
    asyncio.run(debug_message_endpoint())
