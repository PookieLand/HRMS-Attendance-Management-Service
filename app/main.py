from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.attendance import router as attendance_router
from app.core.config import settings
from app.core.database import create_db_and_tables
from app.core.kafka import KafkaProducer
from app.core.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting application...")
    logger.info("Creating database and tables...")
    create_db_and_tables()
    logger.info("Database and tables created successfully")

    logger.info("Initializing Kafka producer...")
    await KafkaProducer.start()
    logger.info("Kafka producer initialized successfully")

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Application shutting down...")
    await KafkaProducer.stop()
    logger.info("Kafka producer stopped")


# Initialize FastAPI application
app = FastAPI(
    debug=settings.DEBUG,
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
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
app.include_router(attendance_router, prefix="/api/v1")


# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
