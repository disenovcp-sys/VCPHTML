import os, requests, time, html as H
from datetime import timezone, timedelta, datetime, date
from collections import defaultdict
import calendar

def w_get(url, params, retries=5):
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=120)
            r.raise_for_status()
            return r
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            if i == retries - 1: raise
            time.sleep(30)

BA        = timezone(timedelta(hours=-3))
NOW       = datetime.now(BA)
HOY       = NOW.date()
AYER      = HOY - timedelta(days=1)
MES_DESDE = date(HOY.year, HOY.month, 1)
MES_HASTA = AYER

MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
         'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
DIAS  = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo']

K    = os.environ['WINDSOR_KEY']
META = os.environ['META_ACCOUNT']
SHOP = os.environ['SHOPIFY_ACCOUNT']
GOOG = os.environ['GOOGLE_ACCOUNT']
BOT  = os.environ['TELEGRAM_BOT']
CHAT = os.environ['TELEGRAM_CHAT']

def w(conn, acct, fields, d1, d2, extra=None):
    p = {'api_key': K, 'account_id': acct,
         'fields': 'account_id,' + ','.join(fields),
         'date_from': d1.strftime('%Y-%m-%d'), 'date_to': d2.strftime('%Y-%m-%d')}
    if extra: p.update(extra)
    r = w_get(f'https://connectors.windsor.ai/{conn}', p)
    r.raise_for_status()
    data = r.json()
    rows = data.get('data', data) if isinstance(data, dict) else data
    fil  = [x for x in rows if str(x.get('account_id', acct)) == str(acct)]
    return fil if fil else rows

META_FIELDS = ['campaign_name','ad_name','spend','impressions','clicks','reach',
               'frequency','actions_offsite_conversion_fb_pixel_purchase',
               'action_values_offsite_conversion_fb_pixel_purchase',
               'actions_add_to_cart','actions_initiate_checkout']

print('Pulling Meta ayer...')
meta_hoy = w('facebook', META, META_FIELDS, AYER, AYER)
print('Pulling Meta mes...')
meta_mes = w('facebook', META, META_FIELDS, MES_DESDE, MES_HASTA)
print('Pulling Google mes...')
goog_mes = w('google_ads', GOOG, ['spend'], MES_DESDE, MES_HASTA)
print('Pulling Shopify mes...')
shop_mes = w('shopify', SHOP, ['order_count','order_total_price'],
             MES_DESDE, MES_HASTA, {'date_filters': '{"orders":"createdAt"}'})

def agg(rows):
    ads = defaultdict(lambda: {'camp':'','spend':0.,'imp':0,'clicks':0,'reach':0,
                                'freq':0.,'compras':0,'val':0.,'cart':0,'checkout':0})
    for row in rows:
        n = row.get('ad_name','') or ''
        if not n: continue
        ads[n]['camp']     = row.get('campaign_name','') or ''
        ads[n]['spend']   += float(row.get('spend',0) or 0)
        ads[n]['imp']     += int(row.get('impressions',0) or 0)
        ads[n]['clicks']  += int(row.get('clicks',0) or 0)
        ads[n]['reach']   += int(row.get('reach',0) or 0)
        ads[n]['compras'] += int(row.get('actions_offsite_conversion_fb_pixel_purchase',0) or 0)
        ads[n]['val']     += float(row.get('action_values_offsite_conversion_fb_pixel_purchase',0) or 0)
        ads[n]['cart']    += int(row.get('actions_add_to_cart',0) or 0)
        ads[n]['checkout']+= int(row.get('actions_initiate_checkout',0) or 0)
        ads[n]['freq']     = max(ads[n]['freq'], float(row.get('frequency',0) or 0))
    return ads

ads_hoy = agg(meta_hoy)
ads_mes = agg(meta_mes)

