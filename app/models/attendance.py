"""
Attendance database models and schemas for Attendance Management Service.

Includes comprehensive attendance tracking with:
- Check-in/Check-out times
- Late arrival tracking
- Early departure tracking
- Overtime calculation
- Short leave tracking
- Status tracking (present, late, absent, etc.)
"""

from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel
from pydantic import Field as PydanticField
from sqlmodel import Field, SQLModel


class AttendanceStatus(str, Enum):
    """Status of attendance record."""

    PENDING = "pending"
    PRESENT = "present"
    LATE = "late"
    ABSENT = "absent"
    ON_LEAVE = "on_leave"
    HALF_DAY = "half_day"
    SHORT_LEAVE = "short_leave"
    WORK_FROM_HOME = "work_from_home"


class CheckType(str, Enum):
    """Type of check action."""

    CHECKIN = "checkin"
    CHECKOUT = "checkout"


# Database Model


class Attendance(SQLModel, table=True):
    """
    ORM model for Attendance table.

    Tracks employee attendance including:
    - Check-in/Check-out times
    - Late arrival and early departure
    - Overtime hours
    - Daily status
    """

    __tablename__ = "attendance"

    id: Optional[int] = Field(default=None, primary_key=True)

    # Employee reference
    employee_id: int = Field(index=True, nullable=False)
    user_id: Optional[int] = Field(default=None, index=True)
    email: Optional[str] = Field(default=None, max_length=255)

    # Date and times
    date: str = Field(index=True, nullable=False, max_length=10)  # YYYY-MM-DD format
    check_in_time: Optional[datetime] = Field(default=None, nullable=True)
    check_out_time: Optional[datetime] = Field(default=None, nullable=True)

    # Status
    status: str = Field(default=AttendanceStatus.PENDING.value, max_length=50)

    # Late arrival tracking
    is_late: bool = Field(default=False)
    late_minutes: int = Field(default=0)
    expected_start_time: Optional[str] = Field(
        default="09:00", max_length=5
    )  # HH:MM format

    # Early departure tracking
    is_early_departure: bool = Field(default=False)
    early_departure_minutes: int = Field(default=0)
    expected_end_time: Optional[str] = Field(
        default="17:00", max_length=5
    )  # HH:MM format

    # Hours tracking
    total_hours_worked: Optional[Decimal] = Field(
        default=None, max_digits=5, decimal_places=2
    )
    standard_hours: Decimal = Field(
        default=Decimal("8.00"), max_digits=5, decimal_places=2
    )

    # Overtime tracking
    is_overtime: bool = Field(default=False)
    overtime_hours: Decimal = Field(
        default=Decimal("0.00"), max_digits=5, decimal_places=2
    )

    # Short leave tracking (worked less than required)
    is_short_leave: bool = Field(default=False)
    short_leave_hours: Decimal = Field(
        default=Decimal("0.00"), max_digits=5, decimal_places=2
    )

    # Notes and metadata
    notes: Optional[str] = Field(default=None, max_length=500)
    check_in_notes: Optional[str] = Field(default=None, max_length=255)
    check_out_notes: Optional[str] = Field(default=None, max_length=255)

    # Recording info
    recorded_by: Optional[int] = Field(default=None)  # User who recorded (if manual)
    is_manual_entry: bool = Field(default=False)

    # Approval (for manual entries or corrections)
    requires_approval: bool = Field(default=False)
    approved_by: Optional[int] = Field(default=None)
    approved_at: Optional[datetime] = Field(default=None)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


# Request Schemas


class CheckInRequest(SQLModel):
    """Schema for employee check-in request."""

    employee_id: int = Field(gt=0)
    notes: Optional[str] = Field(default=None, max_length=255)


class CheckOutRequest(SQLModel):
    """Schema for employee check-out request."""

    employee_id: int = Field(gt=0)
    notes: Optional[str] = Field(default=None, max_length=255)


class CheckInSelfRequest(SQLModel):
    """Schema for self-service check-in (no employee_id needed)."""

    notes: Optional[str] = Field(default=None, max_length=255)


class CheckOutSelfRequest(SQLModel):
    """Schema for self-service check-out (no employee_id needed)."""

    notes: Optional[str] = Field(default=None, max_length=255)


class AttendanceCreate(SQLModel):
    """Schema for creating a new attendance record (manual entry)."""

    employee_id: int = Field(gt=0)
    date: str = Field(min_length=10, max_length=10)  # YYYY-MM-DD format
    check_in_time: Optional[datetime] = Field(default=None)
    check_out_time: Optional[datetime] = Field(default=None)
    status: str = Field(default=AttendanceStatus.PENDING.value, max_length=50)
    notes: Optional[str] = Field(default=None, max_length=500)
    is_manual_entry: bool = Field(default=True)


