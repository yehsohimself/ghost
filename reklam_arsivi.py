"""reklam_arsivi.py - Kullanıcının ödüllü işler analizlerinden (Drive: Cannes Lions 2024/2025/2026, D&AD 2026, Clio 2026, Clio Health 2026,
kullanıcının ilham kütüphanesi) tek, aranabilir reklam arşivi (2026-10-24; kullanıcı: "drive'ımda bolca ödüllü işlerin analizi var, excel halinde").

Drive'a YALNIZ OKUMA (rclone `gdrive_oku:`, Google tabloları xlsx olarak dışa aktarılır) → `reklam_arsivi/kaynak/*.xlsx` → `reklam_arsivi/arsiv.json`
(her iş: kaynak, yıl, ödül, kategori, ajans, marka, proje, ülke, link, problem, bağlam, içgörü, strateji, fikir, sıçrama, cümle, uygulama, rezonans,
sonuç, açıklama, öğrenme). Tablolar farklı başlıklar kullanır; başlık satırı ve sütunlar adlarından bulunur. Aynı iş birden çok tabloda varsa en dolu
kayıt kalır. Kullanım: Ghost (kreatif haberlere arşivden benzer iş: "aynı hamleyi 2025'te X yapmıştı"), Couple (fikir yönlerine emsal), Defter'de arama.
Elle: python reklam_arsivi.py indir | kur | ara "<sorgu>"
"""
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
ARSIV = KLASOR / "reklam_arsivi"
KAYNAK = ARSIV / "kaynak"
DOSYA = ARSIV / "arsiv.json"
# Drive kimliği, yerel ad, görünen kaynak, yıl
def _tablolar():
    """ayarlar.json `reklam_arsivi_tablolar`: [[Drive kimliği, yerel ad, görünen kaynak, yıl], ...] (kullanıcının kendi analiz tabloları)."""
    import ortak
    return [tuple(x) for x in (ortak.ayar().get("reklam_arsivi_tablolar") or []) if isinstance(x, list) and len(x) == 4]


ALAN = {
    "odul": ["ödül", "clio seviyesi", "en yüksek pencil", "ödül seviyesi", "en yüksek tanınma", "award", "level"],
    "kategori": ["kategori", "category", "work categories", "ana kategori", "medium"],
    "ajans": ["ajans", "entrant company", "agency"],
    "marka": ["marka", "client / brand", "brand"],
    "proje": ["proje", "proje ismi", "project", "work_title", "project name"],
    "ulke": ["ülke", "launch country", "country", "market"],
    "link": ["link", "clio link", "d&ad link", "work_url", "video / media", "url"],
    "problem": ["problem", "challenge"],
    "baglam": ["bağlam", "context"],
    "icgoru": ["içgörü", "insight"],
    "strateji": ["stratejik yaklaşım", "stratejik uygunluk", "strategy", "strategic approach", "strategic fit"],
    "fikir": ["fikir", "idea", "premise", "the idea"],
    "sicrama": ["yaratıcı sıçrama", "creative_leap", "creative leap"],
    "cumle": ["kampanya cümlesi", "campaign line", "tagline"],
    "uygulama": ["uygulama", "execution", "mechanism", "hayata geçiş"],
    "rezonans": ["kültürel rezonans", "cultural resonance", "why_it_matters"],
    "sonuc": ["sonuçlar", "sonuç", "results", "result", "amaca uygunluk / sonuç"],
    "neden": ["neden kazandı", "neden bu pencil", "why it won"],
    "aciklama": ["d&ad açıklaması (türkçe)", "alt başlık", "açıklama", "d&ad jüri modu", "description"],
    "ogrenme": ["temel çıkarım", "öğrenme", "learning", "key takeaway"],
}
ICERIK = ("problem", "icgoru", "fikir", "sicrama", "strateji", "aciklama", "uygulama")
ATLA_SEKME = re.compile(r"kontrol|indeks|kayıtlar|shortlist|özet|rehber|readme|staging|control|registry|router|routes|systems|taxonomy|aliases|claims|"
                        r"exclusions|watchlist|tüm işler|award evidence|celebrity|craft|mechanisms", re.I)


def log(m):
    print(m, flush=True)


def indir():
    """Drive'dan (yalnız okuma) tabloları xlsx olarak indirir."""
    KAYNAK.mkdir(parents=True, exist_ok=True)
    n = 0
    for fid, ad, *_ in _tablolar():
        r = subprocess.run(["/opt/homebrew/bin/rclone", "backend", "copyid", "gdrive_oku:", fid, str(KAYNAK / f"{ad}.xlsx"),
                            "--drive-export-formats", "xlsx"], capture_output=True, text=True, timeout=300)
        n += r.returncode == 0
    return n