hoy_meta = sum(a['spend'] for a in ads_hoy.values())
hoy_imp  = sum(a['imp']   for a in ads_hoy.values())
hoy_clk  = sum(a['clicks'] for a in ads_hoy.values())
hoy_comp = sum(a['compras'] for a in ads_hoy.values())
hoy_val  = sum(a['val']   for a in ads_hoy.values())
hoy_roas = hoy_val / hoy_meta if hoy_meta else 0

mes_meta = sum(a['spend']   for a in ads_mes.values())
mes_imp  = sum(a['imp']     for a in ads_mes.values())
mes_clks = sum(a['clicks']  for a in ads_mes.values())
mes_cart = sum(a['cart']    for a in ads_mes.values())
mes_chk  = sum(a['checkout'] for a in ads_mes.values())
mes_comp = sum(a['compras'] for a in ads_mes.values())
mes_val  = sum(a['val']     for a in ads_mes.values())
mes_goog = sum(float(r.get('spend',0) or 0) for r in goog_mes)
mes_shop_rev    = sum(float(r.get('order_total_price',0) or 0) for r in shop_mes)
mes_shop_orders = sum(int(r.get('order_count',0) or 0)         for r in shop_mes)
mes_inv  = mes_meta + mes_goog
mes_roas = mes_shop_rev / mes_inv if mes_inv else 0

camps_mes = defaultdict(lambda: {'spend':0.,'imp':0,'clicks':0,
                                   'compras':0,'val':0.,'cart':0,'checkout':0})
for n, d in ads_mes.items():
    c = d['camp'] or 'Sin campaña'
    camps_mes[c]['spend']   += d['spend']
    camps_mes[c]['imp']     += d['imp']
    camps_mes[c]['clicks']  += d['clicks']
    camps_mes[c]['compras'] += d['compras']
    camps_mes[c]['val']     += d['val']
    camps_mes[c]['cart']    += d['cart']
    camps_mes[c]['checkout']+= d['checkout']

ads_activos       = {n for n, d in ads_hoy.items() if d['spend'] > 0}
camps_activas_ayer = {d['camp'] for n, d in ads_hoy.items() if d['spend'] > 0}
camps_sorted = sorted(
    [(c, d) for c, d in camps_mes.items() if c in camps_activas_ayer],
    key=lambda x: -x[1]['spend']
)

ganador = None; ganador_roas = 0
for n, d in ads_mes.items():
    if d['spend'] < 50000 or d['compras'] < 3: continue
    r = d['val'] / d['spend'] if d['spend'] else 0
    if r > ganador_roas:
        ganador_roas = r; ganador = (n, d)

def fmt(n):   return '$' + f'{n:,.0f}'.replace(',','.')
def pct(a,b): return f'{a/b*100:.1f}%' if b else '—'
def rcol(r):  return 'var(--green)' if r>=8 else ('var(--yellow)' if r>=5 else 'var(--red)')

fecha_hoy = f'{HOY.day} de {MESES[HOY.month-1]} {HOY.year}'
dia_sem   = DIAS[HOY.weekday()]
mes_label = f'{MESES[HOY.month-1]} {HOY.year}'
dias_tr   = (AYER - MES_DESDE).days + 1 if AYER >= MES_DESDE else 0
tot_dias  = calendar.monthrange(HOY.year, HOY.month)[1]
pct_mes   = dias_tr / tot_dias * 100 if tot_dias else 0

def fn_w(n, total): return f'{min(100, n/total*100):.0f}%' if total else '0%'

