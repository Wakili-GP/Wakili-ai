# ============================================
# file: app/history.py
# ============================================
from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass
import os
import threading
from typing import Deque, Dict, List, Tuple

from .config import settings
from .schemas import Message



@dataclass
class _SessionHistoryState:
    messages: Deque[Message]
    summary: str = ""


_lock = threading.RLock()
_conversations: OrderedDict[str, _SessionHistoryState] = OrderedDict()

_history_backend = os.getenv("HISTORY_BACKEND", "memory").strip().lower()
_modal_dict_name = os.getenv("HISTORY_MODAL_DICT_NAME", "wakili-history")


def _to_even(value: int, min_value: int = 2) -> int:
    out = max(min_value, value)
    if out % 2 != 0:
        out += 1
    return out


_history_max_messages = _to_even(settings.history_max_messages, min_value=2)
_history_session_limit = max(1, settings.history_session_limit)
_history_summary_enabled = bool(settings.history_summary_enabled)
_history_summary_trigger_messages = _to_even(
    settings.history_summary_trigger_messages,
    min_value=4,
)
_history_recent_messages = _to_even(settings.history_recent_messages, min_value=2)
_history_summary_max_chars = max(200, settings.history_summary_max_chars)

if _history_recent_messages >= _history_max_messages:
    _history_recent_messages = max(2, _history_max_messages - 2)

_history_summary_trigger_messages = min(
    _history_summary_trigger_messages,
    _history_max_messages,
)
if _history_summary_trigger_messages <= _history_recent_messages:
    _history_summary_trigger_messages = min(
        _history_max_messages,
        _history_recent_messages + 2,
    )

_shared_store = None

if _history_backend == "modal_dict":
    try:
        import modal

        _shared_store = modal.Dict.from_name(_modal_dict_name, create_if_missing=True)
    except Exception:
        _shared_store = None
        _history_backend = "memory"


def _conversation_key(session_id: str) -> str:
    sid = (session_id or "default").strip()
    return sid or "default"


def _compact_text(text: str, max_len: int) -> str:
    clean = " ".join((text or "").split())
    if len(clean) <= max_len:
        return clean
    return clean[: max_len - 3].rstrip() + "..."


def _extract_pairs(messages: List[Message]) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    i = 0
    while i < len(messages):
        msg = messages[i]
        if msg.role == "user":
            user_msg = msg.content
            ai_msg = ""
            if i + 1 < len(messages) and messages[i + 1].role == "assistant":
                ai_msg = messages[i + 1].content
                i += 2
            else:
                i += 1
            pairs.append((user_msg, ai_msg))
        else:
            i += 1
    return pairs


def _build_summary_snippet(messages: List[Message], max_pairs: int = 4) -> str:
    pairs = _extract_pairs(messages)
    if not pairs:
        return ""

    lines: List[str] = []
    for user_msg, ai_msg in pairs[-max_pairs:]:
        user_short = _compact_text(user_msg, max_len=120)
        ai_short = _compact_text(ai_msg, max_len=180)
        if ai_short:
            lines.append(f"- Q: {user_short} | A: {ai_short}")
        else:
            lines.append(f"- Q: {user_short}")
    return "\n".join(lines)


def _merge_summary(existing: str, snippet: str) -> str:
    existing = (existing or "").strip()
    snippet = (snippet or "").strip()
    if not snippet:
        return existing

    merged = f"{existing}\n{snippet}".strip() if existing else snippet
    if len(merged) <= _history_summary_max_chars:
        return merged
    return merged[-_history_summary_max_chars:]


def _new_state(messages: List[Message] | None = None, summary: str = "") -> _SessionHistoryState:
    msg_list = list(messages or [])
    state_summary = (summary or "").strip()

    # If older messages overflowed before this state was loaded, fold them into summary first.
    if len(msg_list) > _history_max_messages:
        overflow = msg_list[: len(msg_list) - _history_max_messages]
        state_summary = _merge_summary(state_summary, _build_summary_snippet(overflow))
        msg_list = msg_list[-_history_max_messages:]

    return _SessionHistoryState(messages=deque(msg_list, maxlen=_history_max_messages), summary=state_summary)


def _deserialize_messages(raw_messages: List[Dict]) -> List[Message]:
    out: List[Message] = []
    for raw in raw_messages:
        try:
            out.append(Message(**raw))
        except Exception:
            continue
    return out


