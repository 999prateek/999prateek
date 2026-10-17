import os
import re
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime
from collections import Counter

def connect(db_path):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con

def init_db(db_path):
    with connect(db_path) as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            language TEXT,
            persona TEXT,
            sources TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            chunks INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            FOREIGN KEY(document_id) REFERENCES documents(id)
        );
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            answer_preview TEXT,
            rating INTEGER NOT NULL,
            comment TEXT,
            created_at TEXT NOT NULL
        );
        """)

def detect_language(text):
    if re.search(r'[\u0900-\u097F]', text):
        return "Hindi / Devanagari"
    if re.search(r'[\u0A80-\u0AFF]', text):
        return "Gujarati"
    if re.search(r'[\u0980-\u09FF]', text):
        return "Bengali"
    if re.search(r'[\u0B80-\u0BFF]', text):
        return "Tamil"
    if re.search(r'[\u0C00-\u0C7F]', text):
        return "Telugu"
    if re.search(r'[\u0C80-\u0CFF]', text):
        return "Kannada"
    if re.search(r'[\u0D00-\u0D7F]', text):
        return "Malayalam"
    hindi_words = {"hai","hain","kaise","kya","mera","mujhe","chahiye","ka","ki","ke","yojana","batao","karo","nahi","mein","mera","kripya"}
    tokens = set(re.findall(r"[a-zA-Z]+", text.lower()))
    if len(tokens & hindi_words) >= 1:
        return "Hinglish"
    return "English / Latin-script"

def translate_text(text, target_language):
    # Intentionally conservative: never silently claim a translation happened without a provider.
    try:
        from deep_translator import GoogleTranslator
        target_map = {"Hindi":"hi", "English":"en", "Gujarati":"gu", "Bengali":"bn", "Tamil":"ta", "Telugu":"te"}
        target = target_map.get(target_language)
        if target:
            return GoogleTranslator(source="auto", target=target).translate(text)
    except Exception:
        pass
    return text

def save_message(db_path, session_id, role, content, language, persona, sources=None):
    import json
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with connect(db_path) as con:
        con.execute("INSERT OR IGNORE INTO sessions(session_id, created_at) VALUES (?,?)", (session_id, now))
        con.execute("""INSERT INTO messages(session_id,role,content,language,persona,sources,created_at)
                       VALUES (?,?,?,?,?,?,?)""",
                    (session_id, role, content, language, persona, json.dumps(sources or [], ensure_ascii=False), now))

def get_history(db_path, session_id):
    import json
    with connect(db_path) as con:
        rows = con.execute("SELECT role,content,sources FROM messages WHERE session_id=? ORDER BY id", (session_id,)).fetchall()
    out=[]
    for r in rows:
        try: sources=json.loads(r["sources"] or "[]")
        except Exception: sources=[]
        out.append({"role":r["role"], "content":r["content"], "sources":sources})
    return out

def save_feedback(db_path, session_id, answer_preview, rating, comment):
    with connect(db_path) as con:
        con.execute("INSERT INTO feedback(session_id,answer_preview,rating,comment,created_at) VALUES (?,?,?,?,?)",
                    (session_id, answer_preview[:400], rating, comment, datetime.utcnow().isoformat(timespec="seconds")+"Z"))

def split_chunks(text, size=850, overlap=120):
    text = re.sub(r'\s+', ' ', text).strip()
    if not text: return []
    chunks=[]
    start=0
    while start < len(text):
        end=min(len(text), start+size)
        chunks.append(text[start:end])
        if end == len(text): break
        start=max(end-overlap, start+1)
    return chunks

def ingest_pdf(db_path, file_path, original_name):
    from pypdf import PdfReader
    reader=PdfReader(str(file_path))
    pages=[]
    for i, page in enumerate(reader.pages):
        try:
            text=page.extract_text() or ""
        except Exception:
            text=""
        if text.strip():
            pages.append(f"[Page {i+1}] {text}")
    content="\n".join(pages)
    chunks=split_chunks(content)
    digest=hashlib.sha256(Path(file_path).read_bytes()).hexdigest()
    with connect(db_path) as con:
        existing=con.execute("SELECT id FROM documents WHERE sha256=?", (digest,)).fetchone()
        if existing:
            return 0
        cur=con.execute("INSERT INTO documents(filename,stored_path,sha256,chunks,created_at) VALUES (?,?,?,?,?)",
                        (original_name, str(file_path), digest, len(chunks), datetime.utcnow().isoformat(timespec="seconds")+"Z"))
        doc_id=cur.lastrowid
        con.executemany("INSERT INTO chunks(document_id,chunk_index,content) VALUES (?,?,?)",
                        [(doc_id,i,c) for i,c in enumerate(chunks)])
    return len(chunks)

def retrieve(db_path, question, limit=4):
    # Lightweight token-overlap retrieval works without external model downloads.
    # For production, replace with multilingual embeddings + pgvector/Qdrant.
    stop=set("the a an is are was were to of and or in on for with how what when where can i you me my please tell about this that from ka ki ke hai hain kya mujhe batao".split())
    qtokens=set(re.findall(r'[\w\u0900-\u097F]+', question.lower()))-stop
    if not qtokens: return []
    with connect(db_path) as con:
        rows=con.execute("""SELECT c.content,d.filename,c.chunk_index FROM chunks c
                             JOIN documents d ON d.id=c.document_id""").fetchall()
    scored=[]
    for r in rows:
        tokens=set(re.findall(r'[\w\u0900-\u097F]+', r["content"].lower()))
        score=len(qtokens & tokens) / max(1, len(qtokens))
        if score > 0:
            scored.append((score, r["filename"], r["chunk_index"], r["content"]))
    scored.sort(reverse=True, key=lambda x:x[0])
    return [{"score":s,"filename":f,"chunk_index":i,"content":c} for s,f,i,c in scored[:limit]]

def call_llm(question, context, target_language, persona):
    endpoint=os.getenv("OPENAI_BASE_URL")
    api_key=os.getenv("OPENAI_API_KEY")
    model=os.getenv("LLM_MODEL", "llama-3.1-8b-instruct")
    if not endpoint or not api_key:
        return None
    try:
        import requests
        prompt = f"""You are RajBhasha AI, a careful Rajasthan education information assistant.
