# -*- coding: utf-8 -*-
"""
rag_pipeline.py

Structure mirrors the original notebook exactly:
  Step 1a – Transcript ingestion
  Step 1b – Text splitting
  Step 1c – Embedding generation
  Step 1d – FAISS vector store
  Step 2  – Retrieval
  Step 3  – Augmentation (PromptTemplate)
  Step 4  – Generation (Gemini)
  Chain   – RunnableParallel → prompt → LLM → StrOutputParser

Extra: .stream() method yields tokens for SSE streaming.
"""

import os
# Clear SSL certificate bundle env vars if they point to non-existent paths on the local system
os.environ.pop("CURL_CA_BUNDLE", None)
os.environ.pop("REQUESTS_CA_BUNDLE", None)

from typing import Iterator

# youtube-transcript-api >= 1.0 changed the API:
#   - FetchedTranscript is iterable, each item has .text
#   - Errors moved to youtube_transcript_api._errors
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import GenericProxyConfig

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableParallel, RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser


# ── API key ───────────────────────────────────────────────────────────────────

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
if not GOOGLE_API_KEY:
    raise EnvironmentError(
        "GOOGLE_API_KEY is not set.\n"
        "  Add GOOGLE_API_KEY=your-key to your .env file."
    )


# ── Pipeline ──────────────────────────────────────────────────────────────────

import time

class SafeGoogleEmbeddings(GoogleGenerativeAIEmbeddings):
    """
    Wrapper for GoogleGenerativeAIEmbeddings that handles the 100 requests-per-minute
    rate limit on the free tier by batching requests and adding retries with exponential backoff.
    """
    def embed_documents(self, texts: list[str], **kwargs) -> list[list[float]]:
        # Use a batch size of 25 and a 5-second sleep to pace requests below the 100 RPM quota
        batch_size = 25
        embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            retries = 5
            backoff = 10
            while retries > 0:
                try:
                    batch_embeddings = super().embed_documents(batch, **kwargs)
                    embeddings.extend(batch_embeddings)
                    break
                except Exception as e:
                    err_msg = str(e).lower()
                    if "429" in err_msg or "quota" in err_msg or "resource" in err_msg:
                        retries -= 1
                        if retries == 0:
                            raise e
                        time.sleep(backoff)
                        backoff += 10
                    else:
                        raise e
            if i + batch_size < len(texts):
                time.sleep(5.0)
        return embeddings


