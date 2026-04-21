import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

async def mark_migrations():
    engine = create_async_engine('postgresql+asyncpg://postgres:2211@localhost:5432/school-erp')
    async with engine.begin() as conn:
        # Get all migration files in order
        migrations = [
            'cd113e54466e',
            'e8f9a1b2c3d4',
            'e37f3a6ed880',
            'f1a2b3c4d5e6',
            'a1b2c3d4e5f6',
            'add_online_payments_001',
            'c1d2e3f4a5b6',
            'add_gl_fields_hostel',
            'add_gl_fields_to_transport_fees',
            'transport_gl_fields_001',
            'sms_notification_001',
            '002_add_otp_tables',
            '003_add_withdrawals_table',
            'tickets_001_add_ticketing_tables',
            '003_add_otp_admin_settings',
            '6cb275da3d42',
        ]
        
        # Mark all as applied
        for migration in migrations:
            try:
                await conn.execute(text(f"INSERT INTO alembic_version (version_num) VALUES ('{migration}')"))
                print(f'Marked as applied: {migration}')
            except Exception as e:
                print(f'Skipping {migration}: {str(e)[:50]}')
        
        await conn.commit()
    await engine.dispose()

asyncio.run(mark_migrations())
