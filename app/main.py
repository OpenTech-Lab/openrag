import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from llama_index.core import Settings as LlamaSettings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.openrouter import OpenRouter

from app.config import settings
from app.routers import chat, upload

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure directories exist on startup
    settings.persist_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    # Set global LlamaIndex defaults so nothing falls back to OpenAI
    LlamaSettings.llm = OpenRouter(
        api_key=settings.openrouter_api_key,
        model=settings.llm_model,
        max_tokens=1024,
    )
    LlamaSettings.embed_model = HuggingFaceEmbedding(
        model_name=settings.embed_model,
    )
    yield


app = FastAPI(title="OpenRAG", lifespan=lifespan)

# Templates
templates = Jinja2Templates(directory="app/templates")
app.state.templates = templates

# Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Routers
app.include_router(upload.router)
app.include_router(chat.router)
