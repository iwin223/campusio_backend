"""School ERP System - Main Application"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path 
from middleware import register_middleware
from dotenv import load_dotenv

# Load environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from database import init_db, close_db
from routers.auth import router as auth_router
from routers.schools import router as schools_router
from routers.students import router as students_router
from routers.staff import router as staff_router
from routers.classes import router as classes_router
from routers.attendance import router as attendance_router
from routers.grades import router as grades_router
from routers.fees import router as fees_router
from routers.timetable import router as timetable_router
from routers.communication import router as communication_router
from routers.dashboard import router as dashboard_router
from routers.email import router as email_router
from routers.sms import router as sms_router
from routers.tickets import router as tickets_router
from routers.parent import router as parent_router
from routers.student_portal import router as student_portal_router
from routers.report_templates import router as report_templates_router
from routers.transport import router as transport_router
from routers.hostel import router as hostel_router
from routers.payroll import router as payroll_router
from routers.finance.coa import router as coa_router
from routers.finance.journal import router as journal_router
from routers.finance.expenses import router as expenses_router
from routers.finance.reports import router as reports_router
from routers.finance_reports import router as finance_reports_router
from routers.payments import router as payments_router
from routers.teacher.grades import router as teacher_grades_router
from routers.teacher.attendance import router as teacher_attendance_router
from routers.teacher.timetable import router as teacher_timetable_router
from routers.teacher.assignments import router as teacher_assignments_router
from routers.teacher_dashboard import router as teacher_dashboard_router
from routers.settlements import router as settlements_router
from routers.billing import router as billing_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info("Starting School ERP System...")
    await init_db()
    logger.info("Application started successfully")
    
    yield
    
    logger.info("Shutting down School ERP System...")
    await close_db()
    logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="School ERP System",
    description="Enterprise-grade School ERP for Ghanaian Basic and JHS Schools",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

register_middleware(app)

# Mount static files
from fastapi.staticfiles import StaticFiles
app.mount("/templates", StaticFiles(directory="templates"), name="templates")


# Include routers with /api prefix
app.include_router(auth_router, prefix="/api")
app.include_router(schools_router, prefix="/api")
app.include_router(students_router, prefix="/api")
app.include_router(staff_router, prefix="/api")
app.include_router(classes_router, prefix="/api")
app.include_router(attendance_router, prefix="/api")
app.include_router(grades_router, prefix="/api")
app.include_router(fees_router, prefix="/api")
app.include_router(timetable_router, prefix="/api")
app.include_router(communication_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(email_router, prefix="/api")
app.include_router(sms_router, prefix="/api")
app.include_router(tickets_router, prefix="/api")
app.include_router(parent_router, prefix="/api")
app.include_router(student_portal_router, prefix="/api")
app.include_router(report_templates_router, prefix="/api")
app.include_router(transport_router, prefix="/api")
app.include_router(hostel_router, prefix="/api")
app.include_router(payroll_router, prefix="/api")
app.include_router(coa_router, prefix="/api")
app.include_router(journal_router, prefix="/api")
app.include_router(expenses_router, prefix="/api")
app.include_router(reports_router, prefix="/api")
app.include_router(finance_reports_router)
app.include_router(payments_router, prefix="/api")
app.include_router(settlements_router, prefix="/api")
app.include_router(teacher_grades_router, prefix="/api")
app.include_router(teacher_attendance_router, prefix="/api")
app.include_router(teacher_timetable_router, prefix="/api")
app.include_router(teacher_assignments_router, prefix="/api")
app.include_router(teacher_dashboard_router, prefix="/api")
app.include_router(billing_router, prefix="/api")


@app.get("/api")
async def root():
    """API root endpoint"""
    return {
        "message": "School ERP System API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}