# ─── Funnel camp mini-cards ───────────────────────────────────
funnel_camps_html = ''
for c, d in camps_sorted[:5]:
    if d['spend'] <= 0: continue
    ce = H.escape(c[:38])
    cierre = pct(d['compras'], d['checkout'])
    funnel_camps_html += f'''
      <div style="background:rgba(167,139,250,0.06);border:1px solid rgba(167,139,250,0.2);border-radius:12px;padding:12px;margin-bottom:8px;">
        <div style="font-family:'DM Mono',monospace;font-size:9px;color:var(--purple);text-transform:uppercase;margin-bottom:8px;">{ce}</div>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:4px;text-align:center;">
          <div style="background:rgba(255,255,255,0.04);border-radius:8px;padding:6px 2px;"><div style="font-family:'DM Serif Display',serif;font-size:14px;color:var(--yellow);">{d["cart"]}</div><div style="font-size:8px;color:var(--muted);">Cart</div></div>
          <div style="background:rgba(255,255,255,0.04);border-radius:8px;padding:6px 2px;"><div style="font-family:'DM Serif Display',serif;font-size:14px;color:var(--yellow);">{d["checkout"]}</div><div style="font-size:8px;color:var(--muted);">Checkout</div></div>
          <div style="background:rgba(110,231,183,0.08);border-radius:8px;padding:6px 2px;"><div style="font-family:'DM Serif Display',serif;font-size:14px;color:var(--green);">{d["compras"]}</div><div style="font-size:8px;color:var(--muted);">Compras</div></div>
          <div style="background:rgba(110,231,183,0.08);border-radius:8px;padding:6px 2px;"><div style="font-family:'DM Serif Display',serif;font-size:14px;color:var(--green);">{cierre}</div><div style="font-size:8px;color:var(--muted);">Cierre</div></div>
        </div>
      </div>'''

# ─── Campaign cards ───────────────────────────────────────────
def camp_card(cname, cdata, all_ads):
    roas = cdata['val'] / cdata['spend'] if cdata['spend'] else 0
    rc   = rcol(roas)
    ctr  = pct(cdata['clicks'], cdata['imp'])
    cpa  = fmt(cdata['spend']/cdata['compras']) if cdata['compras'] else '—'
    rb_cls = 'rg' if roas >= 8 else ('rbl' if roas >= 5 else '')
    rb_sty = '' if roas >= 5 else 'background:rgba(248,113,113,0.07);border:1px solid rgba(248,113,113,0.25);'

    cadena = cname
    rows_html = ''
    for n, d in sorted([(n,d) for n,d in all_ads.items() if d['camp']==cadena],
                       key=lambda x: -x[1]['spend']):
        if d['spend'] <= 0: continue
        ar   = d['val']/d['spend'] if d['spend'] else 0
        actr = pct(d['clicks'], d['imp'])
        col  = 'var(--green)' if n in ads_activos else 'var(--yellow)'

        if d['compras'] == 0:
            rc2 = 'var(--muted)'; rv = f'<span class="ta">0v</span>'
        elif ar >= 8:
            rc2 = 'var(--green)'; rv = f'{ar:.1f}x'
        elif ar >= 5:
            rc2 = 'var(--yellow)'; rv = f'{ar:.1f}x'
        else:
            rc2 = 'var(--red)'; rv = f'{ar:.1f}x'

        ne = H.escape(n[:35])
        cv = 'var(--green)' if (d['imp'] and d['clicks']/d['imp']*100 > 3) else 'var(--yellow)'
        cv2 = 'var(--green)' if d['compras'] > 0 else 'var(--muted)'
        comp_v = str(d['compras']) if d['compras'] > 0 else '—'
        rows_html += f'''
      <tr>
        <td class="n" style="color:{col};">⬤ {ne}</td>
        <td class="r">{fmt(d["spend"])}</td>
        <td class="r" style="color:{cv};">{actr}</td>
        <td class="r" style="color:{cv2};">{comp_v}</td>
        <td class="r" style="color:{rc2};font-weight:700;">{rv}</td>
        <td class="r">{d["freq"]:.2f}</td>
      </tr>'''

    ce = H.escape(cname[:45])
    return f'''
<div class="card">
  <div class="card-tag">📊 {ce}</div>
  <div class="card-title">{ce}</div>
  <div class="mg">
    <div class="mt"><div class="ml">Inversión</div><div class="mv">{fmt(cdata["spend"])}</div><div class="ms">{mes_label}</div></div>
    <div class="mt"><div class="ml">Impresiones</div><div class="mv" style="font-size:18px;">{cdata["imp"]:,}</div><div class="ms">CTR {ctr}</div></div>
    <div class="mt" style="background:rgba(167,139,250,0.06);border-color:rgba(167,139,250,0.2);"><div class="ml" style="color:var(--purple);">Compras pixel</div><div class="mv" style="color:var(--purple);font-size:20px;">{cdata["compras"]}</div><div class="ms">CPA {cpa}</div></div>
    <div class="mt" style="background:rgba(167,139,250,0.04);border-color:rgba(167,139,250,0.15);"><div class="ml" style="color:var(--purple);">Revenue pixel</div><div class="mv" style="color:var(--purple);font-size:18px;">{fmt(cdata["val"])}</div></div>
  </div>
  <div class="rb {rb_cls}" style="{rb_sty}">
    <div class="rl" style="color:{rc};">ROAS</div>
    <div class="rv" style="color:{rc};">{roas:.1f}x</div>
    <div class="rs">{fmt(cdata["val"])} generados · {cdata["compras"]} ventas</div>
  </div>
  <div class="div"></div>
  <div class="sl">Anuncios del mes</div>
  <div class="tbl-wrap"><table class="at">
    <thead><tr><th>Anuncio</th><th class="r">Gasto</th><th class="r">CTR</th><th class="r">Ventas</th><th class="r">ROAS</th><th class="r">Freq</th></tr></thead>
    <tbody>{rows_html}
    </tbody>
  </table></div>
</div>'''

