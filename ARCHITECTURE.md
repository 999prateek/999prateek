# Simplify AI — architecture and roadmap

## Current MVP
- Streamlit UI
- Python core logic
- SQLite session/message/document storage
- PDF/DOCX/TXT/MD/CSV extraction
- Keyword-overlap retrieval over uploaded files
- Optional DuckDuckGo web search
- Configurable OpenAI-compatible LLM endpoint
- Optional Whisper ASR and edge-tts TTS

## Request orchestration
1. Accept user question.
2. Determine a rough language/script label.
3. Optionally retrieve relevant chunks from uploaded documents.
4. Optionally search the public web for current information.
5. Send question, recent conversation turns, retrieved document excerpts, and search snippets to an LLM.
6. Ask the model to distinguish source-backed information from general knowledge.
7. Return answer and display source links/document labels.
8. Save the exchange to local SQLite.

## Recommended production upgrades
- FastAPI backend with Pydantic schemas and streaming responses
- PostgreSQL for accounts, conversations, document metadata, and feedback
- pgvector or Qdrant with multilingual embeddings
- Reranking, confidence thresholds, page-level citations, and document versioning
- OCR for scanned PDFs and tables/images extraction
- Object storage for uploads, malware scanning, file size/type limits
- Redis for rate limits and cache; queue workers for ingestion
- Search API with provider terms/rate limits and freshness metadata
- Authentication, role-based access, encryption, retention/deletion policy
- Evaluation suite for multilingual answer quality, citation precision, retrieval recall, and latency

## Suggested database entities
- users: id, role, preferred language, consent flags
- sessions: id, user_id, created_at, last_activity_at
- messages: id, session_id, role, original_text, response_language, content, source references, created_at
- documents: id, owner_id, filename, checksum, MIME type, upload date, verification status
- chunks: id, document_id, page, section, content, embedding
- feedback: id, message_id, rating, reason, created_at
- search_events: query category, language, timestamp, selected result IDs (avoid storing sensitive raw queries without consent)

## Important behavior
- "Any topic" means broad general-purpose capability, not guaranteed perfect knowledge.
- "Real-time" requires a live search/retrieval source and should show citations and timestamps where possible.
- If a document does not support an answer, the assistant must say so rather than fabricate content.
- For high-stakes domains, use careful language and encourage authoritative verification.
