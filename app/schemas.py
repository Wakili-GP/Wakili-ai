from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class Message(BaseModel):
    role: str = Field(..., description="Message role: user or assistant")
    content: str = Field(..., min_length=1, description="Message text")


class SessionResponse(BaseModel):
    session_id: str


class AskRequest(BaseModel):
    query: str
    session_id: str
    user_id: str
    include_sources: bool = True
    eastern_arabic_numerals: bool = False

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "ما هي حقوق العامل في قانون العمل؟",
                "session_id": "sess_abc123",
                "user_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "include_sources": True,
                "eastern_arabic_numerals": False,
            }
        }
    )


class SourceDoc(BaseModel):
    article_id: Optional[str] = None
    article_number: Optional[str] = None
    law_name: Optional[str] = None
    legal_nature: Optional[str] = None
    keywords: Optional[str] = None
    part: Optional[str] = None
    chapter: Optional[str] = None
    page_content: str


class ClearHistoryResponse(BaseModel):
    session_id: str
    cleared: bool = True

class UpdateTitleRequest(BaseModel):
    new_title: str