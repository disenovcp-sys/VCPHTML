"""
VCP Monday Report — Lunes 9:00 BA
Stock crítico Shopify + fechas de marketing próximas (20 días).
"""
import os, requests
from datetime import datetime, timedelta, timezone, date
from collections import defaultdict

BA    = timezone(timedelta(hours=-3))
HOY   = datetime.now(BA).date()

SHOPIFY_STORE = os.environ['SHOPIFY_STORE']
SHOPIFY_TOKEN = os.environ['SHOPIFY_TOKEN']
BOT           = os.environ['TELEGRAM_BOT']
CHAT          = os.environ['TELEGRAM_CHAT']

# ─── Shopify stock ────────────────────────────────────────────────────────────
def get_stock(max_talles=2):
    """Alerta productos donde solo quedan ≤ max_talles de su curva con stock."""
    url  = f"https://{SHOPIFY_STORE}/admin/api/2026-04/products.json"
    hdrs = {"X-Shopify-Access-Token": SHOPIFY_TOKEN}
    prms = {"limit": 250, "fields": "id,title,variants,status,options"}
    alertas = []
    while url:
        r = requests.get(url, headers=hdrs, params=prms, timeout=30)
        r.raise_for_status()
        for p in r.json().get("products", []):
            if p.get("status") != "active": continue
            variants = p.get("variants", [])
            options  = p.get("options", [])

            if len(options) >= 2:
                # Producto con color + talle → agrupar por color
                por_color = defaultdict(lambda: {"total": 0, "disponibles": 0, "talles": []})
                for v in variants:
                    color = v.get("option1", "") or ""
                    talle = v.get("option2", "") or ""
                    qty   = int(v.get("inventory_quantity") or 0)
                    por_color[color]["total"] += 1
                    if qty > 0:
                        por_color[color]["disponibles"] += 1
                        por_color[color]["talles"].append(talle)
                for color, d in por_color.items():
                    if d["total"] > max_talles and d["disponibles"] <= max_talles:
                        nombre = f"{p['title']} / {color}" if color else p["title"]
                        alertas.append({
                            "nombre": nombre,
                            "disponibles": d["disponibles"],
                            "total": d["total"],
                            "talles": d["talles"],
                        })
            else:
                # Solo talles (sin color separado)
                total = len(variants)
                disp  = [v for v in variants if int(v.get("inventory_quantity") or 0) > 0]
                if total > max_talles and len(disp) <= max_talles:
                    alertas.append({
                        "nombre": p["title"],
                        "disponibles": len(disp),
                        "total": total,
                        "talles": [v.get("option1", "") for v in disp],
                    })

        lnk = r.headers.get("Link", "")
        url, prms = None, None
        for part in lnk.split(","):
            if 'rel="next"' in part:
                url = part.split(";")[0].strip().strip("<>")
    return sorted(alertas, key=lambda x: x["disponibles"])

# ─── Calendario de marketing ──────────────────────────────────────────────────
def _easter(year):
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19*a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2*e + 2*i - h - k) % 7
    m = (a + 11*h + 22*l) // 451
    mo = (h + l - 7*m + 114) // 31
    dy = ((h + l - 7*m + 114) % 31) + 1
    return date(year, mo, dy)

def _nth_weekday(year, month, n, weekday):
    first = date(year, month, 1)
    delta = (weekday - first.weekday()) % 7
    d     = first + timedelta(days=delta + (n - 1) * 7)
    return d if d.month == month else None

