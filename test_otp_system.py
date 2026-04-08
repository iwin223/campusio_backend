"""
Comprehensive OTP System Test Suite

Tests:
1. OTP generation and verification
2. Admin OTP settings management
3. Login flow with OTP
4. SMS/Email delivery methods
5. Role-based OTP requirements
6. OTP expiry and attempt limits
"""

import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, select

from models.user import User, UserRole
from models.school import School
from models.otp import OTP, OTPSettings, OTPAdminSettings
from utils.otp import (
    generate_otp_code,
    create_otp,
    verify_otp,
    get_otp_settings,
    create_or_update_otp_settings,
    get_admin_otp_settings,
    create_or_update_admin_otp_settings,
    send_otp_email,
    send_otp_sms
)
from database import get_session
import uuid


# ==================== Test Database Setup ====================

@pytest.fixture
async def test_db():
    """Create in-memory test database"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    
    async with AsyncSession(engine) as session:
        yield session


# ==================== Test Data Fixtures ====================

@pytest.fixture
async def test_school(test_db):
    """Create test school"""
    school = School(
        id=str(uuid.uuid4()),
        name="Test School",
        email="test@school.com",
        phone="0501234567",
        address="123 Test St",
        city="Accra",
        region="Greater Accra"
    )
    test_db.add(school)
    await test_db.commit()
    await test_db.refresh(school)
    return school


@pytest.fixture
async def test_user_school_admin(test_db, test_school):
    """Create test School Admin user"""
    user = User(
        id=str(uuid.uuid4()),
        email="admin@school.com",
        password_hash="hashed_password",
        first_name="John",
        last_name="Admin",
        phone="0534484781",
        role=UserRole.SCHOOL_ADMIN,
        school_id=test_school.id,
        is_active=True
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest.fixture
async def test_user_teacher(test_db, test_school):
    """Create test Teacher user (OTP optional)"""
    user = User(
        id=str(uuid.uuid4()),
        email="teacher@school.com",
        password_hash="hashed_password",
        first_name="Jane",
        last_name="Teacher",
        phone="0509876543",
        role=UserRole.TEACHER,
        school_id=test_school.id,
        is_active=True
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


# ==================== OTP Generation Tests ====================

class TestOTPGeneration:
    """Test OTP code generation"""
    
    def test_otp_code_generation(self):
        """Test that OTP codes are 6 digits"""
        otp_code = generate_otp_code()
        assert len(otp_code) == 6
        assert otp_code.isdigit()
    
    def test_otp_code_uniqueness(self):
        """Test that generated OTP codes are unique"""
        codes = {generate_otp_code() for _ in range(100)}
        # While not guaranteed, 100 unique out of 100 is highly likely
        assert len(codes) > 90  # Allow for some collisions statistically
    
    def test_otp_code_format(self):
        """Test OTP code format"""
        for _ in range(10):
            code = generate_otp_code()
            assert code.isdigit()
            assert 0 <= int(code) < 1000000


# ==================== OTP Database Tests ====================

@pytest.mark.asyncio
class TestOTPDatabase:
    """Test OTP database operations"""
    
    async def test_create_otp(self, test_db, test_user_school_admin):
        """Test creating OTP record"""
        otp_code, otp_id = await create_otp(test_db, test_user_school_admin.id)
        
        assert len(otp_code) == 6
        assert otp_code.isdigit()
        assert otp_id is not None
        
        # Verify in database
        result = await test_db.execute(select(OTP).where(OTP.id == otp_id))
        otp_record = result.scalar_one_or_none()
        assert otp_record is not None
        assert otp_record.code == otp_code
        assert otp_record.user_id == test_user_school_admin.id
        assert not otp_record.is_used
    
    async def test_otp_expiry(self, test_db, test_user_school_admin):
        """Test OTP expiry time"""
        otp_code, otp_id = await create_otp(test_db, test_user_school_admin.id, expires_in_minutes=10)
        
        result = await test_db.execute(select(OTP).where(OTP.id == otp_id))
        otp_record = result.scalar_one_or_none()
        
        # Check expiry is approximately 10 minutes from now
        expires_in = (otp_record.expires_at - datetime.now(timezone.utc)).total_seconds() / 60
        assert 9.5 < expires_in < 10.5  # Allow 30 second variance
    
    async def test_invalidate_previous_otps(self, test_db, test_user_school_admin):
        """Test that previous unused OTPs are invalidated"""
        # Create first OTP
        code1, id1 = await create_otp(test_db, test_user_school_admin.id)
        
        # Create second OTP
        code2, id2 = await create_otp(test_db, test_user_school_admin.id)
        
        # Check first OTP is marked as used
        result = await test_db.execute(select(OTP).where(OTP.id == id1))
        otp1 = result.scalar_one_or_none()
        assert otp1.is_used
        
        # Check second OTP is not used
        result = await test_db.execute(select(OTP).where(OTP.id == id2))
        otp2 = result.scalar_one_or_none()
        assert not otp2.is_used


# ==================== OTP Verification Tests ====================

@pytest.mark.asyncio
class TestOTPVerification:
    """Test OTP verification"""
    
    async def test_verify_valid_otp(self, test_db, test_user_school_admin):
        """Test verifying a valid OTP"""
        otp_code, _ = await create_otp(test_db, test_user_school_admin.id)
        
        # Should not raise exception
        result = await verify_otp(test_db, test_user_school_admin.id, otp_code)
        assert result is True
        
        # Verify OTP is marked as used
        result = await test_db.execute(
            select(OTP).where(
                OTP.user_id == test_user_school_admin.id,
                OTP.code == otp_code
            )
        )
        otp_record = result.scalar_one_or_none()
        assert otp_record.is_used
    
    async def test_verify_invalid_otp(self, test_db, test_user_school_admin):
        """Test verifying an invalid OTP"""
        await create_otp(test_db, test_user_school_admin.id)
        
        with pytest.raises(Exception) as exc_info:
            await verify_otp(test_db, test_user_school_admin.id, "999999")
        
        assert "Invalid or expired OTP" in str(exc_info.value)
    
    async def test_verify_expired_otp(self, test_db, test_user_school_admin):
        """Test verifying an expired OTP"""
        otp_code, otp_id = await create_otp(test_db, test_user_school_admin.id, expires_in_minutes=0)
        
        # Manually set expiry to past
        result = await test_db.execute(select(OTP).where(OTP.id == otp_id))
        otp_record = result.scalar_one_or_none()
        otp_record.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        test_db.add(otp_record)
        await test_db.commit()
        
        with pytest.raises(Exception) as exc_info:
            await verify_otp(test_db, test_user_school_admin.id, otp_code)
        
        assert "expired" in str(exc_info.value).lower()
    
    async def test_otp_attempt_tracking(self, test_db, test_user_school_admin):
        """Test OTP attempt tracking"""
        otp_code, otp_id = await create_otp(test_db, test_user_school_admin.id)
        
        # Try with wrong code multiple times
        for i in range(3):
            try:
                await verify_otp(test_db, test_user_school_admin.id, "000000")
            except:
                pass
            
            # Check attempt count
            result = await test_db.execute(select(OTP).where(OTP.id == otp_id))
            otp_record = result.scalar_one_or_none()
            assert otp_record.attempts == i + 1


# ==================== OTP Settings Tests ====================

@pytest.mark.asyncio
class TestOTPSettings:
    """Test user OTP settings"""
    
    async def test_get_otp_settings_nonexistent(self, test_db, test_user_teacher):
        """Test getting settings for user with no settings"""
        settings = await get_otp_settings(test_db, test_user_teacher.id)
        assert settings is None
    
    async def test_create_otp_settings(self, test_db, test_user_teacher):
        """Test creating OTP settings"""
        settings = await create_or_update_otp_settings(
            test_db,
            test_user_teacher.id,
            is_enabled=True,
            method="sms"
        )
        
        assert settings.user_id == test_user_teacher.id
        assert settings.is_enabled
        assert settings.method == "sms"
    
    async def test_update_otp_settings(self, test_db, test_user_teacher):
        """Test updating OTP settings"""
        # Create with email
        await create_or_update_otp_settings(
            test_db,
            test_user_teacher.id,
            is_enabled=True,
            method="email"
        )
        
        # Update to SMS
        settings = await create_or_update_otp_settings(
            test_db,
            test_user_teacher.id,
            is_enabled=True,
            method="sms"
        )
        
        # Verify updated
        retrieved = await get_otp_settings(test_db, test_user_teacher.id)
        assert retrieved.method == "sms"
    
    async def test_mandatory_otp_for_admin(self, test_db, test_user_school_admin):
        """Test mandatory OTP setting for admins"""
        settings = await create_or_update_otp_settings(
            test_db,
            test_user_school_admin.id,
            is_enabled=True,
            method="sms"
        )
        
        # For school admin, is_mandatory should be True
        settings.is_mandatory = True
        test_db.add(settings)
        await test_db.commit()
        
        retrieved = await get_otp_settings(test_db, test_user_school_admin.id)
        assert retrieved.is_mandatory


# ==================== Admin OTP Settings Tests ====================

@pytest.mark.asyncio
class TestAdminOTPSettings:
    """Test school-wide OTP admin settings"""
    
    async def test_get_admin_settings_nonexistent(self, test_db, test_school):
        """Test getting settings that don't exist"""
        settings = await get_admin_otp_settings(test_db, test_school.id)
        assert settings is None
    
    async def test_create_admin_otp_settings(self, test_db, test_school):
        """Test creating admin OTP settings"""
        settings = await create_or_update_admin_otp_settings(
            test_db,
            test_school.id,
            is_enabled=True,
            expiry_minutes=10,
            max_attempts=3,
            default_method="sms",
            require_for_roles=["school_admin", "hr"]
        )
        
        assert settings.school_id == test_school.id
        assert settings.is_enabled
        assert settings.expiry_minutes == 10
        assert settings.max_attempts == 3
        assert settings.default_method == "sms"
        assert "school_admin" in settings.require_for_roles
    
    async def test_update_admin_otp_settings(self, test_db, test_school):
        """Test updating admin OTP settings"""
        # Create initial
        await create_or_update_admin_otp_settings(
            test_db,
            test_school.id,
            is_enabled=True,
            default_method="email"
        )
        
        # Update
        settings = await create_or_update_admin_otp_settings(
            test_db,
            test_school.id,
            is_enabled=True,
            expiry_minutes=15,
            max_attempts=5,
            default_method="sms"
        )
        
        assert settings.expiry_minutes == 15
        assert settings.max_attempts == 5
        assert settings.default_method == "sms"
    
    async def test_admin_settings_validation(self, test_db, test_school):
        """Test validation of admin settings"""
        # Test invalid expiry minutes
        with pytest.raises(ValueError) as exc:
            await create_or_update_admin_otp_settings(
                test_db,
                test_school.id,
                expiry_minutes=0  # Invalid: must be 1-60
            )
        assert "expiry_minutes" in str(exc.value)
        
        # Test invalid max attempts
        with pytest.raises(ValueError) as exc:
            await create_or_update_admin_otp_settings(
                test_db,
                test_school.id,
                max_attempts=11  # Invalid: must be 1-10
            )
        assert "max_attempts" in str(exc.value)
        
        # Test invalid method
        with pytest.raises(ValueError) as exc:
            await create_or_update_admin_otp_settings(
                test_db,
                test_school.id,
                default_method="invalid"
            )
        assert "default_method" in str(exc.value)
    
    async def test_admin_settings_role_configuration(self, test_db, test_school):
        """Test role-based OTP requirement configuration"""
        settings = await create_or_update_admin_otp_settings(
            test_db,
            test_school.id,
            require_for_roles=["school_admin", "hr", "teacher"]
        )
        
        roles = settings.require_for_roles.split(",")
        assert "school_admin" in roles
        assert "hr" in roles
        assert "teacher" in roles
        assert "super_admin" not in roles  # Should not have super_admin


