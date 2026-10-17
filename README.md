# RajBhasha AI — Rajasthan Language-Agnostic Education Chatbot

A Python-first hackathon prototype for SIH25104. It includes a Streamlit web UI, local SQLite persistence, PDF ingestion, lightweight retrieval, an optional OpenAI-compatible LLM endpoint, feedback capture, analytics, and optional voice hooks.

## Run locally

Python 3.10+ recommended.

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows
# .venv\Scripts\activate

pip install -r requirements.txt
streamlit run app.py
```

Open the local URL shown by Streamlit (normally http://localhost:8501).

## Configure a language model (recommended)

Copy `.env.example` to `.env`, then set environment variables in your shell or deployment platform. The app currently reads environment variables; it does not automatically parse `.env`.

Example for an OpenAI-compatible local endpoint:
```bash
export OPENAI_BASE_URL=http://localhost:11434/v1
export OPENAI_API_KEY=local-dev-key
export LLM_MODEL=llama3.1
```

Make sure your local model server actually exposes an OpenAI-compatible `/chat/completions` endpoint. Model names and provider URLs vary.

Without a configured LLM, the app still retrieves matching document chunks and shows them as excerpts rather than fabricating an answer.

## Included features

- Hindi/English/Hinglish and script-based language detection
- Chat interface with user personas
- PDF upload and indexing into SQLite
- Source labels and conservative no-answer fallback
- Feedback buttons
- Admin analytics for message volume, language mix, rough topic counts, and recent messages
- Optional Whisper transcription and TTS support

## Important prototype limitations

- The retrieval function uses token overlap, not multilingual semantic embeddings. Replace it with multilingual sentence embeddings plus pgvector or Qdrant before production.
- Language detection is heuristic. It is not reliable for all Romanized dialects or short messages.
- Real Bhashini/Sarvam APIs require current provider credentials and endpoint-specific request schemas; they are not falsely simulated here.
- Streamlit's audio capture and browser support vary. For a robust voice experience, build an explicit upload/record component and test on target devices.
- Analytics are not authenticated in this demo. Do not deploy publicly with real data until you add login, role-based authorization, rate limits, privacy controls, and secure secrets.
- PDF extraction will not OCR scanned PDFs. Add OCR (e.g., Tesseract) as a separate ingestion stage.
- Never treat generated content as an official decision. Show source documents and confirm current rules with the responsible department.

## Architecture blueprint

### Hackathon MVP stack
- **UI:** Streamlit (all-Python interface; fastest path to a demo)
- **API/business logic:** Python modules in this prototype; for a production split, expose services through FastAPI
- **Database:** SQLite for demo; PostgreSQL for multi-user production
- **Cache/session state:** Streamlit session state now; Redis for rate limits, caching, and distributed sessions later
- **Document retrieval:** SQLite chunk store now; multilingual embeddings + pgvector/Qdrant in production
- **LLM:** configurable OpenAI-compatible endpoint (self-hosted vLLM/Ollama-compatible gateway or hosted provider)
- **ASR:** optional faster-whisper locally; production adapter for Bhashini/Sarvam
- **TTS:** optional edge-tts demo; production Indic TTS provider

### Request pipeline
1. Accept typed text or audio.
2. Detect script/language heuristically; production should use a language-ID model and preserve original text.
3. Normalize whitespace and common Hinglish spelling variants without destroying the original.
4. Retrieve relevant passages from verified PDFs.
5. Send question + retrieved context to a multilingual LLM with a strict grounded-answer prompt.
6. Respond in the requested language; if unsupported, ask whether Hindi or English is acceptable.
7. Show citations, confidence/coverage, and a feedback action.
8. Optionally synthesize audio in the selected language.

### Recommended production database entities
- `users`: user ID, role, preferred language, consent flags
- `sessions`: session ID, user ID (nullable/anonymous), created/updated timestamps
- `messages`: session ID, role, original text, detected language, response language, content, created timestamp
- `documents`: title, source URL, publisher, issue date, checksum, verification status
- `chunks`: document ID, page, text, embedding vector, metadata
- `feedback`: message ID, rating, reason, created timestamp
- `events`: anonymized event type, language, topic, timestamp

### Production quality gates
- Only index documents from approved/verified sources.
- Attach page number/URL to every retrieved chunk and show citations inline.
- If retrieval scores are low, ask a clarifying question or say no matching official source was found.
- Use a multilingual embedding model (e.g. BGE-M3 or a suitable Indic embedding model) and evaluate it on Hindi, Hinglish, and Rajasthani samples.
- Build a golden test set with native-speaker-reviewed answers, source attribution, ASR accuracy, and response latency.
- Set retention policies, redact personal data, protect admin analytics, and do not log raw audio by default.
