# YouTube Q&A Chat — Application Documentation

**Scope:** This guide describes the code currently in this repository. It distinguishes implemented behavior from features mentioned in older project notes but not present in the source. The application has two independently run processes: a browser UI and a Python API.

## 1. What the app does

The app lets a user load a YouTube video, then ask questions grounded in its available captions. The browser extracts the video's 11-character ID and requests metadata from the backend. The backend fetches a transcript, splits it into overlapping text chunks, embeds those chunks with Google's embedding model, stores vectors in a per-process FAISS index, and prepares a LangChain retrieval-and-generation chain. On each question, the retriever selects up to four relevant chunks and Gemini generates a response. The response is sent as Server-Sent Events (SSE) and progressively displayed in the chat.

The browser persists chat sessions and the selected session in that browser's `localStorage`. Video indexes and backend pipelines live only in Python process memory; they are not durable and are lost when the server restarts.

## 2. Repository map

```text
.
├── README.md                    # Entry point and quick start
├── docs/
│   └── APP_DOCUMENTATION.md     # This guide
├── First/                       # Next.js frontend
│   ├── app/
│   │   ├── page.tsx             # Main page, session state, API calls, streaming
│   │   ├── layout.tsx           # Root document, metadata, theme bootstrap
│   │   ├── globals.css          # CSS variables and global styles
│   │   └── error.tsx            # App-router error boundary UI
│   ├── components/
│   │   ├── sidebar.tsx          # Session list, create/delete, theme control
│   │   ├── video-input.tsx      # URL/video ID parser and load control
│   │   ├── chat-input.tsx       # Question composer
│   │   ├── chat-message.tsx     # Markdown message rendering and copy action
│   │   └── theme-provider.tsx   # Applies saved/system theme on mount
│   ├── package.json             # Scripts and JS dependencies
│   ├── tailwind.config.ts       # Theme tokens and Tailwind content paths
│   ├── postcss.config.js        # Tailwind and Autoprefixer
│   ├── tsconfig.json            # TypeScript aliases/options
│   └── next.config.js           # Next.js configuration
└── RAG/                         # FastAPI / LangChain backend
    ├── main.py                   # HTTP routes, CORS, metadata, process cache
    ├── rag_pipeline.py           # Transcript, chunking, embeddings, retrieval, Gemini
    ├── evaluation.py             # Paired chunk-size evaluation runner
    ├── results.json              # Evaluation output/checkpoint
    ├── youtube_test_videos.md    # Linked 10-video / 50-question evaluation set
    ├── requirements.txt          # Python runtime dependencies
    ├── list.py                   # Utility to list Google generative models
    ├── test_ingest.py            # Manual ingestion diagnostic
    └── test_transcript.py        # Interactive transcript diagnostic
```

`RAG/venv` and Python bytecode are local generated/runtime files, not application source. Do not treat files inside the checked-in/working virtual environment as project modules.

## 3. Runtime architecture

```text
Browser (Next.js :3000)
  ├─ GET http://127.0.0.1:8000/youtube/info?video_id=...
  │     ├─ YouTube oEmbed for title/channel (best effort)
  │     └─ captions → chunks → Google embeddings → in-memory FAISS → chain
  └─ POST http://127.0.0.1:8000/ask {video_id, query}
        └─ retrieve top 4 transcript chunks → Gemini 2.5 Flash → SSE events
```

The frontend directly calls the fixed loopback backend address in `First/app/page.tsx`; there is no Next.js API proxy in this repository. Run the backend on the same machine as the browser, bound to port 8000. The FastAPI CORS middleware currently allows every origin, method, and header. The UI is client-rendered (`'use client'`) and starts with a mount guard to avoid rendering the persisted state before browser APIs are available.

### Question lifecycle

1. `VideoInput` trims its input and accepts supported YouTube URL forms or a bare ID.
2. `handleLoadVideo` requests `/youtube/info`. On success, the current chat stores video ID, title, channel, and thumbnail. A failed request is shown above the input.
3. `GET /youtube/info` validates the ID. It gets title and author name from YouTube oEmbed, falling back to “Unknown” metadata if that request fails. It constructs and ingests a `YouTubeRAGPipeline` if that video is not already cached in this Python process.
4. The user submits a non-empty question. Enter sends; Shift+Enter inserts a newline. The UI appends the user message and posts `{video_id, query}` to `/ask`.
5. `/ask` looks up the already-loaded pipeline and streams `data: {JSON}\n\n` events. The UI reads the response body, parses `data:` lines, and appends each chunk to a new assistant message. The UI also delays each character by 15 ms to create a typing effect.
6. The prompt instructs Gemini to answer only from retrieved transcript context and to say it does not know when the context is insufficient.

