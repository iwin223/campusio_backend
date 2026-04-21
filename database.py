"""Database configuration and session management for PostgreSQL"""
import asyncio
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker 
from sqlalchemy.pool import QueuePool
from config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

# Fix DATABASE_URL for asyncpg if necessary
database_url = settings.database_url
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

logger.info("🚀 Connecting to database... (Render optimized)")

# ✅ OPTIMIZED: Connection Pooling with QueuePool
# Reuses connections instead of creating new ones per request
# Reduced pool size for Render's connection limits
async_engine = create_async_engine(
    database_url,
    echo=False,
    pool_size=5,
    max_overflow=3,
    pool_timeout=30,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={
        "timeout": 30,
        "command_timeout": 60,
        "server_settings": {
            "application_name": "school_erp_app",
            "jit": "off",
        }
    }
)

# Create async session factory
async_session = sessionmaker(
    bind=async_engine, class_=AsyncSession, expire_on_commit=False
)


async def get_session() -> AsyncSession:
    """Dependency to get database session"""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


# ✅ Initialize DB
async def init_db() -> None:
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

async def close_db():
    """Close database connections"""
    await async_engine.dispose()
    logger.info("Database connections closed")
