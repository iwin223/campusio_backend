import asyncio
import httpx
import json

async def analyze_fees_tab():
    """Analyze the parent portal fees tab"""
    
    student_id = "ba00550b-6c63-4322-a119-0a441df8ad47"  # Kofi Mensah
    
    print("="*70)
    print("PARENT PORTAL - FEES TAB ANALYSIS")
    print("="*70)
    
    try:
        async with httpx.AsyncClient() as client:
            # Login as Sam Marie
            login_response = await client.post(
                "http://localhost:8000/api/auth/login",
                json={
                    "email": "sam.marie@tps001.school.edu.gh",
                    "password": "sam123"
                }
            )
            
            if login_response.status_code != 200:
                print("❌ Login failed")
                return
            
            token = login_response.json().get("access_token")
            headers = {"Authorization": f"Bearer {token}"}
            
            # Get fees data
            fees_response = await client.get(
                f"http://localhost:8000/api/parent/child/{student_id}/fees",
                headers=headers
            )
            
            if fees_response.status_code != 200:
                print(f"❌ Error: {fees_response.status_code}")
                print(fees_response.json())
                return
            
            data = fees_response.json()
            
            print(f"\n📋 STUDENT: {data.get('student_name')}")
            print(f"{'─'*70}\n")
            
            # Analyze summary
            summary = data.get('summary', {})
            print("📊 SUMMARY METRICS:")
            print(f"  Total Due:        GHS {summary.get('total_due', 0):,.2f}")
            print(f"  Total Paid:       GHS {summary.get('total_paid', 0):,.2f}")
            print(f"  Outstanding:      GHS {summary.get('balance', 0):,.2f}")
            print(f"  Collection Rate:  {summary.get('collection_rate', 0)}%")
            
            print(f"\n{'─'*70}\n")
            
            # Analyze fees
            fees = data.get('fees', [])
            if fees:
                print(f"📝 FEE DETAILS ({len(fees)} fees):")
                print(f"{'─'*70}\n")
                
                for i, fee in enumerate(fees, 1):
                    print(f"Fee {i}:")
                    print(f"  Type:         {fee.get('fee_type', 'N/A').upper()}")
                    print(f"  Description:  {fee.get('description', 'N/A')}")
                    print(f"  Amount Due:   GHS {fee.get('amount_due', 0):,.2f}")
                    print(f"  Amount Paid:  GHS {fee.get('amount_paid', 0):,.2f}")
                    print(f"  Balance:      GHS {fee.get('balance', 0):,.2f}")
                    print(f"  Status:       {fee.get('status', 'N/A').upper()}")
                    print(f"  Due Date:     {fee.get('due_date', 'N/A')}")
                    
                    # Show payments
                    payments = fee.get('payments', [])
                    if payments:
                        print(f"  Payments ({len(payments)}):")
                        for payment in payments:
                            print(f"    - Receipt: {payment.get('receipt_number', 'N/A')}")
                            print(f"      Amount: GHS {payment.get('amount', 0):,.2f}")
                            print(f"      Date: {payment.get('payment_date', 'N/A')}")
                            print(f"      Method: {payment.get('payment_method', 'N/A')}")
                    else:
                        print(f"  Payments: None")
                    print()
            else:
                print("📝 NO FEES: Student has no fees recorded in the system")
            
            print(f"{'─'*70}\n")
            
            # Analysis and recommendations
            print("🔍 ANALYSIS & INSIGHTS:\n")
            
            if not fees:
                print("⚠️  ALERT: No fees found for this student")
                print("   Possible reasons:")
                print("   - Fee structure not assigned to student's class")
                print("   - Student enrolled after fee assignment")
                print("   - Fee structure not created for current term")
                print("\n   ACTION: Admin should:")
                print("   - Create a fee structure for the student's class/level")
                print("   - Assign it to the student or their class")
                print("   - Ensure it covers the current academic term")
            else:
                # Calculate statistics
                total_due = summary.get('total_due', 0)
                total_paid = summary.get('total_paid', 0)
                balance = summary.get('balance', 0)
                collection_rate = summary.get('collection_rate', 0)
                
                print(f"✓ Total fees owed: GHS {total_due:,.2f}")
                print(f"✓ Collection rate: {collection_rate}%")
                
                if balance == 0:
                    print("✅ STATUS: PAID IN FULL")
                elif balance == total_due:
                    print(f"⚠️  STATUS: FULLY OUTSTANDING (GHS {balance:,.2f})")
                    print("   ACTION: Parent should make payment")
                else:
                    print(f"⚠️  STATUS: PARTIALLY PAID")
                    print(f"   Outstanding: GHS {balance:,.2f}")
                    print(f"   ({collection_rate}% collected)")
                
                # Check for multiple fee types
                fee_types = set(f.get('fee_type') for f in fees)
                if len(fee_types) > 1:
                    print(f"\n✓ Multiple fee types: {', '.join(fee_types).upper()}")
                
                # Check due dates
                overdue = [f for f in fees if f.get('status') == 'pending' and f.get('balance', 0) > 0]
                if overdue:
                    print(f"\n⚠️  PENDING FEES: {len(overdue)} fee(s) awaiting payment")
            
            print(f"\n{'='*70}\n")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

asyncio.run(analyze_fees_tab())