## 4. Frontend behavior

### Page state and persistence

`First/app/page.tsx` owns a map of `ChatState` objects and the active chat ID. A chat state contains:

| Field | Meaning |
| --- | --- |
| `id` | Millisecond timestamp string used as the session ID and ordering key. |
| `video_id` | YouTube ID loaded in this session, or `null`. |
| `videoTitle` | Display title returned by the API, or `null`. |
| `channel_name` | Channel/author label, or `null`. |
| `thumbnail` | YouTube thumbnail URL, or `null`. |
| `messages` | Ordered `{id, role, content}` user/assistant messages. |

The complete chat map is serialized to `localStorage` key `yt-rag-chats`; the selected ID is stored under `yt-rag-current-chat`. On startup, if the active ID is absent, the page chooses the numerically latest chat ID or creates a blank chat. These values are local to one browser profile and do not sync to the backend or another device. The `theme` preference is stored separately by the sidebar.

### Session controls

- **New Chat** creates an empty session and selects it.
- Selecting an item in the sidebar switches to that session.
- Chat names are the video title, otherwise the first user message truncated to 40 characters, otherwise “New Chat”.
- Delete asks for confirmation, removes the session, and selects the newest remaining session. Deleting the final session causes a new blank session to be created.
- **Clear Chat** asks for confirmation, clears the messages and video metadata for the active session. This is different from deleting a single sidebar session.
- Sidebar sessions sort newest-first by their timestamp ID.

### Video input

`First/components/video-input.tsx` recognizes these forms:

- `youtube.com/watch?v=VIDEO_ID`
- `youtu.be/VIDEO_ID`
- `youtube.com/embed/VIDEO_ID`
- `youtube.com/shorts/VIDEO_ID`
- A bare 11-character ID using letters, digits, `_`, or `-`.

It does local format extraction only. Existence, caption availability, and metadata are checked by the backend. The input is cleared after a successful backend response and kept after a failure. Pressing Enter triggers loading. Invalid input uses a browser alert.

### Chat and message display

`ChatInput` disallows empty/whitespace-only submissions and disables itself during a response. Its textarea grows up to 120 px. `ChatMessage` renders message text using `react-markdown`; assistant messages include a clipboard copy button. A loading indicator is shown while the request is in progress. The page only auto-scrolls when the message container was already within 150 px of the bottom.

### Theme and styling

The root layout's inline script applies a saved `theme` or the system dark-mode preference before rendering. `ThemeProvider` applies it again on mount. The sidebar toggles the `dark` class on `<html>` and persists `theme=dark|light`. `First/app/globals.css` defines CSS HSL tokens; Tailwind maps those tokens into semantic color names. Dark mode is class-based. Framer Motion supplies entry/exit and hover animations; Lucide React supplies icons.

## 5. Backend API reference

Base URL used by the frontend: `http://127.0.0.1:8000`.

### `GET /youtube/info`

Loads video information and ensures the transcript index exists for the current backend process.

**Query parameter**

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `video_id` | string | yes | Exactly 11 characters from `[A-Za-z0-9_-]`. |

**Successful response (`200`)**

```json
{
  "video_id": "dQw4w9WgXcQ",
  "title": "Example title",
  "channel_name": "Example channel",
  "thumbnail": "https://img.youtube.com/vi/dQw4w9WgXcQ/maxresdefault.jpg"
}
```

The thumbnail is constructed from the ID. Title/channel use `https://www.youtube.com/oembed`; an oEmbed failure does not prevent ingestion and returns fallback strings. A video is ingested only once per process, keyed by video ID.

**Failures:** `400` for malformed IDs; `422` if pipeline ingestion raises `RuntimeError` (for example, no captions); `500` for other ingestion errors. FastAPI validation may also return `422` when the parameter is missing or has the wrong type.

### `POST /ask`

Streams an answer for a previously loaded video.

**Request body**

```json
{
  "video_id": "dQw4w9WgXcQ",
  "query": "What is the main point?"
}
```

