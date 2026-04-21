import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

async def fix_versions():
    engine = create_async_engine('postgresql+asyncpg://postgres:2211@localhost:5432/school-erp')
    async with engine.begin() as conn:
        # Delete the conflicting entries
        await conn.execute(text("DELETE FROM alembic_version WHERE version_num IN ('6cb275da3d42', 'tickets_001_add_ticketing_tables')"))
        print('Deleted conflicting migrations from alembic_version')
        # Check what's left
        result = await conn.execute(text('SELECT version_num FROM alembic_version ORDER BY version_num DESC LIMIT 3'))
        rows = result.fetchall()
        for row in rows:
            print(f'Remaining: {row[0]}')
        await conn.commit()
    await engine.dispose()

asyncio.run(fix_versions())
