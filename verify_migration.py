"""Verify teacher portal migration"""
import asyncio
from sqlalchemy import text
from database import async_engine

async def check_tables():
    """Verify all teacher portal tables were created"""
    async with async_engine.begin() as conn:
        # Get table info
        result = await conn.execute(text("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('assignments', 'submissions', 'teacher_resources', 'learning_materials', 'student_progress_notes')
            ORDER BY table_name;
        """))
        tables = result.fetchall()
        
        print("✅ Database Migration Successful!")
        print(f"\n📊 Tables Created: {len(tables)}/5")
        for table in tables:
            print(f"   ✅ {table[0]}")
        
        # Get index info
        print(f"\n📑 Indexes Created:")
        result = await conn.execute(text("""
            SELECT indexname, tablename 
            FROM pg_indexes 
            WHERE tablename IN ('assignments', 'submissions', 'teacher_resources', 'learning_materials', 'student_progress_notes')
            ORDER BY tablename, indexname;
        """))
        indexes = result.fetchall()
        current_table = None
        for idx, table in indexes:
            if table != current_table:
                print(f"\n   Table: {table}")
                current_table = table
            print(f"      - {idx}")

if __name__ == "__main__":
    asyncio.run(check_tables())
