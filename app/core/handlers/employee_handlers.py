"""
Employee event handlers for Attendance Management Service.

These handlers consume employee lifecycle events from the Employee Management Service
and maintain a local cache of employee data for validation and attendance operations.
"""

from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import engine
from app.core.kafka import KafkaConsumer
from app.core.logging import get_logger
from app.models.employee import EmployeeCache

logger = get_logger(__name__)


# Kafka topic names (matching employee-management-service)
EMPLOYEE_CREATED_TOPIC = "employee-created"
EMPLOYEE_UPDATED_TOPIC = "employee-updated"
EMPLOYEE_DELETED_TOPIC = "employee-deleted"
EMPLOYEE_TERMINATED_TOPIC = "employee-terminated"
EMPLOYEE_SUSPENDED_TOPIC = "employee-suspended"
EMPLOYEE_ACTIVATED_TOPIC = "employee-activated"


def handle_employee_created(event_data: dict[str, Any]):
    """
    Handle employee.created event from Employee Management Service.

    Creates or updates the employee cache with the new employee data.
    """
    try:
        data = event_data.get("data", {})
        employee_id = data.get("employee_id")

        if not employee_id:
            logger.error("Employee created event missing employee_id")
            return

        logger.info(f"Processing employee.created event for employee {employee_id}")

        # Extract employee data from event
        email = data.get("email", "")
        first_name = data.get("first_name", "")
        last_name = data.get("last_name", "")
        full_name = f"{first_name} {last_name}".strip()

        # Create employee cache record
        with Session(engine) as session:
            # Check if employee already exists in cache
            existing = session.get(EmployeeCache, employee_id)

            if existing:
                logger.warning(
                    f"Employee {employee_id} already exists in cache, updating instead"
                )
                # Update existing record
                existing.user_id = data.get("user_id")
                existing.email = email
                existing.first_name = first_name
                existing.last_name = last_name
                existing.full_name = full_name
                existing.role = data.get("role", "employee")
                existing.job_title = data.get("job_title", "")
                existing.department = data.get("department")
                existing.team = data.get("team")
                existing.manager_id = data.get("manager_id")
                existing.employment_type = data.get("employment_type", "permanent")
                existing.status = "active"
                existing.joining_date = _parse_date(data.get("joining_date"))
                existing.updated_at = datetime.utcnow()
                existing.synced_at = datetime.utcnow()

                session.add(existing)
                session.commit()
                logger.info(f"Updated existing employee cache for {employee_id}")
            else:
                # Create new record
                employee_cache = EmployeeCache(
                    id=employee_id,
                    user_id=data.get("user_id"),
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    full_name=full_name,
                    role=data.get("role", "employee"),
                    job_title=data.get("job_title", ""),
                    department=data.get("department"),
                    team=data.get("team"),
                    manager_id=data.get("manager_id"),
                    employment_type=data.get("employment_type", "permanent"),
                    status="active",
                    joining_date=_parse_date(data.get("joining_date")),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    synced_at=datetime.utcnow(),
                )

                session.add(employee_cache)
                session.commit()
                logger.info(
                    f"Successfully created employee cache for {employee_id} ({email})"
                )

    except Exception as e:
        logger.error(f"Error handling employee.created event: {e}", exc_info=True)


