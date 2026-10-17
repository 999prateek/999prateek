# Simplify AI — General-purpose multilingual chatbot

Python-first web app with general Q&A through a configured LLM, optional live web search, uploaded document Q&A, multilingual response preferences, chat history, analytics, and optional voice integrations.

## Features
- General-purpose assistant, not restricted to Rajasthan or education
- Optional live public-web search via `ddgs`
- Upload and extract PDF, DOCX, TXT, Markdown, and CSV
- Retrieval-augmented question answering over uploaded files
- Source links for web results and labels for document chunks
- Hindi, English, Hinglish and other language preferences
- Local SQLite chat/document storage
- Optional speech-to-text and text-to-speech
- Analytics view

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```
Windows activation: `.venv\Scripts\activate`

## Configure the AI engine
The app expects an OpenAI-compatible endpoint:
- `OPENAI_BASE_URL` — endpoint base URL, such as a provider's compatible API base
- `OPENAI_API_KEY` — provider key
- `LLM_MODEL` — model identifier accepted by that endpoint

Example environment variables (replace with actual values):
```bash
OPENAI_BASE_URL=https://YOUR_PROVIDER_COMPATIBLE_ENDPOINT/v1
OPENAI_API_KEY=YOUR_API_KEY
LLM_MODEL=YOUR_MODEL_NAME
```
The example is a configuration pattern, not a working credential. Do not put API keys into public GitHub repositories. On Streamlit Community Cloud, set these under app Secrets and adapt the code to read them from `st.secrets` if desired.

Without a configured LLM, the app can display retrieved document passages or web results but cannot synthesize a general AI answer.

## How document Q&A works
1. Upload a supported file.
2. The app extracts text and splits it into overlapping chunks.
3. When you ask a question, lightweight keyword retrieval selects relevant chunks.
4. The selected excerpts are sent to the configured LLM as context.
5. The answer is expected to use the excerpts and admit when the document does not contain the answer.

This starter uses keyword overlap rather than semantic vector embeddings. For production, use multilingual embeddings with pgvector or Qdrant, chunk by headings/pages, rerank passages, and show exact page citations.

## Real-time web answers
When enabled, the app attempts a public-web search for each question and passes result snippets to the model. This improves freshness but is not a guarantee of real-time truth: search may fail, pages may be outdated, and the model can still make mistakes. For production, use a supported search API with explicit rate limits and source handling.

## Deployment
For a no-terminal deployment:
1. Extract the ZIP.
2. Upload files to a GitHub repository using the website.
3. Create a Streamlit Community Cloud app pointing to `app.py`.
4. Add model settings as deployment secrets/environment variables.
5. Deploy and test the public link.

Public deployment requires dependency installation and a configured model provider. This project does not include hosting credentials or a hosted URL.

## Security and limitations
- Never commit API keys or private documents to a public repository.
- Add authentication before sharing private document uploads or analytics.
- This is a prototype, not an infallible "knows everything" system.
- Verify medical, legal, financial, and safety-critical answers with trusted professionals or official sources.
- Scanned PDFs need OCR; this starter only extracts embedded text.
- Local files and SQLite are not a durable multi-user cloud storage architecture.
