#!/usr/bin/env python
"""Quick OTP System Verification Test"""

import sys
import asyncio
from utils.otp import generate_otp_code

def test_otp_generation():
    """Test OTP code generation"""
    print("\n" + "="*60)
    print("OTP SYSTEM QUICK VERIFICATION TEST")
    print("="*60)
    
    print("\n✅ Test 1: OTP Code Generation")
    for i in range(5):
        code = generate_otp_code()
        print(f"   Generated OTP #{i+1}: {code}")
        assert len(code) == 6, f"OTP should be 6 digits, got {len(code)}"
        assert code.isdigit(), f"OTP should contain only digits, got {code}"
    
    print("\n✅ Test 2: OTP Code Uniqueness")
    codes = {generate_otp_code() for _ in range(100)}
    print(f"   Generated 100 codes, {len(codes)} were unique")
    assert len(codes) > 95, "Should have high uniqueness rate"
    
    print("\n✅ Test 3: OTP Format Verification")
    for _ in range(10):
        code = generate_otp_code()
        assert code.isdigit(), "Code should be numeric"
        assert 0 <= int(code) < 1000000, "Code should be in valid range"
    print(f"   All 10 format checks passed ✓")
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print("✅ OTP Generation: WORKING")
    print("✅ OTP Uniqueness: WORKING")
    print("✅ OTP Format: CORRECT")
    print("\nAll OTP core functionality tests PASSED!")
    print("="*60 + "\n")
    
    return True

if __name__ == "__main__":
    try:
        result = test_otp_generation()
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
