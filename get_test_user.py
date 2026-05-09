#!/usr/bin/env python3
"""Get a test user from the database"""
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlmodel import SQLModel
from models.user import User
from config import get_settings

async def get_test_user():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    
    async with AsyncSession(engine) as session:
        result = await session.execute(select(User).limit(5))
        users = result.scalars().all()
        
        if not users:
            print("No users found in database")
            return None
        
        print(f"Found {len(users)} users:")
        for user in users:
            print(f"  ID: {user.id}")
            print(f"  Email: {user.email}")
            print(f"  Role: {user.role}")
            print(f"  School ID: {user.school_id}")
            print(f"  Active: {user.is_active}")
            print()
        
        return users[0]

asyncio.run(get_test_user())