class YouTubeRAGPipeline:
    """
    One instance = one video's complete RAG pipeline.

    Public attributes after ingest():
        .transcript   str  – full raw transcript text
        .chunk_count  int  – number of FAISS-stored chunks
    """

    EMBED_MODEL = "models/gemini-embedding-001"
    CHAT_MODEL  = "models/gemini-2.5-flash"
    CHUNK_SIZE    = 10000
    CHUNK_OVERLAP = 1000
    TOP_K         = 4

    DEFAULT_PROMPT = """You are a careful assistant answering questions about a YouTube video.
Use only the transcript excerpts below as evidence. Do not add outside facts or guess.
Answer the question directly and include the relevant details present in the excerpts.
If the excerpts do not contain enough evidence, say what cannot be determined from the transcript.

Transcript excerpts:
{context}

Question: {question}
Answer:"""

    def __init__(self, chunk_size: int = CHUNK_SIZE, chunk_overlap: int | None = None,
                 temperature: float = 0.2, prompt_template: str = DEFAULT_PROMPT):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be a positive integer")
        resolved_overlap = min(self.CHUNK_OVERLAP, chunk_size - 1) if chunk_overlap is None else chunk_overlap
        if resolved_overlap < 0 or resolved_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be >= 0 and less than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = resolved_overlap
        self.temperature = temperature
        self.prompt_template = prompt_template
        self.transcript:  str = ""
        self.chunk_count: int = 0
        self._retriever       = None
        self._chain           = None

        self._embeddings = SafeGoogleEmbeddings(
            model=self.EMBED_MODEL,
            google_api_key=GOOGLE_API_KEY,
        )
        self._llm = ChatGoogleGenerativeAI(
            model=self.CHAT_MODEL,
            temperature=self.temperature,
            google_api_key=GOOGLE_API_KEY,
        )

    # ── Step 1a – Document ingestion ─────────────────────────────────────────

    def _fetch_transcript(self, video_id: str) -> str:
        http_proxy = os.getenv("YOUTUBE_TRANSCRIPT_HTTP_PROXY")
        https_proxy = os.getenv("YOUTUBE_TRANSCRIPT_HTTPS_PROXY")
        proxy_config = (
            GenericProxyConfig(http_url=http_proxy, https_url=https_proxy)
            if http_proxy or https_proxy
            else None
        )
        ytt = YouTubeTranscriptApi(proxy_config=proxy_config)
        last_error: Exception | None = None

        # Try English first, then Hindi, then any available language
        for lang in [["en"], ["hi"], ["en-IN"]]:
            try:
                fetched = ytt.fetch(video_id, languages=lang)
                return " ".join(s.text for s in fetched)
            except Exception as exc:
                last_error = exc
                continue

        # Last resort: fetch whatever language is available without specifying
        try:
            fetched = ytt.fetch(video_id)
            return " ".join(s.text for s in fetched)
        except Exception as exc:
            last_error = exc

        if last_error is not None:
            raise RuntimeError(
                f"Transcript fetch failed for video '{video_id}'. "
                f"Last error: {type(last_error).__name__}: {last_error}"
            ) from last_error
        raise RuntimeError(f"No transcript available for video '{video_id}'.")

    # ── Step 1b – Text splitting ──────────────────────────────────────────────

    def _split_text(self, transcript: str):
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )
        return splitter.create_documents([transcript])

    # ── Steps 1c & 1d – Embedding + FAISS ────────────────────────────────────

    def _build_vector_store(self, chunks):
        vector_store = FAISS.from_documents(chunks, self._embeddings)
        self._retriever = vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": self.TOP_K},
        )

    # ── Steps 3 & 4 + Chain ───────────────────────────────────────────────────

    def _build_chain(self):
        prompt = PromptTemplate(
            template=self.prompt_template,
            input_variables=["context", "question"],
        )

        def format_docs(retrieved_docs):
            return "\n\n".join(doc.page_content for doc in retrieved_docs)

        parallel_chain = RunnableParallel({
            "context":  self._retriever | RunnableLambda(format_docs),
            "question": RunnablePassthrough(),
        })

        self._chain = parallel_chain | prompt | self._llm | StrOutputParser()

    # ── Public API ────────────────────────────────────────────────────────────

    def ingest(self, video_id: str) -> None:
        """Full ingestion pipeline. Populates .transcript and .chunk_count."""
        self.ingest_transcript(self._fetch_transcript(video_id))

    def ingest_transcript(self, transcript: str) -> None:
        """Build the index from supplied transcript text (also used by evaluations)."""
        if not transcript.strip():
            raise RuntimeError("Transcript is empty.")
        self.transcript  = transcript
        chunks           = self._split_text(self.transcript)
        self.chunk_count = len(chunks)
        self._build_vector_store(chunks)
        self._build_chain()

    def query(self, question: str) -> dict:
        """Non-streaming query. Returns full answer + source chunks."""
        if self._chain is None:
            raise RuntimeError("Pipeline not ready. Call ingest() first.")
        answer      = self._chain.invoke(question)
        source_docs = self._retriever.invoke(question)
        return {
            "answer":        answer,
            "source_chunks": [doc.page_content for doc in source_docs],
        }

    def stream(self, question: str) -> Iterator[str]:
        """Streaming query — yields tokens one-by-one for SSE."""
        if self._chain is None:
            raise RuntimeError("Pipeline not ready. Call ingest() first.")
        for token in self._chain.stream(question):
            yield token
