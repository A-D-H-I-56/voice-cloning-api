"""
Clone management routes.

POST   /clone          — Upload audio → extract embeddings → persist metadata
GET    /clones         — List all voice clones
DELETE /clone/{id}     — Remove embeddings, generated outputs, and DB record
"""

import logging
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, UploadFile, File, status, Request, Depends

from app.config import settings
from app.database import (
    delete_clone_by_id,
    fetch_all_clones,
    fetch_clone_by_id,
    insert_clone,
    update_clone_fields,
)
from app.models import CloneListItem, CloneResponse, DeleteResponse
from app.security import verify_api_key, check_rate_limit
from app.tts_engine import tts_engine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/clone", tags=["Clone"])

_ALLOWED_EXTENSIONS = {".wav", ".mp3"}


def _validate_clone_id(clone_id: str) -> str:
    """Validate clone_id is a valid MongoDB ObjectId (prevents path traversal)."""
    try:
        return str(ObjectId(clone_id))
    except (InvalidId, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid clone ID format: '{clone_id}'",
        )


# ---------- POST /clone ----------


@router.post(
    "",
    response_model=CloneResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a reference audio file and create a voice clone",
    dependencies=[Depends(verify_api_key), Depends(check_rate_limit)],
)
async def create_clone(
    request: Request,
    file: UploadFile = File(..., description="Reference audio (WAV or MP3)"),
):
    suffix = Path(file.filename or "audio").suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{suffix}'. Allowed: {_ALLOWED_EXTENSIONS}",
        )

    # Validate file size (read into memory first to check size)
    file_content = await file.read()
    file_size_mb = len(file_content) / (1024 * 1024)

    if file_size_mb > settings.max_file_size_mb:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large: {file_size_mb:.1f} MB. Max: {settings.max_file_size_mb} MB",
        )

    # Write upload to a temp file (TTS library needs a file-system path)
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = tmp.name
        tmp.write(file_content)

    try:
        now = datetime.now(timezone.utc)

        # Insert placeholder to obtain the MongoDB-generated ID
        clone_id = await insert_clone(
            {
                "original_filename": file.filename,
                "embedding_path": "",  # back-filled after extraction
                "created_at": now,
            }
        )

        # Derive a stable file name from the clone ID
        embedding_path = str(Path(settings.checkpoints_dir) / f"{clone_id}.pt")

        # Extract speaker embeddings and persist as .pt (runs in thread-pool)
        try:
            await tts_engine.extract_and_save_embeddings(tmp_path, embedding_path)
        except Exception as exc:
            # Rollback: delete the incomplete record
            logger.exception("Embedding extraction failed for clone %s", clone_id)
            await delete_clone_by_id(clone_id)
            Path(embedding_path).unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Embedding extraction failed. Check server logs.",
            )

        # Persist the resolved embedding path in MongoDB
        await update_clone_fields(clone_id, {"embedding_path": embedding_path})

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to create clone: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Embedding extraction failed. Check server logs.",
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return CloneResponse(
        clone_id=clone_id,
        original_filename=file.filename or "",
        embedding_path=embedding_path,
        created_at=now,
    )


# ---------- GET /clones ----------


@router.get(
    "s",  # combined with the router prefix this resolves to GET /clones
    response_model=list[CloneListItem],
    summary="List all voice clones",
    dependencies=[Depends(verify_api_key)],
)
async def list_clones():
    docs = await fetch_all_clones()
    return [
        CloneListItem(
            clone_id=doc["_id"],
            original_filename=doc.get("original_filename", ""),
            created_at=doc["created_at"],
        )
        for doc in docs
    ]


# ---------- DELETE /clone/{id} ----------


@router.delete(
    "/{clone_id}",
    response_model=DeleteResponse,
    summary="Delete a voice clone and all associated files",
    dependencies=[Depends(verify_api_key)],
)
async def delete_clone(clone_id: str):
    # Validate clone_id format (prevents path traversal)
    _validate_clone_id(clone_id)

    doc = await fetch_clone_by_id(clone_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Clone '{clone_id}' not found.",
        )

    # 1. Remove embedding .pt file
    embedding_path_str = doc.get("embedding_path", "")
    if embedding_path_str:
        Path(embedding_path_str).unlink(missing_ok=True)

    # 2. Remove entire outputs sub-directory for this clone
    outputs_dir = Path(settings.outputs_dir) / clone_id
    if outputs_dir.exists():
        shutil.rmtree(outputs_dir)

    # 3. Remove MongoDB record
    deleted = await delete_clone_by_id(clone_id)

    return DeleteResponse(
        deleted=deleted,
        clone_id=clone_id,
        message=(
            "Clone and all associated files removed."
            if deleted
            else "Files removed but DB record was already gone."
        ),
    )