# ==================== SMS/Email Delivery Tests ====================

class TestOTPDelivery:
    """Test OTP delivery methods"""
    
    @pytest.mark.asyncio
    async def test_send_otp_sms(self):
        """Test SMS OTP sending"""
        # Note: This will attempt actual SMS send via USMS-GH
        # Set test phone number
        test_phone = "0501234567"  # Will use format_phone_number internally
        
        # Send OTP
        result = await send_otp_sms(test_phone, "123456")
        
        # Should return True or False based on API response
        assert isinstance(result, bool)
        print(f"✅ SMS OTP sending test: {result}")
    
    def test_send_otp_email(self):
        """Test Email OTP sending"""
        # Note: This requires SMTP configuration
        test_email = "test@example.com"
        result = send_otp_email(test_email, "123456", "Test User")
        
        # Should return True or False
        assert isinstance(result, bool)
        print(f"✅ Email OTP sending test: {result}")
    
    @pytest.mark.asyncio
    async def test_sms_with_empty_phone(self):
        """Test SMS sending with empty phone"""
        result = await send_otp_sms("", "123456")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_sms_phone_formatting(self):
        """Test that phone numbers are handled correctly"""
        # This tests the integration with sms_service
        test_cases = [
            "0501234567",      # Local format
            "233501234567",    # International format
            "+233501234567"    # International with plus
        ]
        
        for phone in test_cases:
            result = await send_otp_sms(phone, "123456")
            assert isinstance(result, bool)
            print(f"✅ Phone format {phone}: {result}")