camp_cards_html = '\n'.join(camp_card(c, d, ads_mes) for c, d in camps_sorted if d['spend'] > 0)

# ─── Winner ───────────────────────────────────────────────────
if ganador:
    gn, gd = ganador
    gr = gd['val']/gd['spend'] if gd['spend'] else 0
    winner_html = f'''
<div class="wc">
  <div class="wt">🏆 Anuncio Ganador del Mes</div>
  <h2>{H.escape(gn[:50])}</h2>
  <div class="wcp">{H.escape(gd["camp"])} · ACTIVO</div>
  <div class="ws">
    <div><div class="wsl">Inversión</div><div class="wsv">{fmt(gd["spend"])}</div></div>
    <div><div class="wsl">Ventas</div><div class="wsv">{gd["compras"]}</div></div>
    <div><div class="wsl">Revenue</div><div class="wsv">{fmt(gd["val"])}</div></div>
    <div><div class="wsl">ROAS</div><div class="wsv">{gr:.1f}x</div></div>
    <div><div class="wsl">CTR</div><div class="wsv">{pct(gd["clicks"],gd["imp"])}</div></div>
    <div><div class="wsl">Freq.</div><div class="wsv">{gd["freq"]:.2f}</div></div>
  </div>
</div>'''
else:
    winner_html = ''

# ─── HTML final ───────────────────────────────────────────────
rmc = rcol(mes_roas); rhc = rcol(hoy_roas)

