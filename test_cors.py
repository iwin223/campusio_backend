import asyncio
import httpx

async def test_cors():
    """Test if CORS headers are present in the response"""
    
    student_id = "ba00550b-6c63-4322-a119-0a441df8ad47"
    token = "test_token"  # We'll test preflight first without authentication
    
    async with httpx.AsyncClient() as client:
        # Test OPTIONS request (CORS preflight)
        print("Testing CORS Preflight Request...")
        print("=" * 60)
        
        preflight_response = await client.options(
            f"http://localhost:8000/api/parent/child/{student_id}/assignment-metrics",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization, Content-Type",
            }
        )
        
        print(f"Status: {preflight_response.status_code}\n")
        print("Response Headers:")
        for key, value in preflight_response.headers.items():
            if key.lower().startswith("access-control"):
                print(f"  ✓ {key}: {value}")
            elif key.lower() in ["content-type"]:
                print(f"    {key}: {value}")
        
        cors_headers = {k: v for k, v in preflight_response.headers.items() if k.lower().startswith("access-control")}
        
        if cors_headers:
            print("\n✅ CORS headers found!")
        else:
            print("\n❌ No CORS headers found!")
        
        print("\n" + "=" * 60)
        print("Testing GET Request with Origin header...\n")
        
        get_response = await client.get(
            f"http://localhost:8000/api/parent/child/{student_id}/assignment-metrics",
            headers={
                "Origin": "http://localhost:3000",
                "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        )
        
        print(f"Status: {get_response.status_code}\n")
        print("CORS Response Headers:")
        cors_found = False
        for key, value in get_response.headers.items():
            if key.lower().startswith("access-control"):
                print(f"  ✓ {key}: {value}")
                cors_found = True
            elif key == "Origin":
                print(f"  {key}: {value}")
        
        if not cors_found:
            print("  (No CORS headers)")

asyncio.run(test_cors())
