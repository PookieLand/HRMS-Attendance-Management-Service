"""
Shared API dependencies.
Contains reusable dependency functions for FastAPI endpoints.
Centralizes common dependencies like database sessions, authentication (future), etc.
"""

from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from app.core.database import get_session
from app.core.security import TokenData, get_current_active_user

# Database session dependency
# Use this type annotation in route handlers to get automatic session injection
SessionDep = Annotated[Session, Depends(get_session)]

# Current User dependency for security
CurrentUserDep = Annotated[TokenData, Depends(get_current_active_user)]
