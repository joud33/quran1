import json
import sqlite3
from pathlib import Path

import streamlit as st

# -----------------------------
# إعدادات الصفحة
# -----------------------------
st.set_page_config(page_title="مصحف التتبع", layout="wide")

st.markdown("""
<style>
html, body, [class*="css"] { direction: rtl; text-align: right; font-family: Arial; }
.ayah { padding: 10px 12px; border-radius: 10px; margin: 6px 0; border: 1px solid rgba(0,0,0,0.06); }
.unread { background: rgba(0,0,0,0.03); }
.read { background: rgba(46, 204, 113, 0.14); }
.mem { background: rgba(52, 152, 219, 0.14); }
.small { opacity: 0.75; font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)

st.title("📖 مصحف التتبع — قراءة وحفظ")
st.caption("تتبع قراءتك وحفظك للقرآن: الآيات المقروءة بلون، والمحفوظه بلون مختلف.")

# -----------------------------
# قاعدة البيانات (SQLite)
# -----------------------------
DB_PATH = "progress.db"

def db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    con = db()
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS progress (
            user TEXT NOT NULL,
            surah INTEGER NOT NULL,
            ayah INTEGER NOT NULL,
            status TEXT NOT NULL, -- unread/read/mem
            PRIMARY KEY (user, surah, ayah)
        )
    """)
    con.commit()
    con.close()

init_db()

# -----------------------------
# تحميل بيانات القرآن من quran.json
# -----------------------------
QURAN_PATH = Path("quran.json")
if not QURAN_PATH.exists():
    st.error("ما لقيت ملف quran.json في نفس مجلد المشروع. (شوفي التعليمات تحت)")
    st.stop()

with open(QURAN_PATH, "r", encoding="utf-8") as f:
    quran = json.load(f)

# متوقع شكل الملف:
# quran = [{"surah":1,"name":"الفاتحة","ayahs":[{"ayah":1,"text":"..."}, ...]}, ...]
surah_names = [s["name"] for s in quran]
surah_by_index = {i+1: quran[i] for i in range(len(quran))}

# -----------------------------
# أدوات تقدم المستخدم
# -----------------------------
def get_status_map(user: str, surah: int):
    con = db()
    cur = con.cursor()
    cur.execute("SELECT ayah, status FROM progress WHERE user=? AND surah=?", (user, surah))
    rows = cur.fetchall()
    con.close()
    return {ayah: status for ayah, status in rows}

def set_status(user: str, surah: int, ayah: int, status: str):
    con = db()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO progress (user, surah, ayah, status)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user, surah, ayah) DO UPDATE SET status=excluded.status
    """, (user, surah, ayah, status))
    con.commit()
    con.close()

def stats(user: str):
    con = db()
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM progress WHERE user=? AND status='read'", (user,))
    read_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM progress WHERE user=? AND status='mem'", (user,))
    mem_count = cur.fetchone()[0]
    con.close()
    return read_count, mem_count

# -----------------------------
# الشريط الجانبي
# -----------------------------
st.sidebar.header("⚙️ الإعدادات")

user = st.sidebar.text_input("اسم المستخدم", value="مستخدم")
mode = st.sidebar.radio("وضع الاستخدام", ["📗 قراءة", "🧠 حفظ"], horizontal=True)
selected_surah = st.sidebar.selectbox("اختر السورة", list(range(1, len(quran)+1)),
                                      format_func=lambda i: f"{i} - {surah_by_index[i]['name']}")

read_count, mem_count = stats(user)

st.sidebar.divider()
st.sidebar.subheader("📊 إحصائياتك")
st.sidebar.metric("آيات قُرئت", read_count)
st.sidebar.metric("آيات حُفظت", mem_count)

# -----------------------------
# عرض السورة
# -----------------------------
surah_obj = surah_by_index[selected_surah]
ayahs = surah_obj["ayahs"]

status_map = get_status_map(user, selected_surah)

st.subheader(f"سورة {surah_obj['name']}")

# شريط تقدم للسورة
total_ayahs = len(ayahs)
read_in_surah = sum(1 for a in ayahs if status_map.get(a["ayah"]) in ("read", "mem"))
mem_in_surah = sum(1 for a in ayahs if status_map.get(a["ayah"]) == "mem")

c1, c2, c3 = st.columns(3)
c1.metric("آيات السورة", total_ayahs)
c2.metric("المقروء/المحفوظ", read_in_surah)
c3.metric("المحفوظ فقط", mem_in_surah)

st.progress(read_in_surah / max(1, total_ayahs))

st.markdown("<div class='small'>اضغط على زر (تمت القراءة / تم الحفظ) لكل آية لتغيير لونها وحفظ تقدمك.</div>",
            unsafe_allow_html=True)

# -----------------------------
# عرض الآيات مع أزرار
# -----------------------------
for a in ayahs:
    ayah_no = a["ayah"]
    text = a["text"]

    stt = status_map.get(ayah_no, "unread")
    css = "unread" if stt == "unread" else ("read" if stt == "read" else "mem")

    st.markdown(f"<div class='ayah {css}'><b>({ayah_no})</b> {text}</div>", unsafe_allow_html=True)

    b1, b2, b3 = st.columns([1, 1, 3])
    with b1:
        if st.button("✅ قُرئت", key=f"read_{selected_surah}_{ayah_no}"):
            set_status(user, selected_surah, ayah_no, "read")
            st.rerun()
    with b2:
        if st.button("⭐ حُفظت", key=f"mem_{selected_surah}_{ayah_no}"):
            set_status(user, selected_surah, ayah_no, "mem")
            st.rerun()
    with b3:
        if st.button("↩️ رجّعها غير مقروءة", key=f"un_{selected_surah}_{ayah_no}"):
            set_status(user, selected_surah, ayah_no, "unread")
            st.rerun()

st.caption("✅ البيانات محفوظة تلقائيًا في progress.db داخل نفس المجلد.")