def _n(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _b(s):
    """Başlık karşılaştırması: Türkçe büyük İ/I ve aksanlar katlanır ('İÇGÖRÜ' → 'icgoru')."""
    s = _n(s).replace("İ", "I").lower().replace("\u0307", "")
    return s.translate(str.maketrans("çğıöşüâî", "cgiosuai"))


def _baslik_bul(satirlar):
    en, idx = 0, -1
    for i, r in enumerate(satirlar[:8]):
        hucre = [_b(x) for x in r]
        say = sum(1 for h in hucre if h and any(h == _b(a) or h.startswith(_b(a)) for L in ALAN.values() for a in L))
        if say > en:
            en, idx = say, i
    return idx if en >= 3 else -1


def _sutunlar(baslik):
    hucre = [_b(x) for x in baslik]
    M = {}
    for alan, adlar in ALAN.items():
        for a in map(_b, adlar):                                    # tam eşleşme önce, sonra 'ile başlar'
            j = next((j for j, h in enumerate(hucre) if h == a), None)
            if j is None:
                j = next((j for j, h in enumerate(hucre) if h.startswith(a) and j not in M.values()), None)
            if j is not None and j not in M.values():
                M[alan] = j; break
    return M


def kur():
    import openpyxl
    kayitlar = {}
    for fid, ad, sistem, yil in _tablolar():
        yol = KAYNAK / f"{ad}.xlsx"
        if not yol.exists():
            continue
        wb = openpyxl.load_workbook(yol, read_only=True, data_only=True)
        for ws in wb.worksheets:
            if ATLA_SEKME.search(ws.title) and ws.title.lower() != "weekly picks":
                continue
            satirlar = [list(r) for r in ws.iter_rows(max_row=3000, values_only=True)]
            b = _baslik_bul(satirlar)
            if b < 0:
                continue
            S = _sutunlar(satirlar[b])
            if not ({"marka", "proje"} & set(S)) or not (set(ICERIK) & set(S)):
                continue
            for r in satirlar[b + 1:]:
                x = {k: _n(r[j])[:1500] for k, j in S.items() if j < len(r) and _n(r[j]) and _n(r[j]).lower() not in ("none", "-", "—", "n/a")}
                if not (x.get("proje") or x.get("marka")) or not any(x.get(k) for k in ICERIK):
                    continue
                x.update(kaynak=sistem, yil=yil, sekme=ws.title, tablo=ad)
                if not x.get("odul") and ws.title.lower() in ("grand prix", "grand", "gold", "silver", "bronze"):
                    x["odul"] = ws.title
                if sistem == "Cannes Lions" and yil == 2024:
                    x.setdefault("kategori", ws.title)
                anahtar = (sistem, yil, re.sub(r"\W+", "", (x.get("marka", "") + x.get("proje", "")).lower())[:60])
                dolu = sum(1 for k in ICERIK + ("cumle", "sonuc", "rezonans") if x.get(k))
                if dolu + (1 if not ad.endswith("_en") else 0) > kayitlar.get(anahtar, ({}, -1))[1]:
                    x["id"] = hashlib.sha1("|".join(map(str, anahtar)).encode()).hexdigest()[:10]
                    kayitlar[anahtar] = (x, dolu + (1 if not ad.endswith("_en") else 0))
    L = [x for x, _ in kayitlar.values()]
    ARSIV.mkdir(parents=True, exist_ok=True)
    DOSYA.write_text(json.dumps({"zaman": time.time(), "isler": L}, ensure_ascii=False), encoding="utf-8")
    sayim = {}
    for x in L:
        sayim[f"{x['kaynak']} {x['yil']}"] = sayim.get(f"{x['kaynak']} {x['yil']}", 0) + 1
    log(f"Reklam arşivi: {len(L)} iş · " + ", ".join(f"{k} {v}" for k, v in sorted(sayim.items())))
    return L


_ONB = {"zaman": 0, "isler": [], "dizin": []}
TR = str.maketrans("çğıöşüâîûÇĞİÖŞÜ", "cgiosuaiucgiosu")
BOS = set("bir bu ve ile için gibi daha çok olan olarak kadar ama veya hem her şey the and for with that this from into their your they them have has was were are its our not but you".split())


def _kokler(s):
    s = str(s or "").lower().translate(TR)
    return {w[:5] for w in re.findall(r"[a-z0-9]{4,}", s) if w not in BOS}


def isler():
    if DOSYA.exists() and DOSYA.stat().st_mtime != _ONB["zaman"]:
        _ONB["isler"] = json.loads(DOSYA.read_text(encoding="utf-8")).get("isler") or []
        _ONB["dizin"] = [({"agir": _kokler(f"{x.get('marka', '')} {x.get('proje', '')} {x.get('ajans', '')}"),
                           "orta": _kokler(" ".join(x.get(k, "") for k in ("fikir", "icgoru", "sicrama", "cumle", "kategori"))),
                           "hafif": _kokler(" ".join(x.get(k, "") for k in ("problem", "baglam", "strateji", "uygulama", "aciklama", "rezonans", "ogrenme")))})
                         for x in _ONB["isler"]]
        _ONB["zaman"] = DOSYA.stat().st_mtime
    return _ONB["isler"]


def ara(q, n=20):
    L = isler()
    K = _kokler(q)
    if not K:
        return []
    puan = []
    for x, d in zip(L, _ONB["dizin"]):
        p = 3 * len(K & d["agir"]) + 2 * len(K & d["orta"]) + len(K & d["hafif"])
        if p:
            puan.append((p + {"Grand Prix": 1.5, "Grand": 1.5, "Titanium": 1.5, "Gold": 1}.get(x.get("odul", ""), 0) * 0.3, x))
    puan.sort(key=lambda t: -t[0])
    return [x for _, x in puan[:n]]


def kisa(x, uzun=False):
    """Bir işin tek satırlık künyesi + çekirdeği (istemler için)."""
    k = f"{x.get('marka', '')} · {x.get('proje', '')} ({x.get('ajans', '')}; {x['kaynak']} {x['yil']} {x.get('odul', '')}".strip() + ")"
    cekirdek = x.get("fikir") or x.get("aciklama") or ""
    s = f"{k}: {cekirdek[:300 if uzun else 160]}"
    if uzun:
        for a, ad in (("icgoru", "İçgörü"), ("sicrama", "Sıçrama"), ("cumle", "Cümle"), ("sonuc", "Sonuç"), ("ogrenme", "Çıkarım")):
            if x.get(a):
                s += f" | {ad}: {x[a][:200]}"
    return s


def benzerleri_sec(ogeler, log=print, en_cok=2):
    """ogeler: [{id, metin}] (haber/brief). Her biri için arşivden en çok 2 GERÇEKTEN benzer iş (aynı hamle, aynı içgörü, aynı mecra numarası;
    yalnız aynı kategori/sektör yetmez). Ön eleme kök örtüşmesi (20 aday), seçim sonnet tek çağrı. Döner {id: [{is, neden}]}."""
    import paylasim
    aday = {o["id"]: ara(o["metin"], 20) for o in ogeler}
    aday = {k: v for k, v in aday.items() if v}
    if not aday:
        return {}
    istem = ("Aşağıda haberler/işler ve her biri için kişinin kendi ödüllü reklam arşivinden adaylar var. Her haber için, adaylardan GERÇEKTEN benzer olan "
             "en çok " + str(en_cok) + " işi seç: aynı yaratıcı hamle, aynı içgörü, aynı mecra numarası ya da bilinçli bir karşıtlık. Aynı sektör ya da aynı "
             "kategori YETMEZ. Benzer yoksa boş bırak. neden: iki işin ortak hamlesini ya da farkını tek cümleyle, somut.\n"
             'JSON: {"eslesme": [{"haber": "id", "is": "aday id", "neden": "..."}]}\n\n')
    for o in ogeler:
        if o["id"] not in aday:
            continue
        istem += f"HABER {o['id']}: {o['metin'][:700]}\nADAYLAR:\n" + "\n".join(f"  [{x['id']}] {kisa(x)}" for x in aday[o["id"]]) + "\n\n"
    try:
        c = paylasim._claude_json(istem, model_adi="sonnet", zaman_asimi=240)
    except Exception as e:  # noqa: BLE001
        log(f"Arşiv eşleştirmesi yapılamadı: {e}"); return {}
    tum = {x["id"]: x for L in aday.values() for x in L}
    out = {}
    for e in c.get("eslesme") or []:
        h, i = str(e.get("haber")), str(e.get("is"))
        if i in tum and h in aday and len(out.get(h, [])) < en_cok:
            out.setdefault(h, []).append({"is": tum[i], "neden": str(e.get("neden") or "")[:240]})
    if out:
        log(f"Reklam arşivinden {sum(len(v) for v in out.values())} benzer iş bulundu")
    return out


def tazele(gun=7):
    """Haftada bir Drive'dan yeniden indirip kurar (tablolar büyüyor)."""
    if DOSYA.exists() and DOSYA.stat().st_mtime > time.time() - gun * 86400:
        return False
    if indir():
        kur()
    return True


if __name__ == "__main__":
    k = sys.argv[1] if len(sys.argv) > 1 else "kur"
    if k == "indir":
        print(indir(), "tablo indi"); kur()
    elif k == "ara":
        for x in ara(" ".join(sys.argv[2:]), 10):
            print("-", kisa(x))
    else:
        kur()
