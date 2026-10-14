import os
# Clear SSL certificate bundle env vars if they point to non-existent paths on the local system
os.environ.pop("CURL_CA_BUNDLE", None)
os.environ.pop("REQUESTS_CA_BUNDLE", None)

from dotenv import load_dotenv
load_dotenv()

from youtube_transcript_api import YouTubeTranscriptApi

video_id = input("Enter video ID: ").strip()

ytt = YouTubeTranscriptApi()

print("\n--- Trying English transcript ---")
try:
    fetched = ytt.fetch(video_id, languages=["en"])
    text = " ".join(s.text for s in fetched)
    print(f"SUCCESS — {len(text)} chars")
    print("Preview:", text[:200])
except Exception as e:
    print(f"FAILED: {e}")

print("\n--- Listing all available transcripts ---")
try:
    transcript_list = ytt.list(video_id)
    for t in transcript_list:
        print(f"  lang={t.language_code}  auto={t.is_generated}  translatable={t.is_translatable}")
except Exception as e:
    print(f"FAILED to list: {e}")
