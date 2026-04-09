from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SessionRequest(BaseModel):
    """Frontend requests a new session."""
    include_ask_template: bool = Field(
        default=True,
        description="If true, response includes a ready-to-use payload template for POST /ask",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"include_ask_template": True},
                {"include_ask_template": False},
            ]
        }
    )


class AskPayloadTemplate(BaseModel):
    query: str = Field(default="اكتب سؤالك القانوني هنا")
    session_id: str
    include_sources: bool = True
    eastern_arabic_numerals: bool = False


class SessionResponse(BaseModel):
    """Returned to the frontend so it can attach session_id to every subsequent request."""
    session_id: str
    ask_payload_template: Optional[AskPayloadTemplate] = None


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1, description="User question in Arabic")
    session_id: str = Field(..., min_length=1, description="Session identifier from POST /session")
    include_sources: bool = Field(default=True, description="Return retrieved source docs")
    eastern_arabic_numerals: bool = Field(
        default=False, description="Convert digits 0-9 to Eastern Arabic numerals"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "ما هي حقوق العامل في قانون العمل؟",
                "session_id": "sess_abc123",
                "include_sources": True,
                "eastern_arabic_numerals": False,
            }
        }
    )


class Message(BaseModel):
    role: str = Field(..., description="Message role: user or assistant")
    content: str = Field(..., min_length=1, description="Message text")


class SourceDoc(BaseModel):
    article_id: Optional[str] = None
    article_number: Optional[str] = None
    law_name: Optional[str] = None
    legal_nature: Optional[str] = None
    keywords: Optional[str] = None
    part: Optional[str] = None
    chapter: Optional[str] = None
    page_content: str


class AskResponse(BaseModel):
    answer: str
    session_id: str
    sources: List[SourceDoc] = Field(default_factory=list)
    raw: Dict[str, Any] = Field(default_factory=dict)


class HistoryResponse(BaseModel):
    session_id: str
    history: List[Message] = Field(default_factory=list)


class ClearHistoryResponse(BaseModel):
    session_id: str
    cleared: bool = True
