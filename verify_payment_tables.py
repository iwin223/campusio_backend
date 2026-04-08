"""Verify payment tables created"""
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from config import get_settings


async def verify_tables():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_name IN ('online_transactions', 'payment_verifications')
                """)
            )
            tables = result.fetchall()
            if tables:
                print(f"✅ Tables created: {[t[0] for t in tables]}")
            else:
                print("❌ Tables not found")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(verify_tables())
