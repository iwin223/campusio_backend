"""Models package"""
from models.user import User, UserCreate, UserLogin, UserResponse, UserRole
from models.school import School, SchoolCreate, SchoolType, AcademicTerm, AcademicTermCreate, TermType
from models.student import Student, StudentCreate, StudentStatus, Gender, Parent, ParentCreate, StudentParent
from models.staff import Staff, StaffCreate, StaffType, StaffStatus, TeacherAssignment
from models.classroom import Class, ClassCreate, ClassLevel, Subject, SubjectCreate, SubjectCategory, ClassSubject
from models.attendance import Attendance, AttendanceCreate, AttendanceBulkCreate, AttendanceStatus, StaffAttendance
from models.grade import Grade, GradeCreate, AssessmentType, GradeScale, ReportCard
from models.fee import Fee, FeeCreate, FeeStructure, FeeStructureCreate, FeePayment, FeePaymentCreate, FeeType, PaymentStatus, PaymentMethod
from models.timetable import Timetable, TimetableCreate, Period, PeriodCreate, DayOfWeek, PeriodType
from models.communication import Announcement, AnnouncementCreate, AnnouncementType, AnnouncementAudience, Message, MessageCreate, EmailNotification
from models.report_template import ReportTemplate, ReportTemplateCreate, ReportTemplateUpdate, ReportTemplateResponse
from models.transport import (
    Vehicle, VehicleCreate, VehicleUpdate, VehicleStatus, VehicleType,
    Route, RouteCreate, RouteUpdate, RouteStatus,
    StudentTransport, StudentTransportCreate, StudentTransportUpdate,
    TransportAttendance, TransportAttendanceCreate, TransportAttendanceBulk, AttendanceStatus as TransportAttendanceStatus,
    TransportFee, TransportFeeCreate, TransportFeeUpdate, TransportFeeType,
    VehicleMaintenance, VehicleMaintenanceCreate,
    DriverStaff, DriverStaffCreate, DriverStaffUpdate
)
from models.hostel import (
    Hostel, HostelCreate, HostelUpdate, HostelStatus,
    Room, RoomCreate, RoomUpdate, RoomType, RoomStatus,
    StudentHostel, StudentHostelCreate, StudentHostelUpdate, StudentHostelStatus,
    RoomAllocation, RoomAllocationCreate,
    HostelAttendance, HostelAttendanceCreate, CheckInStatus,
    HostelFee, HostelFeeCreate, HostelFeeUpdate, HostelFeeType,
    HostelMaintenance, HostelMaintenanceCreate,
    HostelVisitor, HostelVisitorCreate,
    HostelComplaint, HostelComplaintCreate, HostelComplaintUpdate
)

__all__ = [
    "User", "UserCreate", "UserLogin", "UserResponse", "UserRole",
    "School", "SchoolCreate", "SchoolType", "AcademicTerm", "AcademicTermCreate", "TermType",
    "Student", "StudentCreate", "StudentStatus", "Gender", "Parent", "ParentCreate", "StudentParent",
    "Staff", "StaffCreate", "StaffType", "StaffStatus", "TeacherAssignment",
    "Class", "ClassCreate", "ClassLevel", "Subject", "SubjectCreate", "SubjectCategory", "ClassSubject",
    "Attendance", "AttendanceCreate", "AttendanceBulkCreate", "AttendanceStatus", "StaffAttendance",
    "Grade", "GradeCreate", "AssessmentType", "GradeScale", "ReportCard",
    "Fee", "FeeCreate", "FeeStructure", "FeeStructureCreate", "FeePayment", "FeePaymentCreate", "FeeType", "PaymentStatus", "PaymentMethod",
    "Timetable", "TimetableCreate", "Period", "PeriodCreate", "DayOfWeek", "PeriodType",
    "Announcement", "AnnouncementCreate", "AnnouncementType", "AnnouncementAudience", "Message", "MessageCreate", "EmailNotification",
    "ReportTemplate", "ReportTemplateCreate", "ReportTemplateUpdate", "ReportTemplateResponse",
    "Vehicle", "VehicleCreate", "VehicleUpdate", "VehicleStatus", "VehicleType",
    "Route", "RouteCreate", "RouteUpdate", "RouteStatus",
    "StudentTransport", "StudentTransportCreate", "StudentTransportUpdate",
    "TransportAttendance", "TransportAttendanceCreate", "TransportAttendanceBulk", "TransportAttendanceStatus",
    "TransportFee", "TransportFeeCreate", "TransportFeeUpdate", "TransportFeeType",
    "VehicleMaintenance", "VehicleMaintenanceCreate",
    "DriverStaff", "DriverStaffCreate", "DriverStaffUpdate",
    "Hostel", "HostelCreate", "HostelUpdate", "HostelStatus",
    "Room", "RoomCreate", "RoomUpdate", "RoomType", "RoomStatus",
    "StudentHostel", "StudentHostelCreate", "StudentHostelUpdate", "StudentHostelStatus",
    "RoomAllocation", "RoomAllocationCreate",
    "HostelAttendance", "HostelAttendanceCreate", "CheckInStatus",
    "HostelFee", "HostelFeeCreate", "HostelFeeUpdate", "HostelFeeType",
    "HostelMaintenance", "HostelMaintenanceCreate",
    "HostelVisitor", "HostelVisitorCreate",
    "HostelComplaint", "HostelComplaintCreate", "HostelComplaintUpdate"
]
