from pydantic import BaseModel
from typing import Literal, Optional
from enum import Enum


class ElementType(str, Enum):
    SCENE_HEADING = "scene_heading"
    ACTION = "action"
    CHARACTER = "character"
    PARENTHETICAL = "parenthetical"
    DIALOGUE = "dialogue"
    TRANSITION = "transition"
    NOTE = "note"
    PAGE_BREAK = "page_break"


class ScreenplayElement(BaseModel):
    id: str
    type: ElementType
    original: str
    translated: Optional[str] = None
    translate: bool


class ScreenplayMetadata(BaseModel):
    title: str
    source_language: str = "en"
    target_language: str = "pt-BR"
    original_format: str = "fountain"


class ScreenplayDocument(BaseModel):
    metadata: ScreenplayMetadata
    elements: list[ScreenplayElement]


class TranslationRequest(BaseModel):
    target_language: str = "pt-BR"


class TranslationResponse(BaseModel):
    session_id: str
    status: str
    message: str


class ProgressEvent(BaseModel):
    stage: Literal["parsing", "translating", "formatting", "generating_output", "done", "error"]
    progress: int  # 0-100
    message: str
    file_url: Optional[str] = None
    error: Optional[str] = None