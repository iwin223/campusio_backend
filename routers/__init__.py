"""Routers package"""
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

__all__ = [
    "auth_router", "schools_router", "students_router", "staff_router",
    "classes_router", "attendance_router", "grades_router", "fees_router",
    "timetable_router", "communication_router", "dashboard_router"
]
