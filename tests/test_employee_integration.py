"""
Integration tests for employee data synchronization.

Tests the employee cache synchronization via Kafka events and
the validation service's cache-first approach.
"""

from datetime import datetime

import pytest
from sqlmodel import Session, select

from app.core.database import engine
from app.core.employee_service import employee_validation_service
from app.core.handlers.employee_handlers import (
    handle_employee_created,
    handle_employee_deleted,
    handle_employee_terminated,
    handle_employee_updated,
)
from app.models.employee import EmployeeCache


@pytest.fixture
def db_session():
    """Create a database session for testing."""
    with Session(engine) as session:
        yield session


@pytest.fixture
def clean_employee_cache(db_session):
    """Clean employee cache before and after tests."""
    # Clean before
    db_session.exec(select(EmployeeCache)).all()
    for employee in db_session.exec(select(EmployeeCache)).all():
        db_session.delete(employee)
    db_session.commit()

    yield

    # Clean after
    for employee in db_session.exec(select(EmployeeCache)).all():
        db_session.delete(employee)
    db_session.commit()


def test_handle_employee_created(clean_employee_cache, db_session):
    """Test that employee created event populates the cache."""
    # Arrange
    event_data = {
        "event_type": "employee.created",
        "data": {
            "employee_id": 1,
            "user_id": 100,
            "email": "john.doe@company.com",
            "first_name": "John",
            "last_name": "Doe",
            "role": "employee",
            "job_title": "Software Engineer",
            "department": "Engineering",
            "team": "Backend",
            "manager_id": 5,
            "employment_type": "permanent",
            "joining_date": "2024-01-15",
        },
    }

    # Act
    handle_employee_created(event_data)

    # Assert
    employee = db_session.get(EmployeeCache, 1)
    assert employee is not None
    assert employee.email == "john.doe@company.com"
    assert employee.first_name == "John"
    assert employee.last_name == "Doe"
    assert employee.full_name == "John Doe"
    assert employee.role == "employee"
    assert employee.job_title == "Software Engineer"
    assert employee.status == "active"


def test_handle_employee_updated(clean_employee_cache, db_session):
    """Test that employee updated event updates the cache."""
    # Arrange - Create initial employee
    employee = EmployeeCache(
        id=1,
        user_id=100,
        email="john.doe@company.com",
        first_name="John",
        last_name="Doe",
        full_name="John Doe",
        role="employee",
        job_title="Junior Engineer",
        department="Engineering",
        employment_type="permanent",
        status="active",
    )
    db_session.add(employee)
    db_session.commit()

    # Act - Update employee
    event_data = {
        "event_type": "employee.updated",
        "data": {
            "employee_id": 1,
            "email": "john.doe@company.com",
            "updated_fields": {
                "job_title": "Senior Engineer",
                "department": "Architecture",
            },
        },
    }
    handle_employee_updated(event_data)

    # Assert
    db_session.refresh(employee)
    assert employee.job_title == "Senior Engineer"
    assert employee.department == "Architecture"


def test_handle_employee_deleted(clean_employee_cache, db_session):
    """Test that employee deleted event marks employee as deleted."""
    # Arrange
    employee = EmployeeCache(
        id=1,
        user_id=100,
        email="john.doe@company.com",
        first_name="John",
        last_name="Doe",
        full_name="John Doe",
        role="employee",
        job_title="Engineer",
        employment_type="permanent",
        status="active",
    )
    db_session.add(employee)
    db_session.commit()

    # Act
    event_data = {
        "event_type": "employee.deleted",
        "data": {
            "employee_id": 1,
            "email": "john.doe@company.com",
        },
    }
    handle_employee_deleted(event_data)

    # Assert
    db_session.refresh(employee)
    assert employee.status == "deleted"


def test_handle_employee_terminated(clean_employee_cache, db_session):
    """Test that employee terminated event marks employee as terminated."""
    # Arrange
    employee = EmployeeCache(
        id=1,
        user_id=100,
        email="john.doe@company.com",
        first_name="John",
        last_name="Doe",
        full_name="John Doe",
        role="employee",
        job_title="Engineer",
        employment_type="permanent",
        status="active",
    )
    db_session.add(employee)
    db_session.commit()

    # Act
    event_data = {
        "event_type": "employee.terminated",
        "data": {
            "employee_id": 1,
            "email": "john.doe@company.com",
        },
    }
    handle_employee_terminated(event_data)

    # Assert
    db_session.refresh(employee)
    assert employee.status == "terminated"


def test_verify_employee_exists_cache_hit(clean_employee_cache, db_session):
    """Test employee validation when employee is in cache."""
    # Arrange
    employee = EmployeeCache(
        id=1,
        user_id=100,
        email="john.doe@company.com",
        first_name="John",
        last_name="Doe",
        full_name="John Doe",
        role="employee",
        job_title="Engineer",
        employment_type="permanent",
        status="active",
    )
    db_session.add(employee)
    db_session.commit()

    # Act
    exists = employee_validation_service.verify_employee_exists(1)

    # Assert
    assert exists is True


