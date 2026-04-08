"""
Test script to verify parent can see conversations with their parent_id stored in database
"""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, or_
from models.communication import Message
from models.student import Parent
from models.user import User, UserRole

async def test_parent_conversations():
    from database import async_engine, async_session as session_factory
    
    async with session_factory() as session:
        print("\n" + "="*80)
        print("PARENT CONVERSATION TEST")
        print("="*80)
        
        # Find a parent user
        parent_user_result = await session.execute(
            select(User).where(User.role == UserRole.PARENT).limit(1)
        )
        parent_user = parent_user_result.scalar_one_or_none()
        
        if not parent_user:
            print("\n  ✗ No parent users found in database")
            return
        
        print(f"\n✓ Found parent user: {parent_user.first_name} {parent_user.last_name}")
        print(f"  User ID: {parent_user.id}")
        
        # Find their parent record
        parent_record_result = await session.execute(
            select(Parent).where(Parent.user_id == parent_user.id)
        )
        parent_record = parent_record_result.scalar_one_or_none()
        
        if parent_record:
            print(f"  Parent ID: {parent_record.id}")
        else:
            print(f"  ✗ No Parent record linked to this user")
        
        # Find messages where this parent is involved
        conditions = [
            Message.sender_id == parent_user.id,
            Message.receiver_id == parent_user.id,
        ]
        if parent_record:
            conditions.extend([
                Message.sender_id == parent_record.id,
                Message.receiver_id == parent_record.id,
            ])
        
        messages_result = await session.execute(
            select(Message).where(or_(*conditions))
        )
        messages = messages_result.scalars().all()
        
        print(f"\n  Messages found: {len(messages)}")
        for msg in messages:
            print(f"    - Sender: {msg.sender_id[:8]}... | Receiver: {msg.receiver_id[:8]}...")
            print(f"      Content: {msg.content[:50]}...")
        
        # Now simulate what the backend query does
        print(f"\n  Testing backend search logic:")
        search_ids = [parent_user.id]
        if parent_record:
            search_ids.append(parent_record.id)
        
        print(f"    Search IDs: {[id[:8] + '...' for id in search_ids]}")
        
        backend_messages_result = await session.execute(
            select(Message).where(
                (Message.sender_id.in_(search_ids)) | (Message.receiver_id.in_(search_ids))
            )
        )
        backend_messages = backend_messages_result.scalars().all()
        
        print(f"    ✓ Backend query found: {len(backend_messages)} messages")
        
        # Group into conversations like the endpoint does
        conversations = {}
        for msg in backend_messages:
            # Determine other_user_id
            if msg.sender_id in search_ids:
                other_user_id = msg.receiver_id
            else:
                other_user_id = msg.sender_id
            
            if other_user_id not in conversations:
                conversations[other_user_id] = {
                    "last_message": msg.content[:50],
                    "with": other_user_id[:8] + "..."
                }
        
        print(f"\n  ✓ Conversations grouped: {len(conversations)}")
        for other_id, data in conversations.items():
            print(f"    - With: {data['with']} | Last: {data['last_message']}")
        
        print("\n" + "="*80)
        if len(conversations) > 0:
            print("✓ PASS: Parent can see conversations!")
        else:
            print("✗ FAIL: Parent has no conversations")
        print("="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(test_parent_conversations())
