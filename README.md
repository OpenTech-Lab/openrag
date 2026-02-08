# OpenRAG

A high-capacity Document Intelligence Platform for indexing and querying large-scale datasets (multi-GB, thousands of PDF/Excel files). Built with LlamaIndex, FastAPI, and htmx.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  htmx UI    │────▶│  FastAPI      │────▶│  LlamaIndex     │
│  (Tailwind) │◀────│  (async)      │◀────│  Ingestion +    │
└─────────────┘     └──────┬───────┘     │  Query Engine   │
                           │              └────────┬────────┘
                           │                       │
                    ┌──────▼───────┐        ┌──────▼────────┐
                    │  Background  │        │  ChromaDB     │
                    │  Tasks       │        │  (persistent) │
                    └──────────────┘        └───────────────┘
```

## Tech Stack

| Layer          | Technology                                |
|----------------|-------------------------------------------|
| Backend        | Python 3.12, FastAPI                      |
| RAG Framework  | LlamaIndex                                |
| LLM            | OpenRouter (any model)                    |
| Embeddings     | HuggingFace (local, free)                 |
| Frontend       | HTML5, Tailwind CSS, htmx                 |
| Vector DB      | ChromaDB (on-disk persistence)            |
| Task Queue     | FastAPI BackgroundTasks                   |

## Features

- **Streamed Uploads** -- multi-GB file ingestion without loading entire files into RAM
- **Background Indexing** -- async job processing with htmx polling for real-time status updates
- **Batch Processing** -- LlamaIndex IngestionPipeline with batching to prevent rate limiting and memory spikes
- **Granular Metadata** -- every chunk includes `file_name`, `page_number`, and `sheet_name`
- **Persistent Vector Store** -- no re-indexing on server restart
- **Source Citations** -- answers cite exact page numbers and Excel sheet names

## Prerequisites

- Python 3.12 (recommended via [mise](https://mise.jdx.dev/))
- An [OpenRouter](https://openrouter.ai/) API key

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/your-org/openrag.git
cd openrag
```

### 2. Set up Python 3.12 (via mise)

```bash
mise use python@3.12
```

### 3. Create and activate a virtual environment

```bash
python -m venv venv
source venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and set your API key:

```
OPENROUTER_API_KEY=sk-or-...
LLM_MODEL=meta-llama/llama-3.3-70b-instruct
EMBED_MODEL=BAAI/bge-small-en-v1.5
PERSIST_DIR=./storage
UPLOAD_DIR=./uploads
CHUNK_SIZE=1024
CHUNK_OVERLAP=50
```

### 6. Run the server

```bash
uvicorn app.main:app --reload
```

The application will be available at `http://localhost:8000`.

## Project Structure

```
openrag/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Pydantic Settings from .env
│   ├── routers/
│   │   ├── upload.py        # File upload + status polling endpoints
│   │   └── chat.py          # Chat page + query endpoints
│   ├── services/
│   │   ├── ingestion.py     # LlamaIndex ingestion pipeline + ChromaDB
│   │   └── query.py         # RAG query engine wrapper
│   ├── templates/
│   │   ├── base.html        # Base layout (Tailwind + htmx)
│   │   ├── index.html       # Upload dashboard
│   │   ├── chat.html        # Chat interface
│   │   └── partials/        # htmx partial templates
│   └── static/
│       └── css/
├── storage/                 # ChromaDB persistence (gitignored)
├── uploads/                 # Uploaded files staging (gitignored)
├── requirements.txt
├── .env.example
├── LICENSE
└── README.md
```

## Usage

### Upload Documents

1. Open the dashboard at `http://localhost:8000`
2. Select a PDF or Excel file and click "Upload & Index"
3. The UI polls for indexing progress automatically via htmx

### Query Documents

1. Navigate to the Chat tab
2. Ask questions about your uploaded documents
3. Responses include source citations with page numbers and sheet names

## Development

```bash
source venv/bin/activate
uvicorn app.main:app --reload
```

## License

MIT License. See [LICENSE](LICENSE) for details.
