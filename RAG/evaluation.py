"""Run the YouTube RAG test set at multiple chunk sizes and save results.json.

Run from the RAG directory: python evaluation.py
Optional: python evaluation.py --video-limit 1 --skip-judge
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
API_KEY = os.environ.get("ANOTHER_API_KEY")
if not API_KEY:
    print("ANOTHER_API_KEY is not set in this process environment; evaluation cannot resume.", file=sys.stderr)
    raise SystemExit(2)
os.environ["GOOGLE_API_KEY"] = API_KEY

from langchain_google_genai import ChatGoogleGenerativeAI  # noqa: E402
from rag_pipeline import YouTubeRAGPipeline  # noqa: E402
from youtube_transcript_api import YouTubeTranscriptApi  # noqa: E402

# The evaluation model can move independently of the production app's default.
EVAL_MODEL = os.getenv("RAG_EVAL_MODEL", "models/gemini-2.5-flash")
YouTubeRAGPipeline.CHAT_MODEL = EVAL_MODEL

TEST_SET = ROOT / "youtube_test_videos.md"
RESULTS_FILE = ROOT / "results.json"
CHUNK_SIZES = (1000, 10000)
CHUNK_OVERLAPS = (200, 200)  # fixed to isolate chunk-size effects
TEMPERATURE = 0.2
MIN_MODEL_CALL_INTERVAL_SECONDS = 13.0
_last_model_call = 0.0
_daily_quota_exhausted = False

JUDGE_PROMPT = """You are evaluating two answers to a question about a video transcript.
Judge only from the supplied retrieved transcript excerpts. Do not reward outside knowledge.
Score each answer from 0 to 4 on faithfulness (supported by excerpts), coverage (answers the question),
and directness (clear, no unsupported filler). Use integer scores. Select the better answer overall,
or tie when there is no meaningful quality difference. Be conservative: a longer answer is not inherently better.
Return ONLY valid JSON with keys: winner ("1000", "10000", or "tie"),
scores (object with keys "1000" and "10000", each containing faithfulness, coverage, directness),
reason (one concise sentence), evidence (one short supporting quote or empty string).

Question: {question}

1000-character answer:
{answer_1000}
Evidence excerpts for this answer:
{context_1000}

