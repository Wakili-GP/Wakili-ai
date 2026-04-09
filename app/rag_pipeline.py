# ============================================
# file: app/rag_pipeline.py
# ============================================
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
import warnings
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Set

import numpy as np
from langchain_chroma import Chroma
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnablePassthrough
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_classic.retrievers import ContextualCompressionRetriever
from langchain_classic.retrievers.document_compressors import CrossEncoderReranker
from rank_bm25 import BM25Okapi

from .config import Settings
from .utils import arabic_tokenize

os.environ["TRANSFORMERS_NO_PROGRESS_BAR"] = "1"
warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Global caches for heavy resources
_embeddings_cache = None
_cross_encoder_cache = None
_cache_lock = threading.RLock()

# Reusable thread pool for parallel retrieval (avoids per-request overhead)
_retrieval_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="retrieval")

# Max characters per document sent to LLM context (keeps prompt tight)
_MAX_DOC_CHARS = 1200
_VECTOR_SYNC_BATCH_SIZE = 256


# ──────────────────────────────────────────────────────────────────
# SYSTEM PROMPT  (decision-tree for 6 response cases)
# ──────────────────────────────────────────────────────────────────

SYSTEM_INSTRUCTIONS: str = """\
<role>
أنت "المساعد القانوني الذكي"، مستشار قانوني متخصص في القوانين المصرية التالية:
• الدستور المصري
• القانون المدني المصري
• قانون العمل المصري
• قانون الأحوال الشخصية المصري
• قانون مكافحة جرائم تقنية المعلومات
• قانون الإجراءات الجنائية المصري

مهمتك: الإجابة بدقة استناداً إلى السياق التشريعي المرفق أدناه.
</role>

<chat_history_instruction>
إذا وُجد سجل محادثة سابق، استخدمه لفهم أسئلة المتابعة والسياق.
لكن دائماً أعطِ الأولوية للسياق التشريعي المسترجع عند الإجابة.
لا تكرر إجابات سابقة بالكامل — أشر إليها باختصار إن لزم.
</chat_history_instruction>

<decision_logic>
حلّل سؤال المستخدم ثم اتبع أول حالة ينطبق شرطها:

━━━ الحالة ١ — الإجابة موجودة في السياق ━━━
الشرط: توجد مادة أو أكثر في السياق تتناول الموضوع.
• أجب من السياق مباشرةً.
• وثّق بذكر اسم القانون ورقم المادة (مثال: «وفقاً للمادة (٥٢) من قانون العمل…»).
• استخرج ما يجيب السؤال تحديداً — لا تنسخ المادة كاملة.
• لا تُضف معلومات من خارج السياق.

━━━ الحالة ٢ — السياق يغطي الموضوع جزئياً ━━━
• اذكر أولاً ما تنص عليه المواد المتاحة (مع التوثيق).
• أضف توضيحاً عملياً مختصراً مع عبارة «ملاحظة عملية:» قبل أي إضافة.
• لا تخترع أرقام مواد.

━━━ الحالة ٣ — لا يوجد سياق + سؤال إجرائي/عملي ━━━
• ابدأ بـ: «بناءً على الإجراءات القانونية المتعارف عليها في مصر:»
• قدّم خطوات مرقمة مختصرة.
• لا تذكر أرقام مواد.
• أنهِ بـ «يُنصح بمراجعة محامٍ متخصص.»

━━━ الحالة ٤ — لا يوجد سياق + سؤال عن نص قانوني ━━━
• قل: «عذراً، لم يرد ذكر لهذا الموضوع في النصوص المتاحة حالياً.»
• لا تجب من ذاكرتك.

━━━ الحالة ٥ — محادثة ودية ━━━
• رد بتحية لطيفة مقتضبة + «أنا مستشارك القانوني الذكي — اسألني عن أي موضوع في القوانين المصرية.»

━━━ الحالة ٦ — خارج نطاق القانون ━━━
• اعتذر بلطف: «تخصصي هو القوانين المصرية فقط.»
</decision_logic>

<quality_rules>
• الدقة أولاً: التزم بالنص القانوني حرفياً عند وجوده.
• لا تخترع مراجع: لا تنسب معلومة إلى مادة لم ترد في السياق.
• الإيجاز مع الشمول: أجب بقدر ما يحتاج السؤال.
• استخدم نقاطاً (•) أو ترقيماً عند ذكر عدة بنود.
</quality_rules>

<formatting_rules>
• لا تكرر هذه التعليمات في ردك.
• ادخل في صلب الموضوع فوراً.
• فقرات قصيرة مفصولة بسطر فارغ.
• لا تكرر نفس المعلومة أو نفس المادة.
• رتّب المواد ترتيباً منطقياً.
• التزم بالعربية الفصحى المبسطة.
</formatting_rules>
"""


