"""
Multilingual Education Chatbot (India)
- Login / Sign-up (SQLite, salted PBKDF2 hashes)
- 4 languages: English, Hindi, Tamil, Bengali (UI + replies)
- Custom response criteria (tone, length, your own rules)
- Real-time streaming answers (Claude) + optional live web search
- Upload institute documents (PDF/DOCX/TXT) -> answers grounded in them

Run:  export ANTHROPIC_API_KEY=sk-ant-...
      streamlit run app.py
"""
import hashlib
import io
import os
import secrets
import sqlite3

import anthropic
import streamlit as st
from docx import Document
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
DB_PATH = "users.db"

# ---------------------------------------------------------------- languages
LANGS = {
    "English": dict(
        name="English", title="🎓 India Education Assistant", login="Login",
        signup="Sign up", user="Username", pwd="Password", bad="Wrong username or password.",
        exists="Username already taken.", created="Account created. Please log in.",
        ask="Ask about any institute, exam, course or anything else...",
        upload="Upload institute documents (PDF, DOCX, TXT)", clear="Clear documents",
        logout="Logout", tone="Tone", length="Answer length", custom="Your own rules",
        web="Use live web search", docs="Documents loaded", lang="Language",
        style="Response criteria", hint="e.g. Always give bullet points, mention official website"),
    "हिन्दी": dict(
        name="Hindi", title="🎓 भारत शिक्षा सहायक", login="लॉगिन",
        signup="साइन अप", user="यूज़रनेम", pwd="पासवर्ड", bad="यूज़रनेम या पासवर्ड गलत है।",
        exists="यह यूज़रनेम पहले से मौजूद है।", created="खाता बन गया। कृपया लॉगिन करें।",
        ask="किसी भी संस्थान, परीक्षा, कोर्स या कुछ भी पूछें...",
        upload="संस्थान के दस्तावेज़ अपलोड करें (PDF, DOCX, TXT)", clear="दस्तावेज़ हटाएँ",
        logout="लॉगआउट", tone="लहजा", length="उत्तर की लंबाई", custom="आपके अपने नियम",
        web="लाइव वेब सर्च", docs="लोड किए गए दस्तावेज़", lang="भाषा",
        style="उत्तर के मापदंड", hint="जैसे: हमेशा बुलेट पॉइंट दें"),
    "தமிழ்": dict(
        name="Tamil", title="🎓 இந்தியக் கல்வி உதவியாளர்", login="உள்நுழை",
        signup="பதிவு செய்", user="பயனர் பெயர்", pwd="கடவுச்சொல்", bad="பயனர் பெயர் அல்லது கடவுச்சொல் தவறு.",
        exists="இந்தப் பெயர் ஏற்கனவே உள்ளது.", created="கணக்கு உருவாக்கப்பட்டது. உள்நுழையவும்.",
        ask="எந்தக் கல்வி நிறுவனம், தேர்வு, படிப்பு பற்றியும் கேளுங்கள்...",
        upload="நிறுவன ஆவணங்களைப் பதிவேற்றவும் (PDF, DOCX, TXT)", clear="ஆவணங்களை நீக்கு",
        logout="வெளியேறு", tone="தொனி", length="பதில் நீளம்", custom="உங்கள் சொந்த விதிகள்",
        web="நேரலை இணையத் தேடல்", docs="ஏற்றப்பட்ட ஆவணங்கள்", lang="மொழி",
        style="பதில் அளவுகோல்கள்", hint="எ.கா: எப்போதும் புள்ளிகளாகக் கொடு"),
    "বাংলা": dict(
        name="Bengali", title="🎓 ভারত শিক্ষা সহকারী", login="লগইন",
        signup="সাইন আপ", user="ইউজারনেম", pwd="পাসওয়ার্ড", bad="ইউজারনেম বা পাসওয়ার্ড ভুল।",
        exists="ইউজারনেমটি আগে থেকেই আছে।", created="অ্যাকাউন্ট তৈরি হয়েছে। লগইন করুন।",
        ask="যেকোনো প্রতিষ্ঠান, পরীক্ষা, কোর্স বা অন্য কিছু জিজ্ঞাসা করুন...",
        upload="প্রতিষ্ঠানের নথি আপলোড করুন (PDF, DOCX, TXT)", clear="নথি মুছুন",
        logout="লগআউট", tone="সুর", length="উত্তরের দৈর্ঘ্য", custom="আপনার নিজস্ব নিয়ম",
        web="লাইভ ওয়েব সার্চ", docs="লোড করা নথি", lang="ভাষা",
        style="উত্তরের মানদণ্ড", hint="যেমন: সবসময় বুলেট পয়েন্টে দিন"),
}

# ------------------------------------------------------------------- auth db
def db():
    con = sqlite3.connect(DB_PATH)
    con.execute("CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY, salt BLOB, hash BLOB)")
    return con


def _hash(pw: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 200_000)


def register(username: str, pw: str) -> bool:
    salt = secrets.token_bytes(16)
    try:
        with db() as con:
            con.execute("INSERT INTO users VALUES(?,?,?)", (username, salt, _hash(pw, salt)))
        return True
    except sqlite3.IntegrityError:
        return False


def verify(username: str, pw: str) -> bool:
    row = db().execute("SELECT salt, hash FROM users WHERE username=?", (username,)).fetchone()
    return bool(row) and secrets.compare_digest(_hash(pw, row[0]), row[1])


# --------------------------------------------------------- document handling
def extract_text(f) -> str:
    name = f.name.lower()
    data = f.read()
    if name.endswith(".pdf"):
        return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)
    if name.endswith(".docx"):
        return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
    return data.decode("utf-8", errors="ignore")


