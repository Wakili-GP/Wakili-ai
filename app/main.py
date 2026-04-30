# ============================================
# file: app/main.py
# ============================================
from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
import uuid
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

from .database import ChatLog, Base, _init_db

import anyio
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import AIMessage

from .config import settings
from .deps import get_chain, reload_chain
from .history import (
    add_to_history,
    clear_history,
    get_history,
    get_history_with_summary,
)
from .schemas import (
    AskRequest,
    ClearHistoryResponse,
    HistoryResponse,
    SessionResponse,
    SourceDoc,
)
from .utils import convert_to_eastern_arabic, format_chat_history

logger = logging.getLogger(__name__)


# Response Cache
class _ResponseCache:
    def __init__(self, maxsize: int = 128, ttl: int = 300):
        self._maxsize = maxsize
        self._ttl = ttl
        self._lock = threading.RLock()
        self._cache: OrderedDict[str, Tuple[float, Dict[str, Any]]] = OrderedDict()

    @staticmethod
    def _key(query, session_id, include_sources, eastern_arabic_numerals):
        raw = f"{query}||{session_id}||{int(include_sources)}||{int(eastern_arabic_numerals)}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, query, session_id, include_sources, eastern_arabic_numerals):
        k = self._key(query, session_id, include_sources, eastern_arabic_numerals)
        with self._lock:
            entry = self._cache.get(k)
            if not entry:
                return None
            ts, data = entry
            if time.time() - ts > self._ttl:
                self._cache.pop(k, None)
                return None
            self._cache.move_to_end(k)
            return data

    def put(self, query, session_id, include_sources, eastern_arabic_numerals, data):
        k = self._key(query, session_id, include_sources, eastern_arabic_numerals)
        with self._lock:
            self._cache[k] = (time.time(), data)
            self._cache.move_to_end(k)
            while len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)

    def clear(self):
        with self._lock:
            self._cache.clear()


_ask_cache = _ResponseCache(
    maxsize=settings.response_cache_maxsize,
    ttl=settings.response_cache_ttl,
)

app = FastAPI(title="Legal RAG API", version="2.0.0")

from fastapi.middleware.cors import CORSMiddleware


# Adding middlware to solve the CORS problem for me
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://www.wakili.me/"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    try:
        _init_db()
        logger.info("DB schema ensured")
    except Exception as e:
        logger.warning(f"DB init skipped: {e}")
    preload = os.getenv("PRELOAD_CHAIN_ON_STARTUP", "true").strip().lower() in {"1", "true", "yes", "on"}
    if preload:
        try:
            get_chain()
        except Exception as e:
            logger.warning(f"Chain preload failed: {e}")


@app.post("/session", response_model=SessionResponse)
def create_session():
    session_id = f"sess_{uuid.uuid4().hex}"
    return SessionResponse(session_id=session_id)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/reload")
def reload():
    reload_chain()
    _ask_cache.clear()
    return {"status": "reloaded"}


@app.get("/history", response_model=HistoryResponse)
def history(session_id: str):
    messages = get_history(session_id=session_id)
    return HistoryResponse(session_id=session_id, history=messages)


@app.post("/clear-history", response_model=ClearHistoryResponse)
def clear(session_id: str):
    clear_history(session_id=session_id)
    return ClearHistoryResponse(session_id=session_id, cleared=True)


@app.get("/chat-sessions")
def get_chat_sessions(user_id: str):
    from .database import _init_db, SessionLocal as LazySession
    _init_db()
    db = LazySession()
    try:
        logs = db.query(ChatLog).filter(ChatLog.user_id == user_id).order_by(ChatLog.asked_at.asc()).all()
        sessions = {}
        for log in logs:
            sid = log.session_id
            if sid not in sessions:
                sessions[sid] = {
                    "session_id": sid,
                    "title": log.question[:50],
                    "created_at": log.asked_at.isoformat(),
                    "last_message": log.response,
                    "updated_at": log.asked_at.isoformat(),
                }
            else:
                sessions[sid]["last_message"] = log.response
                sessions[sid]["updated_at"] = log.asked_at.isoformat()
        return {"success": True, "data": list(sessions.values()), "error": None, "statusCode": 200}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e), "statusCode": 500}
    finally:
        db.close()


