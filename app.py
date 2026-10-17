import os
import uuid
from pathlib import Path
import streamlit as st

from simplify_core import (
    init_db, get_history, save_message, answer_question, ingest_file,
    get_documents, get_analytics, delete_document, transcribe_audio,
    synthesize_audio, detect_language
)

ROOT = Path(__file__).parent
DATA = ROOT / "data"
UPLOADS = DATA / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)
DB = DATA / "simplify.db"

st.set_page_config(page_title="Simplify AI", page_icon="✨", layout="wide")
init_db(DB)

st.markdown("""
<style>
.stApp { background: linear-gradient(180deg,#f8fbff 0%,#fff 100%); }
.hero { padding:1.5rem 1.7rem; border-radius:22px; color:#fff;
background:linear-gradient(120deg,#182848 0%,#315c9b 55%,#6a5acd 100%);
box-shadow:0 10px 30px rgba(24,40,72,.15); }
.hero h1 { margin:0; font-size:2.45rem; letter-spacing:-.04em; }
.hero p { margin:.55rem 0 0; opacity:.9; }
.card { background:white; border:1px solid #e6ebf2; border-radius:16px; padding:1rem; }
.muted { color:#667085; font-size:.88rem; }
div[data-testid="stChatMessage"] { border-radius:15px; }
</style>
""", unsafe_allow_html=True)

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = get_history(DB, st.session_state.session_id)
if "doc_ids" not in st.session_state:
    st.session_state.doc_ids = []

