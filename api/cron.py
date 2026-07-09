from http.server import BaseHTTPRequestHandler
import json
import os
import time
import sys

# To ensure we can import from the same directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from webhook import send_message, generate, redis_client
except ImportError:
    redis_client = None

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        ADMIN_ID = os.environ.get("ADMIN_ID")
        if not ADMIN_ID or not redis_client:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"Error: Missing ADMIN_ID or Redis")
            return

        # Tashkent time = UTC + 5.
        tashkent_time = time.time() + 5 * 3600
        yesterday_time = tashkent_time - 24 * 3600
        yesterday = time.strftime("%Y-%m-%d", time.gmtime(yesterday_time))

        try:
            logs_data = redis_client.lrange(f"logs:{yesterday}", 0, -1)
            logs = [json.loads(x) if isinstance(x, str) else x for x in logs_data] if logs_data else []
        except Exception:
            logs = []

        if not logs:
            send_message(ADMIN_ID, f"Kecha ({yesterday}) uchun hisobot:\nHech qanday suhbat bo'lmagan.")
        else:
            # We limit to 50 logs to avoid token limits
            log_text = "\n".join([f"Mijoz ({l.get('user')}): {l.get('text')}\nBot: {l.get('reply')}" for l in logs[-50:]])
            sys_prompt = f"Kecha ({yesterday}) mijozlar bilan suhbatlar tarixi quyida keltirilgan. Buni o'qib chiq va qisqacha, tushunarli tilda kim nima so'ragani va bot nima javob bergani haqida umumiylashtirilgan hisobot tayyorla:\n\n{log_text}"
            
            report = generate([], prefer_gemini=True, sys_prompt=sys_prompt)
            if report:
                send_message(ADMIN_ID, f"📅 Kechagi kun ({yesterday}) bo'yicha hisobot:\n\n{report}")
            else:
                send_message(ADMIN_ID, "Hisobot tayyorlashda xatolik yuz berdi.")

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Cron job executed")
