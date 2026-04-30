# ============================================
# file: app/utils.py
# ============================================
from __future__ import annotations

import re
from typing import Any, List, Set, Tuple

from langchain_core.messages import HumanMessage, AIMessage


_ARABIC_STOPWORDS: Set[str] = {
    "في", "من", "على", "إلى", "عن", "أن", "هذا", "هذه", "التي", "الذي",
    "ما", "لا", "أو", "و", "كل", "ذلك", "بين", "كان", "قد", "هو", "هي",
    "لم", "بل", "ثم", "إذا", "حتى", "لكن", "منه", "فيه", "عند", "له",
    "بها", "لها", "منها", "فيها", "التى", "الذى", "ولا", "وفى", "كما",
    "تلك", "هنا", "أي", "دون", "ليس", "إلا", "أما", "مع", "عليه",
}


def arabic_tokenize(text: str) -> List[str]:
    """
    Arabic tokenization used by BM25 + metadata index.
    Removes diacritics, keeps Arabic letters/spaces, removes stopwords.
    """
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text)      # strip tashkeel
    text = re.sub(r"[\u0600-\u0605\u060C-\u061F\u0640\u06D4\u06DD-\u06DE]", "", text)  # strip Arabic punctuation
    text = re.sub(r"[^\u0621-\u064A\u0671-\u06D3\s]", " ", text)  # keep Arabic letters only
    tokens = text.split()
    return [t for t in tokens if t not in _ARABIC_STOPWORDS and len(t) > 1]


def convert_to_eastern_arabic(text: str) -> str:
    """Converts 0123456789 to ٠١٢٣٤٥٦٧٨٩"""
    if not isinstance(text, str):
        return text
    western = "0123456789"
    eastern = "٠١٢٣٤٥٦٧٨٩"
    return text.translate(str.maketrans(western, eastern))


def _message_parts(message: Any) -> Tuple[str, str]:
    if isinstance(message, dict):
        return str(message.get("role", "")), str(message.get("content", ""))
    return str(getattr(message, "role", "")), str(getattr(message, "content", ""))


def format_chat_history(messages: list, max_turns: int = 3) -> List:
    """Last *max_turns* Q&A pairs → [HumanMessage, AIMessage, …] for LangChain prompt."""
    if max_turns <= 0:
        return []

    pairs: List[Tuple[str, str]] = []
    i = 0
    while i < len(messages):
        role, content = _message_parts(messages[i])
        if role == "user":
            user_msg = content
            ai_msg = ""
            if i + 1 < len(messages):
                next_role, next_content = _message_parts(messages[i + 1])
                if next_role == "assistant":
                    ai_msg = next_content
                    i += 2
                else:
                    i += 1
            else:
                i += 1
            pairs.append((user_msg, ai_msg))
        else:
            i += 1
    # Keep only recent turns
    history: List = []
    for user_text, ai_text in pairs[-max_turns:]:
        history.append(HumanMessage(content=user_text))
        if ai_text:
            history.append(AIMessage(content=ai_text))
    return history