Both fields are strings. Blank queries are rejected after trimming. The route returns `text/event-stream`; an answer is represented by repeated SSE data records, for example:

```text
data: {"chunk":"The video"}

data: {"chunk":" explains ..."}

data: {"chunk":"","done":true}

```

Each event's `data:` payload is JSON. Normal events have a `chunk` string. The final event has `done: true`. If generation raises after streaming starts, the server emits a chunk with `error: true` containing an error string, then emits the done event. Because headers have already been sent, that generation failure is represented in-band rather than as a new HTTP status.

**Failures before stream start:** `400` for empty query; `404` if that video is not loaded in this process; FastAPI `422` for invalid/missing request fields.

### Interactive API docs

FastAPI's default docs should be available at `http://127.0.0.1:8000/docs` while the backend runs. `/openapi.json` exposes the generated schema.

## 6. RAG and model details

Implementation: `RAG/rag_pipeline.py`.

1. **Transcript retrieval:** `YouTubeTranscriptApi.fetch` tries languages in this order: English (`en`), Hindi (`hi`), English India (`en-IN`), then any available language. It joins caption segment text with spaces. If every attempt fails, it raises a runtime error that the API maps to 422.
2. **Chunking:** `RecursiveCharacterTextSplitter` splits the joined transcript into chunks of 10,000 characters with 1,000 characters overlap in the normal app. The overlap preserves context across boundaries. `YouTubeRAGPipeline` also accepts chunk size, overlap, temperature, and prompt settings; defaults preserve the app's current configuration.
3. **Embeddings:** `GoogleGenerativeAIEmbeddings` uses `models/gemini-embedding-001`. `SafeGoogleEmbeddings` batches document embeddings in groups of 25, waits 5 seconds between batches, and retries quota-like failures up to five attempts with increasing backoff (10, 20, 30, 40 seconds between retries).
4. **Vector index:** `FAISS.from_documents` creates a local in-memory index. The retriever uses similarity search and returns the top four chunks.
5. **Prompt and model:** A LangChain `RunnableParallel` retrieves/formats context while passing through the question. The prompt instructs the assistant to use only transcript excerpts, avoid outside facts or guesses, answer directly, and state what cannot be determined. It feeds `models/gemini-2.5-flash` at temperature `0.2`; `StrOutputParser` yields plain text.
6. **Streaming:** `YouTubeRAGPipeline.stream` yields LangChain output fragments. The FastAPI endpoint wraps each in an SSE event.

The implementation does not attach source timestamps or citations to chunks, persist FAISS indexes, or expose a transcript endpoint. `query()` can return answer and source chunk strings to Python callers, but the HTTP API currently uses `stream()` and sends only generated text.

## 7. Evaluation harness and current findings

`RAG/evaluation.py` reads `RAG/youtube_test_videos.md`, extracts linked video IDs and their five questions, fetches each transcript once, and builds two indexes from that transcript. It compares **1,000-character chunks with 10,000-character chunks**, holding overlap constant at 200 characters so chunk size is the only retrieval configuration changed. Both use the same embedding model, `gemini-2.5-flash`, temperature `0.2`, and grounded-answer prompt. Normal app defaults remain 10,000/1,000.

For each question, the runner stores both answers, retrieved source chunks and latency, plus a Gemini pairwise judgment. The judge scores faithfulness, coverage, and directness from 0 to 4 and selects 1,000, 10,000, or tie. It uses temperature 0 and receives at most 12,000 characters of source excerpts per answer. These model-based preferences are estimates, not human-verified ground truth.

Run from `RAG/` after making `ANOTHER_API_KEY` available in the process environment. The evaluation script uses this variable directly and does not load `.env`; the backend app itself continues to use `GOOGLE_API_KEY` as documented below.

```powershell
python evaluation.py
```

The default output/checkpoint is `RAG/results.json`. `--video-limit 1` limits a diagnostic run, `--skip-judge` omits pairwise scoring, `--output PATH` chooses another file, and `--fresh` starts over. The runner checkpoints after each question and resumes incomplete output when the saved settings match. Gemini calls are paced at 13 seconds to stay under the observed free-tier request rate; a daily quota limit stops the run and leaves a checkpoint. Rerun after quota resets or when using a project with available quota. This evaluation makes many more model calls than ordinary app use and can take substantial time.

### Recorded evaluation results

