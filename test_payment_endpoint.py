import asyncio
import json
from httpx import AsyncClient
from database import async_session
from models.user import User, UserRole
from sqlmodel import select
from server import app

async def test_payment_endpoint():
    """Test the payment initialize endpoint"""
    
    async with async_session() as session:
        # Get a parent user
        parent_result = await session.execute(
            select(User).where(User.role == UserRole.PARENT)
        )
        parent_user = parent_result.scalar_one_or_none()
        
        if not parent_user:
            print("No parent user found!")
            return
        
        print(f"Found parent: {parent_user.first_name} {parent_user.last_name}")
        print(f"Parent ID: {parent_user.id}")
        print()
        
        # Get a fee for this parent's child
        from models.fee import Fee
        from models.student import Student, StudentParent, Parent
        
        # Get parent record
        parent_record_result = await session.execute(
            select(Parent).where(Parent.user_id == parent_user.id)
        )
        parent_record = parent_record_result.scalar_one_or_none()
        
        if not parent_record:
            print("No parent record found!")
            return
        
        # Get first student-parent relationship
        sp_result = await session.execute(
            select(StudentParent).where(StudentParent.parent_id == parent_record.id).limit(1)
        )
        sp = sp_result.scalar_one_or_none()
        
        if not sp:
            print("No student-parent relationship found!")
            return
        
        # Get fee for this student
        fee_result = await session.execute(
            select(Fee).where(Fee.student_id == sp.student_id).limit(1)
        )
        fee = fee_result.scalar_one_or_none()
        
        if not fee:
            print("No fees found!")
            return
        
        print(f"Testing with fee: {fee.id}")
        print(f"Amount: {fee.amount_due}")
        print()
        
        # Test the endpoint
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Create token (would need proper auth, just for testing)
            # Let's just test the payload structure
            
            payload = {
                "fee_id": str(fee.id)
            }
            
            print("Sending payload:")
            print(json.dumps(payload, indent=2))
            print()
            
            response = await client.post(
                "/api/payments/initialize",
                json=payload,
                headers={"Authorization": f"Bearer test-token"}
            )
            
            print(f"Status Code: {response.status_code}")
            print(f"Response:")
            print(json.dumps(response.json(), indent=2))

asyncio.run(test_payment_endpoint())
