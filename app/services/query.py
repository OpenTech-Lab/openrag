from __future__ import annotations

import logging
from dataclasses import dataclass

import chromadb
from llama_index.core import VectorStoreIndex

from app.config import settings
from app.services.ingestion import COLLECTION_NAME, _get_chroma_vector_store

logger = logging.getLogger(__name__)


@dataclass
class SourceRef:
    file_name: str
    page: str
    sheet: str
    text_preview: str


@dataclass
class QueryResult:
    answer: str
    sources: list[SourceRef]


def query_documents(question: str) -> QueryResult:
    """Run a RAG query against the indexed documents.

    Global LlamaIndex Settings (LLM + embed model) are configured at app startup
    in main.py, so no per-call setup is needed here.
    """

    # Check if there are any indexed documents first
    client = chromadb.PersistentClient(path=str(settings.persist_dir))
    collection = client.get_or_create_collection(COLLECTION_NAME)
    if collection.count() == 0:
        return QueryResult(
            answer="No documents have been indexed yet. Please upload files first.",
            sources=[],
        )

    vector_store = _get_chroma_vector_store()
    index = VectorStoreIndex.from_vector_store(vector_store)

    query_engine = index.as_query_engine(
        similarity_top_k=5,
        response_mode="tree_summarize",
    )

    response = query_engine.query(question)

    answer = str(response).strip()
    if not answer or answer.lower() == "empty response":
        answer = "No relevant information found in the indexed documents."

    sources: list[SourceRef] = []
    seen = set()
    for node in response.source_nodes:
        meta = node.metadata or {}
        file_name = meta.get("file_name", "unknown")
        page = meta.get("page_label", "")
        sheet = meta.get("sheet_name", "")
        key = (file_name, page, sheet)
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            SourceRef(
                file_name=file_name,
                page=page,
                sheet=sheet,
                text_preview=node.text[:200] if node.text else "",
            )
        )

    return QueryResult(answer=answer, sources=sources)