10000-character answer:
{answer_10000}
Evidence excerpts for this answer:
{context_10000}
"""


def parse_test_set(markdown: str) -> list[dict[str, Any]]:
    """Read numbered video headings, their first YouTube URL, and numbered questions."""
    videos: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in markdown.splitlines():
        heading = re.match(r"^###\s+\d+\.\s+(.+?)\s*$", line)
        if heading:
            current = {"title": heading.group(1), "video_id": None, "questions": []}
            videos.append(current)
            continue
        if current is None:
            continue
        if current["video_id"] is None:
            match = re.search(r"youtube\.com/watch\?v=([A-Za-z0-9_-]{11})|youtu\.be/([A-Za-z0-9_-]{11})", line)
            if match:
                current["video_id"] = match.group(1) or match.group(2)
        question = re.match(r"^\d+\.\s+(.+?)\s*$", line)
        if question:
            current["questions"].append(question.group(1))
    return videos


def retrieve_answer(pipeline: YouTubeRAGPipeline, question: str) -> dict[str, Any]:
    started = time.perf_counter()
    result = invoke_paced(lambda: pipeline.query(question))
    return {
        "answer": result["answer"],
        "source_chunks": result["source_chunks"],
        "latency_seconds": round(time.perf_counter() - started, 3),
    }


def invoke_paced(operation):
    """Pace Gemini calls for the documented 5 RPM free-tier quota and retry 429s."""
    global _last_model_call, _daily_quota_exhausted
    for attempt in range(5):
        delay = MIN_MODEL_CALL_INTERVAL_SECONDS - (time.monotonic() - _last_model_call)
        if delay > 0:
            time.sleep(delay)
        _last_model_call = time.monotonic()
        try:
            return operation()
        except Exception as exc:
            message = str(exc)
            if "perday" in message.lower() or "per day" in message.lower() or "requestsperday" in message.lower():
                _daily_quota_exhausted = True
                raise
            if not any(marker in message.lower() for marker in ("429", "quota", "resourceexhausted")) or attempt == 4:
                raise
            retry = re.search(r"retry in ([0-9.]+)s", message, flags=re.IGNORECASE)
            wait = float(retry.group(1)) + 2 if retry else MIN_MODEL_CALL_INTERVAL_SECONDS * (attempt + 2)
            print(f"  Gemini rate limit; retrying in {wait:.0f}s", flush=True)
            time.sleep(wait)


def compare_answers(judge: ChatGoogleGenerativeAI, question: str,
                    small: dict[str, Any], large: dict[str, Any]) -> dict[str, Any]:
    def context_text(result: dict[str, Any]) -> str:
        return "\n\n---\n\n".join(result["source_chunks"])[:12000]

    prompt = JUDGE_PROMPT.format(
        question=question,
        answer_1000=small["answer"],
        context_1000=context_text(small),
        answer_10000=large["answer"],
        context_10000=context_text(large),
    )
    raw = invoke_paced(lambda: judge.invoke(prompt)).content
    if isinstance(raw, list):
        raw = "".join(part.get("text", "") for part in raw if isinstance(part, dict))
    text = str(raw).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        parsed = json.loads(text)
        if parsed.get("winner") not in {"1000", "10000", "tie"}:
            raise ValueError("Unexpected winner value")
        return parsed
    except (json.JSONDecodeError, ValueError, AttributeError) as exc:
        return {"winner": "unrated", "scores": {}, "reason": f"Judge output was not valid expected JSON: {exc}", "raw": text}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video-limit", type=int, default=None, help="Run only the first N videos (smoke run).")
    parser.add_argument("--output", type=Path, default=RESULTS_FILE, help="JSON output path (default: RAG/results.json).")
    parser.add_argument("--skip-judge", action="store_true", help="Generate answers but omit the model-based pairwise quality judge.")
    parser.add_argument("--fresh", action="store_true", help="Ignore existing output and start over.")
    parser.add_argument("--new-question-limit", type=int, default=None,
                        help="Stop after this many newly completed question comparisons (resume mode).")
    args = parser.parse_args()

    videos = parse_test_set(TEST_SET.read_text(encoding="utf-8"))
    missing = [video["title"] for video in videos if not video["video_id"] or not video["questions"]]
    if missing:
        print("Test set entries need a YouTube ID and questions: " + "; ".join(missing), file=sys.stderr)
        return 2
    if args.video_limit:
        videos = videos[:args.video_limit]

    judge = None if args.skip_judge else ChatGoogleGenerativeAI(
        model=YouTubeRAGPipeline.CHAT_MODEL,
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY"),
    )
    if args.output.exists() and not args.fresh:
        try:
            report = json.loads(args.output.read_text(encoding="utf-8"))
            if (report.get("evaluation", {}).get("chunk_sizes_characters") != list(CHUNK_SIZES)
                    or report.get("evaluation", {}).get("chunk_overlap_characters") != {"1000": 200, "10000": 200}):
                raise ValueError("Existing result uses different settings; use --fresh.")
            print(f"Resuming from {args.output.name}", flush=True)
        except (json.JSONDecodeError, ValueError) as exc:
            print(f"Cannot resume output: {exc}; use --fresh.", file=sys.stderr)
            return 2
    else:
        report = {
        "evaluation": {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "test_set": str(TEST_SET.name),
            "model": YouTubeRAGPipeline.CHAT_MODEL,
            "embedding_model": YouTubeRAGPipeline.EMBED_MODEL,
            "temperature": TEMPERATURE,
            "chunk_sizes_characters": list(CHUNK_SIZES),
            "chunk_overlap_characters": {"1000": 200, "10000": 200},
            "prompt": YouTubeRAGPipeline.DEFAULT_PROMPT,
            "judge": None if args.skip_judge else "Gemini pairwise rubric; judge temperature 0",
            "rubric": "Faithfulness, coverage, directness (0-4 each); winner selected from transcript excerpts.",
            "caveat": "Model-based preference is a comparative estimate, not human ground truth.",
        },
        "summary": {"answered_questions": 0, "failed_questions": 0, "wins": {"1000": 0, "10000": 0, "tie": 0, "unrated": 0}},
        "videos": [],
        }
    prior_model = report["evaluation"].get("model")
    models_used = report["evaluation"].get("models_used", [])
    if prior_model and prior_model not in models_used:
        models_used.append(prior_model)
    if EVAL_MODEL not in models_used:
        models_used.append(EVAL_MODEL)
    report["evaluation"].update({
        "model": EVAL_MODEL,
        "models_used": models_used,
        "minimum_seconds_between_model_calls": MIN_MODEL_CALL_INTERVAL_SECONDS,
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    })
    existing_videos = {item.get("video_id"): item for item in report.get("videos", [])}
    report["evaluation"].pop("blocked_reason", None)
    report["evaluation"].pop("blocked_date_utc", None)
    report["evaluation"]["status"] = "running"
    completed_this_run = 0

    for video_index, video in enumerate(videos, start=1):
        if _daily_quota_exhausted:
            break
        print(f"[{video_index}/{len(videos)}] Fetching transcript: {video['title']}", flush=True)
        video_result: dict[str, Any] = existing_videos.get(video["video_id"], {
            "title": video["title"], "video_id": video["video_id"], "transcript_characters": 0,
            "variants": {}, "questions": [],
        })
        existing_questions = {item.get("question"): item for item in video_result.get("questions", [])}
        try:
            fetcher = YouTubeRAGPipeline(chunk_size=CHUNK_SIZES[0], temperature=TEMPERATURE)
            transcript = fetcher._fetch_transcript(video["video_id"])
            video_result["transcript_characters"] = len(transcript)
            pipelines: dict[int, YouTubeRAGPipeline] = {}
            for size in CHUNK_SIZES:
                overlap = CHUNK_OVERLAPS[CHUNK_SIZES.index(size)]
                pipeline = YouTubeRAGPipeline(chunk_size=size, chunk_overlap=overlap, temperature=TEMPERATURE)
                pipeline.ingest_transcript(transcript)
                pipelines[size] = pipeline
                video_result["variants"][str(size)] = {
                    "chunk_count": pipeline.chunk_count,
                    "chunk_size_characters": size,
                    "chunk_overlap_characters": overlap,
                }

            for question_index, question in enumerate(video["questions"], start=1):
                if _daily_quota_exhausted:
                    break
                prior = existing_questions.get(question)
                if (prior and "error" not in prior and "1000" in prior.get("answers", {})
                        and "10000" in prior.get("answers", {})
                        and prior.get("comparison", {}).get("winner") in {"1000", "10000", "tie"}):
                    print(f"  Q{question_index}/{len(video['questions'])}: already complete; skipping", flush=True)
                    continue
                print(f"  Q{question_index}/{len(video['questions'])}: {question}", flush=True)
                row: dict[str, Any] = {"question": question, "answers": {}}
                try:
                    for size in CHUNK_SIZES:
                        row["answers"][str(size)] = retrieve_answer(pipelines[size], question)
                    if judge:
                        row["comparison"] = compare_answers(judge, question, row["answers"]["1000"], row["answers"]["10000"])
                    else:
                        row["comparison"] = {"winner": "unrated", "reason": "Judge disabled."}
                except Exception as exc:
                    row["error"] = f"{type(exc).__name__}: {exc}"
                    if _daily_quota_exhausted:
                        report["evaluation"]["status"] = "incomplete"
                        report["evaluation"]["blocked_reason"] = "Gemini daily free-tier quota exhausted"
                        report["evaluation"]["blocked_date_utc"] = datetime.now(timezone.utc).date().isoformat()
                if ("error" not in row and "1000" in row.get("answers", {})
                        and "10000" in row.get("answers", {})):
                    row["model"] = EVAL_MODEL
                    completed_this_run += 1
                existing_questions[question] = row
                video_result["questions"] = [existing_questions[q] for q in video["questions"] if q in existing_questions]
                if video_result not in report["videos"]:
                    report["videos"].append(video_result)
                wins = {"1000": 0, "10000": 0, "tie": 0, "unrated": 0}
                answered = failed = 0
                for saved_video in report["videos"]:
                    for saved_q in saved_video.get("questions", []):
                        if "error" in saved_q:
                            failed += 1
                        elif "1000" in saved_q.get("answers", {}) and "10000" in saved_q.get("answers", {}):
                            answered += 1
                            winner = saved_q.get("comparison", {}).get("winner", "unrated")
                            wins[winner] = wins.get(winner, 0) + 1
                    if saved_video.get("error"):
                        failed += max(0, 5 - len(saved_video.get("questions", [])))
                report["summary"] = {"answered_questions": answered, "failed_questions": failed, "wins": wins}
                report["evaluation"]["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                if _daily_quota_exhausted:
                    print("Stopped after Gemini daily quota exhaustion; saved checkpoint.", flush=True)
                    break
                if args.new_question_limit and completed_this_run >= args.new_question_limit:
                    print(f"Reached new-question limit ({completed_this_run}); saved checkpoint.", flush=True)
                    break
        except Exception as exc:
            video_result["error"] = f"{type(exc).__name__}: {exc}"
            report["summary"]["failed_questions"] += len(video["questions"])
            print(f"  Video failed: {video_result['error']}", file=sys.stderr, flush=True)
        if video_result not in report["videos"]:
            report["videos"].append(video_result)
        if _daily_quota_exhausted:
            break
        if args.new_question_limit and completed_this_run >= args.new_question_limit:
            break
        report["evaluation"]["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Saved evaluation results ({report['summary']['answered_questions']} answered, "
          f"{report['summary']['failed_questions']} failed): {args.output.name}")
    if report["evaluation"].get("status") == "running":
        report["evaluation"]["status"] = (
            "partial_batch_complete"
            if args.new_question_limit and completed_this_run >= args.new_question_limit
            else "incomplete"
        )
        report["evaluation"]["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    return 0 if report["summary"]["answered_questions"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