# ==================== Integration Tests ====================

@pytest.mark.asyncio
class TestOTPIntegration:
    """Integration tests for complete OTP flow"""
    
    async def test_complete_login_otp_flow(self, test_db, test_user_school_admin, test_school):
        """Test complete login + OTP + verification flow"""
        # 1. Get admin settings
        settings = await create_or_update_admin_otp_settings(
            test_db,
            test_school.id,
            is_enabled=True,
            default_method="sms",
            require_for_roles=["school_admin", "hr"]
        )
        assert settings.is_enabled
        
        # 2. User logs in (credentials valid)
        # Normally login would check credentials here
        
        # 3. Check if user role requires OTP
        assert test_user_school_admin.role.value == "school_admin"
        
        # 4. Generate and send OTP
        otp_code, otp_id = await create_otp(test_db, test_user_school_admin.id)
        assert len(otp_code) == 6
        
        # 5. User receives OTP and enters it
        # Verify OTP
        result = await verify_otp(test_db, test_user_school_admin.id, otp_code)
        assert result is True
        
        # 6. Login complete
        print("✅ Complete login + OTP + verification flow successful")
    
    async def test_optional_otp_flow(self, test_db, test_user_teacher):
        """Test OTP flow for user with optional OTP"""
        # Teacher can enable OTP optionally
        settings = await create_or_update_otp_settings(
            test_db,
            test_user_teacher.id,
            is_enabled=True,
            method="email"
        )
        
        # If enabled, they get OTP
        if settings.is_enabled:
            otp_code, _ = await create_otp(test_db, test_user_teacher.id)
            result = await verify_otp(test_db, test_user_teacher.id, otp_code)
            assert result is True
        
        print("✅ Optional OTP flow successful")
    
    async def test_otp_resend_flow(self, test_db, test_user_school_admin):
        """Test resending OTP (new code generation)"""
        # First OTP
        code1, id1 = await create_otp(test_db, test_user_school_admin.id)
        
        # User asks to resend (creates new OTP, old one invalidated)
        code2, id2 = await create_otp(test_db, test_user_school_admin.id)
        
        # codes should be different
        assert code1 != code2
        
        # Old OTP should be marked as used (invalidated)
        result = await test_db.execute(select(OTP).where(OTP.id == id1))
        old_otp = result.scalar_one_or_none()
        assert old_otp.is_used
        
        # New OTP should be usable
        result = await test_db.execute(select(OTP).where(OTP.id == id2))
        new_otp = result.scalar_one_or_none()
        assert not new_otp.is_used
        
        print("✅ OTP resend flow successful")


# ==================== Test Execution ====================

if __name__ == "__main__":
    """Run tests with pytest"""
    pytest.main([__file__, "-v", "--tb=short"])
