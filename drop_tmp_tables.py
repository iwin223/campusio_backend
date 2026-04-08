"""Drop teacher portal tables for clean migration"""
import asyncio
from database import async_engine
from sqlalchemy import text

async def drop_tables():
    """Drop the teacher portal tables if they exist"""
    async with async_engine.begin() as conn:
        tables = [
            'student_progress_notes',
            'learning_materials', 
            'teacher_resources',
            'submissions',
            'assignments'
        ]
        for table in tables:
            try:
                await conn.execute(text(f'DROP TABLE IF EXISTS {table} CASCADE'))
                print(f"✅ Dropped {table}")
            except Exception as e:
                print(f"ℹ️ {table}: {str(e)}")

if __name__ == "__main__":
    asyncio.run(drop_tables())
