import os
import uuid
import sqlite3
from datetime import datetime
from pathlib import Path

import streamlit as st

from chatbot_core import (
    init_db, save_message, get_history, save_feedback, get_analytics,
    ingest_pdf, answer_question, detect_language, translate_text,
    transcribe_audio, synthesize_audio, get_document_stats
)

APP_DIR = Path(__file__).parent
UPLOAD_DIR = APP_DIR / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = APP_DIR / "data" / "chatbot.db"

st.set_page_config(
    page_title="RajBhasha AI | Rajasthan Education Assistant",
    page_icon="🇮🇳",
    layout="wide",
    initial_sidebar_state="expanded",
)
init_db(DB_PATH)

st.markdown("""
<style>
:root { --saffron:#f28c28; --navy:#14213d; --teal:#168c83; }
.stApp { background: linear-gradient(180deg, #fffaf3 0%, #f7fbff 48%, #f7fafc 100%); }
.hero { padding: 1.4rem 1.6rem; border-radius: 22px; color: white;
        background: linear-gradient(120deg, #14213d 0%, #1f5473 60%, #168c83 100%);
        box-shadow: 0 10px 30px rgba(20,33,61,.15); }
.hero h1 { margin:0; font-size:2.2rem; }
.hero p { margin:.45rem 0 0 0; opacity:.92; font-size:1rem; }
.pill { display:inline-block; border:1px solid #d7e4ec; background:#fff;
        padding:.25rem .65rem; border-radius:999px; margin:.15rem; font-size:.82rem; }
.metric-card { background:white; border:1px solid #e6edf2; border-radius:16px;
               padding:1rem; box-shadow:0 4px 16px rgba(20,33,61,.04); }
.small-muted { color:#617182; font-size:.85rem; }
div[data-testid="stChatMessage"] { border-radius:14px; }
</style>
""", unsafe_allow_html=True)

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = get_history(DB_PATH, st.session_state.session_id)
if "language" not in st.session_state:
    st.session_state.language = "Auto-detect"
if "persona" not in st.session_state:
    st.session_state.persona = "Student"

