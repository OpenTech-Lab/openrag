from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Request, UploadFile
from fastapi.responses import HTMLResponse

from app.config import settings
from app.services.ingestion import (
    delete_file,
    get_indexed_files,
    jobs,
    run_ingestion,
    start_ingestion_job,
)

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".xlsx", ".xls"}
STREAM_CHUNK = 1024 * 1024  # 1 MB


@router.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    templates = request.app.state.templates
    files = get_indexed_files()
    return templates.TemplateResponse(
        "index.html", {"request": request, "files": files}
    )


@router.post("/upload", response_class=HTMLResponse)
async def upload_file(
    request: Request,
    file: UploadFile,
    background_tasks: BackgroundTasks,
):
    templates = request.app.state.templates

    # Validate extension
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        return HTMLResponse(
            f'<div class="text-red-500 p-2">Unsupported file type: {suffix}. '
            f"Allowed: {', '.join(ALLOWED_EXTENSIONS)}</div>"
        )

    # Streamed save — never buffer the whole file in RAM
    dest = settings.upload_dir / file.filename
    with open(dest, "wb") as f:
        while chunk := await file.read(STREAM_CHUNK):
            f.write(chunk)

    # Register job and kick off background ingestion
    job_id = start_ingestion_job(dest)
    background_tasks.add_task(run_ingestion, job_id, dest)

    return templates.TemplateResponse(
        "partials/upload_status.html",
        {"request": request, "job_id": job_id, "job": jobs[job_id]},
    )


@router.get("/status/{job_id}", response_class=HTMLResponse)
async def job_status(request: Request, job_id: str):
    templates = request.app.state.templates
    job = jobs.get(job_id)
    if job is None:
        return HTMLResponse('<div class="text-red-500 p-2">Job not found.</div>')

    return templates.TemplateResponse(
        "partials/upload_status.html",
        {"request": request, "job_id": job_id, "job": job},
    )


@router.delete("/files/{filename}", response_class=HTMLResponse)
async def remove_file(request: Request, filename: str):
    templates = request.app.state.templates
    delete_file(filename)
    files = get_indexed_files()
    return templates.TemplateResponse(
        "partials/file_list.html", {"request": request, "files": files}
    )


@router.get("/files", response_class=HTMLResponse)
async def file_list(request: Request):
    templates = request.app.state.templates
    files = get_indexed_files()
    return templates.TemplateResponse(
        "partials/file_list.html", {"request": request, "files": files}
    )
