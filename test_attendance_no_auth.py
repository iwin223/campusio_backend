import asyncio
import httpx

async def test_without_auth():
    """Test the endpoint without authentication"""
    
    student_id = "ba00550b-6c63-4322-a119-0a441df8ad47"
    
    print(f"Testing Attendance Endpoint WITHOUT Authorization")
    print(f"Student ID: {student_id}")
    print(f"\n" + "="*60 + "\n")
    
    try:
        async with httpx.AsyncClient() as client:
            # Try without token
            print("Testing without token...")
            response = await client.get(
                f"http://127.0.0.1:8000/api/parent/child/{student_id}/attendance?days=30"
            )
            
            print(f"Response Status: {response.status_code}\n")
            try:
                print(f"Response: {response.json()}")
            except:
                print(f"Response text: {response.text}")
            
            print("\n" + "="*60 + "\n")
            
            # Try with empty token
            print("Testing with empty token...")
            headers = {"Authorization": "Bearer "}
            response2 = await client.get(
                f"http://127.0.0.1:8000/api/parent/child/{student_id}/attendance?days=30",
                headers=headers
            )
            
            print(f"Response Status: {response2.status_code}\n")
            try:
                print(f"Response: {response2.json()}")
            except:
                print(f"Response text: {response2.text}")
                
    except Exception as e:
        print(f"❌ Exception: {e}")

asyncio.run(test_without_auth())
