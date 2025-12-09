"""
Event definitions for Attendance Management Service.

Defines all event types and their data structures for Kafka publishing.
Events are categorized into:
- Check-in/Check-out events
- Attendance status events (late, early departure, overtime)
- Summary events for dashboard metrics
- Audit events
"""

from datetime import date, datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """All event types produced by the Attendance Management Service."""

    # Check-in/Check-out Events
    ATTENDANCE_CHECKIN = "attendance.checkin"
    ATTENDANCE_CHECKOUT = "attendance.checkout"
    ATTENDANCE_UPDATED = "attendance.updated"
    ATTENDANCE_DELETED = "attendance.deleted"

    # Status Events
    ATTENDANCE_LATE = "attendance.late"
    ATTENDANCE_EARLY_DEPARTURE = "attendance.early.departure"
    ATTENDANCE_OVERTIME = "attendance.overtime"
    ATTENDANCE_SHORT_LEAVE = "attendance.short.leave"
    ATTENDANCE_ABSENT = "attendance.absent"
    ATTENDANCE_PRESENT = "attendance.present"

    # Summary Events
    ATTENDANCE_DAILY_SUMMARY = "attendance.summary.daily"
    ATTENDANCE_WEEKLY_SUMMARY = "attendance.summary.weekly"
    ATTENDANCE_MONTHLY_SUMMARY = "attendance.summary.monthly"

    # Dashboard Metrics Events
    ATTENDANCE_METRICS_UPDATED = "attendance.metrics.updated"

    # Audit Events
    AUDIT_ATTENDANCE_ACTION = "audit.attendance.action"


class EventMetadata(BaseModel):
    """Metadata attached to every event for tracing and correlation."""

    source_service: str = "attendance-management-service"
    correlation_id: str = Field(default_factory=lambda: str(uuid4()))
    causation_id: Optional[str] = None
    actor_user_id: Optional[str] = None
    actor_role: Optional[str] = None
    trace_id: Optional[str] = None
    ip_address: Optional[str] = None


class EventEnvelope(BaseModel):
    """
    Standard envelope for all events.
    Provides consistent structure for Kafka messages.
    """

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: EventType
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    version: str = "1.0"
    data: dict[str, Any]
    metadata: EventMetadata = Field(default_factory=EventMetadata)


# Check-in/Check-out Event Data Models


class AttendanceCheckinEvent(BaseModel):
    """Data for attendance.checkin event."""

    attendance_id: int
    employee_id: int
    user_id: Optional[int] = None
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    check_in_time: datetime
    date: str  # YYYY-MM-DD format
    is_late: bool = False
    late_minutes: int = 0
    department: Optional[str] = None
    recorded_by: Optional[int] = None


class AttendanceCheckoutEvent(BaseModel):
    """Data for attendance.checkout event."""

    attendance_id: int
    employee_id: int
    user_id: Optional[int] = None
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    check_in_time: datetime
    check_out_time: datetime
    date: str  # YYYY-MM-DD format
    total_hours_worked: float
    is_overtime: bool = False
    overtime_hours: float = 0.0
    is_early_departure: bool = False
    early_departure_minutes: int = 0
    status: str  # present, late, short_leave, etc.
    department: Optional[str] = None
    recorded_by: Optional[int] = None


class AttendanceUpdatedEvent(BaseModel):
    """Data for attendance.updated event."""

    attendance_id: int
    employee_id: int
    date: str
    updated_fields: dict[str, Any]
    previous_values: Optional[dict[str, Any]] = None
    updated_by: Optional[int] = None
    reason: Optional[str] = None


class AttendanceDeletedEvent(BaseModel):
    """Data for attendance.deleted event."""

    attendance_id: int
    employee_id: int
    date: str
    deleted_by: int
    reason: Optional[str] = None


# Status Event Data Models


class AttendanceLateEvent(BaseModel):
    """Data for attendance.late event."""

    attendance_id: int
    employee_id: int
    user_id: Optional[int] = None
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date: str
    expected_time: str  # e.g., "09:00"
    actual_time: str
    late_minutes: int
    department: Optional[str] = None
    manager_id: Optional[int] = None
    manager_email: Optional[str] = None


class AttendanceEarlyDepartureEvent(BaseModel):
    """Data for attendance.early.departure event."""

    attendance_id: int
    employee_id: int
    user_id: Optional[int] = None
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date: str
    expected_end_time: str  # e.g., "17:00"
    actual_end_time: str
    early_departure_minutes: int
    total_hours_worked: float
    department: Optional[str] = None
    manager_id: Optional[int] = None


