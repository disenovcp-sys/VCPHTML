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
    url  = f"https://{SHOPIFY_STORE}/admin/api/2026-04/graphql.json"
    hdrs = {
        "X-Shopify-Access-Token": SHOPIFY_TOKEN,
        "Content-Type": "application/json",
    }
    emails = []
    cursor = None
    while True:
        after = f', after: "{cursor}"' if cursor else ""
        query = f"""{{
          abandonedCheckouts(first: 250{after}, query: "created_at:>='{DESDE}T00:00:00-03:00' created_at:<='{HOY}T23:59:59-03:00'") {{
            pageInfo {{ hasNextPage endCursor }}
            edges {{
              node {{ email createdAt completedAt }}
            }}
          }}
        }}"""
        r = requests.post(url, headers=hdrs, json={"query": query}, timeout=30)
        r.raise_for_status()
        result = r.json().get("data", {}).get("abandonedCheckouts", {})
        for edge in result.get("edges", []):
            node = edge.get("node", {})
            if not node.get("completedAt") and node.get("email"):
                emails.append(node["email"].lower().strip())
        page_info = result.get("pageInfo", {})
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
    return sorted(set(emails))

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
