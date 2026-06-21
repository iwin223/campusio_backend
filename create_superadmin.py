"""
One-time script to create the initial super admin account on a fresh system.

Usage:
  python create_superadmin.py
  python create_superadmin.py --email admin@campusio.com --password MySecret123

The account is created with must_change_password=False (you're setting it up yourself).
Run this once per deployment. If the email already exists it will exit safely.
"""
import asyncio
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlmodel import select
from database import async_engine, async_session, init_db
from models.user import User, UserRole
from models.otp import OTPSettings
from auth import get_password_hash


async def create_superadmin(email: str, password: str, first_name: str, last_name: str, phone: str):
    await init_db()

    async with async_session() as session:
        existing = await session.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            print(f"[SKIP] User with email '{email}' already exists.")
            return

        user = User(
            email=email,
            password_hash=get_password_hash(password),
            first_name=first_name,
            last_name=last_name,
            phone=phone or None,
            role=UserRole.SUPER_ADMIN,
            school_id=None,
            must_change_password=False,
        )
        session.add(user)
        await session.flush()

        otp = OTPSettings(
            user_id=user.id,
            is_enabled=True,
            is_mandatory=True,
            method="email",
        )
        session.add(otp)
        await session.commit()

        print(f"[OK] Super admin created.")
        print(f"     Email:    {email}")
        print(f"     Password: {password}")
        print(f"     ID:       {user.id}")
        print()
        print("  Log in at /login. OTP will be sent via email on first sign-in.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create the initial Campusio super admin account")
    parser.add_argument("--email",      default="superadmin@campusio.com", help="Email address")
    parser.add_argument("--password",   default="ChangeMe123!", help="Initial password")
    parser.add_argument("--first-name", default="Super",  dest="first_name")
    parser.add_argument("--last-name",  default="Admin",  dest="last_name")
    parser.add_argument("--phone",      default="", help="Phone number (optional)")
    args = parser.parse_args()

    asyncio.run(create_superadmin(
        email=args.email,
        password=args.password,
        first_name=args.first_name,
        last_name=args.last_name,
        phone=args.phone,
    ))
