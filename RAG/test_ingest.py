import os
# Clear SSL certificate bundle env vars if they point to non-existent paths on the local system
os.environ.pop("CURL_CA_BUNDLE", None)
os.environ.pop("REQUESTS_CA_BUNDLE", None)

from dotenv import load_dotenv
load_dotenv()

from rag_pipeline import YouTubeRAGPipeline
 
p = YouTubeRAGPipeline()
p.ingest('Y9s5Xkg7gpg')
print('SUCCESS')