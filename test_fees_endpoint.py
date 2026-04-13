import asyncio
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select
from models.user import User, UserRole
from models.fee import Fee
import json

database_url = "postgresql+asyncpg://postgres:2211@localhost:5432/school-erp"

async def test_endpoint():
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Get the student ID
        fee_result = await session.execute(select(Fee).limit(1))
        fee = fee_result.scalar_one_or_none()
        student_id = fee.student_id
        
        # Get the parent
        parent_result = await session.execute(
            select(User).where(User.role == UserRole.PARENT).limit(1)
        )
        parent = parent_result.scalar_one_or_none()
        
        print(f"Student ID: {student_id}")
        print(f"Parent: {parent.first_name} {parent.last_name}")
        print(f"Email: {parent.email}")
        print(f"\n🔗 Now testing the endpoint...\n")
        
        # Make HTTP request to get JWT token
        print("Step 1: Getting JWT token...")
        async with httpx.AsyncClient() as client:
            # Login
            login_response = await client.post(
                "http://localhost:8000/api/auth/login",
                json={
                    "email": parent.email,
                    "password": "password123"  # Default password
                }
            )
            
            if login_response.status_code == 200:
                token = login_response.json().get("access_token")
                print(f"✓ Got token: {token[:20]}...")
                
                # Get fees
                print("\nStep 2: Getting child fees...")
                headers = {"Authorization": f"Bearer {token}"}
                fees_response = await client.get(
                    f"http://localhost:8000/api/parent/child/{student_id}/fees",
                    headers=headers
                )
                
                print(f"Status: {fees_response.status_code}")
                if fees_response.status_code == 200:
                    fees_data = fees_response.json()
                    print(f"\n✅ SUCCESS! Fees retrieved:")
                    print(json.dumps(fees_data, indent=2, default=str))
                else:
                    print(f"❌ Error: {fees_response.text}")
            else:
                print(f"❌ Login failed: {login_response.status_code}")
                print(login_response.text)
    
    await engine.dispose()

try:
    asyncio.run(test_endpoint())
except Exception as e:
    print(f"Error: {e}")
