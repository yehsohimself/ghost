"""icerik.py - Studio'da video dışı içerik: görsel ve yazı (2026-11-01; kullanıcı: "Studio sadece video için çalışmamalı. Instagram linki attığımda
oradaki statik görseli de indirebilmeliyim; yazı indirmeye izin vermeyen bir siteden yazı da indirebilmeliyim").

Görsel: Instagram/Pinterest/Tumblr/TikTok fotoğraf gönderisi (gallery-dl), X gönderisi (herkese açık gömme servisi), doğrudan görsel bağlantısı, görseli çok
yazısı az sayfalar. Önizlemede dosyalar önbelleğe iner, yazısı okunur (macOS Vision); "İndir" bunları Görseller klasörüne alır.
Yazı: kademeli okuma: düz istek → tarayıcı kimliği → görünmez Chrome (JavaScript'le açılan sayfalar); istenirse kişinin kendi tarayıcı oturumu. Kopyalama/sağ tık engeli
tarayıcı tarafındadır, sunucudan gelen metni etkilemez. Sayfaya gelmeyen metni (üyelik duvarı) atlatmaya ÇALIŞMAZ: ücretli işaretli yazıda açık kısım alınır ve bu söylenir.
Yazı kaydı transkriptle AYNI biçimde (`transkript_yazi_*.json`, `veri.yazi`): özet, çeviri, Sor, arama, asistan olduğu gibi çalışır; "zaman" = okuma konumu (saniye).
"""
import hashlib
import ipaddress
import json
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import ortak

KLASOR = Path(__file__).resolve().parent
GORSELLER = KLASOR / "indirilenler" / "Görseller"
DIZIN = GORSELLER / ".dizin.json"
KUCUK = GORSELLER / ".kucuk"
ONB = KLASOR / ".onbellek" / "icerik"
COP = KLASOR / ".cop"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
RESIM_UZ = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".heic")
EN_COK_GORSEL = 40
YETERLI_KELIME = 300          # bu kadar metin çıktıysa daha zor yola geçilmez
EN_AZ_YAZI = 120              # altı "okunacak yazı" sayılmaz
_kilit = threading.RLock()

# Bilinen video siteleri: burada önce video yolu (yt-dlp) denenir
VIDEO_SITE = re.compile(r"(^|\.)(youtube\.com|youtu\.be|youtube-nocookie\.com|vimeo\.com|twitch\.tv|dailymotion\.com|fb\.watch|rumble\.com|bilibili\.com|loom\.com|"
                        r"soundcloud\.com|ted\.com|kick\.com|streamable\.com|wistia\.com|mixcloud\.com)$", re.I)
GORSEL_SITE = re.compile(r"(^|\.)(pinterest\.[a-z.]+|pin\.it|tumblr\.com|flickr\.com|imgur\.com|deviantart\.com|artstation\.com|behance\.net|bsky\.app)$", re.I)
BLOK_SAYFA = re.compile(r"access denied|please enable js|enable javascript|too many requests|just a moment|verify you are human|are you a robot|attention required|"
                        r"robot olmadığınızı|you don.t have permission|checking your browser|captcha", re.I)
UCRETLI_IZ = re.compile(r"paywall|subscribe to (continue|read)|to continue reading|subscribers? only|abone ol(un)?\b.{0,40}(devam|oku)|üyelere özel|devamını okumak için", re.I)
KOPYA_ENGEL = re.compile(r"oncontextmenu|oncopy|onselectstart|ondragstart|user-select\s*:\s*none", re.I)
SUS_GORSEL = re.compile(r"logo|icon|avatar|sprite|pixel|badge|spacer|placeholder|profile_images|gravatar|emoji|/ads?/|banner|\.svg(\?|$)|preferred_source", re.I)