def handle_employee_updated(event_data: dict[str, Any]):
    """
    Handle employee.updated event from Employee Management Service.

    Updates the employee cache with the changed fields.
    """
    try:
        data = event_data.get("data", {})
        employee_id = data.get("employee_id")

        if not employee_id:
            logger.error("Employee updated event missing employee_id")
            return

        logger.info(f"Processing employee.updated event for employee {employee_id}")

        with Session(engine) as session:
            employee = session.get(EmployeeCache, employee_id)

            if not employee:
                logger.warning(
                    f"Employee {employee_id} not found in cache, cannot update. "
                    f"Will try to fetch from employee service."
                )
                # If employee doesn't exist, we might have missed the creation event
                # Try to create it with the data we have
                email = data.get("email", "")
                first_name = data.get("first_name", "")
                last_name = data.get("last_name", "")

                if email and first_name and last_name:
                    full_name = f"{first_name} {last_name}".strip()
                    employee = EmployeeCache(
                        id=employee_id,
                        user_id=data.get("user_id"),
                        email=email,
                        first_name=first_name,
                        last_name=last_name,
                        full_name=full_name,
                        role=data.get("role", "employee"),
                        job_title=data.get("job_title", "Unknown"),
                        department=data.get("department"),
                        team=data.get("team"),
                        manager_id=data.get("manager_id"),
                        employment_type=data.get("employment_type", "permanent"),
                        status="active",
                        joining_date=None,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                        synced_at=datetime.utcnow(),
                    )
                    session.add(employee)
                    session.commit()
                    logger.info(
                        f"Created missing employee cache for {employee_id} from update event"
                    )
                return

            # Update fields if present in the event
            updated_fields = data.get("updated_fields", {})

            # Update basic fields
            if "email" in updated_fields:
                employee.email = updated_fields["email"]
            if "first_name" in updated_fields or "last_name" in updated_fields:
                employee.first_name = updated_fields.get(
                    "first_name", employee.first_name
                )
                employee.last_name = updated_fields.get("last_name", employee.last_name)
                employee.full_name = (
                    f"{employee.first_name} {employee.last_name}".strip()
                )
            if "role" in updated_fields:
                employee.role = updated_fields["role"]
            if "job_title" in updated_fields:
                employee.job_title = updated_fields["job_title"]
            if "department" in updated_fields:
                employee.department = updated_fields["department"]
            if "team" in updated_fields:
                employee.team = updated_fields["team"]
            if "manager_id" in updated_fields:
                employee.manager_id = updated_fields["manager_id"]
            if "employment_type" in updated_fields:
                employee.employment_type = updated_fields["employment_type"]
            if "status" in updated_fields:
                employee.status = updated_fields["status"]
            if "user_id" in updated_fields:
                employee.user_id = updated_fields["user_id"]

            employee.updated_at = datetime.utcnow()
            employee.synced_at = datetime.utcnow()

            session.add(employee)
            session.commit()
            logger.info(f"Successfully updated employee cache for {employee_id}")

    except Exception as e:
        logger.error(f"Error handling employee.updated event: {e}", exc_info=True)


def handle_employee_deleted(event_data: dict[str, Any]):
    """
    Handle employee.deleted event from Employee Management Service.

    Removes the employee from the cache or marks as deleted.
    """
    try:
        data = event_data.get("data", {})
        employee_id = data.get("employee_id")

        if not employee_id:
            logger.error("Employee deleted event missing employee_id")
            return

        logger.info(f"Processing employee.deleted event for employee {employee_id}")

        with Session(engine) as session:
            employee = session.get(EmployeeCache, employee_id)

            if not employee:
                logger.warning(
                    f"Employee {employee_id} not found in cache, nothing to delete"
                )
                return

            # Soft delete - mark as deleted instead of removing from database
            # This preserves attendance history for deleted employees
            employee.status = "deleted"
            employee.updated_at = datetime.utcnow()
            employee.synced_at = datetime.utcnow()

            session.add(employee)
            session.commit()
            logger.info(f"Marked employee {employee_id} as deleted in cache")

    except Exception as e:
        logger.error(f"Error handling employee.deleted event: {e}", exc_info=True)


def handle_employee_terminated(event_data: dict[str, Any]):
    """
    Handle employee.terminated event from Employee Management Service.

    Marks the employee as terminated in the cache.
    """
    try:
        data = event_data.get("data", {})
        employee_id = data.get("employee_id")

        if not employee_id:
            logger.error("Employee terminated event missing employee_id")
            return

        logger.info(f"Processing employee.terminated event for employee {employee_id}")

        with Session(engine) as session:
            employee = session.get(EmployeeCache, employee_id)

            if not employee:
                logger.warning(f"Employee {employee_id} not found in cache")
                return

            employee.status = "terminated"
            employee.updated_at = datetime.utcnow()
            employee.synced_at = datetime.utcnow()

            session.add(employee)
            session.commit()
            logger.info(f"Marked employee {employee_id} as terminated in cache")

    except Exception as e:
        logger.error(f"Error handling employee.terminated event: {e}", exc_info=True)


