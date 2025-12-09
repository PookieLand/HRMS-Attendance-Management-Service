"""
Kafka Topic Definitions for Attendance Management Service.

Topic naming follows the pattern: <domain>-<event-type>
This makes topics easily identifiable and organized by business domain.
"""


class KafkaTopics:
    """
    Central registry of all Kafka topics used by the Attendance Management Service.
    Topics are named following the pattern: <domain>-<event-type>
    """

    # Attendance Events - Check-in/Check-out lifecycle
    ATTENDANCE_CHECKIN = "attendance-checkin"
    ATTENDANCE_CHECKOUT = "attendance-checkout"
    ATTENDANCE_UPDATED = "attendance-updated"
    ATTENDANCE_DELETED = "attendance-deleted"

    # Attendance Status Events
    ATTENDANCE_LATE = "attendance-late"
    ATTENDANCE_EARLY_DEPARTURE = "attendance-early-departure"
    ATTENDANCE_OVERTIME = "attendance-overtime"
    ATTENDANCE_SHORT_LEAVE = "attendance-short-leave"
    ATTENDANCE_ABSENT = "attendance-absent"

    # Summary Events - For dashboard and reporting
    ATTENDANCE_DAILY_SUMMARY = "attendance-daily-summary"
    ATTENDANCE_WEEKLY_SUMMARY = "attendance-weekly-summary"
    ATTENDANCE_MONTHLY_SUMMARY = "attendance-monthly-summary"

    # Dashboard Metrics Events
    ATTENDANCE_METRICS_TODAY = "attendance-metrics-today"
    ATTENDANCE_METRICS_UPDATED = "attendance-metrics-updated"

    # Audit Events - For audit service consumption
    AUDIT_ATTENDANCE_ACTION = "audit-attendance-action"

    # Notification Events - Triggers for notification service
    NOTIFICATION_LATE_ARRIVAL = "notification-late-arrival"
    NOTIFICATION_ABSENT_EMPLOYEE = "notification-absent-employee"
    NOTIFICATION_OVERTIME_ALERT = "notification-overtime-alert"

    @classmethod
    def all_topics(cls) -> list[str]:
        """Return list of all topic names."""
        return [
            value
            for name, value in vars(cls).items()
            if isinstance(value, str) and not name.startswith("_")
        ]

    @classmethod
    def attendance_topics(cls) -> list[str]:
        """Return list of attendance-related topics."""
        return [
            cls.ATTENDANCE_CHECKIN,
            cls.ATTENDANCE_CHECKOUT,
            cls.ATTENDANCE_UPDATED,
            cls.ATTENDANCE_DELETED,
        ]

    @classmethod
    def status_topics(cls) -> list[str]:
        """Return list of attendance status topics."""
        return [
            cls.ATTENDANCE_LATE,
            cls.ATTENDANCE_EARLY_DEPARTURE,
            cls.ATTENDANCE_OVERTIME,
            cls.ATTENDANCE_SHORT_LEAVE,
            cls.ATTENDANCE_ABSENT,
        ]

    @classmethod
    def summary_topics(cls) -> list[str]:
        """Return list of summary topics."""
        return [
            cls.ATTENDANCE_DAILY_SUMMARY,
            cls.ATTENDANCE_WEEKLY_SUMMARY,
            cls.ATTENDANCE_MONTHLY_SUMMARY,
        ]

    @classmethod
    def notification_topics(cls) -> list[str]:
        """Return list of notification-related topics."""
        return [
            cls.NOTIFICATION_LATE_ARRIVAL,
            cls.NOTIFICATION_ABSENT_EMPLOYEE,
            cls.NOTIFICATION_OVERTIME_ALERT,
        ]