HTML = '''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard VCP · ''' + fecha_hoy + '''</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
:root{--bg:#0a0a0f;--surface:#111118;--border:rgba(255,255,255,0.07);--purple:#a78bfa;--blue:#8ab4f8;--green:#6ee7b7;--yellow:#fcd34d;--text:#e8e8f0;--muted:#6b6b80;--red:#f87171;}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);font-family:'DM Sans',sans-serif;min-height:100vh;padding:40px 24px;}
.header{text-align:center;margin-bottom:48px;}
.header .label{font-family:'DM Mono',monospace;font-size:11px;letter-spacing:0.2em;color:var(--muted);text-transform:uppercase;margin-bottom:10px;}
.header h1{font-family:'DM Serif Display',serif;font-size:clamp(28px,5vw,44px);line-height:1.1;}
.header h1 em{font-style:italic;color:var(--purple);}
.header .date{margin-top:10px;font-family:'DM Mono',monospace;font-size:12px;color:var(--muted);}
.wrap{max-width:980px;margin:0 auto;}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:32px;}
@media(max-width:700px){.grid{grid-template-columns:1fr;}}
.card{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:28px;position:relative;overflow:hidden;}
.card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;border-radius:16px 16px 0 0;background:linear-gradient(90deg,var(--purple),#818cf8);}
.card-tag{font-family:'DM Mono',monospace;font-size:10px;letter-spacing:0.15em;text-transform:uppercase;padding:4px 10px;border-radius:20px;display:inline-block;margin-bottom:14px;background:rgba(167,139,250,0.12);color:var(--purple);}
.card-title{font-family:'DM Serif Display',serif;font-size:20px;margin-bottom:24px;}
.mg{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:24px;}
.mt{background:rgba(255,255,255,0.03);border:1px solid var(--border);border-radius:10px;padding:14px;}
.ml{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:0.15em;text-transform:uppercase;color:var(--muted);margin-bottom:6px;}
.mv{font-family:'DM Serif Display',serif;font-size:22px;line-height:1;color:var(--purple);}
.ms{font-size:11px;color:var(--muted);margin-top:3px;}
.rb{border-radius:12px;padding:16px;text-align:center;margin-bottom:24px;}
.rb .rl{font-family:'DM Mono',monospace;font-size:10px;letter-spacing:0.15em;text-transform:uppercase;margin-bottom:4px;}
.rb .rv{font-family:'DM Serif Display',serif;font-size:40px;line-height:1;}
.rb .rs{font-size:12px;color:var(--muted);margin-top:4px;}
.rg{background:rgba(110,231,183,0.07);border:1px solid rgba(110,231,183,0.2);}.rg .rl,.rg .rv{color:var(--green);}
.rbl{background:rgba(138,180,248,0.07);border:1px solid rgba(138,180,248,0.25);}.rbl .rl,.rbl .rv{color:var(--blue);}
.sl{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:0.18em;text-transform:uppercase;color:var(--muted);margin-bottom:12px;}
.div{border:none;border-top:1px solid var(--border);margin:20px 0;}
.tbl-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;}
.at{width:100%;border-collapse:collapse;font-size:11px;}
.at th{text-align:left;padding:6px 4px;color:var(--muted);font-family:'DM Mono',monospace;font-size:8.5px;letter-spacing:0.08em;text-transform:uppercase;font-weight:400;border-bottom:1px solid var(--border);white-space:nowrap;}
.at th.r,.at td.r{text-align:right;}
.at td{padding:8px 4px;border-bottom:1px solid rgba(255,255,255,0.03);white-space:nowrap;}
.at td.n{max-width:160px;overflow:hidden;text-overflow:ellipsis;}
.at td.r{font-family:'DM Mono',monospace;font-size:10.5px;}
.fn-grid{display:grid;grid-template-columns:1fr 1fr;gap:32px;align-items:start;}
@media(max-width:600px){body{padding:20px 16px;}.fn-grid{grid-template-columns:1fr!important;}.mg{grid-template-columns:1fr!important;}.grid{grid-template-columns:1fr!important;}.card{padding:20px;}}
.ta{display:inline-block;background:rgba(239,68,68,0.12);color:#f87171;font-family:'DM Mono',monospace;font-size:9px;padding:2px 6px;border-radius:4px;}
.wc{margin-bottom:24px;background:linear-gradient(135deg,rgba(252,211,77,0.08),rgba(252,211,77,0.03));border:1px solid rgba(252,211,77,0.25);border-radius:16px;padding:28px;position:relative;overflow:hidden;}
.wc::before{content:"\\1F3C6";position:absolute;right:28px;top:50%;transform:translateY(-50%);font-size:52px;opacity:0.15;}
.wt{font-family:'DM Mono',monospace;font-size:10px;letter-spacing:0.18em;text-transform:uppercase;color:var(--yellow);margin-bottom:8px;}
.wc h2{font-family:'DM Serif Display',serif;font-size:26px;color:var(--yellow);margin-bottom:6px;}
.wcp{font-size:13px;color:var(--muted);margin-bottom:20px;font-family:'DM Mono',monospace;}
.ws{display:flex;gap:24px;flex-wrap:wrap;}
.wsl{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:0.15em;text-transform:uppercase;color:var(--muted);margin-bottom:2px;}
.wsv{font-family:'DM Serif Display',serif;font-size:20px;color:var(--yellow);}
.kpi{background:rgba(255,255,255,0.03);border:1px solid var(--border);border-radius:10px;padding:14px;}
.kl{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:0.15em;text-transform:uppercase;color:var(--muted);margin-bottom:6px;}
.kv{font-family:'DM Serif Display',serif;font-size:22px;line-height:1;}
.ks{font-size:11px;color:var(--muted);margin-top:3px;}
.fn-bar{height:6px;border-radius:3px;overflow:hidden;background:rgba(255,255,255,0.05);margin-bottom:4px;}
.legend-row{display:flex;gap:20px;flex-wrap:wrap;font-size:11px;color:var(--muted);margin-bottom:18px;align-items:center;}
.dot-active{width:8px;height:8px;border-radius:50%;background:var(--green);display:inline-block;margin-right:4px;}
.dot-warn{width:8px;height:8px;border-radius:50%;background:var(--yellow);display:inline-block;margin-right:4px;}
</style>
</head>
<body>
<div class="header">
  <div class="label">Meta Ads · Google Ads · Shopify · Van Como Pina</div>
  <h1>Dashboard <em>VCP</em></h1>
  <div class="date">''' + fecha_hoy + ' · ' + dia_sem + ''' · Actualizado ahora · En ARS</div>
</div>
<div class="wrap">

<!-- AYER -->
<div style="background:linear-gradient(135deg,rgba(167,139,250,0.08),rgba(167,139,250,0.02));border:1px solid rgba(167,139,250,0.3);border-radius:16px;padding:28px;margin-bottom:24px;position:relative;overflow:hidden;">
  <div style="position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,var(--purple),#818cf8,var(--blue));border-radius:16px 16px 0 0;"></div>
  <div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:16px;margin-bottom:18px;">
    <div>
      <div style="font-family:'DM Mono',monospace;font-size:10px;letter-spacing:0.2em;text-transform:uppercase;color:var(--purple);margin-bottom:8px;">📅 Ayer · ''' + AYER.strftime('%d/%m/%Y') + '''</div>
      <div style="font-family:'DM Serif Display',serif;font-size:22px;">Meta Ads · <span style="font-style:italic;color:var(--purple);">datos completos</span></div>
    </div>
    <div style="text-align:right;">
      <div style="font-family:'DM Mono',monospace;font-size:10px;color:var(--muted);margin-bottom:4px;">GASTO AYER META</div>
      <div style="font-family:'DM Serif Display',serif;font-size:44px;color:var(--purple);line-height:1;">''' + fmt(hoy_meta) + '''</div>
      <div style="font-size:11px;color:var(--muted);">''' + str(hoy_comp) + ' compras pixel · ROAS ' + f'{hoy_roas:.1f}x' + '''</div>
    </div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;">
    <div class="kpi" style="border-color:rgba(167,139,250,0.2);"><div class="kl">Impresiones</div><div class="kv" style="color:var(--text);font-size:18px;">''' + f'{hoy_imp:,}' + '''</div><div class="ks">''' + f'{hoy_clk:,}' + ''' clics</div></div>
    <div class="kpi" style="border-color:rgba(167,139,250,0.2);"><div class="kl">CTR ayer</div><div class="kv" style="color:var(--blue);font-size:18px;">''' + pct(hoy_clk,hoy_imp) + '''</div><div class="ks">Meta solamente</div></div>
    <div class="kpi" style="border-color:rgba(167,139,250,0.2);"><div class="kl">Compras pixel</div><div class="kv" style="color:var(--green);font-size:18px;">''' + str(hoy_comp) + '''</div><div class="ks">ROAS ''' + f'{hoy_roas:.1f}x' + '''</div></div>
    <div class="kpi" style="border-color:rgba(167,139,250,0.2);background:rgba(167,139,250,0.04);"><div class="kl">Revenue pixel</div><div class="kv" style="color:var(--purple);font-size:16px;">''' + fmt(hoy_val) + '''</div></div>
  </div>
</div>

<!-- MES ACUMULADO -->
<div style="background:linear-gradient(135deg,rgba(255,255,255,0.04),rgba(255,255,255,0.01));border:1px solid rgba(255,255,255,0.12);border-radius:16px;padding:28px;position:relative;overflow:hidden;margin-bottom:24px;">
  <div style="position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,var(--purple),var(--blue),var(--yellow),var(--green));border-radius:16px 16px 0 0;"></div>
  <div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:16px;margin-bottom:24px;">
    <div>
      <div style="font-family:'DM Mono',monospace;font-size:10px;letter-spacing:0.2em;text-transform:uppercase;color:var(--muted);margin-bottom:8px;">Acumulado ''' + mes_label + ' · 1 al ' + str(AYER.day) + '''</div>
      <div style="font-family:'DM Serif Display',serif;font-size:24px;">Todas las plataformas · <span style="font-style:italic;color:var(--green);">mes completo</span></div>
    </div>
    <div style="text-align:right;">
      <div style="font-family:'DM Mono',monospace;font-size:10px;color:var(--muted);margin-bottom:4px;">ROAS SHOPIFY</div>
      <div style="font-family:'DM Serif Display',serif;font-size:48px;color:''' + rmc + ''';line-height:1;">''' + f'{mes_roas:.1f}x' + '''</div>
      <div style="font-size:11px;color:var(--muted);">''' + fmt(mes_inv) + ''' invertidos · ''' + f'{pct_mes:.0f}%' + ''' del mes</div>
    </div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px;margin-bottom:24px;">
    <div class="kpi"><div class="kl">Inversión Total</div><div class="kv" style="color:var(--text);">''' + fmt(mes_inv) + '''</div><div class="ks">Meta + Google</div></div>
    <div class="kpi"><div class="kl">Meta</div><div class="kv" style="color:var(--purple);">''' + fmt(mes_meta) + '''</div></div>
    <div class="kpi"><div class="kl">Google</div><div class="kv" style="color:var(--blue);">''' + fmt(mes_goog) + '''</div></div>
    <div class="kpi" style="background:rgba(110,231,183,0.08);border-color:rgba(110,231,183,0.3);"><div class="kl" style="color:var(--green);">Revenue Shopify</div><div class="kv" style="color:var(--green);">''' + fmt(mes_shop_rev) + '''</div><div class="ks">🔥 ''' + str(mes_shop_orders) + ''' órdenes</div></div>
  </div>
  <div class="sl">🔻 Funnel del mes (Meta)</div>
  <div class="fn-grid">
    <div>
      <div style="margin-bottom:4px;"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px;"><div style="display:flex;align-items:center;gap:8px;"><span>👁</span><span style="font-family:'DM Mono',monospace;font-size:10px;text-transform:uppercase;color:var(--muted);">Impresiones</span></div><span style="font-family:'DM Serif Display',serif;font-size:20px;color:var(--blue);">''' + f'{mes_imp:,}' + '''</span></div><div class="fn-bar"><div style="height:100%;width:100%;background:var(--blue);border-radius:3px;"></div></div></div>
      <div style="text-align:center;font-family:'DM Mono',monospace;font-size:9px;color:var(--muted);margin:3px 0;">▼ ''' + pct(mes_clks,mes_imp) + ''' clicaron</div>
      <div style="margin-bottom:4px;"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px;"><div style="display:flex;align-items:center;gap:8px;"><span>🖱</span><span style="font-family:'DM Mono',monospace;font-size:10px;text-transform:uppercase;color:var(--muted);">Clics</span></div><span style="font-family:'DM Serif Display',serif;font-size:20px;color:var(--blue);">''' + f'{mes_clks:,}' + '''</span></div><div class="fn-bar"><div style="height:100%;width:''' + fn_w(mes_clks,mes_imp) + ''';background:var(--blue);border-radius:3px;"></div></div></div>
      <div style="text-align:center;font-family:'DM Mono',monospace;font-size:9px;color:var(--muted);margin:3px 0;">▼ ''' + pct(mes_cart,mes_clks) + ''' agregaron al carrito</div>
      <div style="margin-bottom:4px;"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px;"><div style="display:flex;align-items:center;gap:8px;"><span>🛒</span><span style="font-family:'DM Mono',monospace;font-size:10px;text-transform:uppercase;color:var(--muted);">Add to cart</span></div><span style="font-family:'DM Serif Display',serif;font-size:20px;color:var(--yellow);">''' + f'{mes_cart:,}' + '''</span></div><div class="fn-bar"><div style="height:100%;width:''' + fn_w(mes_cart,mes_imp) + ''';background:var(--yellow);border-radius:3px;"></div></div></div>
      <div style="text-align:center;font-family:'DM Mono',monospace;font-size:9px;color:var(--muted);margin:3px 0;">▼ ''' + pct(mes_chk,mes_cart) + ''' checkout</div>
      <div style="margin-bottom:4px;"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px;"><div style="display:flex;align-items:center;gap:8px;"><span>💳</span><span style="font-family:'DM Mono',monospace;font-size:10px;text-transform:uppercase;color:var(--muted);">Checkout</span></div><span style="font-family:'DM Serif Display',serif;font-size:20px;color:var(--yellow);">''' + f'{mes_chk:,}' + '''</span></div><div class="fn-bar"><div style="height:100%;width:''' + fn_w(mes_chk,mes_imp) + ''';background:var(--yellow);border-radius:3px;"></div></div></div>
      <div style="text-align:center;font-family:'DM Mono',monospace;font-size:9px;color:var(--green);margin:3px 0;">▼ ''' + pct(mes_comp,mes_chk) + ''' cerraron ✅</div>
      <div><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px;"><div style="display:flex;align-items:center;gap:8px;"><span>✅</span><span style="font-family:'DM Mono',monospace;font-size:10px;text-transform:uppercase;color:var(--muted);">Compras pixel</span></div><span style="font-family:'DM Serif Display',serif;font-size:24px;color:var(--green);">''' + f'{mes_comp:,}' + '''</span></div><div class="fn-bar"><div style="height:100%;width:''' + fn_w(mes_comp,mes_imp) + ''';background:var(--green);border-radius:3px;"></div></div></div>
    </div>
    <div>
      <div class="sl" style="margin-bottom:14px;">Cierre por campaña</div>
      ''' + funnel_camps_html + '''
    </div>
  </div>
</div>

''' + winner_html + '''

<div class="legend-row">
  <span><span class="dot-active"></span> Activo hoy</span>
  <span><span class="dot-warn"></span> Activo este mes</span>
</div>

<div class="grid">
''' + camp_cards_html + '''
</div>

</div>
</body>
</html>'''

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(HTML)
print('index.html generado OK')

PAGES_URL = 'https://disenovcp-sys.github.io/VCPHTML/'
msg = (
    f'\U0001f4ca *VCP — Dashboard actualizado*\n\n'
    f'_{fecha_hoy}_\n\n'
    f'\U0001f4b8 Invertido mes: {fmt(mes_inv)}\n'
    f'\U0001f6d2 Revenue Shopify: {fmt(mes_shop_rev)}\n'
    f'\U0001f4c8 ROAS: {mes_roas:.1f}x\n\n'
    f'\U0001f449 [Ver dashboard]({PAGES_URL})'
)
resp = requests.post(f'https://api.telegram.org/bot{BOT}/sendMessage',
    json={'chat_id': CHAT, 'text': msg, 'parse_mode': 'Markdown'}, timeout=15)
resp.raise_for_status()
print('Telegram OK:', resp.json()['result']['message_id'])
