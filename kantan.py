"""kantan.py - Kantan.News küratörlüğü Ghost keşfine (2026-10-24; kullanıcı: "Kantan.news de önemli. Orası çok güzel kürasyon yapıyor").

Kantan bir tek sayfa uygulaması (RSS yok), ama robots.txt herkese açık, YALNIZCA OKUNUR uçları açıkça izinli bırakıyor (/api/news, /api/digest,
/api/bulten, /api/trends); başka hiçbir uç kullanılmaz, giriş yok. Content-Signal: ai-train=no (eğitim YOK; burada yalnızca seçim ve bağlantı),
use=reference (her madde Kantan'a ve asıl kaynağa bağlantı verir).

Kullanılanlar (Kantan'ın kendi seçtikleri, yani küratörlük sinyali):
  - /api/digest     → "Kantan Ping!" günlük seçkisi: spine (öne çıkanlar) + items + most_read (en çok okunan)
  - /api/bulten     → video bülten bölümleri (sabah/akşam haber seçkisi)
  - /api/news/slug/<slug> → haberin asıl kaynağı (`original_link`) ve özeti; bağlantı asıl kaynağa gider, Kantan sayfası `kesif_link` olur
Günde en çok iki kez okunur (sabah/öğle keşfi), sonuç günlük önbellekte (`kayitlar/kesif/kantan_<gün>.json`); ayrıntı isteği ≤20.
"""
import json
import time
from datetime import date, datetime
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
ONB = KLASOR / "kayitlar" / "kesif"
TABAN = "https://kantan.news"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh) VideoHub/1.0 (kisisel okuma araci)"}
ALAN = {"Teknoloji": "teknoloji_ai", "Yapay Zeka": "teknoloji_ai", "Otomobil": "teknoloji_ai", "Bilim": "hikaye", "Uzay": "hikaye", "Oyun": "populer_kultur",
        "Kültür": "populer_kultur", "Sinema": "populer_kultur", "Müzik": "populer_kultur", "Spor": "futbol", "Dünya": "toplum", "Sağlık": "toplum",
        "Ekonomi": "toplum", "Pazarlama": "kreatif", "Tasarım": "kreatif"}
ATLA = {"Savunma"}                                       # kişinin alanlarıyla ilgisiz; siyasete yakın


def _get(yol):
    import requests
    r = requests.get(TABAN + yol, headers=UA, timeout=20)
    r.raise_for_status()
    j = r.json()
    return j.get("data") if j.get("success") else None


def _z(t):
    try:
        return datetime.fromisoformat(str(t).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return time.time()


def maddeler(log=print, saat=12):
    """Kantan'ın bugünkü seçkisi keşif maddesi biçiminde. Son okumadan `saat` geçmediyse önbellek."""
    yol = ONB / f"kantan_{date.today().isoformat()}.json"
    try:
        o = json.loads(yol.read_text(encoding="utf-8"))
        if time.time() - o.get("zaman", 0) < saat * 3600:
            return o["maddeler"]
    except Exception:  # noqa: BLE001
        o = {}
    secilen = []                                         # (slug, temel bilgi, seçki adı)
    try:
        d = _get("/api/digest") or {}
        for grup, ad in (("spine", "Kantan Ping! · öne çıkan"), ("items", "Kantan Ping!"), ("most_read", "Kantan · en çok okunan")):
            for x in d.get(grup) or []:
                secilen.append((x.get("slug"), x, ad))
    except Exception as e:  # noqa: BLE001
        log(f"Kantan seçkisi okunamadı ({e})")
    try:
        b = _get("/api/bulten") or {}
        for ch in b.get("chapters") or []:
            if ch.get("slug") and ch.get("target_type") == "news":
                secilen.append((ch["slug"], {"title": ch.get("title"), "category": ch.get("category")}, "Kantan Bülten"))
    except Exception as e:  # noqa: BLE001
        log(f"Kantan bülteni okunamadı ({e})")
    out, gorulen = [], set()
    for slug, x, ad in secilen:
        if not slug or slug in gorulen or len(out) >= 20:
            continue
        gorulen.add(slug)
        kat = x.get("category_label") or x.get("category") or ""
        if kat in ATLA:
            continue
        try:
            n = _get(f"/api/news/slug/{slug}") or {}
        except Exception:  # noqa: BLE001
            n = {}
        asil = str(n.get("original_link") or "")
        asil = asil if asil.startswith("http") and "#" not in asil.split("/", 3)[-1][:1] else ""
        kantan_link = f"{TABAN}/haber/{slug}"
        resim = n.get("image_url") or x.get("image_url") or ""
        out.append({"alan": ALAN.get(kat, "toplum"), "kaynak": "Kantan.News", "baslik": str(n.get("title") or x.get("title") or "")[:220],
                    "ozet": str(n.get("social_summary") or x.get("social_summary") or n.get("excerpt") or "")[:500],
                    "link": asil or kantan_link, "kesif_link": kantan_link, "kesif_kantan": ad, "kantan_kategori": kat,
                    "resim": (TABAN + resim) if resim.startswith("/") else resim, "zaman": _z(n.get("published_at") or x.get("published_at"))})
    ONB.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps({"zaman": time.time(), "maddeler": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"Kantan.News: {len(out)} seçilmiş haber ({sum(1 for m in out if m['link'] != m['kesif_link'])} asıl kaynakla)")
    return out


def trendler():
    """Kantan'da bugün en çok yazılan etiketler (kategori, etiket, adet)."""
    try:
        return [{"kategori": x.get("category"), "terim": x.get("trending_tag"), "adet": x.get("post_count")} for x in _get("/api/trends") or []]
    except Exception:  # noqa: BLE001
        return []


if __name__ == "__main__":
    for m in maddeler(saat=0):
        print(m["kesif_kantan"], "|", m["alan"], "|", m["baslik"][:80], "→", m["link"][:70])
