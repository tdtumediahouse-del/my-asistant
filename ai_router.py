"""
Aqlli AI router.

Groq va Gemini'ni birga ishlatadi:
  - So'rovni har safar eng kam ishlatilgan provayderga yuborib, yukni taqsimlaydi
    (shunda bitta provayderning bepul limiti tez tugamaydi).
  - Biri limitga yetsa (429) yoki xato bersa — avtomatik ikkinchisiga o'tadi.
  - Ikkalasi ham ishlamasa — xato qaytaradi (bot jim qoladi).
"""
import time
from functools import partial

import aiohttp

import config


class RateLimited(Exception):
    """Provayder limitga yetdi (HTTP 429)."""


class ProviderError(Exception):
    """Umumiy provayder xatosi."""


class Provider:
    def __init__(self, name, call, rpm, rpd):
        self.name = name
        self.call = call          # async fn(session, system, messages) -> str
        self.rpm = rpm
        self.rpd = rpd
        self._minute = []         # oxirgi 60 sekunddagi so'rov vaqtlari
        self._day_count = 0
        self._day_reset = time.time() + 86400
        self.cooldown_until = 0.0

    def _refresh(self, now):
        self._minute = [t for t in self._minute if now - t < 60]
        if now >= self._day_reset:
            self._day_count = 0
            self._day_reset = now + 86400

    def available(self, now):
        self._refresh(now)
        if now < self.cooldown_until:
            return False
        if len(self._minute) >= self.rpm:
            return False
        if self._day_count >= self.rpd:
            return False
        return True

    def load(self, now):
        """0..1 — kunlik limitning qancha qismi ishlatilgan."""
        self._refresh(now)
        return self._day_count / self.rpd if self.rpd else 1.0

    def record(self, now):
        self._minute.append(now)
        self._day_count += 1

    def trip(self, now, seconds):
        self.cooldown_until = now + seconds


class AIRouter:
    def __init__(self, providers):
        self.providers = providers
        self._session = None

    async def _session_get(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def generate(self, system, messages):
        """(javob_matni, provayder_nomi) qaytaradi yoki ProviderError tashlaydi."""
        session = await self._session_get()
        now = time.time()

        ready = [p for p in self.providers if p.available(now)]
        ready.sort(key=lambda p: p.load(now))          # eng kam ishlatilgani birinchi
        # zaxira: hech biri tayyor bo'lmasa ham baribir sinab ko'ramiz
        order = ready or sorted(self.providers, key=lambda p: p.cooldown_until)

        last_err = None
        for p in order:
            try:
                text = await p.call(session, system, messages)
                p.record(time.time())
                return text, p.name
            except RateLimited as e:
                p.trip(time.time(), 60)      # 1 daqiqa tin
                last_err = e
            except Exception as e:
                p.trip(time.time(), 30)      # 30 sekund tin
                last_err = e
        raise ProviderError(f"Hamma provayderlar ishlamadi: {last_err}")


# ---------------------------------------------------------------------------
# Provayder chaqiruvlari
# ---------------------------------------------------------------------------

_TIMEOUT = aiohttp.ClientTimeout(total=40)


async def _groq_call(session, system, messages, *, api_key, model):
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}]
        + [{"role": m["role"], "content": m["content"]} for m in messages],
        "temperature": 0.9,
        "max_tokens": 600,
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    url = "https://api.groq.com/openai/v1/chat/completions"
    async with session.post(url, json=payload, headers=headers, timeout=_TIMEOUT) as r:
        if r.status == 429:
            raise RateLimited("groq 429")
        if r.status >= 400:
            raise ProviderError(f"groq {r.status}: {await r.text()}")
        data = await r.json()
        return data["choices"][0]["message"]["content"].strip()


async def _gemini_call(session, system, messages, *, api_key, model):
    contents = []
    for m in messages:
        role = "model" if m["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.9, "maxOutputTokens": 600},
    }
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    async with session.post(url, json=payload, timeout=_TIMEOUT) as r:
        if r.status == 429:
            raise RateLimited("gemini 429")
        if r.status >= 400:
            raise ProviderError(f"gemini {r.status}: {await r.text()}")
        data = await r.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError):
            # Gemini ba'zan xavfsizlik filtri tufayli bo'sh javob qaytaradi
            raise ProviderError(f"gemini bo'sh javob: {data}")


def build_router():
    providers = []
    if config.GROQ_API_KEY:
        providers.append(
            Provider(
                "groq",
                partial(_groq_call, api_key=config.GROQ_API_KEY, model=config.GROQ_MODEL),
                rpm=config.GROQ_RPM,
                rpd=config.GROQ_RPD,
            )
        )
    if config.GEMINI_API_KEY:
        providers.append(
            Provider(
                "gemini",
                partial(_gemini_call, api_key=config.GEMINI_API_KEY, model=config.GEMINI_MODEL),
                rpm=config.GEMINI_RPM,
                rpd=config.GEMINI_RPD,
            )
        )
    if not providers:
        raise RuntimeError(
            "Kamida bitta AI kaliti kerak: .env ichida GROQ_API_KEY yoki GEMINI_API_KEY to'ldiring."
        )
    return AIRouter(providers)
