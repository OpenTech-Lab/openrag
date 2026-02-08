from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import pdfplumber
import chromadb
from llama_index.core import SimpleDirectoryReader, StorageContext, VectorStoreIndex
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import Document
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core.readers.base import BaseReader
from llama_index.vector_stores.chroma import ChromaVectorStore

from app.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "openrag"


@dataclass
class JobInfo:
    job_id: str
    filename: str
    status: str = "processing"  # processing | completed | error
    progress: int = 0
    error: str = ""


# In-memory job registry (shared across the process)
jobs: dict[str, JobInfo] = {}


def _get_embed_model() -> HuggingFaceEmbedding:
    return HuggingFaceEmbedding(model_name=settings.embed_model)


def _get_chroma_vector_store() -> ChromaVectorStore:
    client = chromadb.PersistentClient(path=str(settings.persist_dir))
    collection = client.get_or_create_collection(COLLECTION_NAME)
    return ChromaVectorStore(chroma_collection=collection)


class _PDFPlumberReader(BaseReader):
    """PDF reader using pdfplumber for reliable CJK text extraction."""

    def load_data(self, file: Path, extra_info: dict | None = None, **kwargs: Any) -> list[Document]:
        documents: list[Document] = []
        with pdfplumber.open(file) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                if not text.strip():
                    continue
                meta = dict(extra_info or {})
                meta["page_label"] = str(i + 1)
                documents.append(Document(text=text, metadata=meta))
        return documents


class _ExcelReaderWithSheetMeta(BaseReader):
    """Read all sheets from an Excel file, injecting sheet_name into metadata."""

    def load_data(self, file: Path, extra_info: dict | None = None, **kwargs: Any) -> list[Document]:
        dfs = pd.read_excel(file, sheet_name=None)  # dict of sheet_name -> DataFrame
        documents: list[Document] = []
        for sheet_name, df in dfs.items():
            df = df.fillna("")
            headers = df.columns.tolist()
            rows: list[str] = []
            for _, row in df.iterrows():
                formatted = ", ".join(f"{h}: {row[h]!s}" for h in headers)
                rows.append(formatted)
            text = "\n".join(rows)
            if not text.strip():
                continue
            meta = dict(extra_info or {})
            meta["sheet_name"] = str(sheet_name)
            documents.append(Document(text=text, metadata=meta))
        return documents


def _build_file_extractors() -> dict[str, Any]:
    """Custom extractors that inject granular metadata."""
    pdf_reader = _PDFPlumberReader()
    excel_reader = _ExcelReaderWithSheetMeta()
    return {
        ".pdf": pdf_reader,
        ".xlsx": excel_reader,
        ".xls": excel_reader,
    }


def get_indexed_files() -> list[dict[str, str]]:
    """Return a list of files that have been uploaded (from the uploads dir)."""
    upload_dir = settings.upload_dir
    if not upload_dir.exists():
        return []
    files = []
    for p in sorted(upload_dir.iterdir()):
        if p.is_file() and not p.name.startswith("."):
            # Check if any job references this file
            status = "ready"
            for job in jobs.values():
                if job.filename == p.name:
                    status = job.status
                    break
            files.append({"name": p.name, "size": _human_size(p.stat().st_size), "status": status})
    return files


def _human_size(nbytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} TB"


def delete_file(filename: str) -> bool:
    """Delete a file from uploads and remove its vectors from ChromaDB."""
    filepath = settings.upload_dir / filename
    if not filepath.is_file():
        return False

    # Remove vectors from ChromaDB that match this file_name
    client = chromadb.PersistentClient(path=str(settings.persist_dir))
    collection = client.get_or_create_collection(COLLECTION_NAME)
    try:
        collection.delete(where={"file_name": filename})
    except Exception:
        logger.warning("Could not delete vectors for %s (collection may be empty)", filename)

    # Remove the file from disk
    filepath.unlink()

    # Clean up any related job entries
    to_remove = [jid for jid, j in jobs.items() if j.filename == filename]
    for jid in to_remove:
        del jobs[jid]

    logger.info("Deleted file and vectors: %s", filename)
    return True


def start_ingestion_job(filepath: Path) -> str:
    """Register a new ingestion job and return the job_id.

    The actual ingestion must be run via ``run_ingestion`` in a background task.
    """
    job_id = uuid.uuid4().hex[:12]
    jobs[job_id] = JobInfo(job_id=job_id, filename=filepath.name)
    return job_id


def run_ingestion(job_id: str, filepath: Path) -> None:
    """Run the full ingestion pipeline (blocking). Call from BackgroundTasks."""
    job = jobs.get(job_id)
    if job is None:
        return

    try:
        logger.info("Ingestion started: %s (%s)", job.filename, job_id)
        job.progress = 10

        # --- Load documents ------------------------------------------------
        reader = SimpleDirectoryReader(
            input_files=[str(filepath)],
            file_extractor=_build_file_extractors(),
        )
        documents = reader.load_data()

        # Inject file_name metadata on every document
        for doc in documents:
            doc.metadata.setdefault("file_name", filepath.name)

        job.progress = 30
        logger.info("Loaded %d document chunks from %s", len(documents), filepath.name)

        # --- Build pipeline ------------------------------------------------
        embed_model = _get_embed_model()
        vector_store = _get_chroma_vector_store()

        pipeline = IngestionPipeline(
            transformations=[
                SentenceSplitter(
                    chunk_size=settings.chunk_size,
                    chunk_overlap=settings.chunk_overlap,
                ),
                embed_model,
            ],
            vector_store=vector_store,
        )

        job.progress = 50

        # --- Run pipeline --------------------------------------------------
        nodes = pipeline.run(documents=documents, show_progress=True)
        job.progress = 90
        logger.info("Indexed %d nodes for %s", len(nodes), filepath.name)

        job.status = "completed"
        job.progress = 100

    except Exception as exc:
        logger.exception("Ingestion failed for %s", filepath.name)
        job.status = "error"
        job.error = str(exc)
