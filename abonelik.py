"""abonelik.py - Kullanıcının ücretli üyelikleri olan sitelerin (Adweek...) tam yazılarını okumak (2026-10-24; kullanıcı: "adweek üyeliğim var,
Ghost bundan da yararlanabilir").

Yol: Chrome'daki oturum çerezleri (yt-dlp'nin `extract_cookies_from_browser`, yalnız bu Mac'te, yalnız listedeki alan adlarının çerezleri) ile
sayfa istenir. Çerezler HİÇBİR yere yazılmaz, yalnız bellekte 6 saat tutulur. Liste: ayarlar.json `abonelikler` (varsayılan adweek.com).
Okunamazsa (Chrome kilitli, Anahtar Zinciri izni yok) sessizce düz istek yapılır; yazının açık kısmı okunur.
"""
import html
import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

KLASOR = Path(__file__).resolve().parent
VARSAYILAN = ["adweek.com"]
_CEREZ = {"zaman": 0, "jar": None, "hata": ""}
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36"


def alanlar():
    try:
        d = json.loads((KLASOR / "ayarlar.json").read_text(encoding="utf-8"))
        L = d.get("abonelikler")
        return [str(x).lower().strip() for x in L] if isinstance(L, list) else VARSAYILAN
    except Exception:  # noqa: BLE001
        return VARSAYILAN


def abone_mi(url):
    h = (urlparse(url).hostname or "").lower()
    return any(h == a or h.endswith("." + a) for a in alanlar())


def _cerezler():
    if _CEREZ["jar"] is not None and time.time() - _CEREZ["zaman"] < 6 * 3600:
        return _CEREZ["jar"]
    jar = requests.cookies.RequestsCookieJar()
    try:
        from yt_dlp.cookies import extract_cookies_from_browser
        A = alanlar()
        for c in extract_cookies_from_browser("chrome"):
            d = c.domain.lstrip(".").lower()
            if any(d == a or d.endswith("." + a) for a in A):
                jar.set_cookie(c)
        _CEREZ["hata"] = ""
    except Exception as e:  # noqa: BLE001
        _CEREZ["hata"] = str(e)[:200]
    _CEREZ.update(zaman=time.time(), jar=jar)
    return jar


def _adweek_tam(url, timeout=20):
    """Adweek yazısının tam metni sitenin kendi WordPress ucundan (slug ile). 26 Ekim: Chrome'da oturum kapalıyken üyelere özel yazılar sayfada yarıda
    kesiliyor (Omnicom yazısı 1.114 karakter), uç tam metni veriyor (3.332). Kişinin ücretli üyeliği var; giriş beklemeden tam yazı okunur.
    Döner: (başlık, içerik html) ya da None."""
    from urllib.parse import urlparse
    yol = [x for x in urlparse(url).path.split("/") if x]
    if len(yol) < 2 or not re.fullmatch(r"[a-z0-9-]{8,}", yol[-1]):
        return None
    try:
        r = requests.get("https://www.adweek.com/wp-json/wp/v2/posts", params={"slug": yol[-1], "_fields": "title,content,date"},
                         headers={"User-Agent": UA}, timeout=timeout)
        L = r.json() if r.status_code == 200 else []
        if L and (L[0].get("content") or {}).get("rendered"):
            return (L[0].get("title") or {}).get("rendered", ""), L[0]["content"]["rendered"], str(L[0].get("date") or "")[:10]
    except Exception:  # noqa: BLE001
        pass
    return None


def get(url, timeout=25, headers=None):
    """requests.get gibi; abonelik sitesiyse Chrome oturumuyla. Adweek yazılarında sayfanın <article> bölümü yerine tam metin konur (okuyucular ilk
    <article>'ı alır)."""
    if abone_mi(url):
        h = {"User-Agent": UA, "Accept-Language": "en,tr;q=0.8", **{k: v for k, v in (headers or {}).items() if k != "User-Agent"}}
        try:
            r = requests.get(url, timeout=timeout, headers=h, cookies=_cerezler())
            if "adweek.com" in (urlparse(r.url).hostname or "") and r.status_code < 400:
                tam = _adweek_tam(r.url)
                if tam:
                    baslik, icerik, tarih = tam
                    ek = (f'<meta property="og:title" content="{html.escape(html.unescape(baslik))}">'
                          f'<meta property="article:published_time" content="{tarih}"><article>{icerik}</article>')
                    r._content = (ek + re.sub(r"(?is)<article\b.*?</article>", " ", r.text)).encode("utf-8")
                    r.encoding = "utf-8"
            return r
        except Exception:  # noqa: BLE001
            pass
    return requests.get(url, timeout=timeout, headers=headers)


def durum():
    jar = _cerezler()
    return {"alanlar": alanlar(), "cerez": len(jar), "hata": _CEREZ["hata"]}
