"""
VCP Dashboard Generator
Consulta Windsor.ai y genera index.html con los datos del día anterior.
"""

import os
import json
import requests
from datetime import datetime, timedelta, timezone

# ─── CONFIG ───────────────────────────────────────────────────────────────────
API_KEY          = os.environ["WINDSOR_API_KEY"]
META_ACCOUNT     = "2224979671146859"
SHOPIFY_ACCOUNT  = "van-como-pina.myshopify.com"
BASE_URL         = "https://api.windsor.ai/all"
ROAS_MINIMO      = 8.0

# Fechas: ayer y los últimos 18 días para el gráfico
hoy      = datetime.now(timezone.utc).date()
ayer     = hoy - timedelta(days=1)
desde    = hoy - timedelta(days=18)

# ─── HELPERS ──────────────────────────────────────────────────────────────────
def fmt_ars(n):
    """Formatea número como $1.234.567"""
    if n >= 1_000_000:
        return f"${n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"${n/1_000:.0f}K"
    return f"${n:,.0f}"

def get_data(connector, account, fields, date_from, date_to, filters=None):
    params = {
        "api_key": API_KEY,
        "connector": connector,
        "account": account,
        "date_from": str(date_from),
        "date_to": str(date_to),
        "fields": ",".join(fields),
    }
    if filters:
        params["filters"] = json.dumps(filters)
    r = requests.get(BASE_URL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("data", data) if isinstance(data, dict) else data

# ─── 1. DATOS DE META (últimos 18 días por campaña) ───────────────────────────
print("Consultando Meta Ads...")
meta_raw = get_data(
    connector="facebook",
    account=META_ACCOUNT,
    fields=["date", "campaign", "spend", "impressions", "clicks",
            "website_purchase_roas_offsite_conversion_fb_pixel_purchase",
            "action_values_offsite_conversion_fb_pixel_purchase",
            "results"],
    date_from=desde,
    date_to=ayer,
    filters=[["spend", "gt", 0]]
)

# Agrupar por día (total cuenta)
from collections import defaultdict
daily = defaultdict(lambda: {"spend": 0, "revenue": 0, "compras": 0})
camp_totals = defaultdict(lambda: {"spend": 0, "revenue": 0, "compras": 0})

for row in meta_raw:
    d   = row.get("date", "")[:10]
    sp  = float(row.get("spend", 0) or 0)
    rev = float(row.get("action_values_offsite_conversion_fb_pixel_purchase", 0) or 0)
    comp = 0
    for res in (row.get("results") or []):
        if "purchase" in res.get("indicator", ""):
            vals = res.get("values", [])
            if vals:
                comp = int(vals[0].get("value", 0))
    camp = row.get("campaign", "Otra")
    daily[d]["spend"]   += sp
    daily[d]["revenue"] += rev
    daily[d]["compras"] += comp
    camp_totals[camp]["spend"]   += sp
    camp_totals[camp]["revenue"] += rev
    camp_totals[camp]["compras"] += comp

# ─── 2. DATOS DE SHOPIFY (ayer) ───────────────────────────────────────────────
print("Consultando Shopify...")
try:
    shopify_raw = get_data(
        connector="shopify",
        account=SHOPIFY_ACCOUNT,
        fields=["date", "order_count", "order_total_price", "order_gross_sales"],
        date_from=ayer,
        date_to=ayer,
    )
    shopify_ventas = sum(float(r.get("order_total_price", 0) or 0) for r in shopify_raw)
    shopify_ordenes = sum(int(r.get("order_count", 0) or 0) for r in shopify_raw)
except Exception as e:
    print(f"Error Shopify: {e}")
    shopify_ventas  = 0
    shopify_ordenes = 0

# ─── 3. KPIs DEL DÍA ANTERIOR ────────────────────────────────────────────────
ayer_str   = str(ayer)
ayer_data  = daily.get(ayer_str, {"spend": 0, "revenue": 0, "compras": 0})
spend_ayer = ayer_data["spend"]
rev_meta   = ayer_data["revenue"]
roas_meta  = round(rev_meta / spend_ayer, 2) if spend_ayer > 0 else 0
roas_real  = round(shopify_ventas / spend_ayer, 2) if spend_ayer > 0 else 0
ticket     = round(shopify_ventas / shopify_ordenes, 0) if shopify_ordenes > 0 else 0

# ─── 4. DATOS DEL GRÁFICO (18 días) ──────────────────────────────────────────
HS_START = "2026-05-11"
HS_END   = "2026-05-17"

chart_data = []
for i in range(18):
    d = desde + timedelta(days=i)
    ds = str(d)
    dd = daily.get(ds)
    if dd and dd["spend"] > 0:
        r = round(dd["revenue"] / dd["spend"], 2)
    else:
        r = None
    hs = 1 if HS_START <= ds <= HS_END else 0
    chart_data.append({
        "d": f"{d.day:02d}/5",
        "r": r,
        "hs": hs
    })

# ─── 5. TOTALS MAYO ──────────────────────────────────────────────────────────
total_spend   = sum(v["spend"]   for v in daily.values())
total_revenue = sum(v["revenue"] for v in daily.values())
total_compras = sum(v["compras"] for v in daily.values())
roas_prom     = round(total_revenue / total_spend, 2) if total_spend > 0 else 0
dias_sobre_8  = sum(1 for v in daily.values() if v["spend"] > 0 and v["revenue"] / v["spend"] >= 8)

# Mejor y peor día
dias_con_datos = {d: v for d, v in daily.items() if v["spend"] > 0}
mejor_dia = max(dias_con_datos, key=lambda d: dias_con_datos[d]["revenue"] / dias_con_datos[d]["spend"]) if dias_con_datos else None
peor_dia  = min(dias_con_datos, key=lambda d: dias_con_datos[d]["revenue"] / dias_con_datos[d]["spend"]) if dias_con_datos else None
mejor_roas = round(dias_con_datos[mejor_dia]["revenue"] / dias_con_datos[mejor_dia]["spend"], 1) if mejor_dia else 0
peor_roas  = round(dias_con_datos[peor_dia]["revenue"]  / dias_con_datos[peor_dia]["spend"],  1) if peor_dia else 0

# Semáforo ROAS
def semaforo(r):
    if r >= 8:   return "green", "✅", "Sobre objetivo"
    if r >= 5:   return "yellow", "⚠️", "Bajo objetivo"
    return "red", "🔴", "Crítico"

color, emoji, label = semaforo(roas_real)

# ─── 6. RESUMEN PARA TELEGRAM ────────────────────────────────────────────────
summary_lines = [
    f"💰 Inversión Meta: {fmt_ars(spend_ayer)}",
    f"🛍 Ventas Shopify: {fmt_ars(shopify_ventas)}",
    f"🎯 ROAS real: {roas_real}x {emoji} ({label})",
    f"📦 Órdenes Shopify: {shopify_ordenes}",
    f"🎫 Ticket promedio: {fmt_ars(ticket)}",
]

with open("daily_summary.txt", "w") as f:
    f.write("\n".join(summary_lines))

print("Resumen del día:", summary_lines)

# ─── 7. GENERAR HTML ─────────────────────────────────────────────────────────
fecha_str = ayer.strftime("%-d de %B %Y").replace("January","enero").replace("February","febrero") \
    .replace("March","marzo").replace("April","abril").replace("May","mayo") \
    .replace("June","junio").replace("July","julio").replace("August","agosto") \
    .replace("September","septiembre").replace("October","octubre") \
    .replace("November","noviembre").replace("December","diciembre")

# Campañas principales
camp_rows = ""
camp_order = [
    "Advantage+ ok",
    "Prospecting Categorias - shopify",
    "Remarketing",
    "Ventas x intereses",
    "02 story - ventas",
    "01 Ventas - FEED",
]
for camp in camp_order:
    data = camp_totals.get(camp)
    if not data or data["spend"] == 0:
        continue
    r = round(data["revenue"] / data["spend"], 2)
    col = "#6ee7b7" if r >= 8 else "#fcd34d" if r >= 5 else "#f87171"
    tag = "✅" if r >= 8 else "⚠️" if r >= 5 else "🔴"
    camp_rows += f"""
    <tr>
      <td class="n">{camp}</td>
      <td class="r">{fmt_ars(data['spend'])}</td>
      <td class="r">{data['compras']}</td>
      <td class="r" style="color:{col};">{r}x</td>
      <td class="r">{tag}</td>
    </tr>"""

# JSON para el gráfico
chart_json = json.dumps(chart_data)

# Leer template y reemplazar placeholders
with open("template.html", "r") as f:
    html = f.read()

replacements = {
    "{{FECHA}}":         fecha_str,
    "{{SPEND_AYER}}":    fmt_ars(spend_ayer),
    "{{VENTAS_SHOPIFY}}": fmt_ars(shopify_ventas),
    "{{ROAS_REAL}}":     str(roas_real),
    "{{ROAS_COLOR}}":    color,
    "{{ROAS_EMOJI}}":    emoji,
    "{{ROAS_LABEL}}":    label,
    "{{ORDENES}}":       str(shopify_ordenes),
    "{{TICKET}}":        fmt_ars(ticket),
    "{{TOTAL_SPEND}}":   fmt_ars(total_spend),
    "{{TOTAL_REVENUE}}": fmt_ars(total_revenue),
    "{{ROAS_PROM}}":     str(roas_prom),
    "{{DIAS_SOBRE_8}}":  str(dias_sobre_8),
    "{{MEJOR_DIA}}":     mejor_dia[8:10]+"/5" if mejor_dia else "—",
    "{{MEJOR_ROAS}}":    str(mejor_roas),
    "{{PEOR_DIA}}":      peor_dia[8:10]+"/5" if peor_dia else "—",
    "{{PEOR_ROAS}}":     str(peor_roas),
    "{{CAMP_ROWS}}":     camp_rows,
    "{{CHART_DATA}}":    chart_json,
}

for k, v in replacements.items():
    html = html.replace(k, str(v))

with open("index.html", "w") as f:
    f.write(html)

print(f"✅ index.html generado — {fecha_str}")
print(f"   ROAS real: {roas_real}x | Shopify: {fmt_ars(shopify_ventas)} | Inversión: {fmt_ars(spend_ayer)}")