User role: {persona}. Respond in {target_language} (if Auto-detect, match user's language).
Use only the supplied context for official policy claims. If context is insufficient, clearly say so and suggest checking the relevant official department.
Do not invent deadlines, eligibility, amounts, URLs, or rules. Be concise and accessible.
Context:
{context[:9000] if context else '[No matching document context found]'}
Question: {question}"""
        response=requests.post(endpoint.rstrip("/")+"/chat/completions",
            headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json"},
            json={"model":model,"messages":[{"role":"system","content":"You provide safe, source-grounded education assistance."},{"role":"user","content":prompt}],"temperature":0.2},
            timeout=45)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None

def answer_question(db_path, question, response_language, persona):
    detected=detect_language(question)
    target=detected if response_language == "Auto-detect" else response_language.replace(" (beta)","")
    hits=retrieve(db_path, question)
    context="\n\n".join([f"Source: {h['filename']} (chunk {h['chunk_index']+1})\n{h['content']}" for h in hits])
    answer=call_llm(question, context, target, persona)
    sources=[]
    for h in hits:
        label=f"{h['filename']} — section chunk {h['chunk_index']+1}"
        if label not in sources: sources.append(label)
    if answer is None:
        if hits:
            excerpts="\n\n".join([f"**{h['filename']}**\n> {h['content'][:650]}{'…' if len(h['content'])>650 else ''}" for h in hits[:3]])
            answer=("I found potentially relevant material in the uploaded knowledge base. I can’t reliably synthesize it because no LLM endpoint is configured. Please verify the full document before acting.\n\n"
                    + excerpts + "\n\n**Note:** This is a retrieval preview, not a verified official determination.")
        else:
            answer=("I couldn’t find a matching passage in the uploaded knowledge base. I don’t want to guess about official rules, eligibility, or deadlines.\n\n"
                    "Try uploading the relevant official Rajasthan education circular or scholarship guideline, or check the responsible government department’s official website. "
                    "You can also ask me to explain a document you upload.")
    # Optional translation if the LLM output isn't in requested target language; avoid translating when no provider.
    return answer, sources, {"language":target, "detected_language":detected}

def transcribe_audio(audio_bytes):
    try:
        from faster_whisper import WhisperModel
        model=WhisperModel(os.getenv("WHISPER_MODEL","small"), device="cpu", compute_type="int8")
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as f:
            f.write(audio_bytes); f.flush()
            segments, info=model.transcribe(f.name, beam_size=3, vad_filter=True)
            text=" ".join(s.text.strip() for s in segments).strip()
        return text, f"Detected language: {info.language}. Local Whisper transcription."
    except Exception:
        return "", "Speech recognition is optional. Install faster-whisper and ffmpeg, or connect Bhashini/Sarvam using their current API credentials."

def synthesize_audio(text, language):
    try:
        import asyncio, edge_tts
        voice_map={"Hindi":"hi-IN-SwaraNeural","English":"en-IN-NeerjaNeural","Hinglish":"hi-IN-SwaraNeural",
                   "Auto-detect":"hi-IN-SwaraNeural","Gujarati":"gu-IN-DhwaniNeural"}
        voice=voice_map.get(language, "hi-IN-SwaraNeural")
        async def run():
            communicate=edge_tts.Communicate(text[:4000], voice)
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                path=f.name
            await communicate.save(path)
            data=Path(path).read_bytes()
            Path(path).unlink(missing_ok=True)
            return data
        return asyncio.run(run()), "Generated demo audio."
    except Exception:
        return None, "TTS is not configured. Install edge-tts or integrate a production Indic TTS provider."

def get_document_stats(db_path):
    import pandas as pd
    with connect(db_path) as con:
        rows=con.execute("SELECT filename, chunks, created_at FROM documents ORDER BY id DESC").fetchall()
    return pd.DataFrame([dict(r) for r in rows])

def get_analytics(db_path):
    import pandas as pd
    with connect(db_path) as con:
        total_messages=con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        total_sessions=con.execute("SELECT COUNT(DISTINCT session_id) FROM messages").fetchone()[0]
        feedback_count=con.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
        lang=con.execute("SELECT COALESCE(language,'Unknown') language, COUNT(*) count FROM messages WHERE role='user' GROUP BY language ORDER BY count DESC").fetchall()
        recent=con.execute("SELECT role, substr(content,1,140) preview, language, persona, created_at FROM messages ORDER BY id DESC LIMIT 15").fetchall()
        user_msgs=con.execute("SELECT content FROM messages WHERE role='user'").fetchall()
    topics=Counter()
    keywords={
      "Scholarships":["scholarship","छात्रवृत्ति","वजीफा","स्कॉलरशिप"],
      "Admissions":["admission","प्रवेश","दाखिला"],
      "Exams":["exam","परीक्षा","result","परिणाम"],
      "School notices":["notice","circular","आदेश","सूचना"],
      "Teachers":["teacher","शिक्षक","भर्ती"],
      "Digital learning":["online","digital","ई-लर्निंग","course"]
    }
    for row in user_msgs:
        text=row["content"].lower()
        found=False
        for topic, words in keywords.items():
            if any(w in text for w in words):
                topics[topic]+=1; found=True
        if not found: topics["Other"]+=1
    return {
        "total_messages":total_messages, "total_sessions":total_sessions, "feedback_count":feedback_count,
        "by_language":pd.DataFrame([dict(r) for r in lang]),
        "topics":pd.DataFrame([{"topic":k,"count":v} for k,v in topics.most_common()]),
        "recent":pd.DataFrame([dict(r) for r in recent])
    }