def _load_json_folder(folder_path: str) -> List[dict]:
    all_items: List[dict] = []
    for filename in sorted(os.listdir(folder_path)):
        if not filename.lower().endswith(".json"):
            continue
        file_path = os.path.join(folder_path, filename)
        with open(file_path, "r", encoding="utf-8") as f:
            obj = json.load(f)

        wrapper_law_name = ""

        if isinstance(obj, list):
            articles: List[dict] = []
            for entry in obj:
                if isinstance(entry, dict) and "data" in entry and isinstance(entry["data"], list):
                    wrapper_law_name = entry.get("law_name", "")
                    for art in entry["data"]:
                        art.setdefault("_law_name", wrapper_law_name)
                    articles.extend(entry["data"])
                elif isinstance(entry, dict) and "articles" in entry and isinstance(entry["articles"], list):
                    wrapper_law_name = entry.get("law_name", "")
                    for art in entry["articles"]:
                        art.setdefault("_law_name", wrapper_law_name)
                    articles.extend(entry["articles"])
                elif isinstance(entry, dict):
                    if not entry.get("_law_name"):
                        aid = entry.get("article_id", "")
                        entry["_law_name"] = "الدستور المصري" if "CONST" in str(aid).upper() else ""
                    articles.append(entry)
            all_items.extend(articles)
        elif isinstance(obj, dict):
            wrapper_law_name = obj.get("law_name", "")
            if "data" in obj and isinstance(obj["data"], list):
                for art in obj["data"]:
                    art.setdefault("_law_name", wrapper_law_name)
                all_items.extend(obj["data"])
            elif "articles" in obj and isinstance(obj["articles"], list):
                for art in obj["articles"]:
                    art.setdefault("_law_name", wrapper_law_name)
                all_items.extend(obj["articles"])
            else:
                obj.setdefault("_law_name", wrapper_law_name)
                all_items.append(obj)
        else:
            logger.warning("Unsupported JSON format in: %s", file_path)

    return all_items


