from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openrouter_api_key: str = ""
    llm_model: str = "meta-llama/llama-3.3-70b-instruct"
    embed_model: str = "BAAI/bge-small-en-v1.5"
    persist_dir: Path = Path("./storage")
    upload_dir: Path = Path("./uploads")
    chunk_size: int = 1024
    chunk_overlap: int = 50

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