class AttendanceOvertimeEvent(BaseModel):
    """Data for attendance.overtime event."""

    attendance_id: int
    employee_id: int
    user_id: Optional[int] = None
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date: str
    standard_hours: float = 8.0
    total_hours_worked: float
    overtime_hours: float
    check_in_time: str
    check_out_time: str
    department: Optional[str] = None


class AttendanceShortLeaveEvent(BaseModel):
    """Data for attendance.short.leave event."""

    attendance_id: int
    employee_id: int
    user_id: Optional[int] = None
    email: Optional[str] = None
    date: str
    hours_worked: float
    hours_short: float
    reason: str = "early_departure"


class AttendanceAbsentEvent(BaseModel):
    """Data for attendance.absent event."""

    employee_id: int
    user_id: Optional[int] = None
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date: str
    is_unplanned: bool = True
    has_approved_leave: bool = False
    department: Optional[str] = None
    manager_id: Optional[int] = None
    manager_email: Optional[str] = None


class AttendancePresentEvent(BaseModel):
    """Data for attendance.present event."""

    attendance_id: int
    employee_id: int
    user_id: Optional[int] = None
    email: Optional[str] = None
    date: str
    check_in_time: str
    status: str = "present"


# Summary Event Data Models


class DailySummaryEvent(BaseModel):
    """Data for attendance.summary.daily event."""

    date: str
    total_employees: int
    present_count: int
    absent_count: int
    late_count: int
    on_leave_count: int
    overtime_count: int
    early_departure_count: int
    average_hours_worked: float
    department_breakdown: Optional[dict[str, dict[str, int]]] = None


class WeeklySummaryEvent(BaseModel):
    """Data for attendance.summary.weekly event."""

    week_start_date: str
    week_end_date: str
    total_working_days: int
    average_attendance_rate: float
    total_late_instances: int
    total_overtime_hours: float
    total_absent_days: int
    employee_count: int
    department_summary: Optional[dict[str, Any]] = None


class MonthlySummaryEvent(BaseModel):
    """Data for attendance.summary.monthly event."""

    month: str  # YYYY-MM format
    year: int
    total_working_days: int
    average_attendance_rate: float
    total_late_instances: int
    total_overtime_hours: float
    total_absent_days: int
    total_leave_days: int
    employee_count: int
    perfect_attendance_count: int
    department_summary: Optional[dict[str, Any]] = None


# Dashboard Metrics Event Data Model


class AttendanceMetricsEvent(BaseModel):
    """Data for attendance.metrics.updated event."""

    date: str
    timestamp: str
    total_employees: int
    checked_in_today: int
    checked_out_today: int
    currently_working: int
    late_today: int
    absent_today: int
    on_leave_today: int
    overtime_today: int
    attendance_rate: float
    average_check_in_time: Optional[str] = None
    department_metrics: Optional[dict[str, dict[str, int]]] = None


# Audit Event Data Model


class AuditAttendanceActionEvent(BaseModel):
    """Data for audit.attendance.action event."""

    actor_user_id: int
    actor_email: str
    actor_role: str
    action: str  # checkin, checkout, update, delete, manual_entry
    resource_type: str = "attendance"
    resource_id: int
    employee_id: int
    description: str
    old_value: Optional[dict[str, Any]] = None
    new_value: Optional[dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


# Helper functions for creating events


def create_event(
    event_type: EventType,
    data: BaseModel,
    actor_user_id: Optional[str] = None,
    actor_role: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> EventEnvelope:
    """
    Helper function to create an event envelope with proper metadata.

    Args:
        event_type: Type of the event
        data: Event data as a Pydantic model
        actor_user_id: ID of the user performing the action
        actor_role: Role of the user performing the action
        correlation_id: Optional correlation ID for tracing

    Returns:
        EventEnvelope ready for publishing
    """
    metadata = EventMetadata(
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        correlation_id=correlation_id or str(uuid4()),
    )

    return EventEnvelope(
        event_type=event_type,
        data=data.model_dump(mode="json"),
        metadata=metadata,
    )


# Constants for business rules
STANDARD_WORK_HOURS = 8.0
STANDARD_START_TIME = "09:00"
STANDARD_END_TIME = "17:00"
LATE_THRESHOLD_MINUTES = 15  # Consider late after 15 minutes past start time
OVERTIME_THRESHOLD_HOURS = 8.0  # Overtime starts after 8 hours