`RAG/results.json` contains **45 valid paired question comparisons out of 50**. The original five used Gemini 2.5 Flash; the following forty used `models/gemini-3.5-flash-lite`. For every evaluated question, both chunk-size answers used the same model. Both variants use 200-character overlap, temperature 0.2, and the same grounded-answer prompt.

| Batch | Model | 1,000-character wins | 10,000-character wins | Ties | Questions |
|---|---|---:|---:|---:|---:|
| Previous five | Gemini 2.5 Flash | 2 | 2 | 1 | 5 |
| Next five evaluable | Gemini 3.5 Flash Lite | 1 | 1 | 3 | 5 |
| Following five | Gemini 3.5 Flash Lite | 2 | 1 | 2 | 5 |
| RAG tutorial five | Gemini 3.5 Flash Lite | 0 | 3 | 2 | 5 |
| Coronavirus video five | Gemini 3.5 Flash Lite | 0 | 0 | 5 | 5 |
| Vaccine video five | Gemini 3.5 Flash Lite | 1 | 2 | 2 | 5 |
| Antibiotic video five | Gemini 3.5 Flash Lite | 1 | 1 | 3 | 5 |
| Immune-system video five | Gemini 3.5 Flash Lite | 2 | 2 | 1 | 5 |
| Virus video five | Gemini 3.5 Flash Lite | 1 | 1 | 3 | 5 |
| **Combined** | Mixed across batches | **10** | **13** | **22** | **45** |

The result is close, with 22 ties; it does not establish that either chunk size is better. Five questions for video `5sLYAQS9sWQ` could not be evaluated because no transcript is available. The remaining 45 questions have valid paired answers and judgments.

Gemini 2.5 Flash Lite returned HTTP 404 for the supplied key. The API recommended Gemini 3.5 Flash Lite, which successfully generated the answer pairs and judgments. To resume the checkpoint with that model, set `ANOTHER_API_KEY` and `RAG_EVAL_MODEL=models/gemini-3.5-flash-lite` in the process environment, then run `python evaluation.py` from `RAG/`. The runner resumes saved rows when chunk settings match; `--new-question-limit 5` caps each run at five newly completed comparisons. Do not treat model-based preferences as human-verified ground truth. The earlier uncontrolled pilot is preserved as `RAG/results_pilot.json`.

## 8. Setup and operation

### Prerequisites

- Node.js and npm compatible with the installed Next.js 14 project.
- Python 3.11 is the version indicated by the local environment's bytecode, but no explicit Python version constraint is declared. Use a version supported by the pinned libraries and FAISS wheel for your OS.
- A Google AI API key enabled for Gemini embedding and generation.
- Network access from the backend to YouTube transcript/oEmbed endpoints and Google AI services.

### Configure the backend

Create `RAG/.env` (or provide `GOOGLE_API_KEY` in the backend process environment):

```dotenv
GOOGLE_API_KEY=your-google-ai-api-key
```

`load_dotenv()` is called by `RAG/main.py`, loading `.env` from the backend's working directory. Start Uvicorn with `RAG` as the working directory so the module imports and `.env` discovery are predictable.

### Install and run (PowerShell)

Backend terminal:

```powershell
cd RAG
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Frontend terminal:

```powershell
cd First
npm install
npm run dev
```

Open `http://localhost:3000`. For a production frontend, run `npm run build` then `npm start` from `First/`. The backend has no production deployment configuration in this repository; run it with an appropriate ASGI server command and configure network/CORS/security for the deployment environment.

### Python dependencies

`RAG/requirements.txt` pins FastAPI, Uvicorn, HTTPX, LangChain packages, Google Generative AI integrations, YouTube Transcript API, FAISS CPU, python-dotenv, and tiktoken. `RAG/evaluation.py` is an API-backed evaluation harness requiring network access and Gemini quota. `RAG/test_ingest.py` and `RAG/test_transcript.py` are manual diagnostic scripts, not a pytest suite. `RAG/list.py` calls Google Generative AI to print available models. These utilities also need `GOOGLE_API_KEY` where applicable.

## 9. Frontend dependencies and scripts

The frontend package is named `youtube-qa-chat` version `0.1.0` and is private. Runtime dependencies include Next.js 14, React 18, Axios, Framer Motion, Lucide React, and React Markdown. (The current page uses browser `fetch`; Axios is present but not used in the inspected application code.) Development dependencies include TypeScript, Tailwind CSS, PostCSS, and type packages.

