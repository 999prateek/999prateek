# SIH25104 — Detailed Architecture & Implementation Blueprint

## 1. Recommended architecture

**Prototype (deliverable here):** Streamlit + Python modules + SQLite + PDF text extraction + token-overlap retrieval + optional compatible LLM endpoint.

**Scale-up target:**
- Web: React/Next.js if a separate frontend team is available; otherwise Streamlit is ideal for the first demo.
- API: FastAPI, Pydantic validation, async endpoints, OpenAPI docs.
- Data: PostgreSQL + pgvector for users, messages, documents, chunks, feedback; object storage for source PDFs.
- Cache/queue: Redis + Celery/RQ for session caching, request throttling, and asynchronous document ingestion.
- AI: multilingual LLM behind a provider adapter; embedding model selected through Hindi/Hinglish evaluation.
- Speech: Bhashini/Sarvam adapter for Indian-language ASR/TTS; faster-whisper as local/offline fallback.
- Observability: structured logs, OpenTelemetry, latency and error metrics, anonymized product analytics.

## 2. AI pipeline

`Audio → ASR → language ID → normalization → retrieval → grounded generation → language rendering → TTS`

- Preserve the raw user utterance alongside normalized text.
- ASR should return transcript, language, timestamps, and confidence when available.
- For mixed Hindi-English text, do not force translation to English unless the selected model requires it. A multilingual LLM can often operate directly on the original.
- If a base-language translation is required, store both original and translated text; retrieval should search both so important terms are not lost.
- Retrieval: chunk by headings/pages, embed chunks with a multilingual model, query top-k, rerank, and enforce a similarity threshold.
- Generation: provide retrieved passages, source identity, page number, and strict instructions not to invent policy details.
- If evidence is weak, return a transparent fallback in the user's language.
- TTS should be an opt-in response action, with language-specific voices and a text fallback.

## 3. Feature plan

### Contextual RAG
- Ingest official PDFs, HTML pages, circulars, scholarship guidelines, and notices.
- Maintain checksum, publisher, source URL, date, and verified status.
- Extract text; OCR scanned pages; chunk by page and heading.
- Store embeddings and metadata; retrieve top-k chunks; return source title and page.
- Add document expiry/re-index checks for changing policy content.

### Rare language / dialect fallback
- First attempt language ID and multilingual retrieval.
- If confidence is low, ask the user to choose Hindi or English, or offer a best-effort response clearly labelled as such.
- Never silently rewrite a dialect and pretend certainty.
- Collect consented, anonymized corrections to improve dialect coverage.

### Admin dashboard
- Aggregate counts by language, topic, date, and answer feedback.
- Do not expose raw conversations by default.
- Add RBAC and audit logs for administrators.
- Suppress small groups where language/topic combinations could identify a person.

## 4. Suggested schema

```sql
CREATE TABLE users (
  id UUID PRIMARY KEY,
  role TEXT NOT NULL CHECK (role IN ('student','teacher','citizen','admin')),
  preferred_language TEXT,
  consent_voice BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sessions (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_activity_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE messages (
  id UUID PRIMARY KEY,
  session_id UUID NOT NULL REFERENCES sessions(id),
  role TEXT NOT NULL CHECK (role IN ('user','assistant','system')),
  original_text TEXT,
  normalized_text TEXT,
  detected_language TEXT,
  response_language TEXT,
  content TEXT NOT NULL,
  source_ids JSONB NOT NULL DEFAULT '[]',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE documents (
  id UUID PRIMARY KEY,
  title TEXT NOT NULL,
  source_url TEXT,
  publisher TEXT,
  issue_date DATE,
  checksum TEXT UNIQUE NOT NULL,
  verified BOOLEAN NOT NULL DEFAULT FALSE,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE chunks (
  id UUID PRIMARY KEY,
  document_id UUID NOT NULL REFERENCES documents(id),
  page_number INT,
  heading TEXT,
  content TEXT NOT NULL,
  embedding VECTOR(1024)
);

CREATE TABLE feedback (
  id UUID PRIMARY KEY,
  message_id UUID NOT NULL REFERENCES messages(id),
  rating SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
  reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## 5. Demo script

1. Start the app and ask in Hinglish: “Scholarship ke liye kaunse documents chahiye?”
2. Before any PDF is uploaded, show the safe no-source fallback.
3. Upload a verified public scholarship PDF or school circular.
4. Ask the same question and show retrieved excerpts and source labels.
5. Configure an LLM endpoint and show a concise answer grounded in the uploaded text.
6. Switch response language and demonstrate language preference.
7. Submit feedback and open Admin analytics.
8. If voice dependencies are available, record a question and play the generated audio response.

## 6. Suggested team split

- AI/RAG: ingestion, multilingual embeddings, evaluation, grounding.
- Backend: FastAPI, PostgreSQL, Redis, auth, provider adapters.
- Frontend: chat, language switcher, audio UX, accessibility.
- Domain/research: verified Rajasthan education documents, eligibility and policy validation.
- QA/demo: test corpus, latency, native-speaker review, offline/failure demo.