class AttendanceUpdate(SQLModel):
    """Schema for updating an existing attendance record."""

    check_in_time: Optional[datetime] = Field(default=None)
    check_out_time: Optional[datetime] = Field(default=None)
    status: Optional[str] = Field(default=None, max_length=50)
    notes: Optional[str] = Field(default=None, max_length=500)
    is_late: Optional[bool] = Field(default=None)
    late_minutes: Optional[int] = Field(default=None)
    is_early_departure: Optional[bool] = Field(default=None)
    early_departure_minutes: Optional[int] = Field(default=None)
    is_overtime: Optional[bool] = Field(default=None)
    overtime_hours: Optional[Decimal] = Field(
        default=None, max_digits=5, decimal_places=2
    )
    is_short_leave: Optional[bool] = Field(default=None)
    short_leave_hours: Optional[Decimal] = Field(
        default=None, max_digits=5, decimal_places=2
    )
    total_hours_worked: Optional[Decimal] = Field(
        default=None, max_digits=5, decimal_places=2
    )


class AttendanceCorrectionRequest(SQLModel):
    """Schema for requesting attendance correction (requires approval)."""

    attendance_id: int = Field(gt=0)
    check_in_time: Optional[datetime] = Field(default=None)
    check_out_time: Optional[datetime] = Field(default=None)
    reason: str = Field(min_length=10, max_length=500)


# Response Schemas


class AttendancePublic(SQLModel):
    """Schema for attendance responses (public view)."""

    id: int
    employee_id: int
    date: str
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    status: str
    is_late: bool = False
    late_minutes: int = 0
    is_early_departure: bool = False
    early_departure_minutes: int = 0
    total_hours_worked: Optional[Decimal] = None
    is_overtime: bool = False
    overtime_hours: Decimal = Decimal("0.00")
    is_short_leave: bool = False
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AttendanceDetailed(SQLModel):
    """Schema for detailed attendance responses (HR/Manager view)."""

    id: int
    employee_id: int
    user_id: Optional[int]
    email: Optional[str]
    date: str
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    status: str
    is_late: bool
    late_minutes: int
    expected_start_time: Optional[str]
    is_early_departure: bool
    early_departure_minutes: int
    expected_end_time: Optional[str]
    total_hours_worked: Optional[Decimal]
    standard_hours: Decimal
    is_overtime: bool
    overtime_hours: Decimal
    is_short_leave: bool
    short_leave_hours: Decimal
    notes: Optional[str]
    check_in_notes: Optional[str]
    check_out_notes: Optional[str]
    recorded_by: Optional[int]
    is_manual_entry: bool
    requires_approval: bool
    approved_by: Optional[int]
    approved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class AttendanceTodayResponse(BaseModel):
    """Response for today's attendance status."""

    employee_id: int
    date: str
    has_checked_in: bool
    has_checked_out: bool
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    status: str
    is_late: bool = False
    late_minutes: int = 0
    hours_worked_so_far: Optional[float] = None


# Summary Schemas


class DailySummary(BaseModel):
    """Schema for daily attendance summary."""

    date: str
    total_employees: int
    present_count: int
    absent_count: int
    late_count: int
    on_leave_count: int
    early_departure_count: int
    overtime_count: int
    average_hours_worked: float
    attendance_rate: float  # Percentage


class WeeklySummary(BaseModel):
    """Schema for weekly attendance summary."""

    week_start_date: str
    week_end_date: str
    employee_id: Optional[int] = None  # If None, summary is for all employees
    total_days: int
    days_present: int
    days_absent: int
    days_late: int
    total_hours_worked: float
    average_daily_hours: float
    total_overtime_hours: float
    attendance_rate: float


class MonthlySummary(SQLModel):
    """Schema for monthly attendance summary."""

    employee_id: int
    month: str  # YYYY-MM format
    year: int
    total_working_days: int
    days_present: int
    days_absent: int
    days_late: int
    days_on_leave: int
    total_hours_worked: float
    average_daily_hours: float
    total_overtime_hours: float
    total_short_leave_hours: float
    attendance_rate: float
    records: list[AttendancePublic] = []


class EmployeeAttendanceHistory(BaseModel):
    """Schema for employee attendance history."""

    employee_id: int
    employee_name: Optional[str] = None
    department: Optional[str] = None
    total_records: int
    records: list[AttendancePublic]


# Dashboard Metrics Schema


class AttendanceDashboardMetrics(BaseModel):
    """Dashboard metrics for attendance overview."""

    date: str
    total_employees: int
    checked_in_today: int
    checked_out_today: int
    currently_working: int
    late_today: int
    absent_today: int
    on_leave_today: int
    overtime_today: int
    early_departures_today: int
    attendance_rate: float
    average_check_in_time: Optional[str] = None
    average_check_out_time: Optional[str] = None
    average_hours_worked: float
    department_breakdown: Optional[dict[str, dict[str, int]]] = None


class AttendanceListResponse(BaseModel):
    """Paginated attendance list response."""

    total: int
    records: list[AttendancePublic]


class AttendanceReport(BaseModel):
    """Comprehensive attendance report."""

    report_type: str  # daily, weekly, monthly
    start_date: str
    end_date: str
    generated_at: str
    total_employees: int
    summary: dict
    department_breakdown: Optional[dict] = None
    records: list[AttendancePublic] = []