with st.sidebar:
    st.markdown("## ✨ Simplify AI")
    st.caption("Understand more. Do more.")
    page = st.radio("Workspace", ["Chat", "My documents", "Analytics", "Settings & help"])
    st.divider()
    language = st.selectbox("Response language", [
        "Auto-detect", "English", "Hindi", "Hinglish", "Gujarati", "Bengali",
        "Tamil", "Telugu", "Marathi", "Punjabi", "Rajasthani"
    ])
    live_search = st.toggle("Use live web search", value=True,
                            help="Searches the public web for recent information when available.")
    use_docs = st.toggle("Use my uploaded documents", value=True)
    if st.button("＋ New chat", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()
    st.divider()
    st.markdown('<div class="muted">General knowledge · Live web search · Document Q&A · Multilingual</div>',
                unsafe_allow_html=True)

if page == "Chat":
    st.markdown("""
    <div class="hero">
      <h1>✨ Simplify AI</h1>
      <p>Your AI assistant for learning, writing, coding, research, planning, and understanding your files.</p>
    </div>
    """, unsafe_allow_html=True)
    st.write("")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="card"><b>🌍 Ask anything</b><p class="muted">General questions across subjects, not limited to one region or domain.</p></div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="card"><b>📄 Understand files</b><p class="muted">Upload documents and ask questions grounded in their content.</p></div>', unsafe_allow_html=True)
    with c3:
        st.markdown('<div class="card"><b>🔎 Current information</b><p class="muted">Optional web search for recent facts, with source links when available.</p></div>', unsafe_allow_html=True)

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m.get("sources"):
                with st.expander("Sources"):
                    for src in m["sources"]:
                        if isinstance(src, dict):
                            st.markdown(f"- [{src.get('title','Source')}]({src.get('url','#')})")
                        else:
                            st.write(f"- {src}")

    with st.expander("🎙️ Ask with voice (optional)", expanded=False):
        audio = st.audio_input("Record your question")
        if audio:
            if st.button("Transcribe voice"):
                transcript, note = transcribe_audio(audio.getvalue())
                if transcript:
                    st.session_state.voice_text = transcript
                    st.success(note)
                else:
                    st.warning(note)
        if st.session_state.get("voice_text"):
            st.text_area("Recognized question", key="voice_text")
            if st.button("Ask this question"):
                st.session_state.pending_question = st.session_state.voice_text
                st.rerun()

    prompt = st.chat_input("Ask Simplify anything, or ask about an uploaded document…")
    question = prompt or st.session_state.pop("pending_question", None)
    if question:
        detected = detect_language(question)
        save_message(DB, st.session_state.session_id, "user", question, detected, [])
        st.session_state.messages.append({"role":"user","content":question,"sources":[]})
        with st.spinner("Thinking and checking relevant sources…"):
            answer, sources, meta = answer_question(
                DB, question, language, live_search, use_docs,
                st.session_state.session_id
            )
        save_message(DB, st.session_state.session_id, "assistant", answer, meta.get("language", language), sources)
        st.session_state.messages.append({"role":"assistant","content":answer,"sources":sources})
        st.session_state.last_answer = answer
        st.rerun()

    if st.session_state.messages and st.session_state.messages[-1]["role"] == "assistant":
        left, right = st.columns([1,5])
        with left:
            if st.button("🔊 Read aloud"):
                audio_bytes, note = synthesize_audio(st.session_state.messages[-1]["content"], language)
                if audio_bytes:
                    st.audio(audio_bytes, format="audio/mp3")
                else:
                    st.info(note)
        with right:
            st.caption("AI can make mistakes. Verify important medical, legal, financial, and safety decisions.")

elif page == "My documents":
    st.markdown('<div class="hero"><h1>📄 My documents</h1><p>Upload files and ask Simplify questions about their contents.</p></div>', unsafe_allow_html=True)
    st.info("Supported formats: PDF, DOCX, TXT, MD, CSV. Scanned PDFs may need OCR before their text can be searched.")
    uploaded = st.file_uploader("Choose files", type=["pdf","docx","txt","md","csv"], accept_multiple_files=True)
    if st.button("Upload and index", type="primary", disabled=not uploaded):
        bar = st.progress(0)
        for i, f in enumerate(uploaded):
            dest = UPLOADS / f"{uuid.uuid4().hex}_{Path(f.name).name}"
            dest.write_bytes(f.getvalue())
            try:
                count = ingest_file(DB, dest, f.name)
                st.success(f"{f.name}: indexed {count} text chunks.")
            except Exception as e:
                st.error(f"{f.name}: could not process — {e}")
            bar.progress((i+1)/len(uploaded))
    st.subheader("Available documents")
    docs = get_documents(DB)
    if docs:
        for doc in docs:
            with st.container(border=True):
                a,b = st.columns([5,1])
                with a:
                    st.markdown(f"**{doc['filename']}**")
                    st.caption(f"{doc['chunks']} chunks · uploaded {doc['created_at']}")
                with b:
                    if st.button("Remove", key=f"remove_{doc['id']}"):
                        delete_document(DB, doc["id"])
                        try: Path(doc["stored_path"]).unlink(missing_ok=True)
                        except Exception: pass
                        st.rerun()
    else:
        st.caption("No documents uploaded yet. Add a file, then ask questions about it in Chat.")

elif page == "Analytics":
    st.markdown('<div class="hero"><h1>📊 Usage analytics</h1><p>Simple local insights from your chat sessions.</p></div>', unsafe_allow_html=True)
    data = get_analytics(DB)
    a,b,c = st.columns(3)
    a.metric("Messages", data["messages"])
    b.metric("Sessions", data["sessions"])
    c.metric("Documents", data["documents"])
    if not data["languages"].empty:
        st.subheader("User languages")
        st.bar_chart(data["languages"].set_index("language"))
    if not data["recent"].empty:
        st.subheader("Recent messages")
        st.dataframe(data["recent"], use_container_width=True, hide_index=True)
    st.caption("Before public deployment, add authentication and privacy controls. Avoid exposing private message content to unauthorized users.")

else:
    st.markdown('<div class="hero"><h1>Settings & help</h1><p>Configure the AI engine and understand the prototype limits.</p></div>', unsafe_allow_html=True)
    st.subheader("AI model setup")
    st.markdown("""
    Simplify uses an **OpenAI-compatible chat endpoint** when configured. You can connect a hosted provider or a local model server that exposes `/chat/completions`.

    Set these environment variables in your deployment settings:
    - `OPENAI_BASE_URL`
    - `OPENAI_API_KEY`
    - `LLM_MODEL`

    For web search, the prototype uses DuckDuckGo search through the `ddgs` Python package. Search availability and results can vary.
    """)
    st.subheader("What this prototype does")
    st.markdown("""
    - Answers general questions through a configured LLM.
    - Can search the public web for current information and provide result links.
    - Extracts text from uploaded PDF, DOCX, TXT, Markdown, and CSV files.
    - Retrieves relevant document chunks and sends them to the model as context.
    - Supports response language selection and optional speech integrations.
    - Uses SQLite locally for chat history and document metadata.
    """)
    st.warning("No AI system literally knows everything or guarantees real-time accuracy. Live web search and an LLM provider must be configured for current, broad answers. Uploaded files are private to this app's local storage; do not deploy publicly without access control.")
    st.code("pip install -r requirements.txt\nstreamlit run app.py", language="bash")