| Command | Effect |
| --- | --- |
| `npm run dev` | Starts the Next.js development server. |
| `npm run build` | Builds the Next.js app for production. |
| `npm start` | Serves a previously built Next.js app. |
| `npm run lint` | Runs the declared `next lint` script; confirm compatibility with the installed Next.js CLI/version when using it. |

TypeScript uses strict checking, no emit, bundler module resolution, and the `@/*` alias mapped to the `First/` root.

## 10. Configuration and environment variables

| Variable | Used by | Required | Notes |
| --- | --- | --- | --- |
| `GOOGLE_API_KEY` | Backend API | yes for actual ingestion/answers | Read when `rag_pipeline.py` is imported; set it before starting the backend process. |
| `ANOTHER_API_KEY` | `RAG/evaluation.py` | yes for evaluation | Read from the process environment only; the evaluation script maps it internally to the Google client key name and never loads `.env`. |
| `CURL_CA_BUNDLE`, `REQUESTS_CA_BUNDLE` | Backend process | no | Both are unconditionally removed by `main.py` and `rag_pipeline.py` to avoid invalid local certificate paths. This changes TLS configuration behavior for the backend process. |

The frontend currently hardcodes `http://127.0.0.1:8000` in its fetch calls. `NEXT_PUBLIC_API_URL` and YouTube/OpenAI/Pinecone variables mentioned by the old `First/README.md` are not read by the current implementation. There is no `.env.example` in the source tree. Do not put a Google key in a `NEXT_PUBLIC_*` variable or frontend source.

## 11. Error handling and troubleshooting

| Symptom | Likely cause / action |
| --- | --- |
| Browser reports a network/server error while loading | Start FastAPI at `127.0.0.1:8000`; check its console. The UI URL is hardcoded. |
| `422` on video load mentioning no transcript | The video has captions unavailable to the transcript library, or the service could not fetch them. Try a video with accessible captions. |
| Google API key error on backend startup | Set `GOOGLE_API_KEY` in `RAG/.env` or the process environment before import/start. |
| Ingestion is slow or returns quota errors | Transcript embedding may involve multiple API calls; quota-like errors are retried with backoff. Check Google API quota and logs. |
| Evaluation stops before all questions complete | Check `RAG/results.json` for per-question errors. Gemini's free-tier daily quota can stop generation/judging; wait for reset or use a project with available quota, then rerun `python evaluation.py` to resume. |
| `404` when asking | Load the video against the same running backend process first. The pipeline cache is in memory and is not shared across workers or restarts. |
| Title/channel show “Unknown” but video loads | YouTube oEmbed failed; metadata fallback is intentional. Transcript ingestion can still succeed. |
| Browser cannot reach backend due to CORS | Current backend allows all origins; if deployment CORS is tightened, include the UI origin. |
| Sidebar data is missing on another browser/device | Chats are stored only in that browser's `localStorage`. |
| Backend restarted and previous video must be loaded again | Expected: indexes are process-local and not persisted. |

The UI's streaming decoder splits decoded byte chunks by newline without carrying an incomplete trailing line over to the next read. Most responses work, but an SSE event split across network chunks could be skipped or parsed later as malformed data. The frontend also treats all non-2xx chat responses generically and does not surface backend detail for `/ask`.

## 12. Security, privacy, and deployment boundaries

- The Google API key belongs only in the backend environment.
- Chat history and video metadata are stored unencrypted in browser `localStorage`; anyone using the same browser profile can access them.
- The backend retains transcripts, vector indexes, model objects, and pipeline references in process memory for every distinct video loaded. There is no eviction policy, persistence, authentication, per-user isolation, or rate limiting.
- CORS is unrestricted (`*`) in the current code. Tighten it to known origins before exposing the API publicly.
- The backend API has no authentication. Do not expose it to an untrusted network as-is.
- User questions and retrieved transcript context are sent to Google's Gemini service for answer generation; chunks are also sent to Google's embedding service during ingestion.
- A request to `/youtube/info` can cause external transcript and model API calls and incur latency/quota usage.
- `RAG/evaluation.py` makes substantially more model calls than normal app use: two answers and a judge comparison per question.
- Thumbnail image requests go directly from the browser to `img.youtube.com`.
- `main.py` and `rag_pipeline.py` remove `CURL_CA_BUNDLE` and `REQUESTS_CA_BUNDLE` from the process environment. Review this behavior for environments relying on custom certificate authorities.

