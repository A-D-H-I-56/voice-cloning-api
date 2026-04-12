"""
Speech synthesis route.

POST /speak — Given a clone_id and text, stream back the generated WAV file.
              The file is also persisted under outputs/{clone_id}/ for later use.
"""

import asyncio
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, status, BackgroundTasks, Request, Depends
from fastapi.responses import FileResponse

from app.config import settings
from app.database import fetch_clone_by_id
from app.models import SpeakRequest
from app.security import verify_api_key, check_rate_limit
from app.tts_engine import tts_engine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/speak", tags=["Speak"])


def remove_file_after_delay(path: str, delay_seconds: int = 5):
    """Remove file after a delay to allow streaming to complete."""
    try:
        # Sleep allows FileResponse to finish streaming the file
        import time
        time.sleep(delay_seconds)

        if Path(path).exists():
            Path(path).unlink()
            logger.info("Temporary output file deleted: %s", path)

        # Remove empty parent directory if it becomes empty
        parent_dir = Path(path).parent
        if parent_dir.exists() and not any(parent_dir.iterdir()):
            parent_dir.rmdir()
            logger.info("Empty directory removed: %s", parent_dir)

    except Exception as e:
        logger.error("Error during cleanup of %s: %s", path, e)


@router.post(
    "",
    summary="Synthesize speech from a cloned voice",
    response_class=FileResponse,
    responses={
        200: {"content": {"audio/wav": {}}, "description": "Generated WAV audio"},
        404: {"description": "Clone not found"},
        400: {"description": "Embedding file missing — re-clone the voice"},
        500: {"description": "Synthesis failed"},
    },
    dependencies=[Depends(verify_api_key), Depends(check_rate_limit)],
)
async def speak(
    request: Request,
    body: SpeakRequest,
    background_tasks: BackgroundTasks,
):
    # 1. Verify the clone exists in MongoDB
    doc = await fetch_clone_by_id(body.clone_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Clone '{body.clone_id}' not found.",
        )

    # 2. Verify the embedding file is present on disk
    embedding_path = doc.get("embedding_path", "")
    if not embedding_path or not Path(embedding_path).is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Embedding file not found on disk. Please re-create the voice clone.",
        )

    # 3. Prepare output path — one sub-folder per clone keeps outputs organised
    output_dir = Path(settings.outputs_dir) / body.clone_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_filename = f"{uuid.uuid4().hex}.wav"
    output_path = str(output_dir / output_filename)

    # 4. Synthesise (runs in thread-pool — does not block the event loop)
    try:
        await tts_engine.synthesize_and_save(
            text=body.text,
            language=body.language,
            embedding_path=embedding_path,
            output_path=output_path,
        )
    except Exception as exc:
        logger.exception("Synthesis failed for clone '%s': %s", body.clone_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Speech synthesis failed. Check server logs.",
        )

    # Schedule cleanup AFTER streaming completes (with delay to be safe)
    background_tasks.add_task(remove_file_after_delay, output_path, delay_seconds=5)

    # 5. Stream the file back to the caller
    return FileResponse(
        path=output_path,
        media_type="audio/wav",
        filename=output_filename,
        headers={
            "X-Clone-ID": body.clone_id,
            "X-Output-Path": output_path,
        },
    )
