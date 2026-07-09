"""
Yordamchi bot — Telegram Business orqali sizning o'rningizga, sizning
uslubingizda javob beradigan bot.

Ishga tushirish:  python bot.py

Egasi (siz) uchun buyruqlar — o'zingizga (yoki istalgan mijozga) yozing:
  .off     -> avto-javobni o'chiradi (o'sha suhbat uchun)
  .on      -> avto-javobni yoqadi
  .status  -> holatni ko'rsatadi
"""
import asyncio
import logging
import random
import sys
from collections import defaultdict, deque

# Windows konsolida emoji-li loglar xato bermasligi uchun UTF-8 ga o'tkazamiz
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from aiogram import Bot, Dispatcher
from aiogram.types import BusinessConnection, Message

import config
from ai_router import ProviderError, build_router
from persona import build_system_prompt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("yordamchi")

if not config.BOT_TOKEN:
    raise SystemExit("BOT_TOKEN yo'q. .env faylni to'ldiring (.env.example dan nusxa oling).")

bot = Bot(config.BOT_TOKEN)
dp = Dispatcher()
router = build_router()
SYSTEM_PROMPT = build_system_prompt()

# ---- holat (xotira) ----
owners: dict[str, int] = {}                       # business_connection_id -> egasining user_id
enabled: dict[str, bool] = defaultdict(lambda: True)   # business_connection_id -> yoqilgan/o'chirilgan
history: dict[tuple, deque] = defaultdict(lambda: deque(maxlen=config.MAX_HISTORY))


async def say(chat_id: int, text: str, bcid: str) -> None:
    """Business akkaunt nomidan xabar yuborish."""
    await bot.send_message(chat_id, text, business_connection_id=bcid)


@dp.business_connection()
async def on_connection(bc: BusinessConnection) -> None:
    owners[bc.id] = bc.user.id
    state = "ulandi ✅" if bc.is_enabled else "uzildi ⛔"
    log.info(f"Business connection {state}  (egasi user_id={bc.user.id})")


@dp.business_message()
async def on_business_message(message: Message) -> None:
    bcid = message.business_connection_id
    owner_id = owners.get(bcid)
    key = (bcid, message.chat.id)
    text = message.text or message.caption

    # ----- 1) Egasining o'zi yozgan xabar -----
    if owner_id and message.from_user and message.from_user.id == owner_id:
        cmd = (text or "").strip().lower()
        if cmd == ".off":
            enabled[bcid] = False
            await say(message.chat.id, "🤖 avto-javob o'chirildi", bcid)
            return
        if cmd == ".on":
            enabled[bcid] = True
            await say(message.chat.id, "🤖 avto-javob yoqildi", bcid)
            return
        if cmd == ".status":
            s = "yoqilgan ✅" if enabled[bcid] else "o'chirilgan ⛔"
            await say(message.chat.id, f"🤖 holat: {s}", bcid)
            return
        # Egasi qo'lda javob berdi — kontekstga qo'shamiz, lekin javob bermaymiz
        if text:
            history[key].append({"role": "assistant", "content": text})
        return

    # ----- 2) Mijoz xabari -----
    if not enabled[bcid]:
        return
    if not text:
        return  # v1: faqat matnli xabarlarga javob beramiz

    history[key].append({"role": "user", "content": text})

    # "yozmoqda..." belgisi + insoncha kichik pauza
    try:
        await bot.send_chat_action(message.chat.id, "typing", business_connection_id=bcid)
    except Exception:
        pass
    await asyncio.sleep(random.uniform(config.MIN_DELAY, config.MAX_DELAY))

    try:
        reply, used = await router.generate(SYSTEM_PROMPT, list(history[key]))
    except ProviderError as e:
        # AI limiti tugadi yoki ishlamadi — soxta javob bermaymiz, zaxira xabar yuboramiz
        log.error(f"AI javob bera olmadi: {e}")
        try:
            await say(message.chat.id, config.FALLBACK_MESSAGE, bcid)
        except Exception:
            pass
        return

    history[key].append({"role": "assistant", "content": reply})
    await say(message.chat.id, reply, bcid)
    log.info(f"[{used}] javob yuborildi -> chat {message.chat.id}")


async def main() -> None:
    me = await bot.get_me()
    log.info(f"Yordamchi bot ishga tushdi: @{me.username}")
    log.info(f"Provayderlar: {', '.join(p.name for p in router.providers)}")
    try:
        await dp.start_polling(bot)
    finally:
        await router.close()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("To'xtatildi.")
