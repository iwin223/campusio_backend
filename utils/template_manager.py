"""
Template Manager - Create and manage school report templates

Usage:
    python -m utils.template_manager create-template --school-id <id> --template-file <path> --name "Template Name"
"""
import asyncio
from sqlmodel import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from models.report_template import ReportTemplate
from config import get_settings
from datetime import datetime
import uuid
import sys

# Get database URL from settings
settings = get_settings()


async def create_school_template(
    school_id: str,
    template_html: str,
    template_name: str,
    description: str = None,
    is_default: bool = False,
    created_by: str = "system"
) -> str:
    """Create or update a report template for a school"""
    
    # Debug: Check if html_content is received
    print(f"🔍 HTML content received: {len(template_html)} characters")
    
    # Setup database connection
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            # If marking as default, unset any existing defaults
            if is_default:
                existing_defaults = await session.execute(
                    select(ReportTemplate).where(
                        ReportTemplate.school_id == school_id,
                        ReportTemplate.is_default == True
                    )
                )
                for existing in existing_defaults.scalars().all():
                    existing.is_default = False
                    session.add(existing)
            
            # Create new template
            template = ReportTemplate(
                id=str(uuid.uuid4()),
                school_id=school_id,
                name=template_name,
                description=description,
                html_content=template_html,
                is_default=is_default,
                is_active=True,
                version=1,
                created_by=created_by,
                created_at=datetime.utcnow()
            )
            
            session.add(template)
            await session.commit()
            
            print(f"✅ Template '{template_name}' created for school {school_id}")
            print(f"   Template ID: {template.id}")
            print(f"   Default: {is_default}")
            return template.id
            
        except Exception as e:
            print(f"❌ Error creating template: {str(e)}")
            raise
        finally:
            await engine.dispose()


async def list_school_templates(school_id: str) -> list:
    """List all templates for a school"""
    
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            result = await session.execute(
                select(ReportTemplate).where(
                    ReportTemplate.school_id == school_id
                ).order_by(ReportTemplate.created_at.desc())
            )
            templates = result.scalars().all()
            
            if not templates:
                print(f"❌ No templates found for school {school_id}")
                return []
            
            print(f"\n📋 Templates for school {school_id}:\n")
            for i, tmpl in enumerate(templates, 1):
                default_mark = "⭐ (DEFAULT)" if tmpl.is_default else ""
                active_mark = "✅ ACTIVE" if tmpl.is_active else "❌ INACTIVE"
                print(f"{i}. {tmpl.name} {default_mark}")
                print(f"   ID: {tmpl.id}")
                print(f"   Status: {active_mark}")
                print(f"   Created: {tmpl.created_at}")
                print(f"   Version: {tmpl.version}\n")
            
            return templates
            
        finally:
            await engine.dispose()


async def set_default_template(school_id: str, template_id: str) -> bool:
    """Set a template as default for a school"""
    
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            # Unset all other defaults
            other_defaults = await session.execute(
                select(ReportTemplate).where(
                    ReportTemplate.school_id == school_id,
                    ReportTemplate.is_default == True
                )
            )
            for tmpl in other_defaults.scalars().all():
                tmpl.is_default = False
                session.add(tmpl)
            
            # Set this one as default
            result = await session.execute(
                select(ReportTemplate).where(
                    ReportTemplate.id == template_id,
                    ReportTemplate.school_id == school_id
                )
            )
            template = result.scalar_one_or_none()
            
            if not template:
                print(f"❌ Template {template_id} not found for school {school_id}")
                return False
            
            template.is_default = True
            template.updated_at = datetime.utcnow()
            session.add(template)
            await session.commit()
            
            print(f"✅ Template '{template.name}' is now default for school {school_id}")
            return True
            
        finally:
            await engine.dispose()


async def update_template_html(template_id: str, school_id: str, new_html: str) -> bool:
    """Update HTML content of an existing template"""
    
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            result = await session.execute(
                select(ReportTemplate).where(
                    ReportTemplate.id == template_id,
                    ReportTemplate.school_id == school_id
                )
            )
            template = result.scalar_one_or_none()
            
            if not template:
                print(f"❌ Template not found")
                return False
            
            template.html_content = new_html
            template.version += 1
            template.updated_at = datetime.utcnow()
            session.add(template)
            await session.commit()
            
            print(f"✅ Template updated successfully")
            print(f"   New version: {template.version}")
            return True
            
        finally:
            await engine.dispose()


# CLI Commands
async def main():
    """Handle CLI commands"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m utils.template_manager list <school_id>")
        print("  python -m utils.template_manager create <school_id> <template_file> <name>")
        print("  python -m utils.template_manager set-default <school_id> <template_id>")
        return
    
    command = sys.argv[1]
    
    if command == "list":
        if len(sys.argv) < 3:
            print("❌ Usage: python -m utils.template_manager list <school_id>")
            return
        school_id = sys.argv[2]
        await list_school_templates(school_id)
    
    elif command == "create":
        if len(sys.argv) < 5:
            print("❌ Usage: python -m utils.template_manager create <school_id> <template_file> <name>")
            return
        
        school_id = sys.argv[2]
        template_file = sys.argv[3]
        template_name = sys.argv[4]
        is_default = "--default" in sys.argv
        
        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            print(f"📖 File read: {len(html_content)} characters")
            if len(html_content) == 0:
                print("⚠️  WARNING: File is empty!")
                return
        except Exception as e:
            print(f"❌ Error reading file: {str(e)}")
            return
        
        await create_school_template(
            school_id=school_id,
            template_html=html_content,
            template_name=template_name,
            is_default=is_default
        )
    
    elif command == "set-default":
        if len(sys.argv) < 4:
            print("❌ Usage: python -m utils.template_manager set-default <school_id> <template_id>")
            return
        
        school_id = sys.argv[2]
        template_id = sys.argv[3]
        await set_default_template(school_id, template_id)
    
    else:
        print(f"❌ Unknown command: {command}")


if __name__ == "__main__":
    asyncio.run(main())
