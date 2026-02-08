from __future__ import annotations

import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.services.query import query_documents

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse("chat.html", {"request": request})


@router.post("/chat", response_class=HTMLResponse)
async def chat_send(request: Request, message: str = Form(...)):
    templates = request.app.state.templates

    try:
        result = query_documents(message)
        return templates.TemplateResponse(
            "partials/chat_message.html",
            {
                "request": request,
                "user_message": message,
                "ai_message": result.answer,
                "sources": result.sources,
                "error": None,
            },
        )
    except Exception as exc:
        logger.exception("Chat query failed")
        return templates.TemplateResponse(
            "partials/chat_message.html",
            {
                "request": request,
                "user_message": message,
                "ai_message": "",
                "sources": [],
                "error": str(exc),
            },
        )