def _stable_item_key(item: dict) -> str:
    """Build a deterministic key for each legal article across reloads."""
    article_id = str(item.get("article_id", "")).strip()
    if article_id:
        return article_id

    law_name = str(item.get("law_name") or item.get("_law_name") or "").strip()
    article_number = str(item.get("article_number", "")).strip()
    if law_name or article_number:
        return f"{law_name}::{article_number}"

    return hashlib.md5(json.dumps(item, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _vector_id_for_item(item_key: str) -> str:
    return f"art_{hashlib.md5(item_key.encode('utf-8')).hexdigest()}"


def _doc_hash(page_content: str, metadata: Dict[str, str]) -> str:
    payload = {
        "page_content": page_content,
        "article_id": metadata.get("article_id", ""),
        "article_number": metadata.get("article_number", ""),
        "law_name": metadata.get("law_name", ""),
        "legal_nature": metadata.get("legal_nature", ""),
        "keywords": metadata.get("keywords", ""),
        "part": metadata.get("part", ""),
        "chapter": metadata.get("chapter", ""),
    }
    return hashlib.md5(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _iter_chunks(items: List[str], chunk_size: int):
    for i in range(0, len(items), chunk_size):
        yield items[i : i + chunk_size]


def _existing_hashes_by_vector_id(vectorstore: Chroma) -> Dict[str, str]:
    """Read current IDs + doc hashes from Chroma to compute an incremental diff."""
    try:
        snapshot = vectorstore.get(include=["metadatas"])
    except Exception:
        return {}

    ids = snapshot.get("ids") or []
    metadatas = snapshot.get("metadatas") or []

    existing: Dict[str, str] = {}
    for idx, vector_id in enumerate(ids):
        metadata = metadatas[idx] if idx < len(metadatas) and isinstance(metadatas[idx], dict) else {}
        existing[str(vector_id)] = str(metadata.get("_doc_hash", "") or "")
    return existing


def _sync_vectorstore_incremental(vectorstore: Chroma, docs_by_vector_id: Dict[str, Document]) -> None:
    """Add/update/delete only changed vectors instead of rebuilding the full store."""
    existing_hashes = _existing_hashes_by_vector_id(vectorstore)
    target_hashes = {
        vector_id: str(doc.metadata.get("_doc_hash", "") or "")
        for vector_id, doc in docs_by_vector_id.items()
    }

    to_delete = [vid for vid in existing_hashes if vid not in target_hashes]
    to_add = [vid for vid in target_hashes if vid not in existing_hashes]
    to_reindex = [
        vid
        for vid in target_hashes
        if vid in existing_hashes and existing_hashes[vid] != target_hashes[vid]
    ]

    if to_delete:
        for chunk in _iter_chunks(to_delete, _VECTOR_SYNC_BATCH_SIZE):
            vectorstore.delete(ids=chunk)

    if to_reindex:
        for chunk in _iter_chunks(to_reindex, _VECTOR_SYNC_BATCH_SIZE):
            vectorstore.delete(ids=chunk)

    to_upsert = to_add + to_reindex
    if to_upsert:
        for chunk_ids in _iter_chunks(to_upsert, _VECTOR_SYNC_BATCH_SIZE):
            chunk_docs = [docs_by_vector_id[vid] for vid in chunk_ids]
            vectorstore.add_documents(documents=chunk_docs, ids=chunk_ids)

    logger.info(
        "✅ Chroma sync: +%d ~%d -%d (total=%d)",
        len(to_add),
        len(to_reindex),
        len(to_delete),
        len(target_hashes),
    )


def build_qa_chain(settings: Settings):
    """
    Builds and returns qa_chain accepting:
        {"input": str, "chat_history": [HumanMessage, AIMessage, …]}
    and returning:
        {"context": [Document], "input": str, "chat_history": list, "answer": str}
    """
    if not os.path.exists(settings.data_dir):
        raise FileNotFoundError(f"Data folder not found: {settings.data_dir}")

    data = _load_json_folder(settings.data_dir)

    # De-duplicate by stable key so reloads produce deterministic vector IDs.
    unique: Dict[str, dict] = {}
    for item in data:
        key = _stable_item_key(item)
        unique[key] = item
    data = list(unique.values())

    docs: List[Document] = []
    vector_ids: List[str] = []
    for item in data:
        article_number = item.get("article_number")
        original_text = item.get("original_text")
        simplified_summary = item.get("simplified_summary")
        if not article_number or not original_text or not simplified_summary:
            continue

        law_name = item.get("law_name") or item.get("_law_name", "")
        part_bab = item.get("part (Bab)", "")
        chapter_fasl = item.get("chapter (Fasl)", "")
        section = item.get("section", "")

        page_content = (
            f"القانون: {law_name}\n"
            f"رقم المادة: {article_number}\n"
            f"الباب: {part_bab}\n"
            f"الفصل: {chapter_fasl}\n"
            f"القسم: {section}\n"
            f"النص الأصلي: {original_text}\n"
            f"الشرح المبسط: {simplified_summary}"
        )

        item_key = _stable_item_key(item)
        vector_id = _vector_id_for_item(item_key)

        metadata = {
            "article_id": item.get("article_id") or str(article_number),
            "article_number": str(article_number),
            "law_name": law_name,
            "legal_nature": item.get("legal_nature", ""),
            "keywords": ", ".join(item.get("keywords", []) or []),
            "part": part_bab,
            "chapter": chapter_fasl,
            "_doc_key": item_key,
        }
        metadata["_doc_hash"] = _doc_hash(page_content=page_content, metadata=metadata)
        docs.append(Document(page_content=page_content, metadata=metadata))
        vector_ids.append(vector_id)

    if not docs:
        raise RuntimeError("No valid documents found in data folder (missing required fields).")

    logger.info("✅ %d legal articles loaded", len(docs))
    docs_by_vector_id: Dict[str, Document] = {
        vid: doc for vid, doc in zip(vector_ids, docs)
    }

    # Cache heavy resources globally
    global _embeddings_cache, _cross_encoder_cache
    
    with _cache_lock:
        # Load embeddings (cached)
        if _embeddings_cache is None:
            logger.info("Loading embeddings model: %s", settings.embedding_model)
            os.makedirs(settings.embedding_cache_dir, exist_ok=True)
            _embeddings_cache = HuggingFaceEmbeddings(
                model_name=settings.embedding_model,
                cache_folder=settings.embedding_cache_dir,
            )
        embeddings = _embeddings_cache

    os.makedirs(settings.chroma_dir, exist_ok=True)
    vectorstore = Chroma(
        persist_directory=settings.chroma_dir,
        embedding_function=embeddings,
    )
    _sync_vectorstore_incremental(vectorstore=vectorstore, docs_by_vector_id=docs_by_vector_id)

    base_retriever = vectorstore.as_retriever(search_kwargs={"k": settings.semantic_k})

    # -----------------------------
    # BM25 retriever
    # -----------------------------
    class BM25Retriever(BaseRetriever):
        """Arabic-aware BM25 retriever (Okapi variant)."""
        corpus_docs: List[Document]
        bm25: Optional[BM25Okapi] = None
        tokenized_corpus: Optional[list] = None
        k: int = 10

        class Config:
            arbitrary_types_allowed = True

        def __init__(self, **data):
            super().__init__(**data)
            self.tokenized_corpus = [arabic_tokenize(doc.page_content) for doc in self.corpus_docs]
            self.bm25 = BM25Okapi(self.tokenized_corpus)

        def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None) -> List[Document]:
            tokenized_query = arabic_tokenize(query)
            if not tokenized_query:
                return []
            scores = self.bm25.get_scores(tokenized_query)
            top_indices = np.argsort(scores)[::-1][: self.k]
            return [self.corpus_docs[i] for i in top_indices if scores[i] > 0]

        async def _aget_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None) -> List[Document]:
            return self._get_relevant_documents(query, run_manager=run_manager)

    bm25_retriever = BM25Retriever(corpus_docs=docs, k=settings.bm25_k)
    logger.info("✅ BM25 retriever ready")

    # -----------------------------
    # Metadata filter retriever
    # -----------------------------
    class MetadataFilterRetriever(BaseRetriever):
        """Scores docs by keyword/law-name overlap using a pre-built inverted index."""
        corpus_docs: List[Document]
        keyword_index: Optional[Dict[str, Set[int]]] = None
        law_name_index: Optional[Dict[str, Set[int]]] = None
        k: int = 10

        class Config:
            arbitrary_types_allowed = True

        def __init__(self, **data):
            super().__init__(**data)
            self.keyword_index = defaultdict(set)
            self.law_name_index = defaultdict(set)
            for idx, doc in enumerate(self.corpus_docs):
                kw_text = (
                    str(doc.metadata.get("keywords", ""))
                    + " "
                    + str(doc.metadata.get("legal_nature", ""))
                    + " "
                    + str(doc.metadata.get("part", ""))
                    + " "
                    + str(doc.metadata.get("chapter", ""))
                )
                for token in arabic_tokenize(kw_text):
                    self.keyword_index[token].add(idx)

                for token in arabic_tokenize(str(doc.metadata.get("law_name", ""))):
                    self.law_name_index[token].add(idx)

        def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None) -> List[Document]:
            query_tokens = arabic_tokenize(query)
            if not query_tokens:
                return []

            scores: Dict[int, float] = defaultdict(float)
            for token in query_tokens:
                for idx in self.keyword_index.get(token, set()):
                    scores[idx] += 3.0       # keyword match weight
                for idx in self.law_name_index.get(token, set()):
                    scores[idx] += 4.0       # law-name match weight (strongest signal)

            if not scores:
                return []

            top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[: self.k]
            return [self.corpus_docs[idx] for idx, _ in top]

        async def _aget_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None) -> List[Document]:
            return self._get_relevant_documents(query, run_manager=run_manager)

    metadata_retriever = MetadataFilterRetriever(corpus_docs=docs, k=settings.meta_k)
    logger.info("✅ Metadata retriever ready")

    # -----------------------------
    # Hybrid RRF retriever (parallel)
    # -----------------------------
    class HybridRRFRetriever(BaseRetriever):
        """Reciprocal Rank Fusion: scores = Σ β / (k + rank) across 3 retrievers."""
        semantic_retriever: BaseRetriever
        bm25_retriever: BM25Retriever
        metadata_retriever: MetadataFilterRetriever
        beta_semantic: float = 0.60
        beta_keyword: float = 0.20
        beta_metadata: float = 0.20
        k: int = 60
        top_k: int = 15

        class Config:
            arbitrary_types_allowed = True

        def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None) -> List[Document]:
            t0 = time.perf_counter()
            fut_sem = _retrieval_pool.submit(self.semantic_retriever.invoke, query)
            fut_bm = _retrieval_pool.submit(self.bm25_retriever.invoke, query)
            fut_meta = _retrieval_pool.submit(self.metadata_retriever.invoke, query)

            semantic_docs = fut_sem.result(timeout=30)
            bm25_docs = fut_bm.result(timeout=30)
            metadata_docs = fut_meta.result(timeout=30)
            logger.info("    [retrieval] semantic=%d bm25=%d meta=%d (%.2fs)",
                        len(semantic_docs), len(bm25_docs), len(metadata_docs),
                        time.perf_counter() - t0)

            rrf_scores: Dict[str, float] = {}
            all_docs: Dict[str, Document] = {}

            for weight, doc_list in [
                (self.beta_semantic, semantic_docs),
                (self.beta_keyword, bm25_docs),
                (self.beta_metadata, metadata_docs),
            ]:
                for rank, doc in enumerate(doc_list, start=1):
                    doc_id = doc.metadata.get("article_id") or doc.metadata.get("article_number") or str(hash(doc.page_content))
                    rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + weight / (self.k + rank)
                    all_docs.setdefault(doc_id, doc)

            sorted_ids = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
            return [all_docs[did] for did, _ in sorted_ids[: self.top_k] if did in all_docs]

        async def _aget_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None) -> List[Document]:
            return self._get_relevant_documents(query, run_manager=run_manager)

    hybrid_retriever = HybridRRFRetriever(
        semantic_retriever=base_retriever,
        bm25_retriever=bm25_retriever,
        metadata_retriever=metadata_retriever,
        beta_semantic=settings.beta_semantic,
        beta_keyword=settings.beta_bm25,
        beta_metadata=settings.beta_metadata,
        k=settings.rrf_k,
        top_k=settings.hybrid_top_k,
    )
    logger.info("✅ Hybrid RRF (β sem=%.2f bm25=%.2f meta=%.2f)", settings.beta_semantic, settings.beta_bm25, settings.beta_metadata)

    # -----------------------------
    # Reranker (CrossEncoder) - cached
    # -----------------------------
    _RERANKER_HF_ID = "BAAI/bge-reranker-v2-m3"
    reranker_path = settings.reranker_model_path

    if reranker_path and os.path.exists(reranker_path):
        has_weights = any(
            f.endswith((".bin", ".safetensors", ".pt"))
            for f in os.listdir(reranker_path)
        )
        if not has_weights:
            logger.info("Local reranker dir has no weights; using HF cached model: %s", _RERANKER_HF_ID)
            reranker_path = _RERANKER_HF_ID
    else:
        logger.info("No local reranker dir; using HF cached model: %s", _RERANKER_HF_ID)
        reranker_path = _RERANKER_HF_ID

    with _cache_lock:
        if _cross_encoder_cache is None:
            logger.info("Loading cross encoder reranker...")
            _cross_encoder_cache = HuggingFaceCrossEncoder(model_name=reranker_path)
        cross_encoder = _cross_encoder_cache

    compressor = CrossEncoderReranker(model=cross_encoder, top_n=settings.reranker_top_n)
    final_retriever = ContextualCompressionRetriever(
        base_compressor=compressor,
        base_retriever=hybrid_retriever,
    )
    logger.info("✅ Reranker ready (top_n=%d)", settings.reranker_top_n)

    # -----------------------------
    # LLM (Groq)
    # -----------------------------
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is missing in .env")

    llm = ChatGroq(
        groq_api_key=settings.groq_api_key,
        model_name=settings.groq_model_name,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        model_kwargs={"top_p": settings.top_p},
        max_retries=settings.llm_max_retries,
        request_timeout=settings.llm_timeout,
    )

    # -----------------------------
    # Prompt (system + context + chat history + user)
    # -----------------------------
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_INSTRUCTIONS),
        ("system", "السياق التشريعي المتاح (المصدر الأساسي):\n{context}"),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "سؤال المستفيد:\n{input}"),
    ])

    # -----------------------------
    # Chain (retrieve → format → generate) with timing
    # -----------------------------
    def _format_context(docs_list: List[Document]) -> str:
        """Join doc texts with a separator for the LLM prompt, truncating overly long docs."""
        parts = []
        for d in docs_list:
            text = d.page_content
            if len(text) > _MAX_DOC_CHARS:
                text = text[:_MAX_DOC_CHARS] + " …"
            parts.append(text)
        return "\n\n---\n\n".join(parts)

    def _timed_retrieve(query: str) -> List[Document]:
        """Retrieve + rerank with timing logs."""
        t0 = time.perf_counter()
        docs = final_retriever.invoke(query)
        elapsed = time.perf_counter() - t0
        logger.info("    [retrieval+rerank] %d docs in %.2fs", len(docs), elapsed)
        return docs

    qa_chain = (
        RunnableParallel({
            "context":      (lambda x: x["input"]) | RunnableLambda(_timed_retrieve),
            "input":        lambda x: x["input"],
            "chat_history": lambda x: x.get("chat_history", []),
        })
        .assign(
            answer=(
                RunnableLambda(lambda x: {
                    "context":      _format_context(x["context"]),
                    "input":        x["input"],
                    "chat_history": x.get("chat_history", []),
                })
                | prompt
                | llm
                | StrOutputParser()
            ),
        )
    )

    logger.info("✅ System ready!")

    # Warmup: run one dummy rerank pass so the first real request isn't 10x slower
    try:
        _warmup_doc = docs[0] if docs else Document(page_content="warmup")
        compressor.compress_documents([_warmup_doc], "warmup")
        logger.info("✅ Reranker warmup done")
    except Exception:
        logger.debug("Reranker warmup skipped")

    # Attach components to the chain for the streaming endpoint
    qa_chain._wakili_retriever = final_retriever
    qa_chain._wakili_llm = llm
    qa_chain._wakili_prompt = prompt
    qa_chain._wakili_format_context = _format_context

    return qa_chain

