"""
VCP Weekly Summary — corre los lunes, cubre los últimos 7 días.
"""
import os, requests
from datetime import datetime, timedelta, timezone
from collections import defaultdict

BA    = timezone(timedelta(hours=-3))
HOY   = datetime.now(BA).date()
HASTA = HOY - timedelta(days=1)
DESDE = HOY - timedelta(days=7)

K             = os.environ['WINDSOR_KEY']
META          = os.environ['META_ACCOUNT']
BOT           = os.environ['TELEGRAM_BOT']
CHAT          = os.environ['TELEGRAM_CHAT']
SHOPIFY_STORE = os.environ['SHOPIFY_STORE']
SHOPIFY_TOKEN = os.environ['SHOPIFY_TOKEN']
PAGES_URL     = os.environ.get('PAGES_URL', 'https://disenovcp-sys.github.io/vcp-dashboard')

MESES = ['enero','febrero','marzo','abril','mayo','junio',
         'julio','agosto','septiembre','octubre','noviembre','diciembre']

def w_meta():
    p = {
        'api_key': K,
        'account_id': META,
        'fields': 'account_id,date,campaign_name,spend,'
                  'action_values_offsite_conversion_fb_pixel_purchase,'
                  'actions_offsite_conversion_fb_pixel_purchase',
        'date_from': str(DESDE),
        'date_to':   str(HASTA),
    }
    r = requests.get('https://connectors.windsor.ai/facebook', params=p, timeout=120)
    r.raise_for_status()
    data = r.json()
    return data.get('data', data) if isinstance(data, dict) else data

def shopify_orders(date_min, date_max):
    url  = f"https://{SHOPIFY_STORE}/admin/api/2026-04/orders.json"
    hdrs = {"X-Shopify-Access-Token": SHOPIFY_TOKEN}
    prms = {
        "created_at_min": f"{date_min}T00:00:00-03:00",
        "created_at_max": f"{date_max}T23:59:59-03:00",
        "status": "any", "limit": 250,
        "fields": "id,total_price,financial_status",
    }
    out = []
    while url:
        r = requests.get(url, headers=hdrs, params=prms, timeout=30)
        r.raise_for_status()
        out.extend(r.json().get("orders", []))
        lnk = r.headers.get("Link", "")
        url, prms = None, None
        for part in lnk.split(","):
            if 'rel="next"' in part:
                url = part.split(";")[0].strip().strip("<>")
    return [o for o in out if o.get("financial_status") in ("paid", "pending", "partially_paid")]

def fmt_k(n):
    if n >= 1_000_000: return f"${n/1_000_000:.1f}M"
    if n >= 1_000:     return f"${n/1_000:.0f}K"
    return f"${n:,.0f}"

print("Consultando Meta (7 días)...")
meta_rows = w_meta()

daily = defaultdict(lambda: {"spend": 0.0, "val": 0.0, "compras": 0})
camps = defaultdict(lambda: {"spend": 0.0, "val": 0.0})
for row in meta_rows:
    d = str(row.get("date", ""))[:10]
    sp  = float(row.get("spend", 0) or 0)
    val = float(row.get("action_values_offsite_conversion_fb_pixel_purchase", 0) or 0)
    comp= int(row.get("actions_offsite_conversion_fb_pixel_purchase", 0) or 0)
    daily[d]["spend"]   += sp
    daily[d]["val"]     += val
    daily[d]["compras"] += comp
    c = row.get("campaign_name", "Otra") or "Otra"
    camps[c]["spend"] += sp
    camps[c]["val"]   += val

total_meta  = sum(v["spend"] for v in daily.values())
total_val   = sum(v["val"]   for v in daily.values())
total_compras_meta = sum(v["compras"] for v in daily.values())

print("Consultando Shopify (7 días)...")
orders = shopify_orders(DESDE, HASTA)
total_shop_rev    = sum(float(o.get("total_price", 0) or 0) for o in orders)
total_shop_orders = len(orders)
ticket = total_shop_rev / total_shop_orders if total_shop_orders else 0

roas_real  = total_shop_rev / total_meta if total_meta else 0
roas_pixel = total_val      / total_meta if total_meta else 0

roas_emoji = "✅" if roas_real >= 8 else ("⚠️" if roas_real >= 5 else "🔴")

dias_con = {d: v for d, v in daily.items() if v["spend"] > 0}
dias_ok  = sum(1 for v in dias_con.values() if v["spend"] > 0 and v["val"] / v["spend"] >= 8)

mejor = max(dias_con, key=lambda d: dias_con[d]["val"] / dias_con[d]["spend"]) if dias_con else None
peor  = min(dias_con, key=lambda d: dias_con[d]["val"] / dias_con[d]["spend"]) if dias_con else None
mejor_roas = dias_con[mejor]["val"] / dias_con[mejor]["spend"] if mejor else 0
peor_roas  = dias_con[peor]["val"]  / dias_con[peor]["spend"]  if peor  else 0

def fmt_dia(ds):
    if not ds: return "—"
    d = datetime.strptime(ds, "%Y-%m-%d")
    return f"{d.day} {MESES[d.month-1]}"

top_camps = sorted(
    [(c, d) for c, d in camps.items() if d["spend"] > 0],
    key=lambda x: -x[1]["spend"]
)[:3]

camps_lines = ""
for c, d in top_camps:
    r = d["val"] / d["spend"] if d["spend"] else 0
    camps_lines += f"\n  • {c[:30]}: {fmt_k(d['spend'])} · {r:.1f}x"

semana_str = f"{DESDE.strftime('%d/%m')} al {HASTA.strftime('%d/%m/%Y')}"

msg = f"""📊 *Resumen Semanal VCP*
_{semana_str}_

💰 Inversión Meta: {fmt_k(total_meta)}
🛍 Ventas Shopify: {fmt_k(total_shop_rev)}
🎯 ROAS real: {roas_real:.1f}x {roas_emoji}
📦 Órdenes: {total_shop_orders}
🎫 Ticket promedio: {fmt_k(ticket)}

📅 *Días sobre ROAS 8x:* {dias_ok}/7
📈 Mejor día: {fmt_dia(mejor)} ({mejor_roas:.1f}x)
📉 Peor día: {fmt_dia(peor)} ({peor_roas:.1f}x)

🏆 *Top campañas (gasto):*{camps_lines}

🔗 [Ver dashboard]({PAGES_URL})"""

try:
    resp = requests.post(
        f"https://api.telegram.org/bot{BOT}/sendMessage",
        json={"chat_id": CHAT, "text": msg, "parse_mode": "Markdown",
              "disable_web_page_preview": False},
        timeout=10,
    )
    if resp.ok:
        print("✅ Resumen semanal enviado a Telegram")
    else:
        print(f"❌ Telegram error: {resp.text}")
except Exception as e:
    print(f"❌ Telegram exception: {e}")
