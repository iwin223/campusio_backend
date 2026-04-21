"""Debug database contents"""
import asyncio
from sqlmodel import select, text
from database import async_session

async def check_database():
    async with async_session() as session:
        print("=== CHECKING DATABASE ===\n")
        
        # Check tables
        result = await session.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"))
        tables = result.scalars().all()
        print(f'✓ Total tables: {len(tables)}')
        if tables:
            print(f'  Tables: {", ".join(sorted(tables)[:5])}...')
        
        # Check users table
        try:
            result = await session.execute(text('SELECT COUNT(*) as count FROM users'))
            count = result.scalar()
            print(f'\n✓ Users table exists with {count} rows')
        except Exception as e:
            print(f'\n✗ Users table error: {e}')
        
        # Check schools table
        try:
            result = await session.execute(text('SELECT COUNT(*) as count FROM schools'))
            count = result.scalar()
            print(f'✓ Schools table exists with {count} rows')
        except Exception as e:
            print(f'✗ Schools table error: {e}')
        
        # Check classes table
        try:
            result = await session.execute(text('SELECT COUNT(*) as count FROM classes'))
            count = result.scalar()
            print(f'✓ Classes table exists with {count} rows')
        except Exception as e:
            print(f'✗ Classes table error: {e}')

asyncio.run(check_database())