# ------------------------------------------------------------------------------------------------------- bağlantı
def guvenli(link):
    """Yalnız herkese açık http(s): bu Mac'e ya da yerel ağa giden bağlantı açılmaz."""
    try:
        u = urlparse(str(link))
        if u.scheme not in ("http", "https") or not u.hostname:
            return False
        h = u.hostname.lower()
        if h in ("localhost",) or h.endswith((".local", ".localhost", ".internal")):
            return False
        for b in socket.getaddrinfo(h, None):
            ip = ipaddress.ip_address(b[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
                return False
        return True
    except Exception:  # noqa: BLE001
        return False


def link_turu(link):
    """video | gorsel (gönderi ya da doğrudan görsel) | pdf | sayfa. Yalnız adrese bakar, ağa çıkmaz."""
    u = urlparse(str(link))
    h, y = (u.hostname or "").lower(), u.path.lower()
    if y.endswith(".pdf"):
        return "pdf"
    if y.endswith(RESIM_UZ):
        return "gorsel"
    if h.endswith("instagram.com"):
        return "video" if re.search(r"/(reel|reels|tv)/", y) else ("gorsel" if "/p/" in y else "sayfa")
    if h.endswith("tiktok.com"):
        return "gorsel" if "/photo/" in y else "video"
    if h in ("x.com", "www.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"):
        return "gorsel" if "/status/" in y else "sayfa"
    if h.endswith("facebook.com"):
        return "video" if re.search(r"/(watch|reel|videos)", y) else "sayfa"
    if h.endswith("reddit.com"):
        return "sayfa"
    if VIDEO_SITE.search(h):
        return "video"
    if GORSEL_SITE.search(h):
        return "gorsel"
    return "sayfa"


def _kisa(link):
    return hashlib.sha1(str(link).encode()).hexdigest()[:14]


def _site_adi(link):
    return re.sub(r"^www\.", "", (urlparse(link).hostname or "").lower())


def _tek_satir(s, n=80):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    if len(s) <= n:
        return s
    k = s[:n].rsplit(" ", 1)[0]
    return (k or s[:n]).rstrip(" ,.;:-") + "…"


def _ad_temizle(s, n=70):
    s = re.sub(r"[#@]\S+", " ", str(s or ""))
    s = re.sub(r"[^\w .,'’&()\-]+", " ", s, flags=re.UNICODE)
    return ortak.guvenli_ad(_tek_satir(s, n).rstrip("…")) or "Görsel"


# ------------------------------------------------------------------------------------------------------- sayfa okuma
def _cerezler(url):
    """Kişinin Chrome oturumu: yalnız bu sitenin çerezleri, yalnız bellekte."""
    import requests
    jar = requests.cookies.RequestsCookieJar()
    h = (urlparse(url).hostname or "").lower()
    kok = ".".join(h.split(".")[-3:] if re.search(r"\.(com|co|org|net|gov|edu)\.[a-z]{2}$", h) else h.split(".")[-2:])
    from yt_dlp.cookies import extract_cookies_from_browser
    for c in extract_cookies_from_browser("chrome"):
        d = c.domain.lstrip(".").lower()
        if d == kok or d.endswith("." + kok):
            jar.set_cookie(c)
    return jar


def _duz(url, cerez=False):
    import requests
    return requests.get(url, timeout=25, headers={"User-Agent": UA, "Accept-Language": "tr,en;q=0.8,de;q=0.6"}, cookies=_cerezler(url) if cerez else None)


def _kimlik(url):
    from curl_cffi import requests as cr
    return cr.get(url, impersonate="chrome", timeout=25, allow_redirects=True)


def _krom(url):
    """Görünmez Chrome: JavaScript'le gelen sayfalar. Boş, geçici profil (kişinin oturumu kullanılmaz)."""
    if not Path(CHROME).exists():
        return ""
    with tempfile.TemporaryDirectory() as d:
        p = subprocess.run([CHROME, "--headless=new", f"--user-data-dir={d}", "--disable-gpu", "--no-first-run", "--virtual-time-budget=8000", "--dump-dom", url],
                           capture_output=True, text=True, timeout=60)
    return p.stdout or ""


def _ld_json(h):
    """Sayfanın yapısal verisi: articleBody, ücretli işareti, tarih."""
    out = {"govde": "", "ucretli": False, "yazar": "", "tarih": "", "baslik": ""}
    for m in re.finditer(r'(?is)<script[^>]+application/ld\+json[^>]*>(.*?)</script>', h):
        try:
            d = json.loads(m.group(1).strip())
        except Exception:  # noqa: BLE001
            continue
        for x in (d if isinstance(d, list) else (d.get("@graph") or [d]) if isinstance(d, dict) else []):
            if not isinstance(x, dict):
                continue
            if str(x.get("isAccessibleForFree")).lower() == "false":
                out["ucretli"] = True
            if isinstance(x.get("articleBody"), str) and len(x["articleBody"]) > len(out["govde"]):
                out["govde"] = x["articleBody"]
                out["baslik"] = str(x.get("headline") or "")
                out["tarih"] = str(x.get("datePublished") or "")[:10]
                a = x.get("author")
                a = a[0] if isinstance(a, list) and a else a
                out["yazar"] = str(a.get("name") if isinstance(a, dict) else a or "")
    return out


def _satir_temiz(s):
    """Markdown satır içi işaretleri düz metne."""
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", s)
    s = re.sub(r"\[([^\]]*)\]\((?:<[^>]*>|[^)]*)\)", r"\1", s)
    s = re.sub(r"(\*\*|__)(.+?)\1", r"\2", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", s)
    s = re.sub(r"\\([\\`*_{}\[\]()#+\-.!|>])", r"\1", s)
    return re.sub(r"\s+", " ", s).strip()


def bloklara(md, baslik=""):
    """Markdown → [{tur: h1|h2|h3|p|li|alinti|tablo|img, metin, url}]. Baştaki başlık tekrarı ve art arda aynı satırlar atılır."""
    out, tablo, gorulen = [], [], set()

    def tablo_bitir():
        if tablo:
            satir = [r for r in tablo if not re.fullmatch(r"[\s|:\-]+", r)]
            if len(satir) >= 2:
                out.append({"tur": "tablo", "metin": "\n".join(" | ".join(_satir_temiz(h) for h in r.strip().strip("|").split("|")) for r in satir)})
            tablo.clear()
    for ham in str(md or "").splitlines():
        s = ham.strip()
        if s.startswith("|") and s.endswith("|"):
            tablo.append(s)
            continue
        tablo_bitir()
        if not s:
            continue
        m = re.fullmatch(r"!\[([^\]]*)\]\(<?([^)>\s]+)>?[^)]*\)", s)
        if m:
            out.append({"tur": "img", "metin": _satir_temiz(m.group(1)), "url": m.group(2)})
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            d = len(m.group(1))
            b = {"tur": "h1" if d == 1 else "h2" if d == 2 else "h3", "metin": _satir_temiz(m.group(2))}
        elif re.match(r"^([-*+]|\d+[.)])\s+", s):
            b = {"tur": "li", "metin": _satir_temiz(re.sub(r"^([-*+]|\d+[.)])\s+", "", s))}
        elif s.startswith(">"):
            b = {"tur": "alinti", "metin": _satir_temiz(s.lstrip("> "))}
        else:
            b = {"tur": "p", "metin": _satir_temiz(s)}
        if not b["metin"] or len(b["metin"]) < 2:
            continue
        anahtar = b["metin"].lower()
        if anahtar in gorulen and len(anahtar) < 200:
            continue
        gorulen.add(anahtar)
        out.append(b)
    tablo_bitir()
    if baslik:
        taban = re.sub(r"\W+", "", baslik).lower()
        for i, b in enumerate(out[:3]):
            if b["tur"] in ("h1", "h2", "p") and re.sub(r"\W+", "", b["metin"]).lower() == taban:
                out.pop(i)
                break
    return out


def _dil_bul(metin, h=""):
    m = re.search(r'<html[^>]+lang=["\']([a-zA-Z]{2})', h or "")
    if m:
        return m.group(1).lower()
    k = " " + str(metin or "")[:6000].lower() + " "
    puan = {"tr": sum(k.count(x) for x in (" ve ", " bir ", " için ", " ile ", " bu ", " olarak ")), "en": sum(k.count(x) for x in (" the ", " and ", " of ", " to ", " that ")),
            "de": sum(k.count(x) for x in (" der ", " die ", " und ", " das ", " nicht "))}
    return max(puan, key=puan.get)


def html_coz(h, url):
    """Ham sayfadan yazı. Döner: {baslik, yazar, tarih, site, dil, bloklar, kelime, kapak, ucretli, kopya_engeli, blok}"""
    import html as H
    import trafilatura
    md = trafilatura.extract(h, url=url, include_images=True, include_formatting=True, include_tables=True, include_links=False, output_format="markdown", favor_recall=True) or ""
    try:
        m = trafilatura.extract_metadata(h, default_url=url)
    except Exception:  # noqa: BLE001
        m = None
    ld = _ld_json(h)
    baslik = H.unescape(str((m.title if m else "") or ld["baslik"] or "")).strip()
    bl = bloklara(md, baslik)
    kel = sum(len(b["metin"].split()) for b in bl if b["tur"] != "img")
    # Yayıncının yapısal verisindeki tam metin (ücretli işaretli değilse): sayfa JS ile çiziyorsa ya da çıkarıcı kısa kaldıysa
    govde = H.unescape(ld["govde"])
    if not ld["ucretli"] and len(govde.split()) > kel * 1.3 and len(govde.split()) >= EN_AZ_YAZI:
        parca = [x.strip() for x in re.split(r"\n{1,}", govde) if x.strip()]
        if len(parca) < 3:
            cumle = re.split(r"(?<=[.!?…])\s+", govde)
            parca = [" ".join(cumle[i:i + 4]) for i in range(0, len(cumle), 4)]
        resimler = [b for b in bl if b["tur"] == "img"]
        bl = resimler[:1] + [{"tur": "p", "metin": _satir_temiz(x)} for x in parca]
        kel = len(govde.split())
    mk = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', h, re.I) or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', h, re.I)
    kapak = urljoin(url, H.unescape(mk.group(1))) if mk else ""
    metin = " ".join(b["metin"] for b in bl if b["tur"] != "img")
    return {"baslik": baslik or _site_adi(url), "yazar": str((m.author if m else "") or ld["yazar"] or "")[:120], "tarih": str((m.date if m else "") or ld["tarih"] or "")[:10],
            "site": str((m.sitename if m else "") or _site_adi(url))[:80], "dil": _dil_bul(metin, h), "bloklar": bl, "kelime": kel, "kapak": kapak,
            "makale": bool(re.search(r'property=["\']og:type["\'][^>]+content=["\']article|"@type"\s*:\s*"(News)?Article"', h, re.I)), "ucretli": ld["ucretli"] or bool(kel < 400 and UCRETLI_IZ.search(h)), "kopya_engeli": bool(KOPYA_ENGEL.search(h)), "blok": bool(kel < 150 and BLOK_SAYFA.search(metin + " " + baslik))}


def _pdf_metin(veri):
    with tempfile.NamedTemporaryFile(suffix=".pdf") as t:
        t.write(veri)
        t.flush()
        from Foundation import NSURL
        from Quartz import PDFDocument
        d = PDFDocument.alloc().initWithURL_(NSURL.fileURLWithPath_(t.name))
        if not d:
            return "", ""
        sayfa = [str(d.pageAtIndex_(i).string() or "") for i in range(min(d.pageCount(), 400))]
        ozn = d.documentAttributes() or {}
        return "\n\n".join(sayfa), str(ozn.get("Title") or "")


def _pdf_kayit(link, icerik_baytlari):
    try:
        metin, ad = _pdf_metin(icerik_baytlari)
    except Exception as e:  # noqa: BLE001
        return {"hata": f"PDF okunamadı: {str(e)[:100]}"}
    bl = [{"tur": "p", "metin": _satir_temiz(x)} for x in re.split(r"\n\s*\n", metin) if len(x.strip()) > 2]
    kel = sum(len(b["metin"].split()) for b in bl)
    if kel < 20:
        return {"hata": "Bu PDF'in metni okunamadı (taranmış olabilir)."}
    return {"baslik": ad or Path(urlparse(link).path).stem, "yazar": "", "tarih": "", "site": _site_adi(link), "dil": _dil_bul(metin), "bloklar": bl, "kelime": kel, "kapak": "",
            "ucretli": False, "kopya_engeli": False, "blok": False, "yontem": "pdf", "link": link}


def yazi_al(link, cerez=""):
    """Kademeli okuma; en iyi sonucu döner ya da {hata}. cerez: 'chrome' ise kişinin kendi oturumu."""
    denemeler = []
    try:
        import abonelik
        if abonelik.abone_mi(link):
            denemeler.append(("abonelik", lambda: abonelik.get(link, timeout=25, headers={"User-Agent": UA})))
    except ImportError:
        pass
    if cerez == "chrome":
        denemeler.append(("oturum", lambda: _duz(link, True)))
    denemeler += [("duz", lambda: _duz(link)), ("kimlik", lambda: _kimlik(link)), ("krom", lambda: _krom(link))]
    en_iyi, durum = None, 0
    for ad, f in denemeler:
        try:
            r = f()
            h = r if isinstance(r, str) else r.text
            kod = 200 if isinstance(r, str) else r.status_code
            tur = "" if isinstance(r, str) else str(r.headers.get("content-type") or "").lower()
            if "pdf" in tur or (not isinstance(r, str) and r.content[:5] == b"%PDF-"):
                return _pdf_kayit(link, r.content)
            if tur and "html" not in tur and "text" not in tur:
                continue
        except Exception:  # noqa: BLE001
            continue
        durum = durum or kod
        if kod >= 400 or len(h) < 200:
            continue
        s = html_coz(h, link)
        s["yontem"] = ad
        if s["blok"]:
            continue
        if not en_iyi or s["kelime"] > en_iyi["kelime"]:
            en_iyi = s
        if en_iyi["kelime"] >= YETERLI_KELIME:
            break
        if s["ucretli"] and ad != "duz":
            break
    if not en_iyi:
        return {"hata": "giris" if durum in (401, 403) else "Sayfa açılmadı.", "durum": durum}
    en_iyi["link"] = link
    return en_iyi


# ------------------------------------------------------------------------------------------------------- görsel bulma
def _gallery(link, oturum=False):
    """gallery-dl yalnız bilgi modunda. Döner: (öğeler, üst bilgi) ya da ([], {})."""
    komut = [sys.executable, "-m", "gallery_dl", "-j", "-q"]
    if oturum:
        h = (urlparse(link).hostname or "").lower()
        komut += ["--cookies-from-browser", "chrome/." + ".".join(h.split(".")[-2:])]
    try:
        p = subprocess.run(komut + [link], capture_output=True, text=True, timeout=45)
        d = json.loads(p.stdout or "[]")
    except Exception:  # noqa: BLE001
        return [], {}
    og, ust = [], {}
    for x in d if isinstance(d, list) else []:
        if not isinstance(x, list) or len(x) < 2:
            continue
        if x[0] == 3 and len(x) >= 3 and isinstance(x[2], dict):
            m = x[2]
            uz = str(m.get("extension") or Path(urlparse(str(x[1])).path).suffix.lstrip(".")).lower()
            og.append({"url": str(x[1]), "en": int(m.get("width") or 0), "boy": int(m.get("height") or 0), "video": uz in ("mp4", "mov", "webm", "m4v")})
            ust = ust or m
        elif x[0] == 2 and isinstance(x[1], dict):
            ust = ust or x[1]
    return og, ust


def _x_gonderi(link):
    """X gönderisi: herkese açık gömme servisi (giriş yok, yalnız okuma)."""
    import requests
    m = re.search(r"/status(?:es)?/(\d+)", link)
    if not m:
        return None
    r = requests.get("https://cdn.syndication.twimg.com/tweet-result", params={"id": m.group(1), "token": "a", "lang": "tr"}, headers={"User-Agent": UA}, timeout=15)
    if r.status_code != 200:
        return None
    d = r.json()
    og = []
    for x in d.get("mediaDetails") or []:
        if x.get("type") == "photo":
            og.append({"url": x["media_url_https"] + "?name=orig", "en": int((x.get("original_info") or {}).get("width") or 0), "boy": int((x.get("original_info") or {}).get("height") or 0), "video": False})
        else:
            og.append({"url": "", "en": 0, "boy": 0, "video": True})
    u = d.get("user") or {}
    return {"ogeler": og, "kanal": "@" + str(u.get("screen_name") or ""), "metin": re.sub(r"\s*https://t\.co/\S+\s*$", "", str(d.get("text") or "")), "tarih": str(d.get("created_at") or "")[:10], "platform": "X"}


def _og_gorseller(h, url, en_cok=EN_COK_GORSEL):
    import html as H
    out = []

    def ekle(u):
        u = urljoin(url, H.unescape(str(u)))
        if u.startswith("http") and not SUS_GORSEL.search(u) and u not in out:
            out.append(u)
    for m in re.finditer(r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)(?::src)?["\'][^>]+content=["\']([^"\']+)', h, re.I):
        ekle(m.group(1))
    for m in re.finditer(r'(?is)<img\b[^>]*>', h):
        t = m.group(0)
        ss = re.search(r'srcset=["\']([^"\']+)', t, re.I)
        if ss:
            aday = [x.strip().split() for x in ss.group(1).split(",") if x.strip()]
            aday = [(a[0], float(re.sub(r"\D", "", a[1]) or 0) if len(a) > 1 else 0) for a in aday if a]
            if aday:
                ekle(max(aday, key=lambda z: z[1])[0])
                continue
        s = re.search(r'\b(?:data-src|src)=["\']([^"\']+)', t, re.I)
        if s and not s.group(1).startswith("data:"):
            ekle(s.group(1))
    return out[:en_cok]


def gorsel_bul(link, cerez=""):
    """Bağlantıdaki görseller. Döner: {tur:'gorsel', baslik, kanal, metin, platform, tarih, ogeler:[{url,en,boy,video}], video_sayi} ya da None (görsel yok)."""
    y = urlparse(link).path.lower()
    h = (urlparse(link).hostname or "").lower()
    if y.endswith(RESIM_UZ):
        return {"tur": "gorsel", "baslik": Path(y).stem.replace("-", " ").replace("_", " ")[:80], "kanal": _site_adi(link), "metin": "", "platform": _site_adi(link), "tarih": "",
                "ogeler": [{"url": link, "en": 0, "boy": 0, "video": False}]}
    bilgi = None
    if h in ("x.com", "www.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"):
        try:
            bilgi = _x_gonderi(link)
        except Exception:  # noqa: BLE001
            bilgi = None
        if bilgi and not bilgi["ogeler"]:
            bilgi = {**bilgi, "yalniz_metin": True}
    if not bilgi:
        ig = h.endswith("instagram.com")
        og, ust = _gallery(link, oturum=ig or cerez == "chrome")     # Instagram giriş olmadan hız sınırına takılıyor: kişinin kendi oturumuyla, yalnız bu gönderi
        if not og and not ig and cerez != "chrome":
            og, ust = _gallery(link)
        if og:
            metin = ust.get("description") or ust.get("content") or ust.get("title") or ""
            bilgi = {"ogeler": og, "kanal": ("@" + str(ust["username"])) if ust.get("username") else str(ust.get("author") or ust.get("user") or ""), "metin": str(metin)[:4000],
                     "tarih": str(ust.get("post_date") or ust.get("date") or "")[:10], "platform": str(ust.get("category") or _site_adi(link)).capitalize()}
        elif ig or link_turu(link) == "gorsel":                      # son çare: sayfanın paylaşım görseli
            try:
                r = _kimlik(link)
                import html as H
                m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', r.text, re.I)
                t = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', r.text, re.I)
                if m:
                    bilgi = {"ogeler": [{"url": H.unescape(m.group(1)), "en": 0, "boy": 0, "video": False}], "kanal": "", "metin": H.unescape(t.group(1)) if t else "", "tarih": "",
                             "platform": _site_adi(link), "tek_kucuk": True}
            except Exception:  # noqa: BLE001
                pass
    if not bilgi:
        return None
    resim = [o for o in bilgi["ogeler"] if not o["video"]]
    if not resim and not bilgi.get("yalniz_metin"):
        return None                                                  # hepsi video: video yolu
    ad = _tek_satir(bilgi["metin"].split("\n")[0], 70) if bilgi["metin"] else ""
    return {"tur": "gorsel", "baslik": ad or bilgi["kanal"] or _site_adi(link), "kanal": bilgi["kanal"], "metin": bilgi["metin"], "platform": bilgi["platform"], "tarih": bilgi["tarih"],
            "ogeler": resim[:EN_COK_GORSEL], "video_sayi": len(bilgi["ogeler"]) - len(resim), "yalniz_metin": bool(bilgi.get("yalniz_metin")), "tek_kucuk": bool(bilgi.get("tek_kucuk"))}


def _resim_indir(url, hedef, referer="", en_az=0):
    """Görseli indirip jpg/png/gif olarak yazar. Döner: (yol, en, boy) ya da None."""
    from io import BytesIO
    from PIL import Image
    if not guvenli(url):
        return None
    try:
        from curl_cffi import requests as cr
        r = cr.get(url, impersonate="chrome", timeout=30, headers={"Referer": referer} if referer else None, allow_redirects=True)
        if r.status_code >= 400 or len(r.content) < 500 or len(r.content) > 60_000_000:
            return None
        ver = r.content
        im = Image.open(BytesIO(ver))
        en, boy = im.size
        if en < en_az or boy < en_az * 0.4:
            return None
        bicim = (im.format or "").upper()
        if bicim == "GIF" and getattr(im, "n_frames", 1) > 1:
            yol = Path(str(hedef) + ".gif")
            yol.write_bytes(ver)
        elif bicim == "PNG":
            yol = Path(str(hedef) + ".png")
            yol.write_bytes(ver)
        elif bicim == "JPEG":
            yol = Path(str(hedef) + ".jpg")
            yol.write_bytes(ver)
        else:                                                         # webp, avif...: her yerde açılsın diye jpg
            yol = Path(str(hedef) + ".jpg")
            im.convert("RGB").save(yol, "JPEG", quality=95)
        return yol, en, boy
    except Exception:  # noqa: BLE001
        return None


def _kucuk_yaz(kaynak, hedef, uzun=720):
    from PIL import Image
    im = Image.open(kaynak)
    im.seek(0)
    im = im.convert("RGB")
    im.thumbnail((uzun, uzun))
    im.save(hedef, "JPEG", quality=84)


def _ocr(yol):
    """Görseldeki yazı (macOS Vision)."""
    try:
        import goruntu
        kaynak = Path(yol)
        if kaynak.suffix == ".gif":
            return ""
        s = goruntu.yazi_oku(str(kaynak))
        metin = "\n".join(x for x in (str(y).strip() for y in (s or [])) if x)
        return metin if len(metin.split()) >= 4 and sum(c.isalpha() for c in metin) >= 15 else ""   # stadyum panosu, logo kırıntısı yazı sayılmaz
    except Exception:  # noqa: BLE001
        return ""


def _onb_temizle():
    try:
        for d in ONB.iterdir():
            if d.is_dir() and time.time() - d.stat().st_mtime > 2 * 86400:
                shutil.rmtree(d, ignore_errors=True)
    except OSError:
        pass


def on_hazirla(bilgi, link):
    """Önizleme: görseller önbelleğe iner, küçük kopya + yazı. bilgi'ye `id`, `dosyalar` ekler ve JSON'a yazar."""
    kod = _kisa(link)
    d = ONB / kod
    d.mkdir(parents=True, exist_ok=True)
    _onb_temizle()
    from concurrent.futures import ThreadPoolExecutor
    genel = not bilgi.get("ogeler") or all(not o["en"] for o in bilgi["ogeler"])

    def isle(a):
        i, o = a
        s = _resim_indir(o["url"], d / f"g{i}", referer=link, en_az=220 if genel and len(bilgi["ogeler"]) > 1 else 0)
        if not s:
            return None
        yol, en, boy = s
        try:
            _kucuk_yaz(yol, d / f"k{i}.jpg")
        except Exception:  # noqa: BLE001
            return None
        return {"i": i, "ad": yol.name, "kucuk": f"k{i}.jpg", "en": en, "boy": boy, "boyut": yol.stat().st_size, "ozet": hashlib.md5(yol.read_bytes()).hexdigest()}
    with ThreadPoolExecutor(6) as h:
        sonuc = [x for x in h.map(isle, enumerate(bilgi.get("ogeler") or [])) if x]
    tek, gor = [], set()
    for x in sonuc:
        if x["ozet"] not in gor:
            gor.add(x["ozet"])
            tek.append(x)
    for x in tek:                                                      # yazı tanıma sırayla (Vision iş parçacığı dostu değil, kare başına ~0,1 sn)
        x["yazi"] = _ocr(d / x["ad"])
    bilgi = {**bilgi, "id": kod, "link": link, "dosyalar": tek}
    (d / "bilgi.json").write_text(json.dumps(bilgi, ensure_ascii=False), encoding="utf-8")
    return bilgi


def on_bilgi(kod):
    if not re.fullmatch(r"[0-9a-f]{14}", str(kod or "")):
        return None
    try:
        return json.loads((ONB / kod / "bilgi.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


# ------------------------------------------------------------------------------------------------------- görsel kaydı
def _dizin():
    try:
        return json.loads(DIZIN.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _dizin_yaz(d):
    GORSELLER.mkdir(parents=True, exist_ok=True)
    t = DIZIN.with_suffix(".tmp")
    t.write_text(json.dumps(d, ensure_ascii=False, indent=0), encoding="utf-8")
    t.replace(DIZIN)


def mevcut_gorsel(link):
    for k, v in _dizin().items():
        if v.get("link") == link and all((GORSELLER / f["ad"]).exists() for f in v.get("dosyalar") or []):
            return {"id": k, "tarih": v.get("olusturma"), "sayi": len(v.get("dosyalar") or [])}
    return None


def gorsel_kaydet(kod, secim=None):
    """Önizlemedeki görselleri Görseller klasörüne alır. Döner: kayıt. Aynı gönderi yeniden istenirse aynı kayıt (yeni seçim eklenir)."""
    b = on_bilgi(kod)
    if not b:
        raise ValueError("Önizleme bulunamadı; linki yeniden yapıştırın.")
    secilen = [f for f in b["dosyalar"] if secim is None or f["i"] in secim]
    if not secilen:
        raise ValueError("Görsel seçilmedi.")
    GORSELLER.mkdir(parents=True, exist_ok=True)
    KUCUK.mkdir(parents=True, exist_ok=True)
    aciklama = re.sub(r"[#@]\S+", " ", b.get("metin", ""))
    aciklama = _tek_satir(re.sub(r"[^\w .,'’&()\-]+", " ", aciklama, flags=re.UNICODE), 44).rstrip("…").strip()
    taban = _ad_temizle(" - ".join(x for x in (b.get("kanal", "").lstrip("@"), aciklama) if x) or b.get("baslik") or kod)
    with _kilit:
        d = _dizin()
        k = d.get(kod) or {"id": kod, "baslik": b.get("baslik", ""), "kanal": b.get("kanal", ""), "link": b.get("link", ""), "platform": b.get("platform", ""), "metin": b.get("metin", ""),
                           "tarih": b.get("tarih", ""), "olusturma": time.time(), "dosyalar": []}
        var = {f["i"] for f in k["dosyalar"]}
        for sira, f in enumerate(secilen, 1):
            if f["i"] in var:
                continue
            kaynak = ONB / kod / f["ad"]
            ek = f" {f['i'] + 1}" if len(b["dosyalar"]) > 1 else ""
            hedef = GORSELLER / f"{taban}{ek}{kaynak.suffix}"
            n = 2
            while hedef.exists():
                hedef = GORSELLER / f"{taban}{ek}_{n}{kaynak.suffix}"
                n += 1
            shutil.copy2(kaynak, hedef)
            kk = KUCUK / f"{kod}_{f['i']}.jpg"
            shutil.copy2(ONB / kod / f["kucuk"], kk)
            k["dosyalar"].append({"i": f["i"], "ad": hedef.name, "kucuk": kk.name, "en": f["en"], "boy": f["boy"], "boyut": f["boyut"], "yazi": f.get("yazi", "")})
        k["dosyalar"].sort(key=lambda x: x["i"])
        d[kod] = k
        _dizin_yaz(d)
    return k


def gorsel_liste():
    d = _dizin()
    L = [v for v in d.values() if any((GORSELLER / f["ad"]).exists() for f in v.get("dosyalar") or [])]
    return sorted(L, key=lambda v: -float(v.get("olusturma") or 0))


def gorsel_kayit(kid):
    return _dizin().get(str(kid))


def gorsel_dosya(kid, n):
    k = gorsel_kayit(kid)
    for f in (k or {}).get("dosyalar") or []:
        if f["i"] == n:
            y = GORSELLER / f["ad"]
            return y if y.is_file() else None
    return None


def gorsel_sil(kid):
    with _kilit:
        d = _dizin()
        k = d.get(kid)
        if not k:
            return False
        hedef = COP / f"gorsel__{kid}"
        hedef.mkdir(parents=True, exist_ok=True)
        for f in k.get("dosyalar") or []:
            y = GORSELLER / f["ad"]
            if y.exists():
                shutil.move(str(y), str(hedef / f["ad"]))
        (hedef / "kayit.json").write_text(json.dumps(k, ensure_ascii=False), encoding="utf-8")
        del d[kid]
        _dizin_yaz(d)
    return True


def gorsel_geri(kid):
    hedef = COP / f"gorsel__{kid}"
    try:
        k = json.loads((hedef / "kayit.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return False
    with _kilit:
        d = _dizin()
        for f in k.get("dosyalar") or []:
            y = hedef / f["ad"]
            if y.exists():
                shutil.move(str(y), str(GORSELLER / f["ad"]))
        d[kid] = k
        _dizin_yaz(d)
    shutil.rmtree(hedef, ignore_errors=True)
    return True


def gorsel_betimle(kid):
    """Kaydedilen görsellere kısa betim + etiket (Claude). Görseller'de aramayı ve asistanı besler; olmazsa sessizce atlanır."""
    try:
        import claude_yaz
        if not claude_yaz.hazir():
            return
        k = gorsel_kayit(kid)
        if not k or k.get("betim"):
            return
        yollar = [str(GORSELLER / f["ad"]) for f in k["dosyalar"][:4] if not f["ad"].endswith(".gif")]
        if not yollar:
            return
        y = claude_yaz.sor_gorsel('Bu görselleri Türkçe betimle. Yalnız JSON: {"betim": "1-2 cümle, görünen somut şeyler", "etiketler": ["en çok 8 kısa etiket"]}\n'
                                  f"Bağlam (gönderi metni): {_tek_satir(k.get('metin', ''), 300)}", yollar, zaman_asimi=180)
        m = re.search(r"\{.*\}", y, re.S)
        j = json.loads(m.group(0)) if m else {}
        with _kilit:
            d = _dizin()
            if kid in d:
                d[kid]["betim"] = str(j.get("betim") or "")[:400]
                d[kid]["etiketler"] = [str(x)[:30] for x in (j.get("etiketler") or [])][:8]
                _dizin_yaz(d)
    except Exception:  # noqa: BLE001
        pass


# ------------------------------------------------------------------------------------------------------- yazı kaydı
OKUMA_HIZ = 3.6               # kelime/sn: "okuma konumu" hem özet bölümlerinin hem bağlantıların zamanı olur


def mevcut_yazi(link):
    try:
        import kitaplik_onbellek
        for s in kitaplik_onbellek.hepsi():
            v = s.get("veri") if isinstance(s, dict) and "veri" in s else s
            if isinstance(v, dict) and v.get("yazi") and v.get("link") == link:
                return {"temel": s.get("temel") or "", "baslik": v.get("baslik"), "tarih": v.get("olusturma")}
    except Exception:  # noqa: BLE001
        pass
    for js in KLASOR.glob("transkript_yazi_*.json"):
        try:
            v = json.loads(js.read_text(encoding="utf-8"))["veri"]
            if v.get("link") == link:
                return {"temel": js.stem, "baslik": v.get("baslik"), "tarih": v.get("olusturma")}
        except Exception:  # noqa: BLE001
            continue
    return None


def _ad_uret(baslik):
    taban = re.sub(r"[^\w]+", "_", _tek_satir(baslik, 46).rstrip("…"), flags=re.UNICODE).strip("_") or "yazi"
    ad = f"transkript_yazi_{taban}"
    n = 2
    while (KLASOR / f"{ad}.json").exists():
        ad = f"transkript_yazi_{taban}_{n}"
        n += 1
    return ad


def yazi_kaydet(s, gorseller=True):
    """Okunan yazıdan kayıt. Döner: temel."""
    temel = _ad_uret(s["baslik"])
    bl = s["bloklar"]
    segmentler, resimler, t, kare = [], [], 0.0, KLASOR / "kareler" / temel
    n_img = 0
    for b in bl:
        if b["tur"] == "img":
            if gorseller and n_img < 30 and not SUS_GORSEL.search(b.get("url", "")):
                kare.mkdir(parents=True, exist_ok=True)
                r = _resim_indir(urljoin(s["link"], b["url"]), kare / f"gecici_{n_img}", referer=s["link"], en_az=300)
                if r:
                    from PIL import Image
                    hedef = kare / f"k_{n_img}.jpg"
                    im = Image.open(r[0])
                    im.seek(0)
                    im = im.convert("RGB")
                    im.thumbnail((1400, 1400))
                    im.save(hedef, "JPEG", quality=88)
                    r[0].unlink(missing_ok=True)
                    resimler.append({"sonra": len(segmentler) - 1, "ad": hedef.name, "alt": b.get("metin", ""), "en": r[1], "boy": r[2]})
                    n_img += 1
            continue
        kel = len(b["metin"].split())
        sn = max(0.5, kel / OKUMA_HIZ)
        segmentler.append({"bas": round(t, 2), "bit": round(t + sn, 2), "k": "Y", "metin": b["metin"], "tur": b["tur"], "ayri": True})
        t += sn
    kapak = ""
    kaynak_kapak = s.get("kapak") or ""
    if kaynak_kapak:
        r = _resim_indir(kaynak_kapak, KLASOR / temel, referer=s["link"], en_az=200)
        if r:
            if r[0].suffix != ".jpg":
                from PIL import Image
                Image.open(r[0]).convert("RGB").save(KLASOR / f"{temel}.jpg", "JPEG", quality=88)
                r[0].unlink(missing_ok=True)
            kapak = f"{temel}.jpg"
    veri = {"baslik": s["baslik"], "link": s["link"], "video_id": "yazi_" + _kisa(s["link"]), "kanal": s.get("yazar") or s.get("site") or "", "platform": s.get("site") or "", "sure": round(t, 1),
            "dil": s.get("dil") or "tr", "etiket": {"Y": s.get("yazar") or s.get("site") or "Yazı"}, "kapak": kapak, "olusturma": time.time(), "kaynak": "Sayfadan alındı",
            "yazi": {"site": s.get("site") or "", "yazar": s.get("yazar") or "", "tarih": s.get("tarih") or "", "kelime": s["kelime"], "okuma_dk": max(1, round(s["kelime"] / 230)),
                     "gorseller": resimler, "turler": [g["tur"] for g in segmentler], "kisitli": bool(s.get("ucretli") and s["kelime"] < 500), "kopya_engeli": bool(s.get("kopya_engeli")), "yontem": s.get("yontem") or ""}}
    ciktilari_yaz(KLASOR / temel, veri, segmentler)
    return temel


def _ozet_metin(veri):
    o = veri.get("ozet") if isinstance(veri.get("ozet"), dict) else {}
    return str(o.get("ozet") or ""), [str(x) for x in (o.get("maddeler") or [])]


def _kunye_metin(veri):
    y = veri.get("yazi") or {}
    return " · ".join(x for x in (y.get("yazar"), y.get("site"), y.get("tarih"), f"{y.get('okuma_dk', 1)} dk okuma") if x)


def yaz_txt(yol, veri, segmentler):
    ozet, maddeler = _ozet_metin(veri)
    s = [veri.get("baslik", ""), _kunye_metin(veri), f"Kaynak: {veri.get('link', '')}", ""]
    if ozet:
        s += ["ÖZET", ozet, ""] + [f"- {m}" for m in maddeler] + ([""] if maddeler else [])
    for g in segmentler:
        t = g.get("tur")
        s.append(("\n" + g["metin"].upper() + "\n") if t in ("h1", "h2") else ("\n" + g["metin"] + "\n") if t == "h3" else f"- {g['metin']}" if t == "li" else f"“{g['metin']}”" if t == "alinti" else g["metin"] + ("" if t == "tablo" else "\n"))
    Path(yol).write_text("\n".join(s).rstrip() + "\n", encoding="utf-8")


def yaz_md(yol, veri, segmentler):
    ozet, maddeler = _ozet_metin(veri)
    s = [f"# {veri.get('baslik', '')}", "", _kunye_metin(veri), "", f"Kaynak: <{veri.get('link', '')}>", ""]
    if ozet:
        s += ["## Özet", "", ozet, ""] + [f"- {m}" for m in maddeler] + ([""] if maddeler else [])
    onek = {"h1": "## ", "h2": "## ", "h3": "### ", "li": "- ", "alinti": "> "}
    for g in segmentler:
        if g.get("tur") == "tablo":
            sat = g["metin"].split("\n")
            s += ["| " + sat[0] + " |", "|" + " --- |" * (sat[0].count("|") + 1)] + ["| " + x + " |" for x in sat[1:]] + [""]
        else:
            s += [onek.get(g.get("tur"), "") + g["metin"], ""]
    Path(yol).write_text("\n".join(s).rstrip() + "\n", encoding="utf-8")


def yaz_docx(yol, temel, veri, segmentler):
    from docx import Document
    from docx.shared import Cm, Pt
    d = Document()
    for b in d.sections:
        b.page_width, b.page_height, b.left_margin, b.right_margin = Cm(21), Cm(29.7), Cm(2.5), Cm(2.5)
    d.styles["Normal"].font.name = "Calibri"
    d.styles["Normal"].font.size = Pt(11.5)
    d.add_heading(veri.get("baslik", ""), 0)
    p = d.add_paragraph(_kunye_metin(veri))
    p.runs[0].font.size = Pt(10)
    p = d.add_paragraph(f"Kaynak: {veri.get('link', '')}")
    p.runs[0].font.size = Pt(9)
    ozet, maddeler = _ozet_metin(veri)
    if ozet:
        d.add_heading("Özet", 2)
        d.add_paragraph(ozet)
        for m in maddeler:
            d.add_paragraph(m, style="List Bullet")
        d.add_heading("Yazı", 2)
    kare = KLASOR / "kareler" / temel
    res = {}
    for g in (veri.get("yazi") or {}).get("gorseller") or []:
        res.setdefault(g["sonra"], []).append(g)

    def resim(i):
        for g in res.get(i, []):
            try:
                d.add_picture(str(kare / g["ad"]), width=Cm(16))
                if g.get("alt"):
                    a = d.add_paragraph(g["alt"])
                    a.runs[0].font.size = Pt(9)
            except Exception:  # noqa: BLE001
                pass
    resim(-1)
    for i, s in enumerate(segmentler):
        t = s.get("tur")
        if t in ("h1", "h2"):
            d.add_heading(s["metin"], 2)
        elif t == "h3":
            d.add_heading(s["metin"], 3)
        elif t == "li":
            d.add_paragraph(s["metin"], style="List Bullet")
        elif t == "alinti":
            d.add_paragraph(s["metin"], style="Intense Quote")
        elif t == "tablo":
            sat = [x.split(" | ") for x in s["metin"].split("\n")]
            sut = max(len(x) for x in sat)
            tb = d.add_table(rows=len(sat), cols=sut)
            tb.style = "Table Grid"
            for r, x in enumerate(sat):
                for c, h in enumerate(x):
                    tb.cell(r, c).text = h
        else:
            d.add_paragraph(s["metin"])
        resim(i)
    d.save(str(yol))


def _kacis(s):
    import html
    return html.escape(str(s or ""))


def html_yaz(temel, veri, segmentler):
    """Tek dosyalık okuma sayfası (PDF bunun çıktısı)."""
    import base64
    ozet, maddeler = _ozet_metin(veri)
    kare = KLASOR / "kareler" / temel
    res = {}
    for g in (veri.get("yazi") or {}).get("gorseller") or []:
        res.setdefault(g["sonra"], []).append(g)

    def resim(i):
        o = ""
        for g in res.get(i, []):
            try:
                b = base64.b64encode((kare / g["ad"]).read_bytes()).decode()
                o += f'<figure><img src="data:image/jpeg;base64,{b}" alt="">' + (f"<figcaption>{_kacis(g.get('alt'))}</figcaption>" if g.get("alt") else "") + "</figure>"
            except OSError:
                pass
        return o
    g = [resim(-1)]
    liste = False
    for i, s in enumerate(segmentler):
        t = s.get("tur")
        if t == "li" and not liste:
            g.append("<ul>")
            liste = True
        if t != "li" and liste:
            g.append("</ul>")
            liste = False
        if t in ("h1", "h2"):
            g.append(f"<h2>{_kacis(s['metin'])}</h2>")
        elif t == "h3":
            g.append(f"<h3>{_kacis(s['metin'])}</h3>")
        elif t == "li":
            g.append(f"<li>{_kacis(s['metin'])}</li>")
        elif t == "alinti":
            g.append(f"<blockquote>{_kacis(s['metin'])}</blockquote>")
        elif t == "tablo":
            g.append("<table>" + "".join("<tr>" + "".join(f"<td>{_kacis(h)}</td>" for h in x.split(" | ")) + "</tr>" for x in s["metin"].split("\n")) + "</table>")
        else:
            g.append(f"<p>{_kacis(s['metin'])}</p>")
        g.append(resim(i))
    if liste:
        g.append("</ul>")
    oz = (f"<section class='oz'><h2>Özet</h2><p>{_kacis(ozet)}</p>" + ("<ul>" + "".join(f"<li>{_kacis(m)}</li>" for m in maddeler) + "</ul>" if maddeler else "") + "</section>") if ozet else ""
    return f"""<!doctype html><html lang="{_kacis(veri.get('dil') or 'tr')}"><head><meta charset="utf-8"><title>{_kacis(veri.get('baslik'))}</title><style>
body{{font:17px/1.6 Georgia,'Times New Roman',serif;color:#1c1c1e;max-width:680px;margin:40px auto;padding:0 20px}}h1{{font:700 34px/1.2 -apple-system,Helvetica,sans-serif;margin:0 0 12px}}
h2,h3{{font-family:-apple-system,Helvetica,sans-serif;line-height:1.3;margin:1.6em 0 .5em}}.k{{font:14px -apple-system,Helvetica,sans-serif;color:#6e6e73}}.k a{{color:inherit}}img{{max-width:100%;height:auto;border-radius:6px}}
figure{{margin:1.4em 0}}figcaption{{font:13px -apple-system,Helvetica,sans-serif;color:#6e6e73;margin-top:6px}}blockquote{{border-left:3px solid #d1d1d6;margin:1.2em 0;padding-left:16px;color:#3a3a3c}}
table{{border-collapse:collapse;font:14px -apple-system,Helvetica,sans-serif;width:100%}}td{{border:1px solid #d1d1d6;padding:6px 8px}}.oz{{background:#f5f5f3;padding:4px 18px 10px;border-radius:10px;margin:1.4em 0}}
</style></head><body><h1>{_kacis(veri.get('baslik'))}</h1><div class="k">{_kacis(_kunye_metin(veri))}<br><a href="{_kacis(veri.get('link'))}">{_kacis(veri.get('link'))}</a></div>{oz}{''.join(g)}</body></html>"""


def pdf_yaz(temel):
    """Okuma sayfasından PDF (görünmez Chrome). Döner: yol."""
    js = KLASOR / f"{temel}.json"
    hedef = KLASOR / f"{temel}.pdf"
    if hedef.exists() and hedef.stat().st_mtime >= js.stat().st_mtime:
        return hedef
    d = json.loads(js.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as t:
        sayfa = Path(t) / "sayfa.html"
        sayfa.write_text(html_yaz(temel, d["veri"], d["segmentler"]), encoding="utf-8")
        subprocess.run([CHROME, "--headless=new", f"--user-data-dir={t}/p", "--disable-gpu", "--no-first-run", "--no-pdf-header-footer", f"--print-to-pdf={hedef}", sayfa.as_uri()],
                       capture_output=True, timeout=90)
    if not hedef.exists():
        raise RuntimeError("PDF üretilemedi.")
    return hedef


def ciktilari_yaz(temel_yol, veri, segmentler):
    """transkript.ciktilari_yaz'ın yazı karşılığı: özet ya da ad değişince de buradan geçer."""
    import kayit_json
    temel = Path(temel_yol).name
    yaz_txt(str(temel_yol) + ".txt", veri, segmentler)
    with kayit_json.kilit(str(temel_yol) + ".json"):
        kayit_json.yaz(str(temel_yol) + ".json", {"veri": veri, "segmentler": segmentler})
    yaz_md(str(temel_yol) + ".md", veri, segmentler)
    try:
        yaz_docx(str(temel_yol) + ".docx", temel, veri, segmentler)
    except Exception as e:  # noqa: BLE001
        print("yazı Word'e yazılamadı:", str(e)[:200], flush=True)
    return []


# ------------------------------------------------------------------------------------------------------- önizleme
def incele(link, cerez=""):
    """Video dışı içerik önizlemesi: {tur: gorsel|yazi, ...} ya da {tur: None, hata}. Görselde dosyalar önbelleğe iner."""
    t = link_turu(link)
    if t == "gorsel":
        g = gorsel_bul(link, cerez)
        if not g:
            return {"tur": None}
        if g.get("yalniz_metin"):                                       # görselsiz X gönderisi: kısa yazı
            return {"tur": "gorsel", **on_hazirla(g, link)}
        g = on_hazirla(g, link)
        return g if g["dosyalar"] else {"tur": None, "hata": "Görsel indirilemedi."}
    s = yazi_al(link, cerez)
    if s.get("hata"):
        g = gorsel_sayfa(link) if s.get("hata") != "giris" else None
        return g or {"tur": None, "hata": s["hata"]}
    if not s.get("makale") and urlparse(link).path.strip("/") == "":                # site ana sayfası: manşet yığını, yazı değil
        g = gorsel_sayfa(link)
        return g or {"tur": None, "hata": "Bu bir ana sayfa; okumak istediğiniz yazının linkini yapıştırın."}
    if s["kelime"] < EN_AZ_YAZI and not (s["kelime"] >= 15 and s.get("makale")):   # makale ama açık kısmı kısa: yazı olarak kalır, kısıtlı olduğu söylenir
        g = gorsel_sayfa(link)
        if g:
            return g
        return {"tur": None, "hata": "Bu sayfada okunacak bir yazı ya da görsel bulamadım."}
    if s["kelime"] < EN_AZ_YAZI:
        s["ucretli"] = True
    return {"tur": "yazi", **s}


def gorsel_sayfa(link):
    """Yazısı az, görseli çok sayfa (portfolyo, galeri)."""
    try:
        r = _kimlik(link)
        if r.status_code >= 400:
            return None
        L = _og_gorseller(r.text, link, 30)
    except Exception:  # noqa: BLE001
        return None
    if not L:
        return None
    import html as H
    t = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', r.text, re.I) or re.search(r"(?is)<title[^>]*>(.*?)</title>", r.text)
    g = on_hazirla({"tur": "gorsel", "baslik": _tek_satir(H.unescape(t.group(1)), 80) if t else _site_adi(link), "kanal": _site_adi(link), "metin": "", "platform": _site_adi(link), "tarih": "",
                    "ogeler": [{"url": u, "en": 0, "boy": 0, "video": False} for u in L]}, link)
    return g if g["dosyalar"] else None


if __name__ == "__main__":
    s = incele(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "")
    print(json.dumps({k: (v if k != "bloklar" else f"{len(v)} blok") for k, v in s.items()}, ensure_ascii=False, indent=1)[:2500])
