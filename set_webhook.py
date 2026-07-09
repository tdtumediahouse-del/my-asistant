"""
Telegram webhook'ini o'rnatish / tekshirish / o'chirish.

Ishlatish:
  python set_webhook.py https://SENING-LOYIHANG.vercel.app/api/webhook   # o'rnatish
  python set_webhook.py info                                             # holatni ko'rish
  python set_webhook.py delete                                           # o'chirish (polling'ga qaytish)
"""
import json
import os
import sys
import urllib.request

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

TOKEN = (os.environ.get("BOT_TOKEN") or "").strip()
if not TOKEN:
    raise SystemExit("BOT_TOKEN yo'q (.env ni tekshiring).")

API = f"https://api.telegram.org/bot{TOKEN}"
ALLOWED = ["business_connection", "business_message", "edited_business_message", "message"]


def call(method, payload=None):
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(
        f"{API}/{method}", data=data,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "info"
    if arg == "info":
        print(json.dumps(call("getWebhookInfo"), indent=2, ensure_ascii=False))
    elif arg == "delete":
        print(call("deleteWebhook", {"drop_pending_updates": False}))
    else:
        res = call("setWebhook", {"url": arg, "allowed_updates": ALLOWED})
        print(res)
        print("\nHolat:")
        print(json.dumps(call("getWebhookInfo"), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
