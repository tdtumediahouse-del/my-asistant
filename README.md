# Yordamchi bot 🤖

Telegram **Business** orqali ishlaydigan bot. Sizga kelgan xabarlarga **sizning
yordamchingiz** sifatida javob beradi. Groq + Gemini bilan ishlaydi (biri limitga
yetsa — ikkinchisiga o'tadi). AI limiti tugasa soxta javob bermay, "egasi o'zi javob
beradi" deb yozadi.

Ikki xil ishlash usuli bor:

| Usul | Fayl | Qayerda |
|------|------|---------|
| **Webhook** (deploy uchun) | `api/webhook.py` | Vercel — bepul, karta kerak emas, 24/7 |
| **Polling** (lokal test) | `bot.py` | O'z kompyuteringizda sinash uchun |

---

## A) Vercel'ga deploy (asosiy, bepul, 24/7)

### 1. Kodni GitHub'ga joylang
Loyihani GitHub repositoriyasiga yuklang (`.env` yuklanmaydi — u `.gitignore` da).

### 2. Vercel'ga import qiling
1. https://vercel.com — GitHub bilan kiring (karta kerak emas).
2. **Add New → Project** → repositoriyani tanlang → **Deploy**.

### 3. Muhit o'zgaruvchilarini (env) qo'shing
Vercel loyiha → **Settings → Environment Variables** ga quyidagilarni qo'shing:

| Nomi | Qiymati |
|------|---------|
| `BOT_TOKEN` | @BotFather token |
| `GROQ_API_KEY` | Groq kaliti |
| `GEMINI_API_KEY` | Gemini kaliti |
| `GEMINI_MODEL` | `gemini-2.5-flash` |
| `OWNER_NAME` | `Mirsoat Xolmurodov` |

Keyin **Redeploy** qiling.

### 4. Webhook'ni ulang
Loyihangiz manzili `https://SIZNING-LOYIHA.vercel.app` bo'ladi. Lokal terminalda:

```powershell
python set_webhook.py https://SIZNING-LOYIHA.vercel.app/api/webhook
python set_webhook.py info     # tekshirish
```

### 5. Botni Business'ga ulang
Telegram → **Settings → Business → Chatbots** → **@jduadyfuafbot** → "Reply to messages" yoqing.

Tayyor! Endi kimdir yozsa, bot 24/7 javob beradi.

---

## B) Lokal test (ixtiyoriy)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-local.txt
copy .env.example .env      # keyin .env ni to'ldiring
python bot.py
```

> Diqqat: lokal `bot.py` polling ishlatadi. Vercel webhook bilan bir vaqtda **ikkalasini
> birga ishlatmang** — Telegram bittasiga ulanadi. Webhook o'rnatilgan bo'lsa, lokal test
> uchun avval `python set_webhook.py delete` qiling.

---

## Sozlash

- **Xarakter:** `persona/character.txt` — bot kim nomidan va qanday javob berishini belgilaydi.
- **Zaxira xabar:** `OWNER_NAME` va (ixtiyoriy) `FALLBACK_MESSAGE` env orqali.

## Boshqaruv (faqat lokal `bot.py` da)
Egasi o'ziga yozadi: `.off` (o'chirish), `.on` (yoqish), `.status`. *(Webhook versiyada
hozircha yo'q — kerak bo'lsa qo'shamiz.)*

## Eslatmalar
- Webhook serverless bo'lgani uchun suhbat tarixi saqlanmaydi (har xabar mustaqil javob).
  Kerak bo'lsa bepul Upstash Redis bilan xotira qo'shsa bo'ladi.
- `gemini-2.0-flash` o'rniga `gemini-2.5-flash` ishlatilyapti (2.0 ning bepul kvotasi tugagan edi).
