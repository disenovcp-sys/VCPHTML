"""
Agrega como tags todas las palabras del título de cada producto activo.
Así cualquier palabra del nombre encuentra el producto en el buscador.
"""
import os, requests, time

STORE = os.environ['SHOPIFY_STORE']
TOKEN = os.environ['SHOPIFY_TOKEN']

STOP = {
    'de','del','la','el','los','las','y','con','sin','para','en','a','c',
    'fit','the','and','for','von','van','una','uno','los','sus','por','al',
}

def get_products():
    url  = f"https://{STORE}/admin/api/2026-04/products.json"
    hdrs = {"X-Shopify-Access-Token": TOKEN}
    prms = {"limit": 250, "status": "active", "fields": "id,title,tags"}
    all_p = []
    while url:
        r = requests.get(url, headers=hdrs, params=prms, timeout=30)
        r.raise_for_status()
        all_p.extend(r.json().get("products", []))
        lnk = r.headers.get("Link", "")
        url, prms = None, None
        for part in lnk.split(","):
            if 'rel="next"' in part:
                url = part.split(";")[0].strip().strip("<>")
    return all_p

def title_words(title):
    words = set()
    for w in title.split():
        w = w.strip("(),./–-").lower()
        if len(w) > 1 and w not in STOP:
            words.add(w)
    return words

products = get_products()
print(f"Total productos activos: {len(products)}")

updated = 0
skipped = 0
for p in products:
    existing = set(t.strip().lower() for t in p["tags"].split(",") if t.strip())
    words    = title_words(p["title"])
    new_tags = existing | words

    if new_tags == existing:
        skipped += 1
        continue

    added = words - existing
    url  = f"https://{STORE}/admin/api/2026-04/products/{p['id']}.json"
    hdrs = {"X-Shopify-Access-Token": TOKEN, "Content-Type": "application/json"}
    r = requests.put(url, headers=hdrs,
                     json={"product": {"id": p["id"], "tags": ", ".join(sorted(new_tags))}},
                     timeout=30)
    r.raise_for_status()
    print(f"  ✅ {p['title']} → +{added}")
    updated += 1
    time.sleep(0.5)

print(f"\nActualizados: {updated} | Sin cambios: {skipped}")
