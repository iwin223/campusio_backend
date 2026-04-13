import asyncio
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select
from models.fee import Fee

database_url = "postgresql+asyncpg://postgres:2211@localhost:5432/school-erp"

async def test_attendance_endpoint():
    """Test the attendance endpoint"""
    
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Get the student ID
        fee_result = await session.execute(select(Fee).limit(1))
        fee = fee_result.scalar_one_or_none()
        student_id = fee.student_id
        
        print(f"Testing Attendance Endpoint")
        print(f"Student ID: {student_id}")
        print(f"\n" + "="*60 + "\n")
        
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
                    print(f"✅ Login successful!\n")
                    
                    # Step 2: Get attendance
                    print("Step 2: Fetching child attendance...")
                    headers = {"Authorization": f"Bearer {token}"}
                    attendance_response = await client.get(
                        f"http://127.0.0.1:8000/api/parent/child/{student_id}/attendance?days=30",
                        headers=headers
                    )
                    
                    print(f"Response Status: {attendance_response.status_code}\n")
                    
                    if attendance_response.status_code == 200:
                        data = attendance_response.json()
                        print("✅ SUCCESS!")
                        print(f"Student: {data.get('student_name')}")
                        print(f"Attendance Summary: {data.get('summary')}")
                        print(f"Records count: {len(data.get('records', []))}")
                    else:
                        print(f"❌ Error: {attendance_response.status_code}")
                        print(f"Response: {attendance_response.json()}")
                else:
                    print(f"❌ Login failed: {login_response.status_code}")
                    print(login_response.json())
        except Exception as e:
            print(f"❌ Exception: {e}")
    
    await engine.dispose()

asyncio.run(test_attendance_endpoint())
