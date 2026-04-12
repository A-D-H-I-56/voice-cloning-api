from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


# ----- Request Schemas -----

class SpeakRequest(BaseModel):
    clone_id: str = Field(..., description="ID of the voice clone to use")
    text: str = Field(..., min_length=1, max_length=4096, description="Text to synthesize")
    language: str = Field(default="en", description="BCP-47 language code, e.g. 'en', 'fr', 'de'")


# ----- Response Schemas -----

class CloneResponse(BaseModel):
    clone_id: str
    original_filename: str
    embedding_path: str
    created_at: datetime


class SpeakResponse(BaseModel):
    clone_id: str
    output_path: str
    text: str
    language: str


class CloneListItem(BaseModel):
    clone_id: str
    original_filename: str
    created_at: datetime


class DeleteResponse(BaseModel):
    deleted: bool
    clone_id: str
    message: str
