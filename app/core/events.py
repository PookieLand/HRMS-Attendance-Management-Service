from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class EventType(str, Enum):
    ATTENDANCE_MARKED = "attendance.marked"
    ATTENDANCE_UPDATED = "attendance.updated"
    ATTENDANCE_DELETED = "attendance.deleted"


class EventMetadata(BaseModel):
    source_service: str = "attendance-management-service"
    correlation_id: str = Field(default_factory=lambda: str(uuid4()))
    causation_id: str | None = None
    user_id: str | None = None
    trace_id: str | None = None


class EventEnvelope(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: EventType
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    version: str = "1.0"
    data: dict[str, Any]
    metadata: EventMetadata


class AttendanceMarkedEvent(BaseModel):
    attendance_id: int
    employee_id: int
    check_in_time: str
    check_out_time: str | None
    status: str
    date: str


class AttendanceUpdatedEvent(BaseModel):
    attendance_id: int
    employee_id: int
    updated_fields: dict[str, Any]


class AttendanceDeletedEvent(BaseModel):
    attendance_id: int
    employee_id: int
    date: str
