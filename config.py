"""Sozlamalar — hammasi .env fayldan o'qiladi."""
import os
from dotenv import load_dotenv

load_dotenv()

# ===== Telegram =====
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# ===== AI kalitlari =====
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

# ===== Bepul limit (taxminiy — router shu asosda yukni taqsimlaydi) =====
GROQ_RPM = int(os.getenv("GROQ_RPM", "25"))
GROQ_RPD = int(os.getenv("GROQ_RPD", "900"))
GEMINI_RPM = int(os.getenv("GEMINI_RPM", "12"))
GEMINI_RPD = int(os.getenv("GEMINI_RPD", "1400"))

# ===== Xatti-harakat =====
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "8"))   # nechta oxirgi xabar eslab qolinsin
MIN_DELAY = float(os.getenv("MIN_DELAY", "1.5"))   # javobdan oldingi "insoncha" pauza (sekund)
MAX_DELAY = float(os.getenv("MAX_DELAY", "4.0"))

# ===== Egasi va zaxira xabari =====
OWNER_NAME = os.getenv("OWNER_NAME", "Mirsoat Xolmurodov").strip()

# AI limiti tugasa yoki ishlamasa — bot mana shu xabarni yuboradi (soxta javob bermaydi)
# .env da bo'sh qoldirilsa (yoki umuman yo'q bo'lsa) — quyidagi standart ishlatiladi.
FALLBACK_MESSAGE = os.getenv("FALLBACK_MESSAGE", "").strip() or (
    f"Assalomu alaykum! Men {OWNER_NAME}ning yordamchisiman. "
    f"Ayni damda javob bera olmayapman — iltimos, {OWNER_NAME} o'zlari "
    f"javob berishlarini biroz kutib turing. Rahmat! 🙏"
)
