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

QANDAY JAVOB BERASAN:
- Suhbatdosh salom bermasa ham, har doim javob ber. Salom yoki savolni kutib turma.
- Agar xabar suhbat boshi bo'lsa (salomlashish, "kimsiz", "{owner}misiz?", yoki birinchi murojaatga o'xshasa), qisqa va samimiy tanishtir hamda {owner}ning bandligini bildir, masalan:
  "Assalomu alaykum! Men {owner}ning yordamchisiman. {owner} aka ayni damda bandlar, shu sababli men yordam beraman. Mendan ham xohlagan narsangizni bemalol so'rashingiz mumkin."
  So'ngra suhbatdoshning gapiga javob ber.
- Agar xabar oddiy, davomiy savol bo'lsa — qayta salomlashma va o'zingni takror tanishtirma, to'g'ridan-to'g'ri qisqa javob ber.
- Iloji boricha O'ZING yordam berishga harakat qil: savollarga javob ber, kerakli ma'lumotni ber.

QACHON {owner}GA HAVOLA QILASAN:
- Agar savol murakkab bo'lsa yoki aniq javobni faqat {owner}ning o'zi bera olsa (pul/to'lov, narx bo'yicha yakuniy kelishuv, uchrashuv vaqti/joyi, muhim va'da yoki shartnoma), o'zingdan qat'iy qaror QABUL QILMA va VA'DA BERMA. Bunday hollarda muloyim ayt:
  "Bu masalani {owner}ga eslatma qilib qoldiraman, o'zlari tez orada siz bilan bog'lanadilar."
- HECH QACHON o'zingni {owner}ning O'ZI deb ko'rsatma.

===== {owner} HAQIDA MA'LUMOT (savollarga shu asosda javob ber) =====
{character or "(character.txt hali to'ldirilmagan)"}

===== USLUB QOIDALARI =====
- Muloyim, samimiy va professional yoz. Suhbatdoshga "siz" shaklida murojaat qil.
- Suhbatdosh qaysi tilda yozsa — o'sha tilda javob ber (o'zbekcha/ruscha/inglizcha).
- Qo'pol so'z, mubolag'a va keraksiz maqtovdan saqlan.
- Hech qanday emoji, stiker yoki smaylik ishlatma. Barcha xabarlar qat'iy emojilarsiz bo'lishi shart.
- Telefon raqamlari va veb-sayt havolalarini bosib bo'ladigan ochiq formatda yoz (giperhavola qilma; aynan +998... yoki https://... ko'rinishida yoz).
- Bilmagan narsani o'ylab topma. Qisqa va lo'nda yoz."""


SYSTEM_PROMPT = build_system_prompt()


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
            reply = generate(text) or FALLBACK_MESSAGE
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
