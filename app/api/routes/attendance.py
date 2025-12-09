from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from app.api.clients.employee_service import employee_service
from app.api.dependencies import CurrentUserDep, SessionDep
from app.core.events import (
    AttendanceCheckinEvent,
    AttendanceCheckoutEvent,
    AttendanceUpdatedEvent,
    EventEnvelope,
    EventMetadata,
    EventType,
)
from app.core.kafka import publish_event
from app.core.logging import get_logger
from app.core.security import TokenData, require_role
from app.models.attendance import (
    Attendance,
    AttendanceCreate,
    AttendancePublic,
    AttendanceUpdate,
    CheckInRequest,
    CheckOutRequest,
    MonthlySummary,
)

logger = get_logger(__name__)

# Create router with prefix and tags for better organization
router = APIRouter(
    prefix="/attendance",
    tags=["attendance"],
    responses={404: {"description": "Attendance record not found"}},
)


@router.post("/check-in", response_model=AttendancePublic, status_code=201)
async def check_in(
    request: CheckInRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> Attendance:
    """
    Employee check-in endpoint.
    Records the check-in time for an employee on the current date.

    **RBAC:** Employees can only check in themselves, HR/Managers can check in anyone.

    Args:
        request: Check-in request with employee_id
        session: Database session (injected)
        current_user: Current authenticated user

    Returns:
        Created or updated attendance record with check-in time

    Raises:
        HTTPException: 400 if employee doesn't exist, 403 if unauthorized, 404 if not found
    """
    # RBAC: Employees can only check in themselves
    # HR-Administrators, HR-Managers, and Team-Managers can check in anyone
    is_hr_or_manager = any(
        role in current_user.groups
        for role in ["HR-Administrators", "HR-Managers", "Team-Managers"]
    )

    if not is_hr_or_manager:
        # Regular employees can only check in themselves
        # Verify the employee_id matches the current user's employee record
        employee_data = await employee_service.get_employee(request.employee_id)
        if not employee_data:
            raise HTTPException(
                status_code=400,
                detail=f"Employee {request.employee_id} does not exist",
            )

        # Check if the employee's email matches the current user's email
        if employee_data.get("email") != current_user.email:
            logger.warning(
                f"User {current_user.email} attempted to check in for another employee {request.employee_id}"
            )
            raise HTTPException(
                status_code=403,
                detail="You can only check in for yourself",
            )

    logger.info(
        f"Check-in initiated by {current_user.email} for employee {request.employee_id}"
    )
    # Verify employee exists in employee service
    employee_exists = await employee_service.verify_employee_exists(request.employee_id)
    if not employee_exists:
        logger.warning(
            f"Check-in attempted for non-existent employee {request.employee_id}"
        )
        raise HTTPException(
            status_code=400,
            detail=f"Employee {request.employee_id} does not exist",
        )

    # Get today's date in YYYY-MM-DD format
    today = datetime.now().date().isoformat()
    check_in_time = datetime.now()

    # Check if attendance record already exists for today
    statement = select(Attendance).where(
        (Attendance.employee_id == request.employee_id) & (Attendance.date == today)
    )
    existing_record = session.exec(statement).first()

    if existing_record:
        # Update existing record with check-in time
        logger.info(f"Updating check-in for employee {request.employee_id} on {today}")
        existing_record.check_in_time = check_in_time
        existing_record.status = "present"
        existing_record.updated_at = datetime.now()
        session.add(existing_record)
        session.commit()
        session.refresh(existing_record)
        logger.info(f"Employee {request.employee_id} checked in at {check_in_time}")

        # Publish attendance marked event
        try:
            event = EventEnvelope(
                event_type=EventType.ATTENDANCE_MARKED,
                data={
                    "attendance_id": str(existing_record.id),
                    "employee_id": existing_record.employee_id,
                    "check_in_time": existing_record.check_in_time.isoformat()
                    if existing_record.check_in_time
                    else None,
                    "check_out_time": existing_record.check_out_time.isoformat()
                    if existing_record.check_out_time
                    else None,
                    "status": existing_record.status,
                    "date": existing_record.date,
                },
                metadata=EventMetadata(user_id=current_user.sub),
            )
            await publish_event("attendance-events", event)
            logger.info(f"Published attendance marked event for: {existing_record.id}")
        except Exception as e:
            logger.warning(f"Failed to publish attendance marked event: {e}")

        return existing_record
    else:
        # Create new attendance record
        logger.info(
            f"Creating new check-in for employee {request.employee_id} on {today}"
        )
        new_record = Attendance(
            employee_id=request.employee_id,
            date=today,
            check_in_time=check_in_time,
            status="present",
        )
        session.add(new_record)
        session.commit()
        session.refresh(new_record)
        logger.info(f"Employee {request.employee_id} checked in at {check_in_time}")

        # Publish attendance marked event
        try:
            event = EventEnvelope(
                event_type=EventType.ATTENDANCE_MARKED,
                data={
                    "attendance_id": str(new_record.id),
                    "employee_id": new_record.employee_id,
                    "check_in_time": new_record.check_in_time.isoformat()
                    if new_record.check_in_time
                    else None,
                    "check_out_time": new_record.check_out_time.isoformat()
                    if new_record.check_out_time
                    else None,
                    "status": new_record.status,
                    "date": new_record.date,
                },
                metadata=EventMetadata(user_id=current_user.sub),
            )
            await publish_event("attendance-events", event)
            logger.info(f"Published attendance marked event for: {new_record.id}")
        except Exception as e:
            logger.warning(f"Failed to publish attendance marked event: {e}")

        return new_record


@router.post("/check-out", response_model=AttendancePublic, status_code=200)
async def check_out(
    request: CheckOutRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> Attendance:
    """
    Employee check-out endpoint.
    Records the check-out time for an employee on the current date.

    **RBAC:** Employees can only check out themselves, HR/Managers can check out anyone.

    Args:
        request: Check-out request with employee_id
        session: Database session (injected)
        current_user: Current authenticated user

    Returns:
        Updated attendance record with check-out time

    Raises:
        HTTPException: 400 if employee doesn't exist, 403 if unauthorized, 404 if no check-in found
    """
    # RBAC: Employees can only check out themselves
    is_hr_or_manager = any(
        role in current_user.groups
        for role in ["HR-Administrators", "HR-Managers", "Team-Managers"]
    )

    if not is_hr_or_manager:
        # Regular employees can only check out themselves
        employee_data = await employee_service.get_employee(request.employee_id)
        if not employee_data:
            raise HTTPException(
                status_code=400,
                detail=f"Employee {request.employee_id} does not exist",
            )

        if employee_data.get("email") != current_user.email:
            logger.warning(
                f"User {current_user.email} attempted to check out for another employee {request.employee_id}"
            )
            raise HTTPException(
                status_code=403,
                detail="You can only check out for yourself",
            )

    logger.info(
        f"Check-out initiated by {current_user.email} for employee {request.employee_id}"
    )
    # Verify employee exists in employee service
    employee_exists = await employee_service.verify_employee_exists(request.employee_id)
    if not employee_exists:
        logger.warning(
            f"Check-out attempted for non-existent employee {request.employee_id}"
        )
        raise HTTPException(
            status_code=400,
            detail=f"Employee {request.employee_id} does not exist",
        )

    # Get today's date in YYYY-MM-DD format
    today = datetime.now().date().isoformat()
    check_out_time = datetime.now()

    # Find today's attendance record
    statement = select(Attendance).where(
        (Attendance.employee_id == request.employee_id) & (Attendance.date == today)
    )
    record = session.exec(statement).first()

    if not record:
        logger.warning(
            f"Check-out attempted but no check-in found for employee {request.employee_id} on {today}"
        )
        raise HTTPException(
            status_code=404,
            detail="No check-in record found for today. Please check in first.",
        )

    # Update record with check-out time
    logger.info(f"Updating check-out for employee {request.employee_id} on {today}")
    record.check_out_time = check_out_time
    record.updated_at = datetime.now()
    session.add(record)
    session.commit()
    session.refresh(record)
    logger.info(f"Employee {request.employee_id} checked out at {check_out_time}")

    # Publish attendance updated event
    try:
        event = EventEnvelope(
            event_type=EventType.ATTENDANCE_UPDATED,
            data={
                "attendance_id": str(record.id),
                "employee_id": record.employee_id,
                "updated_fields": {"check_out_time": check_out_time.isoformat()},
            },
            metadata=EventMetadata(user_id=current_user.sub),
        )
        await publish_event("attendance-events", event)
        logger.info(f"Published attendance updated event for: {record.id}")
    except Exception as e:
        logger.warning(f"Failed to publish attendance updated event: {e}")

    return record


@router.get("/{attendance_id}", response_model=AttendancePublic)
def get_attendance(
    attendance_id: int,
    session: SessionDep,
    current_user: Annotated[
        TokenData,
        Depends(require_role("HR-Administrators", "HR-Managers", "Team-Managers")),
    ],
) -> Attendance:
    """
    Get a specific attendance record by ID.

    **RBAC:** Only HR-Administrators, HR-Managers, and Team-Managers can view individual records.

    Args:
        attendance_id: The ID of the attendance record to retrieve
        session: Database session (injected)
        current_user: Current authenticated user (HR/Manager role required)

    Returns:
        Attendance record data

    Raises:
        HTTPException: 403 if unauthorized, 404 if attendance record not found
    """
    logger.info(f"Fetching attendance record with ID: {attendance_id}")
    record = session.get(Attendance, attendance_id)
    if not record:
        logger.warning(f"Attendance record with ID {attendance_id} not found")
        raise HTTPException(status_code=404, detail="Attendance record not found")
    logger.info(f"Attendance record found: {record.id}")
    return record


@router.get("/employee/{employee_id}", response_model=list[AttendancePublic])
async def get_employee_attendance(
    employee_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 100,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[Attendance]:
    """
    Get all attendance records for a specific employee.
    Supports date range filtering for better query control.

    **RBAC:** Employees can view their own records, HR/Managers can view anyone's records.

    Args:
        employee_id: The ID of the employee
        session: Database session (injected)
        current_user: Current authenticated user
        offset: Number of records to skip (default: 0)
        limit: Maximum number of records to return (default: 100, max: 100)
        start_date: Optional start date in YYYY-MM-DD format
        end_date: Optional end date in YYYY-MM-DD format

    Returns:
        List of attendance records for the employee

    Raises:
        HTTPException: 400 if date format is invalid, 403 if unauthorized
    """
    # RBAC: Employees can only view their own records
    is_hr_or_manager = any(
        role in current_user.groups
        for role in ["HR-Administrators", "HR-Managers", "Team-Managers"]
    )

    if not is_hr_or_manager:
        # Regular employees can only view their own attendance
        employee_data = await employee_service.get_employee(employee_id)
        if not employee_data:
            raise HTTPException(
                status_code=404,
                detail=f"Employee {employee_id} not found",
            )

        if employee_data.get("email") != current_user.email:
            logger.warning(
                f"User {current_user.email} attempted to view attendance for another employee {employee_id}"
            )
            raise HTTPException(
                status_code=403,
                detail="You can only view your own attendance records",
            )
    logger.info(
        f"Fetching attendance records for employee {employee_id} "
        f"(offset={offset}, limit={limit})"
    )

    statement = select(Attendance).where(Attendance.employee_id == employee_id)

    # Apply date range filters if provided
    if start_date:
        try:
            datetime.fromisoformat(start_date)
            statement = statement.where(Attendance.date >= start_date)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="start_date must be in YYYY-MM-DD format",
            )

    if end_date:
        try:
            datetime.fromisoformat(end_date)
            statement = statement.where(Attendance.date <= end_date)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="end_date must be in YYYY-MM-DD format",
            )

    statement = statement.offset(offset).limit(limit)
    records = session.exec(statement).all()
    logger.info(
        f"Retrieved {len(records)} attendance record(s) for employee {employee_id}"
    )
    return list(records)


@router.get("/summary/{employee_id}/{month}", response_model=MonthlySummary)
async def get_monthly_summary(
    employee_id: int,
    month: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> MonthlySummary:
    """
    Get monthly attendance summary for a specific employee.
    Provides aggregated statistics for the specified month.

    **RBAC:** Employees can view their own summary, HR/Managers can view anyone's summary.

    Args:
        employee_id: The ID of the employee
        month: Month in YYYY-MM format
        session: Database session (injected)
        current_user: Current authenticated user

    Returns:
        Monthly attendance summary with statistics and records

    Raises:
        HTTPException: 400 if month format is invalid, 403 if unauthorized
    """
    # RBAC: Employees can only view their own summary
    is_hr_or_manager = any(
        role in current_user.groups
        for role in ["HR-Administrators", "HR-Managers", "Team-Managers"]
    )

    if not is_hr_or_manager:
        # Regular employees can only view their own summary
        employee_data = await employee_service.get_employee(employee_id)
        if not employee_data:
            raise HTTPException(
                status_code=404,
                detail=f"Employee {employee_id} not found",
            )

        if employee_data.get("email") != current_user.email:
            logger.warning(
                f"User {current_user.email} attempted to view summary for another employee {employee_id}"
            )
            raise HTTPException(
                status_code=403,
                detail="You can only view your own attendance summary",
            )
    logger.info(f"Fetching monthly summary for employee {employee_id}, month {month}")

    # Validate month format
    try:
        datetime.fromisoformat(f"{month}-01")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Month must be in YYYY-MM format",
        )

    # Get all records for the month
    start_date = f"{month}-01"
    # Calculate last day of month
    first_of_month = datetime.fromisoformat(f"{month}-01")
    if first_of_month.month == 12:
        last_of_month = datetime(first_of_month.year + 1, 1, 1) - timedelta(days=1)
    else:
        last_of_month = datetime(
            first_of_month.year, first_of_month.month + 1, 1
        ) - timedelta(days=1)
    end_date = last_of_month.date().isoformat()

    statement = select(Attendance).where(
        (Attendance.employee_id == employee_id)
        & (Attendance.date >= start_date)
        & (Attendance.date <= end_date)
    )
    records = session.exec(statement).all()

    # Calculate statistics
    present_count = sum(1 for r in records if r.status == "present")
    absent_count = sum(1 for r in records if r.status == "absent")
    late_count = sum(1 for r in records if r.status == "late")

    # Calculate total working hours
    total_hours = 0.0
    for record in records:
        if record.check_in_time and record.check_out_time:
            duration = record.check_out_time - record.check_in_time
            total_hours += duration.total_seconds() / 3600

    logger.info(
        f"Monthly summary for employee {employee_id}: "
        f"{present_count} present, {absent_count} absent, {late_count} late"
    )

    return MonthlySummary(
        employee_id=employee_id,
        month=month,
        total_days_worked=present_count,
        total_present=present_count,
        total_absent=absent_count,
        total_late=late_count,
        working_hours=total_hours,
        records=[AttendancePublic.model_validate(r) for r in records],
    )


@router.post("/check-in/me", response_model=AttendancePublic, status_code=201)
async def check_in_self(
    session: SessionDep,
    current_user: CurrentUserDep,
) -> Attendance:
    """
    Employee self check-in endpoint (simplified - no employee_id required).
    Records the check-in time for the current authenticated user.

    **RBAC:** Any authenticated employee can check in themselves.

    Args:
        session: Database session (injected)
        current_user: Current authenticated user

    Returns:
        Created or updated attendance record with check-in time

    Raises:
        HTTPException: 404 if employee record not found
    """
    logger.info(f"Self check-in initiated by {current_user.email}")

    # Look up employee by current user's email
    employee_data = await employee_service.get_employee_by_email(current_user.email)
    if not employee_data:
        raise HTTPException(
            status_code=404,
            detail="Employee record not found for current user",
        )

    employee_id = employee_data.get("id")

    # Get today's date in YYYY-MM-DD format
    today = datetime.now().date().isoformat()
    check_in_time = datetime.now()

    # Check if attendance record already exists for today
    statement = select(Attendance).where(
        (Attendance.employee_id == employee_id) & (Attendance.date == today)
    )
    existing_record = session.exec(statement).first()

    if existing_record:
        # Update existing record with check-in time
        logger.info(f"Updating check-in for employee {employee_id} on {today}")
        existing_record.check_in_time = check_in_time
        existing_record.status = "present"
        existing_record.updated_at = datetime.now()
        session.add(existing_record)
        session.commit()
        session.refresh(existing_record)
        logger.info(f"Employee {employee_id} checked in at {check_in_time}")

        # Publish attendance marked event
        try:
            event = EventEnvelope(
                event_type=EventType.ATTENDANCE_MARKED,
                data={
                    "attendance_id": str(existing_record.id),
                    "employee_id": existing_record.employee_id,
                    "check_in_time": existing_record.check_in_time.isoformat()
                    if existing_record.check_in_time
                    else None,
                    "check_out_time": existing_record.check_out_time.isoformat()
                    if existing_record.check_out_time
                    else None,
                    "status": existing_record.status,
                    "date": existing_record.date,
                },
                metadata=EventMetadata(user_id=current_user.sub),
            )
            await publish_event("attendance-events", event)
            logger.info(f"Published attendance marked event for: {existing_record.id}")
        except Exception as e:
            logger.warning(f"Failed to publish attendance marked event: {e}")

        return existing_record
    else:
        # Create new attendance record
        logger.info(f"Creating new check-in for employee {employee_id} on {today}")
        new_record = Attendance(
            employee_id=employee_id,
            date=today,
            check_in_time=check_in_time,
            status="present",
        )
        session.add(new_record)
        session.commit()
        session.refresh(new_record)
        logger.info(f"Employee {employee_id} checked in at {check_in_time}")

        # Publish attendance marked event
        try:
            event = EventEnvelope(
                event_type=EventType.ATTENDANCE_MARKED,
                data={
                    "attendance_id": str(new_record.id),
                    "employee_id": new_record.employee_id,
                    "check_in_time": new_record.check_in_time.isoformat()
                    if new_record.check_in_time
                    else None,
                    "check_out_time": new_record.check_out_time.isoformat()
                    if new_record.check_out_time
                    else None,
                    "status": new_record.status,
                    "date": new_record.date,
                },
                metadata=EventMetadata(user_id=current_user.sub),
            )
            await publish_event("attendance-events", event)
            logger.info(f"Published attendance marked event for: {new_record.id}")
        except Exception as e:
            logger.warning(f"Failed to publish attendance marked event: {e}")

        return new_record


@router.post("/check-out/me", response_model=AttendancePublic, status_code=200)
async def check_out_self(
    session: SessionDep,
    current_user: CurrentUserDep,
) -> Attendance:
    """
    Employee self check-out endpoint (simplified - no employee_id required).
    Records the check-out time for the current authenticated user.

    **RBAC:** Any authenticated employee can check out themselves.

    Args:
        session: Database session (injected)
        current_user: Current authenticated user

    Returns:
        Updated attendance record with check-out time

    Raises:
        HTTPException: 404 if no check-in found or employee record not found
    """
    logger.info(f"Self check-out initiated by {current_user.email}")

    # Look up employee by current user's email
    employee_data = await employee_service.get_employee_by_email(current_user.email)
    if not employee_data:
        raise HTTPException(
            status_code=404,
            detail="Employee record not found for current user",
        )

    employee_id = employee_data.get("id")

    # Get today's date in YYYY-MM-DD format
    today = datetime.now().date().isoformat()
    check_out_time = datetime.now()

    # Find today's attendance record
    statement = select(Attendance).where(
        (Attendance.employee_id == employee_id) & (Attendance.date == today)
    )
    record = session.exec(statement).first()

    if not record:
        logger.warning(
            f"Check-out attempted but no check-in found for employee {employee_id} on {today}"
        )
        raise HTTPException(
            status_code=404,
            detail="No check-in record found for today. Please check in first.",
        )

    # Update record with check-out time
    logger.info(f"Updating check-out for employee {employee_id} on {today}")
    record.check_out_time = check_out_time
    record.updated_at = datetime.now()
    session.add(record)
    session.commit()
    session.refresh(record)
    logger.info(f"Employee {employee_id} checked out at {check_out_time}")

    # Publish attendance updated event
    try:
        event = EventEnvelope(
            event_type=EventType.ATTENDANCE_UPDATED,
            data={
                "attendance_id": str(record.id),
                "employee_id": record.employee_id,
                "updated_fields": {"check_out_time": check_out_time.isoformat()},
            },
            metadata=EventMetadata(user_id=current_user.sub),
        )
        await publish_event("attendance-events", event)
        logger.info(f"Published attendance updated event for: {record.id}")
    except Exception as e:
        logger.warning(f"Failed to publish attendance updated event: {e}")

    return record


@router.get("/me/today", response_model=AttendancePublic | None)
async def get_my_attendance_today(
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """
    Get current user's attendance record for today.
    Convenient endpoint for employees to check their own attendance status.

    **RBAC:** Any authenticated employee can access their own today's record.

    Args:
        session: Database session (injected)
        current_user: Current authenticated user

    Returns:
        Today's attendance record or None if not checked in yet
    """
    # Get employee_id from current user's email
    # We need to find the employee by email
    employee_data = await employee_service.get_employee_by_email(current_user.email)
    if not employee_data:
        raise HTTPException(
            status_code=404,
            detail="Employee record not found for current user",
        )

    employee_id = employee_data.get("id")
    today = datetime.now().date().isoformat()

    statement = select(Attendance).where(
        (Attendance.employee_id == employee_id) & (Attendance.date == today)
    )
    record = session.exec(statement).first()

    logger.info(
        f"User {current_user.email} (employee {employee_id}) fetched today's attendance"
    )
    return record


@router.get("/me/history", response_model=list[AttendancePublic])
async def get_my_attendance_history(
    session: SessionDep,
    current_user: CurrentUserDep,
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 100,
    start_date: str | None = None,
    end_date: str | None = None,
):
    """
    Get current user's attendance history.
    Convenient endpoint for employees to view their own attendance records.

    **RBAC:** Any authenticated employee can access their own records.

    Args:
        session: Database session (injected)
        current_user: Current authenticated user
        offset: Number of records to skip (default: 0)
        limit: Maximum number of records to return (default: 100, max: 100)
        start_date: Optional start date in YYYY-MM-DD format
        end_date: Optional end date in YYYY-MM-DD format

    Returns:
        List of attendance records for the current user
    """
    # Get employee_id from current user's email
    employee_data = await employee_service.get_employee_by_email(current_user.email)
    if not employee_data:
        raise HTTPException(
            status_code=404,
            detail="Employee record not found for current user",
        )

    employee_id = employee_data.get("id")

    statement = select(Attendance).where(Attendance.employee_id == employee_id)

    # Apply date range filters if provided
    if start_date:
        try:
            datetime.fromisoformat(start_date)
            statement = statement.where(Attendance.date >= start_date)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="start_date must be in YYYY-MM-DD format",
            )

    if end_date:
        try:
            datetime.fromisoformat(end_date)
            statement = statement.where(Attendance.date <= end_date)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="end_date must be in YYYY-MM-DD format",
            )

    statement = statement.offset(offset).limit(limit)
    records = session.exec(statement).all()

    logger.info(
        f"User {current_user.email} (employee {employee_id}) fetched {len(records)} attendance records"
    )
    return list(records)


