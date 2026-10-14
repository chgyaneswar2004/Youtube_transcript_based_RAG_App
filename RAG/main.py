# -*- coding: utf-8 -*-
"""
main.py  –  YouTube RAG Backend
Endpoints:
  GET  /youtube/info?video_id=XXX  →  video metadata + builds RAG knowledge base
  POST /ask                        →  SSE streaming RAG answer
"""

import os
# Clear SSL certificate bundle env vars if they point to non-existent paths on the local system
os.environ.pop("CURL_CA_BUNDLE", None)
os.environ.pop("REQUESTS_CA_BUNDLE", None)

import re
import json
from dotenv import load_dotenv

load_dotenv()  # loads GOOGLE_API_KEY from .env automatically

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from rag_pipeline import YouTubeRAGPipeline


# ── In-memory store: video_id → pipeline ─────────────────────────────────────
pipeline_store: dict[str, YouTubeRAGPipeline] = {}


# ── Schemas ───────────────────────────────────────────────────────────────────

class VideoResponse(BaseModel):
    video_id:     str
    title:        str
    channel_name: str
    thumbnail:    str

class AskRequest(BaseModel):
    video_id: str
    query:    str


# ── Helpers ───────────────────────────────────────────────────────────────────

def fetch_video_metadata(video_id: str) -> dict:
    """
    Fetches title + channel name via YouTube oEmbed (no API key needed).
    oEmbed returns: title, author_name (channel), thumbnail_url.
    Falls back to safe defaults on any failure.
    """
    try:
        resp = httpx.get(
            "https://www.youtube.com/oembed",
            params={"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"},
            timeout=8,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "title":        data.get("title", "Unknown Title"),
                "channel_name": data.get("author_name", "Unknown Channel"),
                "thumbnail":    f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
            }
    except Exception:
        pass

    return {
        "title":        "Unknown Title",
        "channel_name": "Unknown Channel",
        "thumbnail":    f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
    }


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="YouTube RAG API",
    description="Load a YouTube video, then stream answers via RAG.",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Endpoint 1 ────────────────────────────────────────────────────────────────
# GET /youtube/info?video_id=<11-char-id>

@app.get(
    "/youtube/info",
    response_model=VideoResponse,
    summary="Fetch video details and build RAG knowledge base",
)
def get_video_info(video_id: str = Query(..., description="YouTube video ID (11 chars)")):
    video_id = video_id.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        raise HTTPException(status_code=400, detail=f"Invalid YouTube video ID: {video_id!r}")

    meta = fetch_video_metadata(video_id)

    if video_id not in pipeline_store:
        try:
            pipeline = YouTubeRAGPipeline()
            pipeline.ingest(video_id)
            pipeline_store[video_id] = pipeline
        except RuntimeError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")

    return VideoResponse(
        video_id=video_id,
        title=meta["title"],
        channel_name=meta["channel_name"],
        thumbnail=meta["thumbnail"],
    )


# ── Endpoint 2 ────────────────────────────────────────────────────────────────
# POST /ask  →  SSE stream

@app.post("/ask", summary="Ask a question — streams answer as SSE")
def ask(req: AskRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    pipeline = pipeline_store.get(req.video_id)
    if pipeline is None:
        raise HTTPException(
            status_code=404,
            detail=f"Video '{req.video_id}' not loaded. Call GET /youtube/info first.",
        )

    def event_stream():
        try:
            for token in pipeline.stream(req.query):
                yield f"data: {json.dumps({'chunk': token})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'chunk': f'[Error: {e}]', 'error': True})}\n\n"
        finally:
            yield f"data: {json.dumps({'chunk': '', 'done': True})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
        },
    )