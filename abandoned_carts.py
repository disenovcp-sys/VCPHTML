"""
VCP Abandoned Carts — cada 3 días
Envía por Telegram los emails de carritos abandonados en los últimos 3 días.
"""
import os, requests
from datetime import datetime, timedelta, timezone

BA    = timezone(timedelta(hours=-3))
HOY   = datetime.now(BA).date()
DESDE = HOY - timedelta(days=3)

SHOPIFY_STORE = os.environ['SHOPIFY_STORE']
SHOPIFY_TOKEN = os.environ['SHOPIFY_TOKEN']
BOT           = os.environ['TELEGRAM_BOT']
CHAT          = os.environ['TELEGRAM_CHAT']

def get_abandoned_carts():
    url  = f"https://{SHOPIFY_STORE}/admin/api/2026-04/checkouts.json"
    hdrs = {"X-Shopify-Access-Token": SHOPIFY_TOKEN}
    prms = {
        "created_at_min": f"{DESDE}T00:00:00-03:00",
        "created_at_max": f"{HOY}T23:59:59-03:00",
        "limit": 250,
    }
    carts = []
    while url:
        r = requests.get(url, headers=hdrs, params=prms, timeout=30)
        r.raise_for_status()
        for c in r.json().get("checkouts", []):
            if not c.get("completed_at") and c.get("email"):
                carts.append(c["email"].lower().strip())
        lnk = r.headers.get("Link", "")
        url, prms = None, None
        for part in lnk.split(","):
            if 'rel="next"' in part:
                url = part.split(";")[0].strip().strip("<>")
    return sorted(set(carts))

print("Consultando carritos abandonados...")
try:
    emails = get_abandoned_carts()
except Exception as e:
    print(f"Error: {e}")
    emails = []

if emails:
    emails_txt = "\n".join(f"  • {email}" for email in emails)
    msg = f"""🛒 *Carritos abandonados — {DESDE.strftime('%d/%m')} al {HOY.strftime('%d/%m/%Y')}*

📧 *{len(emails)} personas:*
{emails_txt}"""
else:
    msg = f"""🛒 *Carritos abandonados — {DESDE.strftime('%d/%m')} al {HOY.strftime('%d/%m/%Y')}*

✅ Sin carritos abandonados en los últimos 3 días."""

try:
    resp = requests.post(
        f"https://api.telegram.org/bot{BOT}/sendMessage",
        json={"chat_id": CHAT, "text": msg, "parse_mode": "Markdown",
              "disable_web_page_preview": True},
        timeout=10,
    )
    if resp.ok:
        print(f"✅ Enviado — {len(emails)} carritos abandonados")
    else:
        print(f"❌ Telegram error: {resp.text}")
except Exception as e:
    print(f"❌ Telegram exception: {e}")
