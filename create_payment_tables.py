"""Create online payment tables directly"""
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlmodel import SQLModel
from config import get_settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_payment_tables():
    """Create online payment tables directly in database"""
    
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=True)
    
    try:
        # Import models to ensure metadata is populated
        from models.payment import OnlineTransaction, PaymentVerification
        
        async with engine.begin() as conn:
            # Create tables
            await conn.run_sync(SQLModel.metadata.create_all)
            logger.info("✅ All tables created successfully")
            
            # Verify tables exist
            result = await conn.execute(
                text("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name IN ('online_transactions', 'payment_verifications')
                """)
            )
            tables = result.fetchall()
            logger.info(f"✅ Found {len(tables)} new tables: {[t[0] for t in tables]}")
    
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_payment_tables())
