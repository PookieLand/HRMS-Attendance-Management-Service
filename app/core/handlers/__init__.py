"""
Kafka event handlers for the Attendance Management Service.

This module contains handlers that consume events from other services
and update local state accordingly.
"""

from .employee_handlers import register_employee_handlers

__all__ = ["register_employee_handlers"]
