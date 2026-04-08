"""Verify payment table structure"""
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from config import get_settings


async def verify_structure():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    
    try:
        async with engine.begin() as conn:
            # Check online_transactions columns
            result = await conn.execute(
                text("""
                    SELECT column_name, data_type FROM information_schema.columns 
                    WHERE table_name = 'online_transactions' 
                    ORDER BY ordinal_position
                """)
            )
            print("✅ online_transactions columns:")
            for col in result.fetchall():
                print(f"   - {col[0]}: {col[1]}")
            
            # Check payment_verifications columns
            result = await conn.execute(
                text("""
                    SELECT column_name, data_type FROM information_schema.columns 
                    WHERE table_name = 'payment_verifications' 
                    ORDER BY ordinal_position
                """)
            )
            print("\n✅ payment_verifications columns:")
            for col in result.fetchall():
                print(f"   - {col[0]}: {col[1]}")
            
            # Check indexes
            result = await conn.execute(
                text("""
                    SELECT indexname FROM pg_indexes 
                    WHERE tablename IN ('online_transactions', 'payment_verifications')
                """)
            )
            print("\n✅ Indexes created:")
            for idx in result.fetchall():
                print(f"   - {idx[0]}")
    
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(verify_structure())