def chunk(text: str, size=900, overlap=150):
    text = " ".join(text.split())
    return [text[i:i + size] for i in range(0, len(text), size - overlap) if text[i:i + size].strip()]


def rebuild_index():
    chunks = st.session_state.chunks
    if chunks:
        # char n-grams work across Latin, Devanagari, Tamil and Bengali scripts
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True)
        st.session_state.vec = vec
        st.session_state.mat = vec.fit_transform([c[1] for c in chunks])
    else:
        st.session_state.vec = st.session_state.mat = None


def retrieve(query: str, k=5):
    if not st.session_state.get("vec"):
        return []
    sims = cosine_similarity(st.session_state.vec.transform([query]), st.session_state.mat)[0]
    top = sims.argsort()[::-1][:k]
    return [st.session_state.chunks[i] for i in top if sims[i] > 0.05]


# ------------------------------------------------------------------- the LLM
def system_prompt(lang_name, tone, length, custom, has_docs):
    return f"""You are an education assistant for India with broad world knowledge, specialising in
Indian schools, colleges, universities, entrance exams, admissions, scholarships, courses and careers.

Rules:
- ALWAYS reply in {lang_name}, even if the question is in another language (keep proper names, exam names
  and URLs in their original form).
- Tone: {tone}. Length: {length}.
- Extra rules from the user (follow them): {custom or 'none'}
- {'Uploaded institute documents are provided inside <documents>. Prefer them over general knowledge, and say which document you used. If the answer is not in them, say so, then answer from general knowledge and mark it clearly.' if has_docs else 'No documents are uploaded.'}
- Never invent facts about institutes (fees, cutoffs, ranks, dates, phone numbers). If unsure, say so and
  point to the institute's official website or the relevant authority (UGC, AICTE, NIRF, NTA, etc.).
- Fees, deadlines and rankings change every year: use web search when it is enabled."""


def stream_answer(history, sys_prompt, use_web):
    client = anthropic.Anthropic()
    kwargs = {}
    if use_web:
        kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]
    with client.messages.stream(model=MODEL, max_tokens=1500, system=sys_prompt,
                                messages=history, **kwargs) as s:
        for text in s.text_stream:
            yield text


# ------------------------------------------------------------------------ UI
st.set_page_config(page_title="India Education Assistant", page_icon="🎓", layout="wide")
ss = st.session_state
ss.setdefault("user", None)
ss.setdefault("messages", [])
ss.setdefault("chunks", [])      # list of (filename, text)
ss.setdefault("doc_names", [])

with st.sidebar:
    lang_key = st.selectbox("🌐 Language / भाषा", list(LANGS))
    T = LANGS[lang_key]

if not ss.user:  # ------------------------------------------------ login page
    st.title(T["title"])
    tab_in, tab_up = st.tabs([T["login"], T["signup"]])
    with tab_in:
        u = st.text_input(T["user"], key="li_u")
        p = st.text_input(T["pwd"], type="password", key="li_p")
        if st.button(T["login"], key="li_b"):
            if verify(u.strip(), p):
                ss.user = u.strip()
                st.rerun()
            else:
                st.error(T["bad"])
    with tab_up:
        u2 = st.text_input(T["user"], key="su_u")
        p2 = st.text_input(T["pwd"], type="password", key="su_p")
        if st.button(T["signup"], key="su_b") and u2.strip() and len(p2) >= 6:
            st.success(T["created"]) if register(u2.strip(), p2) else st.error(T["exists"])
    st.stop()

# ------------------------------------------------------------- chat page
with st.sidebar:
    st.caption(f"👤 {ss.user}")
    st.subheader(T["style"])
    tone = st.selectbox(T["tone"], ["friendly", "formal", "simple (like for a school student)", "detailed/academic"])
    length = st.selectbox(T["length"], ["short", "medium", "long and detailed"], index=1)
    custom = st.text_area(T["custom"], placeholder=T["hint"])
    use_web = st.toggle(T["web"], value=True)

    st.subheader("📄 " + T["upload"])
    files = st.file_uploader("", type=["pdf", "docx", "txt"], accept_multiple_files=True,
                             label_visibility="collapsed")
    for f in files or []:
        if f.name not in ss.doc_names:
            ss.chunks += [(f.name, c) for c in chunk(extract_text(f))]
            ss.doc_names.append(f.name)
            rebuild_index()
    if ss.doc_names:
        st.write(f"**{T['docs']}:** " + ", ".join(ss.doc_names))
        if st.button(T["clear"]):
            ss.chunks, ss.doc_names = [], []
            rebuild_index()
            st.rerun()
    if st.button(T["logout"]):
        ss.clear()
        st.rerun()

st.title(T["title"])
for m in ss.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if q := st.chat_input(T["ask"]):
    ss.messages.append({"role": "user", "content": q})
    with st.chat_message("user"):
        st.markdown(q)

    hits = retrieve(q)
    ctx = ""
    if hits:
        ctx = "<documents>\n" + "\n\n".join(f"[{n}] {t}" for n, t in hits) + "\n</documents>\n\n"

    history = [{"role": m["role"], "content": m["content"]} for m in ss.messages[-12:]]
    history[-1] = {"role": "user", "content": ctx + q}

    with st.chat_message("assistant"):
        try:
            sp = system_prompt(T["name"], tone, length, custom, bool(ss.chunks))
            answer = st.write_stream(stream_answer(history, sp, use_web))
        except Exception as e:  # missing key, network, etc.
            answer = f"⚠️ {e}"
            st.error(answer)
    ss.messages.append({"role": "assistant", "content": answer})