def _rollup_if_needed(state: _SessionHistoryState) -> bool:
    if not _history_summary_enabled:
        return False

    messages = list(state.messages)
    if len(messages) <= _history_summary_trigger_messages:
        return False

    fold_count = len(messages) - _history_recent_messages
    if fold_count % 2 != 0:
        fold_count -= 1
    if fold_count < 2:
        return False

    older = messages[:fold_count]
    recent = messages[fold_count:]
    snippet = _build_summary_snippet(older)
    if not snippet:
        return False

    state.summary = _merge_summary(state.summary, snippet)
    state.messages = deque(recent[-_history_max_messages:], maxlen=_history_max_messages)
    return True


def _load_modal_state(key: str) -> Tuple[_SessionHistoryState, bool]:
    raw_state = _shared_store.get(key, [])
    if isinstance(raw_state, list):
        # Backward-compatible with legacy list-only storage.
        return _new_state(messages=_deserialize_messages(raw_state), summary=""), True

    if isinstance(raw_state, dict):
        raw_messages = raw_state.get("messages", [])
        raw_summary = str(raw_state.get("summary", "") or "")
        return _new_state(messages=_deserialize_messages(raw_messages), summary=raw_summary), False

    return _new_state(), True


def _save_modal_state(key: str, state: _SessionHistoryState):
    _shared_store[key] = {
        "messages": [m.model_dump() for m in list(state.messages)],
        "summary": state.summary,
    }


def get_history_with_summary(session_id: str) -> Tuple[List[Message], str]:
    """Return exact recent history plus rolled-up summary of older turns."""
    key = _conversation_key(session_id)

    if _history_backend == "modal_dict" and _shared_store is not None:
        state, migrated = _load_modal_state(key)
        changed = _rollup_if_needed(state)
        if migrated or changed:
            _save_modal_state(key, state)
        return list(state.messages), state.summary

    with _lock:
        state = _conversations.get(key)
        if state is None:
            return [], ""
        _conversations.move_to_end(key)
        return list(state.messages), state.summary


def get_history(session_id: str) -> List[Message]:
    """Retrieve bounded conversation history for a session."""
    messages, _ = get_history_with_summary(session_id)
    return messages


def get_history_summary(session_id: str) -> str:
    """Retrieve rolled summary for older turns in a session."""
    _, summary = get_history_with_summary(session_id)
    return summary


def add_to_history(session_id: str, user_msg: str, assistant_msg: str):
    """Add user + assistant turn and update hybrid (summary + recent turns) memory."""
    key = _conversation_key(session_id)

    if _history_backend == "modal_dict" and _shared_store is not None:
        state, _ = _load_modal_state(key)
        state.messages.append(Message(role="user", content=user_msg))
        state.messages.append(Message(role="assistant", content=assistant_msg))
        _rollup_if_needed(state)
        _save_modal_state(key, state)
        return

    with _lock:
        state = _conversations.get(key)
        if state is None:
            state = _new_state()
            _conversations[key] = state
        _conversations.move_to_end(key)
        state.messages.append(Message(role="user", content=user_msg))
        state.messages.append(Message(role="assistant", content=assistant_msg))
        _rollup_if_needed(state)

        # LRU eviction for very large numbers of sessions.
        while len(_conversations) > _history_session_limit:
            _conversations.popitem(last=False)


def clear_history(session_id: str):
    """Clear conversation history for a session."""
    key = _conversation_key(session_id)
    if _history_backend == "modal_dict" and _shared_store is not None:
        try:
            _shared_store.pop(key)
        except KeyError:
            pass
        return

    with _lock:
        if key in _conversations:
            del _conversations[key]


def get_history_text(session_id: str, max_messages: int = 6) -> str:
    """Convert hybrid history state to formatted text for debugging/admin use."""
    history, summary = get_history_with_summary(session_id)
    if not history and not summary:
        return ""

    # Keep only last max_messages messages
    recent = history[-max_messages:]

    history_text = ""
    if summary:
        history_text += f"Summary of older conversation:\n{summary}\n\n"

    history_text += "Recent conversation:\n"
    for msg in recent:
        role_label = "user" if msg.role == "user" else "assistant"
        history_text += f"{role_label}: {msg.content}\n"

    return history_text + "\n---\n\n"