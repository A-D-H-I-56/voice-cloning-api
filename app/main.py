import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.config import settings
from app.database import close_db, connect_db
from app.routes.clone_routes import router as clone_router
from app.routes.speak_routes import router as speak_router
from app.tts_engine import tts_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- Startup ----
    logger.info("========== APPLICATION STARTUP ==========")

    # Validate production settings
    if not settings.debug:
        logger.info("Validating security settings...")
        try:
            settings.validate_security_settings()
        except RuntimeError as e:
            logger.error("Security validation failed: %s", e)
            raise

    logger.info("Creating storage directories…")
    Path(settings.checkpoints_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.outputs_dir).mkdir(parents=True, exist_ok=True)

    logger.info("Connecting to MongoDB at %s…", settings.mongo_uri[:50] + "...")
    await connect_db()

    # Model loads lazily on first API request (not at startup)
    # This allows HF Spaces to start quickly without timeout
    logger.info("TTS model will load on first API request (lazy loading)")
    logger.info("API is ready to accept requests")
    logger.info("========== STARTUP COMPLETE ==========\n")

    yield  # application is running

    # ---- Shutdown ----
    logger.info("\n========== APPLICATION SHUTDOWN ==========")
    logger.info("Waiting for in-flight requests to complete...")
    import asyncio
    await asyncio.sleep(2)  # Grace period for in-flight requests

    logger.info("Closing MongoDB connection…")
    await close_db()

    logger.info("Goodbye!")
    logger.info("========== SHUTDOWN COMPLETE ==========")


app = FastAPI(
    title="Voice Cloning API",
    description=(
        "Production-ready voice cloning service powered by Coqui XTTS-v2. "
        "Clone any voice from a short audio sample and synthesise speech in multiple languages."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(clone_router)
app.include_router(speak_router)


@app.get("/health", tags=["Health"])
async def health():
    """Health check endpoint (no auth required for Kubernetes/load balancers)."""
    return {
        "status": "ok",
        "tts_device": tts_engine.device,
        "model": settings.tts_model,
    }
