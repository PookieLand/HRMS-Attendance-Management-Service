"""
Employee cache model for Attendance Management Service.

This model stores essential employee information received from Kafka events
published by the Employee Management Service. It serves as a local cache
to validate employee existence without making HTTP calls.
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class EmployeeCache(SQLModel, table=True):
    """
    Employee cache table to store employee data from Kafka events.

    This table is synchronized with the Employee Management Service via Kafka.
    When employees are created, updated, or deleted, events are consumed and
    this cache is updated accordingly.
    """

    __tablename__ = "employee_cache"

    id: int = Field(primary_key=True, description="Employee ID from employee service")
    user_id: Optional[int] = Field(
        default=None, index=True, description="Asgardeo user ID"
    )
    email: str = Field(
        index=True, unique=True, max_length=255, description="Employee email"
    )
    first_name: str = Field(max_length=255, description="Employee first name")
    last_name: str = Field(max_length=255, description="Employee last name")
    full_name: str = Field(max_length=511, description="Full name for display")
    role: str = Field(
        max_length=100,
        description="Employee role (HR_Admin, HR_Manager, manager, employee)",
    )
    job_title: str = Field(max_length=255, description="Job title/position")
    department: Optional[str] = Field(
        default=None, max_length=255, description="Department name"
    )
    team: Optional[str] = Field(default=None, max_length=255, description="Team name")
    manager_id: Optional[int] = Field(
        default=None, index=True, description="Manager employee ID"
    )
    employment_type: str = Field(
        max_length=50, description="Employment type (permanent, contract)"
    )
    status: str = Field(
        default="active", max_length=50, index=True, description="Employee status"
    )
    joining_date: Optional[datetime] = Field(
        default=None, description="Date joined the company"
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Cache record created at"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Cache record updated at"
    )
    synced_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last synced from Kafka event"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "user_id": 123,
                "email": "john.doe@company.com",
                "first_name": "John",
                "last_name": "Doe",
                "full_name": "John Doe",
                "role": "employee",
                "job_title": "Software Engineer",
                "department": "Engineering",
                "team": "Backend Team",
                "manager_id": 5,
                "employment_type": "permanent",
                "status": "active",
                "joining_date": "2024-01-15T00:00:00",
            }
        }


class EmployeePublic(SQLModel):
    """
    Public schema for employee cache responses.
    """

    id: int
    email: str
    first_name: str
    last_name: str
    full_name: str
    role: str
    job_title: str
    department: Optional[str] = None
    team: Optional[str] = None
    manager_id: Optional[int] = None
    employment_type: str
    status: str
    joining_date: Optional[datetime] = None
