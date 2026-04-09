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

import anyio
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage

from .config import settings
from .deps import get_chain, reload_chain
from .history import add_to_history, clear_history, get_history, get_history_with_summary
from .schemas import (
    AskPayloadTemplate,
    AskRequest,
    AskResponse,
    ClearHistoryResponse,
    HistoryResponse,
    SessionRequest,
    SessionResponse,
    SourceDoc,
)
from .utils import convert_to_eastern_arabic, format_chat_history

logger = logging.getLogger(__name__)


# ─── Lightweight TTL-LRU cache for /ask responses ────────────────

class _ResponseCache:
    """Thread-safe LRU cache with TTL for RAG responses.
    Avoids re-running the full pipeline for identical (query, session) pairs.
    """
    def __init__(self, maxsize: int = 128, ttl: int = 300):
        self._maxsize = maxsize
        self._ttl = ttl                         # seconds
        self._lock = threading.RLock()
        self._cache: OrderedDict[str, Tuple[float, Dict[str, Any]]] = OrderedDict()

    @staticmethod
    def _key(
        query: str,
        session_id: str,
        include_sources: bool,
        eastern_arabic_numerals: bool,
    ) -> str:
        key_raw = (
            f"{query}||{session_id}||{int(include_sources)}||{int(eastern_arabic_numerals)}"
        )
        return hashlib.md5(key_raw.encode()).hexdigest()

    def get(
        self,
        query: str,
        session_id: str,
        include_sources: bool,
        eastern_arabic_numerals: bool,
    ) -> Optional[Dict[str, Any]]:
        k = self._key(query, session_id, include_sources, eastern_arabic_numerals)
        with self._lock:
            entry = self._cache.get(k)
            if entry is None:
                return None
            ts, data = entry
            if time.time() - ts > self._ttl:
                self._cache.pop(k, None)
                return None
            self._cache.move_to_end(k)
            return data

    def put(
        self,
        query: str,
        session_id: str,
        include_sources: bool,
        eastern_arabic_numerals: bool,
        data: Dict[str, Any],
    ) -> None:
        k = self._key(query, session_id, include_sources, eastern_arabic_numerals)
        with self._lock:
            self._cache[k] = (time.time(), data)
            self._cache.move_to_end(k)
            while len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


_ask_cache = _ResponseCache(
    maxsize=settings.response_cache_maxsize,
    ttl=settings.response_cache_ttl,
)

app = FastAPI(title="Legal RAG API", version="2.0.0")