with st.sidebar:
    st.markdown("## 🇮🇳 RajBhasha AI")
    st.caption("Language-agnostic education assistant")
    page = st.radio("Navigate", ["Chat assistant", "Knowledge base", "Admin analytics", "About & setup"])
    st.divider()
    st.session_state.persona = st.selectbox("I am a…", ["Student", "Teacher", "Citizen", "Administrator"])
    st.session_state.language = st.selectbox(
        "Preferred response language",
        ["Auto-detect", "Hindi", "English", "Hinglish", "Rajasthani (beta)", "Gujarati", "Marwari (beta)"],
        index=["Auto-detect", "Hindi", "English", "Hinglish", "Rajasthani (beta)", "Gujarati", "Marwari (beta)"].index(st.session_state.language)
    )
    if st.button("＋ New conversation", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()
    st.markdown("---")
    st.markdown('<span class="pill">Text</span><span class="pill">Voice-ready</span><span class="pill">RAG</span>', unsafe_allow_html=True)
    st.caption("Prototype • Local SQLite • Optional AI providers")

if page == "Chat assistant":
    st.markdown("""
    <div class="hero">
      <h1>Namaste! कैसे मदद करूँ?</h1>
      <p>Ask about school notices, scholarships, admissions, exams, learning resources, or Rajasthan government education services.</p>
    </div>
    """, unsafe_allow_html=True)
    st.write("")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="metric-card"><b>🗣️ Your language</b><p class="small-muted">Hindi, English, Hinglish and supported regional languages.</p></div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="metric-card"><b>📚 Grounded answers</b><p class="small-muted">Answers can cite uploaded circulars and education PDFs.</p></div>', unsafe_allow_html=True)
    with c3:
        st.markdown('<div class="metric-card"><b>🔒 Privacy-first demo</b><p class="small-muted">Local prototype storage; no account required.</p></div>', unsafe_allow_html=True)
    st.write("")
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m.get("sources"):
                with st.expander("Sources used"):
                    for source in m["sources"]:
                        st.write(f"• {source}")

    with st.expander("🎙️ Ask with voice", expanded=False):
        audio = st.audio_input("Record your question")
        if audio is not None:
            if st.button("Transcribe recording"):
                with st.spinner("Transcribing…"):
                    transcript, note = transcribe_audio(audio.getvalue())
                st.session_state.voice_transcript = transcript
                if note:
                    st.info(note)
                st.text_area("Recognized text (edit if needed)", key="voice_transcript")
                st.caption("Submit the recognized text in the chat box below.")
    if "voice_transcript" in st.session_state and st.session_state.voice_transcript:
        st.info("Voice transcript is ready. Copy it into the message box, or press the button below.")
        if st.button("Use voice transcript"):
            question = st.session_state.voice_transcript
            user_lang = detect_language(question)
            save_message(DB_PATH, st.session_state.session_id, "user", question, user_lang, st.session_state.persona)
            st.session_state.messages.append({"role":"user", "content":question})
            with st.spinner("Finding a grounded answer…"):
                answer, sources, meta = answer_question(DB_PATH, question, st.session_state.language, st.session_state.persona)
            save_message(DB_PATH, st.session_state.session_id, "assistant", answer, meta.get("language","unknown"), st.session_state.persona, sources=sources)
            st.session_state.messages.append({"role":"assistant","content":answer,"sources":sources})
            st.session_state.last_answer = answer
            st.session_state.last_message_id = meta.get("message_id")
            st.rerun()

    prompt = st.chat_input("Type in Hindi, English, Hinglish, or another supported language…")
    if prompt:
        detected = detect_language(prompt)
        save_message(DB_PATH, st.session_state.session_id, "user", prompt, detected, st.session_state.persona)
        st.session_state.messages.append({"role":"user","content":prompt})
        with st.spinner("Searching knowledge base and preparing your answer…"):
            answer, sources, meta = answer_question(DB_PATH, prompt, st.session_state.language, st.session_state.persona)
        save_message(DB_PATH, st.session_state.session_id, "assistant", answer, meta.get("language", detected), st.session_state.persona, sources=sources)
        st.session_state.messages.append({"role":"assistant","content":answer,"sources":sources})
        st.session_state.last_answer = answer
        st.session_state.last_message_id = meta.get("message_id")
        st.rerun()

    if st.session_state.messages and st.session_state.messages[-1]["role"] == "assistant":
        st.divider()
        st.markdown("**Was this answer helpful?**")
        fb1, fb2, fb3 = st.columns([1,1,4])
        with fb1:
            if st.button("👍 Helpful"):
                save_feedback(DB_PATH, st.session_state.session_id, st.session_state.messages[-1]["content"], 1, "Helpful")
                st.success("Thanks for your feedback.")
        with fb2:
            if st.button("👎 Not helpful"):
                save_feedback(DB_PATH, st.session_state.session_id, st.session_state.messages[-1]["content"], 0, "Not helpful")
                st.success("Feedback saved.")
        with fb3:
            if st.button("🔊 Read answer aloud"):
                audio_bytes, note = synthesize_audio(st.session_state.messages[-1]["content"], st.session_state.language)
                if audio_bytes:
                    st.audio(audio_bytes, format="audio/mp3")
                else:
                    st.info(note)

elif page == "Knowledge base":
    st.markdown('<div class="hero"><h1>📚 Knowledge base</h1><p>Upload official PDFs to ground answers in real documents.</p></div>', unsafe_allow_html=True)
    st.warning("For the demo, upload verified and public documents only. The app does not automatically verify that a document is official.")
    uploads = st.file_uploader("Upload circulars, scholarship guidelines, school notices, or education PDFs", type=["pdf"], accept_multiple_files=True)
    if st.button("Index selected PDFs", type="primary", disabled=not uploads):
        progress = st.progress(0)
        results = []
        for i, f in enumerate(uploads):
            dest = UPLOAD_DIR / f"{uuid.uuid4().hex}_{Path(f.name).name}"
            dest.write_bytes(f.getvalue())
            try:
                count = ingest_pdf(DB_PATH, dest, f.name)
                results.append(f"✅ {f.name}: indexed {count} text chunks")
            except Exception as e:
                results.append(f"⚠️ {f.name}: could not index ({e})")
            progress.progress((i + 1) / len(uploads))
        for line in results:
            st.write(line)
    st.subheader("Indexed documents")
    stats = get_document_stats(DB_PATH)
    if stats:
        st.dataframe(stats, use_container_width=True, hide_index=True)
    else:
        st.info("No documents indexed yet. You can try the demo questions in the chat, or upload a PDF.")

elif page == "Admin analytics":
    st.markdown('<div class="hero"><h1>📊 Admin analytics</h1><p>Understand usage patterns and improve the service.</p></div>', unsafe_allow_html=True)
    analytics = get_analytics(DB_PATH)
    a, b, c = st.columns(3)
    a.metric("Messages", analytics["total_messages"])
    b.metric("Sessions", analytics["total_sessions"])
    c.metric("Feedback entries", analytics["feedback_count"])
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Messages by language")
        if analytics["by_language"]:
            st.bar_chart(analytics["by_language"].set_index("language"))
        else:
            st.info("No usage data yet.")
    with col2:
        st.subheader("Popular topics (keyword estimate)")
        if analytics["topics"]:
            st.bar_chart(analytics["topics"].set_index("topic"))
        else:
            st.info("No usage data yet.")
    st.subheader("Recent conversations (privacy-safe preview)")
    if not analytics["recent"].empty:
        st.dataframe(analytics["recent"], use_container_width=True, hide_index=True)
    st.caption("This dashboard is a prototype. Production analytics should aggregate/anonymize data and enforce administrator access controls.")

else:
    st.markdown('<div class="hero"><h1>About RajBhasha AI</h1><p>A multilingual education-access assistant prototype for Rajasthan.</p></div>', unsafe_allow_html=True)
    st.subheader("What works in this prototype")
    st.markdown("""
    - Text chat with automatic script-based language detection and Hindi/English/Hinglish response preference.
    - PDF ingestion and retrieval-augmented answers with source labels.
    - Local SQLite storage for sessions, messages, documents, and feedback.
    - Admin analytics for languages, topic keywords, and recent activity.
    - Optional speech-to-text and text-to-speech integrations with graceful fallbacks.
    """)
    st.subheader("Production integrations to configure")
    st.markdown("""
    1. **LLM:** Set `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `LLM_MODEL` for an OpenAI-compatible endpoint, or adapt `chatbot_core.py` to a self-hosted vLLM/Ollama endpoint.
    2. **ASR:** Install `faster-whisper` for local speech recognition, or wire a Bhashini/Sarvam endpoint using their current official API documentation and credentials.
    3. **TTS:** Install `edge-tts` for a demo voice, or use a production Hindi/Indic TTS provider.
    4. **Scale:** Move SQLite to PostgreSQL, embeddings to pgvector/Qdrant, and background PDF processing to Celery/RQ with Redis.
    """)
    st.code("pip install -r requirements.txt\nstreamlit run app.py", language="bash")
    st.subheader("Important safeguards")
    st.markdown("""
    - Always show sources and tell users when no authoritative source was found.
    - Never invent scholarship deadlines, eligibility, or official rules.
    - Add role-based access control before exposing admin analytics publicly.
    - Encrypt secrets, limit retention, redact personal information, and obtain consent for voice processing.
    - Test Hindi, Hinglish, Marwari/Rajasthani variants, noisy audio, and code-switching with native speakers.
    """)