def test_verify_employee_exists_inactive_employee(clean_employee_cache, db_session):
    """Test that inactive employees are not considered as existing."""
    # Arrange
    employee = EmployeeCache(
        id=1,
        user_id=100,
        email="john.doe@company.com",
        first_name="John",
        last_name="Doe",
        full_name="John Doe",
        role="employee",
        job_title="Engineer",
        employment_type="permanent",
        status="terminated",  # Inactive status
    )
    db_session.add(employee)
    db_session.commit()

    # Act
    exists = employee_validation_service.verify_employee_exists(1)

    # Assert
    assert exists is False


@pytest.mark.asyncio
async def test_get_employee_from_cache(clean_employee_cache, db_session):
    """Test retrieving employee data from cache."""
    # Arrange
    employee = EmployeeCache(
        id=1,
        user_id=100,
        email="john.doe@company.com",
        first_name="John",
        last_name="Doe",
        full_name="John Doe",
        role="employee",
        job_title="Software Engineer",
        department="Engineering",
        team="Backend",
        manager_id=5,
        employment_type="permanent",
        status="active",
    )
    db_session.add(employee)
    db_session.commit()

    # Act
    employee_data = await employee_validation_service.get_employee(1)

    # Assert
    assert employee_data is not None
    assert employee_data["id"] == 1
    assert employee_data["email"] == "john.doe@company.com"
    assert employee_data["first_name"] == "John"
    assert employee_data["last_name"] == "Doe"
    assert employee_data["job_title"] == "Software Engineer"


@pytest.mark.asyncio
async def test_get_employee_by_email(clean_employee_cache, db_session):
    """Test retrieving employee by email from cache."""
    # Arrange
    employee = EmployeeCache(
        id=1,
        user_id=100,
        email="john.doe@company.com",
        first_name="John",
        last_name="Doe",
        full_name="John Doe",
        role="employee",
        job_title="Engineer",
        employment_type="permanent",
        status="active",
    )
    db_session.add(employee)
    db_session.commit()

    # Act
    employee_data = await employee_validation_service.get_employee_by_email(
        "john.doe@company.com"
    )

    # Assert
    assert employee_data is not None
    assert employee_data["id"] == 1
    assert employee_data["email"] == "john.doe@company.com"


def test_get_cached_employee_count(clean_employee_cache, db_session):
    """Test getting cached employee count."""
    # Arrange - Add multiple employees
    for i in range(1, 4):
        employee = EmployeeCache(
            id=i,
            email=f"employee{i}@company.com",
            first_name=f"Employee",
            last_name=f"{i}",
            full_name=f"Employee {i}",
            role="employee",
            job_title="Engineer",
            employment_type="permanent",
            status="active",
        )
        db_session.add(employee)
    db_session.commit()

    # Act
    count = employee_validation_service.get_cached_employee_count()

    # Assert
    assert count == 3


def test_get_active_employee_count(clean_employee_cache, db_session):
    """Test getting active employee count."""
    # Arrange - Add employees with different statuses
    employees = [
        EmployeeCache(
            id=1,
            email="active1@company.com",
            first_name="Active",
            last_name="One",
            full_name="Active One",
            role="employee",
            job_title="Engineer",
            employment_type="permanent",
            status="active",
        ),
        EmployeeCache(
            id=2,
            email="active2@company.com",
            first_name="Active",
            last_name="Two",
            full_name="Active Two",
            role="employee",
            job_title="Engineer",
            employment_type="permanent",
            status="active",
        ),
        EmployeeCache(
            id=3,
            email="terminated@company.com",
            first_name="Terminated",
            last_name="User",
            full_name="Terminated User",
            role="employee",
            job_title="Engineer",
            employment_type="permanent",
            status="terminated",
        ),
    ]
    for employee in employees:
        db_session.add(employee)
    db_session.commit()

    # Act
    active_count = employee_validation_service.get_active_employee_count()

    # Assert
    assert active_count == 2


def test_employee_created_event_idempotency(clean_employee_cache, db_session):
    """Test that duplicate employee created events don't cause errors."""
    # Arrange
    event_data = {
        "event_type": "employee.created",
        "data": {
            "employee_id": 1,
            "user_id": 100,
            "email": "john.doe@company.com",
            "first_name": "John",
            "last_name": "Doe",
            "role": "employee",
            "job_title": "Engineer",
            "employment_type": "permanent",
            "joining_date": "2024-01-15",
        },
    }

    # Act - Process same event twice
    handle_employee_created(event_data)
    handle_employee_created(event_data)

    # Assert - Should still have only one employee
    employees = db_session.exec(select(EmployeeCache)).all()
    assert len(employees) == 1
    assert employees[0].id == 1