# Optional: allow frontend calls
allow_any_origin = "*" in settings.cors_allowed_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=not allow_any_origin,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    preload = os.getenv("PRELOAD_CHAIN_ON_STARTUP", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if preload:
        get_chain()


# ─── Session management ──────────────────────────────────────────

@app.post("/session", response_model=SessionResponse)
def create_session(payload: SessionRequest = SessionRequest()):
    """Frontend calls this to get a new session_id and an optional /ask template."""
    session_id = f"sess_{uuid.uuid4().hex}"
    ask_template = None
    if payload.include_ask_template:
        ask_template = AskPayloadTemplate(
            query="اكتب سؤالك القانوني هنا",
            session_id=session_id,
            include_sources=True,
            eastern_arabic_numerals=False,
        )
    return SessionResponse(session_id=session_id, ask_payload_template=ask_template)


# ─── Health & maintenance ────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/reload")
def reload():
    reload_chain()
    _ask_cache.clear()
    return {"status": "reloaded"}


# ─── History ─────────────────────────────────────────────────────

@app.get("/history", response_model=HistoryResponse)
def history(session_id: str):
    messages = get_history(session_id=session_id)
    return HistoryResponse(session_id=session_id, history=messages)


@app.post("/clear-history", response_model=ClearHistoryResponse)
def clear(session_id: str):
    clear_history(session_id=session_id)
    return ClearHistoryResponse(session_id=session_id, cleared=True)


# ─── Ask (RAG) ───────────────────────────────────────────────────

def _dedupe_sources(docs) -> List[SourceDoc]:
    if not docs:
        return []
    seen = set()
    out: List[SourceDoc] = []
    for doc in docs:
        article_num = str(doc.metadata.get("article_number", "")).strip()
        if article_num and article_num in seen:
            continue
        if article_num:
            seen.add(article_num)
        out.append(
            SourceDoc(
                article_id=str(doc.metadata.get("article_id", "")) or None,
                article_number=article_num or None,
                law_name=str(doc.metadata.get("law_name", "")) or None,
                legal_nature=str(doc.metadata.get("legal_nature", "")) or None,
                keywords=str(doc.metadata.get("keywords", "")) or None,
                part=str(doc.metadata.get("part", "")) or None,
                chapter=str(doc.metadata.get("chapter", "")) or None,
                page_content=str(doc.page_content or ""),
            )
        )
    return out


@app.post("/ask", response_model=AskResponse)
async def ask(payload: AskRequest, background_tasks: BackgroundTasks):
    t0 = time.perf_counter()
    chain = await anyio.to_thread.run_sync(get_chain)
    active_session_id = payload.session_id

    # ── Check response cache (skip RAG for identical recent queries) ──
    cached = _ask_cache.get(
        payload.query,
        active_session_id,
        payload.include_sources,
        payload.eastern_arabic_numerals,
    )
    if cached is not None:
        logger.info("POST /ask cache HIT (%.3fs)", time.perf_counter() - t0)
        # Record in history in the background so response returns immediately
        background_tasks.add_task(
            add_to_history,
            session_id=active_session_id,
            user_msg=payload.query,
            assistant_msg=cached["answer"],
        )
        return AskResponse(**cached, session_id=active_session_id)

    # ── Build chat history from stored conversation ──
    t_hist = time.perf_counter()
    chat_history = []
    if settings.chat_history_turns > 0 or settings.history_summary_enabled:
        raw_history, history_summary = await anyio.to_thread.run_sync(
            lambda: get_history_with_summary(session_id=active_session_id)
        )
        if settings.chat_history_turns > 0:
            chat_history = format_chat_history(raw_history, max_turns=settings.chat_history_turns)
        if settings.history_summary_enabled and history_summary:
            chat_history.insert(
                0,
                AIMessage(content=f"Summary of older conversation turns:\n{history_summary}"),
            )
    logger.info("  history: %.3fs", time.perf_counter() - t_hist)

    # ── RAG pipeline (retrieval + reranking + LLM) ──
    t_rag = time.perf_counter()
    try:
        result = await anyio.to_thread.run_sync(
            lambda: chain.invoke({"input": payload.query, "chat_history": chat_history})
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    logger.info("  rag pipeline: %.3fs", time.perf_counter() - t_rag)

    answer = result.get("answer", "")
    sources_docs = result.get("context", []) if payload.include_sources else []
    sources = _dedupe_sources(sources_docs)

    if payload.eastern_arabic_numerals:
        answer = convert_to_eastern_arabic(answer)
        if payload.include_sources:
            for s in sources:
                s.page_content = convert_to_eastern_arabic(s.page_content)
                if s.article_number:
                    s.article_number = convert_to_eastern_arabic(s.article_number)

    # Build serializable raw dict (omit Document objects and non-serializable fields)
    safe_raw = {k: v for k, v in result.items() if k not in ("context", "chat_history")}

    # ── Store in cache ──
    cache_payload = {
        "answer": answer,
        "sources": [s.model_dump() for s in sources],
        "raw": safe_raw,
    }
    _ask_cache.put(
        payload.query,
        active_session_id,
        payload.include_sources,
        payload.eastern_arabic_numerals,
        cache_payload,
    )

    elapsed = time.perf_counter() - t0
    logger.info("POST /ask completed in %.2fs", elapsed)

    # Record in history in the background
    background_tasks.add_task(
        add_to_history,
        session_id=active_session_id,
        user_msg=payload.query,
        assistant_msg=answer,
    )

    return AskResponse(
        answer=answer,
        session_id=active_session_id,
        sources=sources,
        raw=safe_raw,
    )



