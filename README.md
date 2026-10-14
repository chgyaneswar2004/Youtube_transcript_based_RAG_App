# YouTube Q&A Chat

YouTube Q&A Chat is a local web application for asking questions about a YouTube video's captions. The Next.js interface talks to a FastAPI service, which downloads an available transcript, indexes it in a temporary FAISS vector store, retrieves relevant passages, and asks Google Gemini to generate an answer.

## Documentation

The full product, architecture, API, setup, configuration, and troubleshooting guide is in [docs/APP_DOCUMENTATION.md](docs/APP_DOCUMENTATION.md).

## Quick start

You need Node.js/npm, Python 3.11 or compatible, and a Google AI API key with Gemini access.

1. In `RAG/.env`, set `GOOGLE_API_KEY=your-key`.
2. Start the backend from the repository root:

   ```powershell
   cd RAG
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   uvicorn main:app --reload --host 127.0.0.1 --port 8000
   ```

3. In a second terminal, start the frontend:

   ```powershell
   cd First
   npm install
   npm run dev
   ```

4. Open http://localhost:3000.

The frontend uses the fixed backend URL `http://127.0.0.1:8000`. See the full guide for exact API behavior, limitations, and production considerations.

Run the comparative evaluation from `RAG/` with `python evaluation.py`. Set `ANOTHER_API_KEY` in the process environment first. It uses the linked test set to compare 1,000- and 10,000-character chunks and writes `results.json`.

## Top-level layout

- `First/` — Next.js 14 / React client application.
- `RAG/` — FastAPI backend and LangChain RAG pipeline.
- `docs/APP_DOCUMENTATION.md` — full documentation of the current implementation.

