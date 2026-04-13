"""
Fetch all available banks from PaystackAPI to find correct bank codes for Ghana mobile money
"""
import httpx
import asyncio
import json
import os
from dotenv import load_dotenv

load_dotenv()

PAYSTACK_SECRET = os.getenv("PAYSTACK_SECRET_KEY")

async def get_paystack_banks():
    """Fetch all banks from Paystack"""
    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        # Get all banks - try with currency=GHS
        response = await client.get(
            "https://api.paystack.co/bank?currency=GHS",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            banks = data.get("data", [])
            
            print(f"\n✅ Found {len(banks)} banks for GHS currency\n")
            
            # Filter for mobile money providers
            momo_banks = [b for b in banks if any(x in b.get("name", "").lower() for x in ["mtn", "vodafone", "airtel", "tigo", "mobile", "money"])]
            
            print("== MOBILE MONEY PROVIDERS ==")
            for bank in sorted(momo_banks, key=lambda x: x.get("name", "")):
                print(f"  Name: {bank.get('name')}")
                print(f"  Code: {bank.get('code')}")
                print(f"  ID: {bank.get('id')}")
                print()
            
            print("\n== ALL BANKS ==")
            for bank in sorted(banks, key=lambda x: x.get("name", "")):
                print(f"{bank.get('code'):6} | {bank.get('name')}")
        else:
            print(f"Error: {response.status_code}")
            print(response.text)

asyncio.run(get_paystack_banks())
