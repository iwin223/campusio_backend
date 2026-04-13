import asyncio
import httpx

async def test_marie_access():
    """Test that Sam Marie can access Kofi Mensah's information"""
    
    student_id = "ba00550b-6c63-4322-a119-0a441df8ad47"  # Kofi Mensah
    
    print(f"Testing Sam Marie's Access to Kofi Mensah")
    print(f"\n" + "="*60 + "\n")
    
    try:
        async with httpx.AsyncClient() as client:
            # Step 1: Login as Sam Marie
            print("Step 1: Authenticating Sam Marie...")
            login_response = await client.post(
                "http://localhost:8000/api/auth/login",
                json={
                    "email": "sam.marie@tps001.school.edu.gh",
                    "password": "sam123"  # Default password from seed data
                }
            )
            
            if login_response.status_code == 200:
                token = login_response.json().get("access_token")
                print(f"✅ Login successful!\n")
                
                headers = {"Authorization": f"Bearer {token}"}
                
                # Test multiple endpoints
                endpoints = [
                    ("Fees", f"/api/parent/child/{student_id}/fees"),
                    ("Attendance", f"/api/parent/child/{student_id}/attendance?days=30"),
                    ("Assignments", f"/api/parent/child/{student_id}/assignments"),
                    ("Grades", f"/api/parent/child/{student_id}/grades"),
                ]
                
                print("Step 2: Testing endpoints...\n")
                
                for name, endpoint in endpoints:
                    response = await client.get(
                        f"http://localhost:8000{endpoint}",
                        headers=headers
                    )
                    
                    status = "✅" if response.status_code == 200 else "❌"
                    print(f"{status} {name:<15} {response.status_code}")
                
            else:
                print(f"❌ Login failed: {login_response.status_code}")
                print(login_response.json())
    except Exception as e:
        print(f"❌ Exception: {e}")

asyncio.run(test_marie_access())
