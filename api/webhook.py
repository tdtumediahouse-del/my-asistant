"""
Vercel serverless webhook — Telegram Business xabarlariga javob beradi.

Telegram yangilanish (update) kelganda shu funksiya chaqiriladi:
  Telegram -> POST /api/webhook -> Groq/Gemini -> javob -> Telegram

Serverless bo'lgani uchun holat (xotira) saqlanmaydi: har xabar mustaqil javob oladi.
AI limiti/xatosi bo'lsa soxta javob bermay, FALLBACK_MESSAGE yuboriladi.
"""
from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _env(key, default=""):
    return (os.environ.get(key) or default).strip()


BOT_TOKEN = _env("BOT_TOKEN")
GROQ_API_KEY = _env("GROQ_API_KEY")
GEMINI_API_KEY = _env("GEMINI_API_KEY")
GROQ_MODEL = _env("GROQ_MODEL", "llama-3.3-70b-versatile")
GEMINI_MODEL = _env("GEMINI_MODEL", "gemini-2.5-flash")
OWNER_NAME = _env("OWNER_NAME", "Mirsoat Xolmurodov")
FALLBACK_MESSAGE = _env("FALLBACK_MESSAGE") or (
    f"Assalomu alaykum! Men {OWNER_NAME}ning yordamchisiman. "
    f"Ayni damda javob bera olmayapman — iltimos, {OWNER_NAME} o'zlari "
    f"javob berishlarini biroz kutib turing. Rahmat! 🙏"
)


def _read_character():
    path = os.path.join(ROOT, "persona", "character.txt")
    try:
        out = []
        for line in open(path, encoding="utf-8").read().splitlines():
            if line.strip().startswith("#"):
                continue
            out.append(line)
        return "\n".join(out).strip()
    except Exception:
        return ""


def build_system_prompt():
    owner = OWNER_NAME
    character = _read_character()
    return f"""Sen — {owner}ning shaxsiy YORDAMCHISISAN (sun'iy intellekt yordamchi).
{owner} band bo'lganda yoki hozir javob bera olmaganda, uning o'rniga suhbatdoshlarga
javob berasan.

MUHIM QOIDA — O'ZINGNI TANISHTIRISH:
- Doim o'zingni "{owner}ning yordamchisi" sifatida tanishtir.
- HECH QACHON o'zingni {owner}ning O'ZI deb ko'rsatma.
- Suhbat boshida yoki "kimsan / bu kim / {owner}mi?" deb so'ralsa, aniq ayt:
  "Assalomu alaykum! Men {owner}ning yordamchisiman."

===== {owner} HAQIDA MA'LUMOT (savollarga shu asosda javob ber) =====
{character or "(character.txt hali to'ldirilmagan)"}

===== JAVOB BERISH QOIDALARI =====
- Muloyim, samimiy va professional yoz. Suhbatdoshga "siz" shaklida murojaat qil.
- Suhbatdosh qaysi tilda yozsa — o'sha tilda javob ber (o'zbekcha/ruscha/inglizcha).
- Qo'pol so'z ishlatma, mubolag'a va keraksiz maqtovdan saqlan.
- JIDDIY masalalarda (pul/to'lov, uchrashuv vaqti yoki joyi, muhim va'da, shartnoma,
  narx bo'yicha yakuniy kelishuv) o'zingdan qat'iy qaror qabul QILMA va aniq va'da BERMA.
  Bunday hollarda: "Bu masalada {owner} o'zlari aniq javob beradilar, biroz kutib turing"
  deb yumshoq ayt.
- Bilmagan yoki ishonchsiz narsani o'ylab topma.
- Qisqa va lo'nda yoz — 1-3 jumla yetarli."""


SYSTEM_PROMPT = build_system_prompt()


def _post_json(url, payload, headers=None, timeout=30):
    data = json.dumps(payload).encode()
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _groq(system, text):
    data = _post_json(
        "https://api.groq.com/openai/v1/chat/completions",
        {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
            "temperature": 0.9,
            "max_tokens": 600,
        },
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
    )
    return data["choices"][0]["message"]["content"].strip()


def _gemini(system, text):
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    data = _post_json(
        url,
        {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": text}]}],
            "generationConfig": {"temperature": 0.9, "maxOutputTokens": 600},
        },
    )
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def generate(text, prefer_gemini=False):
    """Groq/Gemini'dan javob oladi. Biri ishlamasa ikkinchisi. Hech biri bo'lmasa None."""
    chain = []
    if prefer_gemini:
        if GEMINI_API_KEY:
            chain.append(_gemini)
        if GROQ_API_KEY:
            chain.append(_groq)
    else:
        if GROQ_API_KEY:
            chain.append(_groq)
        if GEMINI_API_KEY:
            chain.append(_gemini)
    for fn in chain:
        try:
            reply = fn(SYSTEM_PROMPT, text)
            if reply:
                return reply
        except Exception:
            continue
    return None


def send_message(chat_id, text, business_connection_id):
    try:
        _post_json(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            {
                "chat_id": chat_id,
                "text": text,
                "business_connection_id": business_connection_id,
            },
        )
    except Exception:
        pass


def process_update(update):
    msg = update.get("business_message")
    if not msg:
        return
    text = msg.get("text") or msg.get("caption")
    if not text:
        return
    chat_id = (msg.get("chat") or {}).get("id")
    from_id = (msg.get("from") or {}).get("id")
    bcid = msg.get("business_connection_id")
    if chat_id is None or bcid is None:
        return
    # Faqat mijozning KIRUVCHI xabari: shaxsiy chatda from.id == chat.id bo'ladi.
    # Egasi o'zi yozgan yoki botning o'z xabari (from != chat) — javob berilmaydi (loop bo'lmaydi).
    if from_id != chat_id:
        return
    prefer_gemini = bool(update.get("update_id", 0) % 2)  # yukni ~50/50 taqsimlash
    reply = generate(text, prefer_gemini) or FALLBACK_MESSAGE
    send_message(chat_id, reply, bcid)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):  # health-check
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Yordamchi bot webhook ishlayapti")

    def do_POST(self):
        length = int(self.headers.get("content-length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            update = json.loads(raw.decode() or "{}")
            process_update(update)
        except Exception:
            pass
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
