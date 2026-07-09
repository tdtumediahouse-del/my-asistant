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
import time
try:
    from upstash_redis import Redis
except ImportError:
    Redis = None

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
    f"javob berishlarini biroz kutib turing. Rahmat!"
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
{owner} hozir band bo'lgani uchun uning o'rniga suhbatdoshlarga sen javob berasan.
Sen uning O'ZI EMASSAN — doim uning yordamchisisan.

QANDAY JAVOB BERASAN (MUHIM QOIDALAR):
1. MIJOZ NIMA SO'RASA FAQAT SHUNGA JAVOB BER. Ortiqcha gap gapirma. Agar suhbatdosh so'ramasa, {owner}ning shaxsiy ma'lumotlari, nima ish qilishi, qayerda o'qishi kabi narsalarni aslo yoza ko'rma.
2. {owner}ni mijoz bilan muhokama qilma. "U bunday inson, u yerda o'qiydi" kabi gaplar kerak emas. Qisqa va lo'nda bo'l.
3. Har bir yozgan javobingda o'zingni yordamchi (asistent) ekanligingni albatta bildirib o't. Masalan: "Sizga asistent javob beryapti".
4. Har bir xabarda qayta-qayta salomlasha ko'rma. Salomlashishni faqatgina suhbatning eng boshida 1 marta ayt.
5. Agar suhbatdosh bergan savolning javobini aniq bilmasang, o'zingdan hech narsa o'ylab topma. Bunday holda va boshqa barcha murakkab holatlarda qisqa qilib: "Bu masalani {owner}ga eslatma qilib qoldiraman, o'zlari sizga javob beradilar" deb ayt.

===== {owner} HAQIDA MA'LUMOT (savollarga shu asosda javob ber, lekin ortiqcha gapirma) =====
{character or "(character.txt hali to'ldirilmagan)"}

===== USLUB QOIDALARI =====
- Muloyim, samimiy va professional yoz. Suhbatdoshga "siz" shaklida murojaat qil.
- Suhbatdosh qaysi tilda yozsa — o'sha tilda javob ber (o'zbekcha/ruscha/inglizcha).
- Qo'pol so'z, mubolag'a va keraksiz maqtovdan saqlan. Hech qanday emoji, stiker yoki smaylik ishlatma. Barcha xabarlar qat'iy emojilarsiz bo'lishi shart.
- Telefon raqamlari va veb-sayt havolalarini ochiq matn qilib yoz (+998... yoki https://...)."""


SYSTEM_PROMPT = build_system_prompt()

UPSTASH_URL = _env("UPSTASH_REDIS_REST_URL")
UPSTASH_TOKEN = _env("UPSTASH_REDIS_REST_TOKEN")
redis_client = None
if Redis and UPSTASH_URL and UPSTASH_TOKEN:
    redis_client = Redis(url=UPSTASH_URL, token=UPSTASH_TOKEN)

def get_history(chat_id):
    if not redis_client: return []
    try:
        data = redis_client.get(f"history:{chat_id}")
        if data:
            return json.loads(data) if isinstance(data, str) else data
    except Exception:
        pass
    return []

def save_history(chat_id, history):
    if not redis_client: return
    try:
        history = history[-20:] # Faqat oxirgi 20 ta xabar saqlanadi
        redis_client.setex(f"history:{chat_id}", 15 * 24 * 3600, json.dumps(history))
    except Exception:
        pass


def _post_json(url, payload, headers=None, timeout=30):
    data = json.dumps(payload).encode()
    # User-Agent MUHIM: Groq API Cloudflare ortida — urllib ning standart User-Agent'ini
    # (Python-urllib) "error code: 1010" bilan bloklaydi. Brauzer User-Agent'i bu muammoni yechadi.
    hdrs = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _groq(system, messages_history):
    messages = [{"role": "system", "content": system}]
    messages.extend(messages_history)
    data = _post_json(
        "https://api.groq.com/openai/v1/chat/completions",
        {
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": 0.9,
            "max_tokens": 600,
        },
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
    )
    return data["choices"][0]["message"]["content"].strip()


def _gemini(system, messages_history):
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    contents = []
    for msg in messages_history:
        role = "model" if msg["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        
    data = _post_json(
        url,
        {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": contents,
            "generationConfig": {"temperature": 0.9, "maxOutputTokens": 600},
        },
    )
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def generate(messages_history, prefer_gemini=False):
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
            reply = fn(SYSTEM_PROMPT, messages_history)
            if reply:
                return reply
        except Exception:
            continue
    return None


def send_message(chat_id, text, business_connection_id=None):
    try:
        payload = {
            "chat_id": chat_id,
            "text": text,
        }
        if business_connection_id:
            payload["business_connection_id"] = business_connection_id
            
        _post_json(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            payload,
        )
    except Exception:
        pass


def process_update(update):
    # Oddiy xabarlarni yoki business xabarlarni ajratib olamiz
    is_business = "business_message" in update
    msg = update.get("business_message") or update.get("message")
    
    if not msg:
        return
        
    text = msg.get("text") or msg.get("caption")
    if not text:
        return
        
    chat_id = (msg.get("chat") or {}).get("id")
    from_id = (msg.get("from") or {}).get("id")
    
    if not chat_id:
        return

    # Agar bu botning o'ziga to'g'ridan-to'g'ri yozilgan xabar bo'lsa (Business emas)
    if not is_business:
        if text.startswith("/start"):
            welcome = (
                "Assalomu alaykum! Men yordamchi AI botman.\n\n"
                "Meni ishlashim uchun Telegram sozlamalaridan 'Telegram Business' bo'limiga kiring "
                "va meni ulab oling. Shundan so'ng mijozlaringizga sizning o'rningizga javob berishni boshlayman!"
            )
            send_message(chat_id, welcome)
        else:
            # Oddiy xabarlarga ham AI sifatida javob beraveradi (sinab ko'rish uchun qulay)
            history = get_history(chat_id)
            history.append({"role": "user", "content": text})
            reply = generate(history) or FALLBACK_MESSAGE
            history.append({"role": "assistant", "content": reply})
            save_history(chat_id, history)
            send_message(chat_id, reply)
        return

    # Faqat mijozning KIRUVCHI xabari: shaxsiy chatda from.id == chat.id bo'ladi.
    # Egasi o'zi yozgan yoki botning o'z xabari (from != chat) — javob berilmaydi (loop bo'lmaydi).
    if from_id != chat_id:
        return
        
    bcid = msg.get("business_connection_id")
    if not bcid:
        return
        
    prefer_gemini = bool(update.get("update_id", 0) % 2)  # yukni ~50/50 taqsimlash
    history = get_history(chat_id)
    history.append({"role": "user", "content": text})
    reply = generate(history, prefer_gemini) or FALLBACK_MESSAGE
    history.append({"role": "assistant", "content": reply})
    save_history(chat_id, history)
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
