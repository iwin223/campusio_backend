#!/usr/bin/env python3
"""
Verify the message response format is correct and JSON serializable
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database import SessionLocal
from models.communication import Message
from models.user import User

def main():
    db = SessionLocal()
    
    try:
        print("✓ Checking actual message response format...\n")
        
        # Get a message
        message = db.query(Message).first()
        if not message:
            print("✗ No messages found in database")
            return
            
        # Get sender info
        sender = db.query(User).filter(User.id == message.sender_id).first()
        
        # Build the response like the endpoint does
        response = {
            "id": message.id,
            "sender_id": message.sender_id,
            "sender_name": f"{sender.first_name} {sender.last_name}" if sender else "Unknown",
            "receiver_id": message.receiver_id,
            "content": message.content,
            "message_type": message.message_type.value,  # ← The fix: .value converts enum to string
            "is_read": message.is_read,
            "created_at": message.created_at.isoformat()
        }
        
        print("✓ Response object:")
        print(json.dumps(response, indent=2))
        
        print("\n✓ Each field:")
        print(f"  - id: {type(message.id).__name__} = {message.id}")
        print(f"  - sender_name: {type(response['sender_name']).__name__} = '{response['sender_name']}'")
        print(f"  - message_type: {type(response['message_type']).__name__} = '{response['message_type']}'")
        print(f"  - content: {type(response['content']).__name__} = '{response['content'][:50]}'...")
        print(f"  - is_read: {type(response['is_read']).__name__} = {response['is_read']}")
        print(f"  - created_at: {type(response['created_at']).__name__} = '{response['created_at']}'")
        
        print("\n✓ JSON Serializable? ", end="")
        try:
            json.dumps(response)
            print("YES ✓")
        except Exception as e:
            print(f"NO ✗ - {e}")
            
    finally:
        db.close()

if __name__ == "__main__":
    main()
