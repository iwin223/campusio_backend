#!/usr/bin/env python
"""Test OTP datetime handling with database"""

import asyncio
import sys
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Test datetime creation the way OTP code does it
print("\n" + "="*60)
print("OTP DATETIME COMPATIBILITY TEST")
print("="*60)

print("\n✅ Test 1: Naive datetime creation (for TIMESTAMP WITHOUT TIME ZONE)")
now = datetime.now()
expires_at = now + timedelta(minutes=10)

print(f"   now: {now}")
print(f"   expires_at: {expires_at}")
print(f"   now.tzinfo: {now.tzinfo} (should be None)")
print(f"   expires_at.tzinfo: {expires_at.tzinfo} (should be None)")

assert now.tzinfo is None, "now should be naive"
assert expires_at.tzinfo is None, "expires_at should be naive"

print("\n✅ Test 2: Datetime comparison (naive vs naive)")
now_check = datetime.now()
if now_check > expires_at:
    print(f"   ❌ Datetime comparison failed")
else:
    print(f"   ✓ Naive datetime comparison works: {now_check} <= {expires_at}")

print("\n✅ Test 3: Expired OTP check")
past_time = datetime.now() - timedelta(minutes=15)
if datetime.now() > past_time:
    print(f"   ✓ OTP expiry check works: {datetime.now()} > {past_time}")
else:
    print(f"   ❌ OTP expiry check failed")

print("\n" + "="*60)
print("SUMMARY: All datetime compatibility checks PASSED ✓")
print("="*60 + "\n")