def handle_employee_suspended(event_data: dict[str, Any]):
    """
    Handle employee.suspended event from Employee Management Service.

    Marks the employee as suspended in the cache.
    """
    try:
        data = event_data.get("data", {})
        employee_id = data.get("employee_id")

        if not employee_id:
            logger.error("Employee suspended event missing employee_id")
            return

        logger.info(f"Processing employee.suspended event for employee {employee_id}")

        with Session(engine) as session:
            employee = session.get(EmployeeCache, employee_id)

            if not employee:
                logger.warning(f"Employee {employee_id} not found in cache")
                return

            employee.status = "suspended"
            employee.updated_at = datetime.utcnow()
            employee.synced_at = datetime.utcnow()

            session.add(employee)
            session.commit()
            logger.info(f"Marked employee {employee_id} as suspended in cache")

    except Exception as e:
        logger.error(f"Error handling employee.suspended event: {e}", exc_info=True)


def handle_employee_activated(event_data: dict[str, Any]):
    """
    Handle employee.activated event from Employee Management Service.

    Marks the employee as active in the cache.
    """
    try:
        data = event_data.get("data", {})
        employee_id = data.get("employee_id")

        if not employee_id:
            logger.error("Employee activated event missing employee_id")
            return

        logger.info(f"Processing employee.activated event for employee {employee_id}")

        with Session(engine) as session:
            employee = session.get(EmployeeCache, employee_id)

            if not employee:
                logger.warning(f"Employee {employee_id} not found in cache")
                return

            employee.status = "active"
            employee.updated_at = datetime.utcnow()
            employee.synced_at = datetime.utcnow()

            session.add(employee)
            session.commit()
            logger.info(f"Marked employee {employee_id} as active in cache")

    except Exception as e:
        logger.error(f"Error handling employee.activated event: {e}", exc_info=True)


def _parse_date(date_value: Any) -> datetime | None:
    """
    Parse date value from event data.

    Handles various date formats including ISO strings and date objects.
    """
    if date_value is None:
        return None

    if isinstance(date_value, datetime):
        return date_value

    if isinstance(date_value, str):
        try:
            # Try ISO format
            return datetime.fromisoformat(date_value.replace("Z", "+00:00"))
        except ValueError:
            try:
                # Try common date format
                return datetime.strptime(date_value, "%Y-%m-%d")
            except ValueError:
                logger.warning(f"Could not parse date: {date_value}")
                return None

    return None


def register_employee_handlers():
    """
    Register all employee event handlers with the Kafka consumer.

    This function should be called during application startup to ensure
    the attendance service stays synchronized with employee data.
    """
    if not settings.KAFKA_ENABLED:
        logger.info("Kafka is disabled, skipping employee handler registration")
        return

    logger.info("Registering employee event handlers...")

    # Register handlers for employee lifecycle events
    KafkaConsumer.register_handler(EMPLOYEE_CREATED_TOPIC, handle_employee_created)
    KafkaConsumer.register_handler(EMPLOYEE_UPDATED_TOPIC, handle_employee_updated)
    KafkaConsumer.register_handler(EMPLOYEE_DELETED_TOPIC, handle_employee_deleted)
    KafkaConsumer.register_handler(
        EMPLOYEE_TERMINATED_TOPIC, handle_employee_terminated
    )

    logger.info(
        f"Registered handlers for topics: {EMPLOYEE_CREATED_TOPIC}, "
        f"{EMPLOYEE_UPDATED_TOPIC}, {EMPLOYEE_DELETED_TOPIC}, {EMPLOYEE_TERMINATED_TOPIC}"
    )

    logger.info("Employee event handlers registered successfully")
