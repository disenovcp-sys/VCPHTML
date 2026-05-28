"""
VCP Telegram Notifier
Envía el resumen diario con la URL del dashboard a Telegram.
"""

import os
import requests
from datetime import datetime, timedelta, timezone

TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
URL     = os.environ.get("GITHUB_PAGES_URL", "https://tuusuario.github.io/vcp-dashboard")

ayer = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%d/%m/%Y")

try:
    with open("daily_summary.txt", "r") as f:
        summary = f.read()
except FileNotFoundError:
    summary = "Dashboard actualizado correctamente."

mensaje = f"""📊 *VCP Dashboard — {ayer}*

{summary}

🔗 [Ver informe completo]({URL})"""

resp = requests.post(
    f"https://api.telegram.org/bot{TOKEN}/sendMessage",
    json={
        "chat_id": CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    },
    timeout=10,
)

if resp.ok:
    print("✅ Mensaje enviado a Telegram")
else:
    print(f"❌ Error Telegram: {resp.text}")