@router.get("/dashboard/summary", response_model=dict)
async def get_attendance_dashboard(
    session: SessionDep,
    current_user: Annotated[
        TokenData,
        Depends(require_role("HR-Administrators", "HR-Managers", "Team-Managers")),
    ],
    date: str | None = None,
):
    """
    Get attendance dashboard summary for managers.
    Shows overall attendance statistics for a specific date (defaults to today).

    **RBAC:** Only HR-Administrators, HR-Managers, and Team-Managers can access.

    Args:
        session: Database session (injected)
        current_user: Current authenticated user (Manager role required)
        date: Optional date in YYYY-MM-DD format (defaults to today)

    Returns:
        Dashboard summary with attendance statistics
    """
    target_date = date or datetime.now().date().isoformat()

    # Validate date format
    try:
        datetime.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="date must be in YYYY-MM-DD format",
        )

    # Get all attendance records for the target date
    statement = select(Attendance).where(Attendance.date == target_date)
    records = session.exec(statement).all()

    # Calculate statistics
    total_employees_checked_in = len(records)
    present_count = sum(1 for r in records if r.status == "present")
    absent_count = sum(1 for r in records if r.status == "absent")
    late_count = sum(1 for r in records if r.status == "late")
    pending_count = sum(1 for r in records if r.status == "pending")

    # Get employees who haven't checked in yet
    # (This would require getting total employee count from employee service)
    employees_list = await employee_service.get_employees_list(limit=1000)
    total_employees = len(employees_list) if employees_list else 0
    not_checked_in = total_employees - total_employees_checked_in

    logger.info(
        f"Manager {current_user.email} accessed dashboard for date {target_date}"
    )

    return {
        "date": target_date,
        "total_employees": total_employees,
        "checked_in": total_employees_checked_in,
        "not_checked_in": not_checked_in,
        "present": present_count,
        "absent": absent_count,
        "late": late_count,
        "pending": pending_count,
        "records": [AttendancePublic.model_validate(r) for r in records],
    }


# auth check
@router.get("/auth/check")
async def protected_endpoint(current_user: CurrentUserDep):
    logger.info(f"Protected endpoint accessed by : {current_user.sub}")
    return {"authenticated": "ok", "username": current_user.username}
