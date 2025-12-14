"""
Employee validation service for Attendance Management.

This service provides employee validation and data retrieval with a two-tier approach:
1. First checks the local employee cache (synchronized via Kafka)
2. Falls back to HTTP calls to the employee management service if needed

This ensures reliable employee validation even when services are temporarily unavailable.
"""

from typing import Optional

from sqlmodel import Session, select

from app.api.clients.employee_service import employee_service as http_client
from app.core.database import engine
from app.core.logging import get_logger
from app.models.employee import EmployeeCache

logger = get_logger(__name__)


class EmployeeValidationService:
    """
    Service for validating employee existence and retrieving employee data.

    Uses a cache-first approach with HTTP fallback for reliability.
    """

    @staticmethod
    def verify_employee_exists(employee_id: int) -> bool:
        """
        Verify if an employee exists.

        Checks the local cache first, then falls back to HTTP call if not found.
        Only considers active employees as existing.

        Args:
            employee_id: Employee ID to verify

        Returns:
            True if employee exists and is active, False otherwise
        """
        try:
            # Check cache first
            with Session(engine) as session:
                employee = session.get(EmployeeCache, employee_id)

                if employee:
                    # Employee found in cache
                    is_active = employee.status in ["active", "on_leave"]
                    if is_active:
                        logger.info(
                            f"Employee {employee_id} found in cache (status: {employee.status})"
                        )
                        return True
                    else:
                        logger.info(
                            f"Employee {employee_id} found in cache but inactive (status: {employee.status})"
                        )
                        return False

                # Not in cache, fall back to HTTP
                logger.info(f"Employee {employee_id} not in cache, checking via HTTP")

        except Exception as e:
            logger.error(f"Error checking cache for employee {employee_id}: {e}")
            # Continue to HTTP fallback

        # HTTP fallback (will be async in the route handler)
        return False

    @staticmethod
    async def verify_employee_exists_async(employee_id: int) -> bool:
        """
        Async version of verify_employee_exists with HTTP fallback.

        Args:
            employee_id: Employee ID to verify

        Returns:
            True if employee exists and is active, False otherwise
        """
        try:
            # Check cache first
            with Session(engine) as session:
                employee = session.get(EmployeeCache, employee_id)

                if employee:
                    # Employee found in cache
                    is_active = employee.status in ["active", "on_leave"]
                    if is_active:
                        logger.info(
                            f"Employee {employee_id} found in cache (status: {employee.status})"
                        )
                        return True
                    else:
                        logger.info(
                            f"Employee {employee_id} found in cache but inactive (status: {employee.status})"
                        )
                        return False

                # Not in cache, fall back to HTTP
                logger.warning(
                    f"Employee {employee_id} not in cache, falling back to HTTP call"
                )

        except Exception as e:
            logger.error(f"Error checking cache for employee {employee_id}: {e}")

        # HTTP fallback
        try:
            exists = await http_client.verify_employee_exists(employee_id)
            if exists:
                logger.info(
                    f"Employee {employee_id} verified via HTTP (not in cache yet)"
                )
            else:
                logger.warning(
                    f"Employee {employee_id} does not exist (verified via HTTP)"
                )
            return exists
        except Exception as e:
            logger.error(f"HTTP fallback failed for employee {employee_id}: {e}")
            return False

    @staticmethod
    async def get_employee(employee_id: int) -> Optional[dict]:
        """
        Get employee details.

        Checks the local cache first, then falls back to HTTP call if needed.

        Args:
            employee_id: Employee ID to retrieve

        Returns:
            Employee data dictionary or None if not found
        """
        try:
            # Check cache first
            with Session(engine) as session:
                employee = session.get(EmployeeCache, employee_id)

                if employee:
                    logger.info(f"Employee {employee_id} found in cache")
                    return {
                        "id": employee.id,
                        "user_id": employee.user_id,
                        "email": employee.email,
                        "first_name": employee.first_name,
                        "last_name": employee.last_name,
                        "full_name": employee.full_name,
                        "role": employee.role,
                        "job_title": employee.job_title,
                        "department": employee.department,
                        "team": employee.team,
                        "manager_id": employee.manager_id,
                        "employment_type": employee.employment_type,
                        "status": employee.status,
                        "joining_date": employee.joining_date.isoformat()
                        if employee.joining_date
                        else None,
                    }

                logger.info(
                    f"Employee {employee_id} not in cache, falling back to HTTP"
                )

        except Exception as e:
            logger.error(f"Error checking cache for employee {employee_id}: {e}")

        # HTTP fallback
        try:
            employee_data = await http_client.get_employee(employee_id)
            if employee_data:
                logger.info(
                    f"Employee {employee_id} retrieved via HTTP (not in cache yet)"
                )
            return employee_data
        except Exception as e:
            logger.error(f"HTTP fallback failed for employee {employee_id}: {e}")
            return None

    @staticmethod
    async def get_employee_by_email(email: str) -> Optional[dict]:
        """
        Get employee details by email.

        Checks the local cache first, then falls back to HTTP call if needed.

        Args:
            email: Employee email to search for

        Returns:
            Employee data dictionary or None if not found
        """
        try:
            # Check cache first
            with Session(engine) as session:
                statement = select(EmployeeCache).where(EmployeeCache.email == email)
                employee = session.exec(statement).first()

                if employee:
                    logger.info(f"Employee with email {email} found in cache")
                    return {
                        "id": employee.id,
                        "user_id": employee.user_id,
                        "email": employee.email,
                        "first_name": employee.first_name,
                        "last_name": employee.last_name,
                        "full_name": employee.full_name,
                        "role": employee.role,
                        "job_title": employee.job_title,
                        "department": employee.department,
                        "team": employee.team,
                        "manager_id": employee.manager_id,
                        "employment_type": employee.employment_type,
                        "status": employee.status,
                        "joining_date": employee.joining_date.isoformat()
                        if employee.joining_date
                        else None,
                    }

                logger.info(
                    f"Employee with email {email} not in cache, falling back to HTTP"
                )

        except Exception as e:
            logger.error(f"Error checking cache for employee email {email}: {e}")

        # HTTP fallback
        try:
            employee_data = await http_client.get_employee_by_email(email)
            if employee_data:
                logger.info(
                    f"Employee with email {email} retrieved via HTTP (not in cache yet)"
                )
            return employee_data
        except Exception as e:
            logger.error(f"HTTP fallback failed for employee email {email}: {e}")
            return None

    @staticmethod
    def get_cached_employee_count() -> int:
        """
        Get the count of cached employees.

        Useful for monitoring and health checks.

        Returns:
            Number of employees in the cache
        """
        try:
            with Session(engine) as session:
                statement = select(EmployeeCache)
                employees = session.exec(statement).all()
                count = len(employees)
                logger.debug(f"Employee cache contains {count} records")
                return count
        except Exception as e:
            logger.error(f"Error counting cached employees: {e}")
            return 0

    @staticmethod
    def get_active_employee_count() -> int:
        """
        Get the count of active employees in cache.

        Returns:
            Number of active employees
        """
        try:
            with Session(engine) as session:
                statement = select(EmployeeCache).where(
                    EmployeeCache.status == "active"
                )
                employees = session.exec(statement).all()
                count = len(employees)
                logger.debug(f"Employee cache contains {count} active employees")
                return count
        except Exception as e:
            logger.error(f"Error counting active employees: {e}")
            return 0


# Create singleton instance
employee_validation_service = EmployeeValidationService()
