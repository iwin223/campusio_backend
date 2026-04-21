"""Models package"""
from models.user import User, UserCreate, UserLogin, UserResponse, UserRole
from models.school import School, SchoolCreate, SchoolType, AcademicTerm, AcademicTermCreate, TermType
from models.student import Student, StudentCreate, StudentStatus, Gender, Parent, ParentCreate, StudentParent
from models.staff import Staff, StaffCreate, StaffType, StaffStatus, TeacherAssignment
from models.classroom import Class, ClassCreate, ClassLevel, Subject, SubjectCreate, SubjectCategory, ClassSubject
from models.attendance import Attendance, AttendanceCreate, AttendanceBulkCreate, AttendanceStatus, StaffAttendance
from models.grade import Grade, GradeCreate, AssessmentType, GradeScale, ReportCard
from models.fee import Fee, FeeCreate, FeeStructure, FeeStructureCreate, FeePayment, FeePaymentCreate, FeeType, PaymentStatus, PaymentMethod
from models.payroll import (
    PayrollContract, PayrollContractCreate, PayrollContractUpdate, PaySchedule,
    PayrollRun, PayrollRunCreate, PayrollStatus,
    PayrollLineItem, PayrollAdjustment, PayrollAdjustmentCreate,
    PayrollCategory, PayslipResponse
)
from models.timetable import Timetable, TimetableCreate, Period, PeriodCreate, DayOfWeek, PeriodType
from models.communication import Announcement, AnnouncementCreate, AnnouncementType, AnnouncementAudience, Message, MessageCreate, EmailNotification
from models.report_template import ReportTemplate, ReportTemplateCreate, ReportTemplateUpdate, ReportTemplateResponse
from models.assignment import (
    Assignment, AssignmentCreate, AssignmentUpdate, AssignmentResponse, AssignmentType, AssignmentStatus,
    Submission, SubmissionCreate, SubmissionGrade, SubmissionResponse, SubmissionStatus,
    TeacherResource, TeacherResourceCreate, ResourceType,
    LearningMaterial, LearningMaterialCreate,
    StudentProgressNote, StudentProgressNoteCreate, StudentProgressNoteResponse, ProgressNoteType,
    AssignmentStats, ClassPerformanceMetrics, SubmissionSummary
)
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
from models.billing import (
    PlatformSubscription, SubscriptionInvoice, SubscriptionStatus,
    PlatformSubscriptionResponse, SubscriptionInvoiceResponse,
    GenerateSubscriptionRequest, ProcessSubscriptionPaymentRequest,
    SubscriptionMetrics,
    # Phase 2 Models
    BillingConfiguration, BillingConfigurationResponse,
    DiscountRule, PaymentReminder, LateFeeCharge,
    BillingReport
)
from models.settlement import Withdrawal, WithdrawalStatus, WithdrawalRead
from models.ticket import (
    Ticket, TicketCreate, TicketUpdate, TicketResponse, TicketDetailResponse,
    TicketCategory, TicketPriority, TicketStatus,
    TicketComment, TicketCommentCreate, TicketCommentResponse,
    TicketAttachment, TicketNotification, TicketCloseRequest
)
from models.otp import (
    OTP, OTPBase, OTPSettings, OTPVerificationRequest, OTPVerificationResponse,
    OTPAdminSettings
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
    "PayrollContract", "PayrollContractCreate", "PayrollContractUpdate", "PaySchedule",
    "PayrollRun", "PayrollRunCreate", "PayrollStatus",
    "PayrollLineItem", "PayrollAdjustment", "PayrollAdjustmentCreate",
    "PayrollCategory", "PayslipResponse",
    "Timetable", "TimetableCreate", "Period", "PeriodCreate", "DayOfWeek", "PeriodType",
    "Announcement", "AnnouncementCreate", "AnnouncementType", "AnnouncementAudience", "Message", "MessageCreate", "EmailNotification",
    "ReportTemplate", "ReportTemplateCreate", "ReportTemplateUpdate", "ReportTemplateResponse",
    # Teacher Portal - Assignment/Submission Models
    "Assignment", "AssignmentCreate", "AssignmentUpdate", "AssignmentResponse", "AssignmentType", "AssignmentStatus",
    "Submission", "SubmissionCreate", "SubmissionGrade", "SubmissionResponse", "SubmissionStatus",
    "TeacherResource", "TeacherResourceCreate", "ResourceType",
    "LearningMaterial", "LearningMaterialCreate",
    "StudentProgressNote", "StudentProgressNoteCreate", "StudentProgressNoteResponse", "ProgressNoteType",
    "AssignmentStats", "ClassPerformanceMetrics", "SubmissionSummary",
    # Transport Module
    "Vehicle", "VehicleCreate", "VehicleUpdate", "VehicleStatus", "VehicleType",
    "Route", "RouteCreate", "RouteUpdate", "RouteStatus",
    "StudentTransport", "StudentTransportCreate", "StudentTransportUpdate",
    "TransportAttendance", "TransportAttendanceCreate", "TransportAttendanceBulk", "TransportAttendanceStatus",
    "TransportFee", "TransportFeeCreate", "TransportFeeUpdate", "TransportFeeType",
    "VehicleMaintenance", "VehicleMaintenanceCreate",
    "DriverStaff", "DriverStaffCreate", "DriverStaffUpdate",
    # Hostel Module
    "Hostel", "HostelCreate", "HostelUpdate", "HostelStatus",
    "Room", "RoomCreate", "RoomUpdate", "RoomType", "RoomStatus",
    "StudentHostel", "StudentHostelCreate", "StudentHostelUpdate", "StudentHostelStatus",
    "RoomAllocation", "RoomAllocationCreate",
    "HostelAttendance", "HostelAttendanceCreate", "CheckInStatus",
    "HostelFee", "HostelFeeCreate", "HostelFeeUpdate", "HostelFeeType",
    "HostelMaintenance", "HostelMaintenanceCreate",
    "HostelVisitor", "HostelVisitorCreate",
    "HostelComplaint", "HostelComplaintCreate", "HostelComplaintUpdate",
    # Platform Billing Module
    "PlatformSubscription", "SubscriptionInvoice", "SubscriptionStatus",
    "PlatformSubscriptionResponse", "SubscriptionInvoiceResponse",
    "GenerateSubscriptionRequest", "ProcessSubscriptionPaymentRequest",
    "SubscriptionMetrics",
    # Platform Billing Phase 2
    "BillingConfiguration", "BillingConfigurationResponse",
    "DiscountRule", "PaymentReminder", "LateFeeCharge",
    "BillingReport",
    # Settlement Module
    "Withdrawal", "WithdrawalStatus", "WithdrawalRead",
    # Ticket Module
    "Ticket", "TicketCreate", "TicketUpdate", "TicketResponse", "TicketDetailResponse",
    "TicketCategory", "TicketPriority", "TicketStatus",
    "TicketComment", "TicketCommentCreate", "TicketCommentResponse",
    "TicketAttachment", "TicketNotification", "TicketCloseRequest",
    # OTP Module
    "OTP", "OTPBase", "OTPSettings", "OTPVerificationRequest", "OTPVerificationResponse",
    "OTPAdminSettings",
]