## 13. Current limitations and non-features

These are not implemented in the current source, even if they appear in the older `First/README.md`:

- No Next.js `/api/load-video` or `/api/chat` routes; the app talks directly to FastAPI.
- No OpenAI/Gemini provider selection; the code uses Google Gemini.
- No persistent database or server-side chat history.
- No accounts, authentication, multi-user permissions, or conversation sharing.
- No transcript cache or durable FAISS/vector database; only a Python process dictionary cache exists.
- No timestamps, citations, source highlighting, transcript browser, or exported chat.
- No server-side streaming through Next.js; the browser consumes the FastAPI SSE body directly.
- No configurable backend URL in frontend environment variables.
- No automated unit/integration test suite is supplied. An API-backed comparative evaluation harness exists, but its current results are incomplete and are not ground truth.

## 14. File-by-file reference

### Frontend

- `First/app/page.tsx` — defines `Message` and exported `ChatState`, manages browser state and persistence, calls `/youtube/info` and `/ask`, parses SSE, handles session lifecycle, displays loaded video and chat UI.
- `First/app/layout.tsx` — imports global styles, exports page metadata and viewport settings, applies an early theme class, and wraps content in `ThemeProvider`.
- `First/app/error.tsx` — client error boundary screen; logs the caught error and offers retry/reset and home navigation.
- `First/app/globals.css` — Tailwind directives, light/dark CSS variables, base borders, smooth scrolling, and scrollbar styling.
- `First/components/video-input.tsx` — video URL parser, validation feedback, load state and Enter-key handling.
- `First/components/chat-input.tsx` — controlled growing textarea, Enter/Shift+Enter behavior, and disabled/loading send button.
- `First/components/chat-message.tsx` — animated user/assistant bubbles, Markdown formatting, loading dots, and copy-to-clipboard action.
- `First/components/sidebar.tsx` — session navigation, derived labels, delete confirmations, and theme toggle.
- `First/components/theme-provider.tsx` — applies persisted/system theme after mount. Theme state is not managed through React context.
- `First/next.config.js` — enables React strict mode.
- `First/tailwind.config.ts` — scans app/components, defines semantic CSS-token colors and class dark mode.
- `First/postcss.config.js` — registers Tailwind and Autoprefixer.
- `First/tsconfig.json` — strict TypeScript setup and `@/` root alias.

### Backend

- `RAG/main.py` — creates FastAPI app metadata, wildcard CORS middleware, Pydantic request/response schemas, best-effort oEmbed metadata lookup, `GET /youtube/info`, `POST /ask`, and the in-memory video-to-pipeline dictionary.
- `RAG/rag_pipeline.py` — validates presence of `GOOGLE_API_KEY` on import, wraps Google embedding calls with quota retry/backoff, fetches captions, chunks text, builds FAISS retrieval, configures Gemini prompt/model, and supports full or streamed answers.
- `RAG/evaluation.py` — parses the linked question set, builds same-transcript indexes at two fixed-overlap chunk sizes, records answers/retrievals/latencies, asks Gemini for pairwise rubric judgments, rate-limits calls, and checkpoints `results.json`.
- `RAG/results.json` — machine-readable controlled evaluation output; currently incomplete, as described above.
- `RAG/results_pilot.json` — preserved pilot from the earlier run with different overlap settings.
- `RAG/youtube_test_videos.md` — ten linked videos and fifty evaluation questions.
- `RAG/list.py` — prints available Google generative model IDs/methods using `google.generativeai`.
- `RAG/test_ingest.py` — runs ingestion for a hard-coded sample video ID and prints success if complete.
- `RAG/test_transcript.py` — interactively asks for a video ID and prints transcript fetch status/preview plus available transcript languages.
- `RAG/requirements.txt` — dependency pins/ranges for the backend.

## 15. Suggested maintenance checklist

When changing this application, keep the endpoint payloads in `First/app/page.tsx` and `RAG/main.py` aligned; retain a final SSE event or update the client parser; update this guide when routes, storage, models, prompts, or configuration change; keep overlap fixed when isolating chunk size in an evaluation; keep secrets on the backend; and revisit CORS, authentication, resource limits, and persistence before public deployment.

