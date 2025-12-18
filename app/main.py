"""
Attendance Management Service - Main Application Entry Point.

This service handles employee attendance tracking including:
- Check-in/Check-out operations
- Late arrival and early departure tracking
- Overtime calculation
- Dashboard metrics with Redis caching
- Kafka event publishing for audit and notifications
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.attendance import router as attendance_router
from app.core.cache import RedisClient
from app.core.config import settings
from app.core.database import create_db_and_tables
from app.core.handlers import register_employee_handlers
from app.core.kafka import KafkaConsumer, KafkaProducer
from app.core.logging import get_logger
from app.models.attendance import Attendance

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting Attendance Management Service...")

    logger.info("Creating database and tables...")
    create_db_and_tables()
    logger.info("Database and tables created successfully")

    logger.info("Initializing Redis client...")
    try:
        RedisClient.get_client()
        if RedisClient.ping():
            logger.info("Redis client connected successfully")
        else:
            logger.warning("Redis connection failed, caching will be disabled")
    except Exception as e:
        logger.warning(f"Failed to initialize Redis: {e}")

    logger.info("Initializing Kafka producer...")
    await KafkaProducer.start()
    logger.info("Kafka producer initialized")

    # Register Kafka event handlers
    logger.info("Registering employee event handlers...")
    register_employee_handlers()
    logger.info("Employee event handlers registered")

    # Start Kafka consumer if there are handlers registered
    logger.info("Starting Kafka consumer...")
    await KafkaConsumer.start()
    logger.info("Kafka consumer started")

    logger.info("Attendance Management Service startup complete")

    yield

    # Shutdown
    logger.info("Attendance Management Service shutting down...")

    logger.info("Stopping Kafka consumer...")
    await KafkaConsumer.stop()
    logger.info("Kafka consumer stopped")

    logger.info("Stopping Kafka producer...")
    await KafkaProducer.stop()
    logger.info("Kafka producer stopped")

    logger.info("Closing Redis client...")
    RedisClient.close()
    logger.info("Redis client closed")

    logger.info("Attendance Management Service shutdown complete")


# Initialize FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Attendance Management Service for HRMS - Tracks employee check-in/out, overtime, and attendance metrics",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)


# Include routers
app.include_router(attendance_router, prefix="/api/v1/attendance")


# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check():
    """
    Health check endpoint for container orchestration and monitoring.
    """
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.get("/ready", tags=["health"])
async def readiness_check():
    """
    Readiness check endpoint for Kubernetes.
    Verifies that the service is ready to accept traffic.
    """
    # Check Redis connection
    redis_ready = False
    try:
        redis_ready = RedisClient.ping()
    except Exception:
        pass

    # Check Kafka producer
    kafka_ready = KafkaProducer._started

    all_ready = redis_ready and kafka_ready

    return {
        "status": "ready" if all_ready else "not_ready",
        "checks": {
            "redis": "ok" if redis_ready else "error",
            "kafka_producer": "ok" if kafka_ready else "error",
        },
    }


@app.get("/", tags=["root"])
async def root():
    """
    Root endpoint with service information.
    """
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
    }