_FECHAS_FIJAS = [
    ((1,  1),  "🎆 Año Nuevo"),
    ((1,  6),  "🎁 Reyes Magos"),
    ((2,  9),  "🍕 Día de la Pizza"),
    ((2, 14),  "💕 San Valentín"),
    ((3,  8),  "♀ Día de la Mujer"),
    ((3, 17),  "🍀 San Patricio"),
    ((4,  2),  "🇦🇷 Día de Malvinas"),
    ((5,  1),  "👷 Día del Trabajador"),
    ((5,  4),  "⭐ Star Wars Day"),
    ((5, 25),  "🇦🇷 Revolución de Mayo"),
    ((5, 28),  "🍔 Día de la Hamburguesa"),
    ((6,  1),  "💰 Aguinaldo Junio"),
    ((6, 20),  "🇦🇷 Día de la Bandera"),
    ((6, 21),  "❄️ Inicio del Invierno"),
    ((7,  9),  "🇦🇷 Día de la Independencia"),
    ((7, 14),  "🏖 Vacaciones de Invierno"),
    ((7, 20),  "🤝 Día del Amigo"),
    ((8, 17),  "🏅 Día de San Martín"),
    ((9, 21),  "🌸 Primavera / Día del Estudiante"),
    ((10,11),  "🍮 Día del Dulce de Leche"),
    ((10,31),  "🎃 Halloween"),
    ((11,20),  "🇦🇷 Día de la Soberanía"),
    ((11,30),  "🧉 Día del Mate"),
    ((12, 8),  "✨ Inmaculada Concepción"),
    ((12,15),  "💰 Aguinaldo Diciembre"),
    ((12,24),  "🎄 Nochebuena"),
    ((12,25),  "🎄 Navidad"),
    ((12,31),  "🎆 Fin de Año"),
]

_HOT_SALE = {
    2026: date(2026, 5, 18),
    2027: date(2027, 5, 17),
}

def fechas_proximas(days=20):
    eventos = []
    for year in [HOY.year, HOY.year + 1]:
        for (m, d_), name in _FECHAS_FIJAS:
            try: eventos.append((date(year, m, d_), name))
            except ValueError: pass
        p = _easter(year)
        eventos += [
            (p,                      "✝️ Pascuas"),
            (p - timedelta(days=7),  "✝️ Semana Santa"),
            (p - timedelta(days=47), "🎉 Carnaval"),
        ]
        for month, n, name in [
            (6,  3, "👨 Día del Padre"),
            (8,  3, "🧒 Día de las Infancias"),
            (10, 3, "👩 Día de la Madre"),
        ]:
            d_ = _nth_weekday(year, month, n, 6)
            if d_: eventos.append((d_, name))
        cyber = _nth_weekday(year, 11, 1, 0)
        if cyber: eventos.append((cyber, "💻 CyberMonday"))
        bf = _nth_weekday(year, 11, 4, 4)
        if bf: eventos.append((bf, "🖤 Black Friday"))
    for hs in _HOT_SALE.values():
        eventos.append((hs, "🔥 Hot Sale"))
    return sorted(
        [(d_, n) for d_, n in eventos if 0 < (d_ - HOY).days <= days],
        key=lambda x: x[0]
    )

# ─── Ejecutar ─────────────────────────────────────────────────────────────────
print("Consultando stock...")
try:
    stock_crit = get_stock(max_talles=2)
except Exception as e:
    print(f"Error stock: {e}")
    stock_crit = []

fechas = fechas_proximas(days=20)

# Stock
if stock_crit:
    stock_txt = "\n".join(
        f"  ⚠️ {a['nombre'][:38]} — {a['disponibles']}/{a['total']} talles ({', '.join(a['talles'])})"
        for a in stock_crit[:10]
    )
else:
    stock_txt = "  ✅ Sin productos con curva crítica"

# Fechas
if fechas:
    fechas_txt = "\n".join(
        f"  📌 {d_.strftime('%d/%m')} — {n} (en {(d_ - HOY).days}d)"
        for d_, n in fechas
    )
else:
    fechas_txt = "  Sin fechas próximas en los próximos 20 días"

msg = f"""📋 *VCP — Lunes {HOY.strftime('%d/%m/%Y')}*

📦 *Stock crítico (≤3 uds):*
{stock_txt}

📅 *Fechas de marketing próximas:*
{fechas_txt}"""

try:
    resp = requests.post(
        f"https://api.telegram.org/bot{BOT}/sendMessage",
        json={"chat_id": CHAT, "text": msg, "parse_mode": "Markdown",
              "disable_web_page_preview": True},
        timeout=10,
    )
    if resp.ok:
        print("✅ Monday report enviado")
    else:
        print(f"❌ Telegram error: {resp.text}")
except Exception as e:
    print(f"❌ Telegram exception: {e}")
