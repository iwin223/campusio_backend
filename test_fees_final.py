import asyncio
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select
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
        
        print(f"🔗 Testing Parent Portal - Fees Endpoint\n")
        print(f"Student ID: {student_id}")
        print(f"Parent Email: parent@school.edu.gh")
        print(f"\n" + "="*50 + "\n")
        
        try:
            async with httpx.AsyncClient() as client:
                # Step 1: Login
                print("Step 1: Authenticating parent...")
                login_response = await client.post(
                    "http://localhost:8000/api/auth/login",
                    json={
                        "email": "parent@school.edu.gh",
                        "password": "parent123"
                    }
                )
                
                if login_response.status_code == 200:
                    token = login_response.json().get("access_token")
                    print(f"✅ Login successful!")
                    print(f"   Token: {token[:30]}...\n")
                    
                    # Step 2: Get fees
                    print("Step 2: Fetching child fees...")
                    headers = {"Authorization": f"Bearer {token}"}
                    fees_response = await client.get(
                        f"http://localhost:8000/api/parent/child/{student_id}/fees",
                        headers=headers
                    )
                    
                    print(f"Response Status: {fees_response.status_code}\n")
                    
                    if fees_response.status_code == 200:
                        fees_data = fees_response.json()
                        print("✅ SUCCESS! Fees retrieved:")
                        print(json.dumps(fees_data, indent=2, default=str))
                    else:
                        print(f"❌ Error: {fees_response.status_code}")
                        print(fees_response.text)
                else:
                    print(f"❌ Login failed: {login_response.status_code}")
                    print(login_response.json())
        except Exception as e:
            print(f"❌ Exception: {e}")
    
    await engine.dispose()

asyncio.run(test_endpoint())