def _dedupe_sources(docs) -> List[SourceDoc]:
    if not docs:
        return []
    seen = set()
    out = []
    for doc in docs:
        article_num = str(doc.metadata.get("article_number", "")).strip()
        if article_num and article_num in seen:
            continue
        if article_num:
            seen.add(article_num)
        out.append(SourceDoc(
            article_id=str(doc.metadata.get("article_id", "")) or None,
            article_number=article_num or None,
            law_name=str(doc.metadata.get("law_name", "")) or None,
            legal_nature=str(doc.metadata.get("legal_nature", "")) or None,
            keywords=str(doc.metadata.get("keywords", "")) or None,
            part=str(doc.metadata.get("part", "")) or None,
            chapter=str(doc.metadata.get("chapter", "")) or None,
            page_content=str(doc.page_content or ""),
        ))
    return out


def _save_chat_log(session_id: str, user_id: str, question: str, response: str):
    from .database import _init_db, SessionLocal as LazySession
    _init_db()
    db = LazySession()
    try:
        db.add(ChatLog(user_id=user_id, session_id=session_id, question=question, response=response))
        db.commit()
        logger.info(f"Chat log saved for session {session_id}")
    except Exception as e:
        logger.error(f"Failed to save chat log: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


_CONVERSATIONAL_PATTERNS = [
    "ما هو السؤال السابق", "ما سألت", "كررت", "ماذا قلت",
    "اشرح أكثر", "وضح", "هل يمكنك",
    "شكرا", "شكراً", "شكرًا",
    "مرحبا", "مرحباً", "أهلا", "أهلاً",
    "من أنت", "ما اسمك", "كيف حالك",
    "مساء", "صباح", "السلام", "هلا",
]

def _is_conversational(query: str) -> bool:
    return any(p in query.strip() for p in _CONVERSATIONAL_PATTERNS)

def _docs_are_relevant(docs: list) -> bool:
    if not docs:
        return False
    for doc in docs:
        if len(str(doc.page_content or "").strip()) > 50:
            return True
    return False


@app.post("/ask")
async def ask(payload: AskRequest, background_tasks: BackgroundTasks):

    chain = await anyio.to_thread.run_sync(get_chain)
    session_id = payload.session_id
    user_session_id = f"{payload.user_id}:{session_id}"

    cached = _ask_cache.get(payload.query, session_id, payload.include_sources, payload.eastern_arabic_numerals)
    if cached:
        background_tasks.add_task(add_to_history, session_id=user_session_id, user_msg=payload.query, assistant_msg=cached["answer"])
        background_tasks.add_task(_save_chat_log, session_id=session_id, user_id=payload.user_id, question=payload.query, response=cached["answer"])
        return {"success": True, "statusCode": 200, "error": None, "data": {"answer": cached["answer"], "session_id": session_id, "sources": cached["sources"]}}

    chat_history = []
    if settings.chat_history_turns > 0 or settings.history_summary_enabled:
        raw_history, summary = await anyio.to_thread.run_sync(lambda: get_history_with_summary(session_id=user_session_id))
        if settings.chat_history_turns > 0:
            chat_history = format_chat_history(raw_history, settings.chat_history_turns)
        if settings.history_summary_enabled and summary:
            chat_history.insert(0, AIMessage(content=f"Summary:\n{summary}"))

    try:
        retriever = chain._wakili_retriever
        docs = await anyio.to_thread.run_sync(lambda: retriever.invoke(payload.query))
        context_text = chain._wakili_format_context(docs)
        prompt_value = chain._wakili_prompt.invoke({"context": context_text, "input": payload.query, "chat_history": chat_history})
        full_answer = ""
        async for chunk in chain._wakili_llm.astream(prompt_value):
            if chunk.content:
                full_answer += chunk.content
    except Exception as e:
        return {"success": False, "statusCode": 500, "error": str(e), "data": None}

    sources = []
    if payload.include_sources and not _is_conversational(payload.query) and _docs_are_relevant(docs):
        sources = _dedupe_sources(docs)

    _ask_cache.put(payload.query, session_id, payload.include_sources, payload.eastern_arabic_numerals,
                   {"answer": full_answer, "sources": [s.model_dump() for s in sources], "raw": {}})

    background_tasks.add_task(add_to_history, session_id=user_session_id, user_msg=payload.query, assistant_msg=full_answer)
    background_tasks.add_task(_save_chat_log, session_id=session_id, user_id=payload.user_id, question=payload.query, response=full_answer)

    return {
        "success": True,
        "statusCode": 200,
        "error": None,
        "data": {
            "answer": full_answer,
            "session_id": session_id,
            "sources": [s.model_dump() for s in sources],
        }
    }