"""kesif.py - Ghost'un günlük keşfi (2026-10-21; kullanıcı: "çok AI odaklı oldu; creative biriyim, futbol, toplum, popüler kültür, futbol+teknoloji,
güzel hikâyeler; Instagram story ve LinkedIn de; günde çok daha fazla paylaşım").

Akış: alan alan haber akışları (RSS; Google News arama akışları dahil, anahtar gerekmez) → son 36 saatin maddeleri → Claude (sonnet) kişinin
HEDEF profiline göre dengeli ~16 öneri seçer: her birine alan, platform (x | story | linkedin), neden ilginç, kişinin açısı (alanlar arası bağlam),
story için tek satır üstü yazı → `kayitlar/kesif/<tarih>.json`. Ardından X ve LinkedIn önerileri için taslak kendiliğinden yazılır (ghost kaydı,
kaynak_tur 'kesif'); story önerileri görsel + üstü yazıyla hazır durur. Kullanıcı "kendi yorumum" yazarsa taslak o yorumla yeniden kurulur.
"""
import email.utils
import html
import json
import re
import requests
import time
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
KESIF = KLASOR / "kayitlar" / "kesif"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15"}


def _gn(q, dil="tr", sure="2d"):
    bolge = {"tr": "TR", "de": "DE"}.get(dil, "US")
    return f"https://news.google.com/rss/search?q={urllib.parse.quote(q + ' when:' + sure)}&hl={dil}&gl={bolge}&ceid={bolge}:{dil}"


ALMANCA = {"11Freunde", "kicker", "Horizont", "W&V", "Spiegel Netzwelt", "heise", "Mit Vergnügen"}   # 24 Ekim: Türk okurun okumadığı kaynaklar; Almanya bakışı, yapısal yenilik

try:
    _TAKIM = __import__("ortak").kimlik()["takim"]         # tuttuğu takım (profil/x.json); boşsa takım kaynakları yok
except Exception:  # noqa: BLE001
    _TAKIM = ""

# 26 Ekim (kullanıcı: "boş beleş spor news sitelerinden haberler getiriyorsun; yeterince derinlikli değil, günlük talk. Sadece spor değil, genelde de
# böyle bak"): günlük haber akışları (NTV Spor, BBC Sport, kicker anlık, genel Google Haberler aramaları, Webrazzi, Good News Network) çıkarıldı;
# derin yayınlar eklendi. DERIN: uzun okuma, analiz, yapı/karar/iş modeli anlatan yayınlar; karışımın ham başlık malzemesi yalnız bunlardan ve
# kürasyondan (bülten, Kantan, dinlediği yayınlar, izlediği hesaplar) gelir.
KAYNAKLAR = {
    "futbol": [("11Freunde", "https://11freunde.de/feed"), ("The Blizzard", "https://www.theblizzard.co.uk/feed/"),
               ("Spielverlagerung", "https://spielverlagerung.com/feed/"), ("Josimar", "https://josimarfootball.com/feed/"),
               ("Swiss Ramble", "https://swissramble.substack.com/feed"),   # The Athletic çıkarıldı: akışı NFL, F1, canlı maç güncellemesi (günlük)
               ("Footy Headlines", "https://www.footyheadlines.com/feeds/posts/default")],
    "futbol_teknoloji": [("SportsPro", "https://www.sportspromedia.com/feed/"),
                         ("Opta Analyst", "https://theanalyst.com/feed"), ("Off The Pitch", "https://offthepitch.com/rss.xml"),
                         ("Training Ground Guru", "https://trainingground.guru/feed/"), ("FM Scout", "https://www.fmscout.com/rss.php")],
    "kreatif": [("Bigumigu", "https://bigumigu.com/feed/"), ("Muse by Clios", "https://musebycl.io/rss.xml"), ("Creative Boom", "https://www.creativeboom.com/feed/"),
                ("Design Week", "https://www.designweek.co.uk/feed/"), ("LBB", _gn("site:lbbonline.com", "en")), ("It's Nice That", "https://www.itsnicethat.com/articles.rss"), ("Creative Review", "https://www.creativereview.co.uk/feed/"), ("Dezeen", "https://www.dezeen.com/feed/")],
    # 26 Ekim (kullanıcı: "konulara reklamcılık da katalım; Adweek üyeliğim var, başka bir sürü kaynak var"): sektörün kendisi (ajanslar, holdingler,
    # medya, pazarlama stratejisi); Adweek'in sektör bölümleri `adweek()` ile buraya, yaratıcılık bölümü kreatife.
    "reklamcilik": [("Ad Age", _gn("site:adage.com", "en")), ("Digiday", "https://digiday.com/feed/"), ("Marketing Week", "https://www.marketingweek.com/feed/"),
                    ("AdExchanger", "https://www.adexchanger.com/feed/"), ("The Drum", _gn("site:thedrum.com", "en")), ("Horizont", "https://www.horizont.net/news/feed/"),
                    ("W&V", _gn("site:wuv.de", "de")), ("MediaCat", "https://mediacat.com/feed/"), ("Marketing Türkiye", "https://www.marketingturkiye.com.tr/feed/"),
                    ("Campaign Türkiye", "https://www.campaigntr.com/feed/")],
    # 26 Ekim (kullanıcı: "gusto sahibi olduğumu gösteren içerikler; yemek, niş konular, içecek, başka her şey"): bilen birinin seçtiği şeyler
    "gusto": [("Punch", "https://punchdrink.com/feed/"), ("Eater", "https://www.eater.com/rss/index.xml"), ("Bon Appétit", "https://www.bonappetit.com/feed/rss"),
              ("The Guardian Food", "https://www.theguardian.com/food/rss"), ("Decanter", "https://www.decanter.com/feed/"), ("Jancis Robinson", "https://www.jancisrobinson.com/rss"),
              ("Sprudge", "https://sprudge.com/feed"), ("Monocle", "https://monocle.com/feed/"), ("Wallpaper*", "https://www.wallpaper.com/feeds/all"),
              ("Hodinkee", "https://www.hodinkee.com/articles.rss"), ("Highsnobiety", "https://www.highsnobiety.com/feed/"), ("Mit Vergnügen", "https://mitvergnuegen.com/feed/"),
              # 27 Ekim (kullanıcı: "birçok çeşitli alandan gusto"): yemek-içecek dışı zevk alanları
              ("Dezeen Design", "https://www.dezeen.com/design/feed/"), ("Core77", _gn("site:core77.com", "en")),
              ("Fragrantica", _gn("site:fragrantica.com", "en")), ("Analog Planet", "https://www.analogplanet.com/rss.xml"),
              ("Typewolf", "https://www.typewolf.com/feed"), ("Craft Council", _gn("craftsmanship OR artisan OR zanaat", "en")), ("Condé Nast Traveller", "https://www.cntraveller.com/feed/rss"),
              ("Gastronomi (TR)", _gn("gastronomi OR şarap OR kahve kültürü", "tr"))],
    "toplum": [("Aeon", "https://aeon.co/feed.rss"), ("Evrim Ağacı", "https://evrimagaci.org/rss.xml"), ("Daktilo 1984", "https://www.daktilo1984.com/feed/"),
               ("Manifold", "https://www.manifold.press/rss"), ("The Guardian Long Read", "https://www.theguardian.com/news/series/the-long-read/rss"),
               ("The New Yorker", "https://www.newyorker.com/feed/everything"), ("The Atlantic", "https://www.theatlantic.com/feed/all/")],
    "populer_kultur": [("Kayıp Rıhtım", "https://www.kayiprihtim.com/feed/"), ("Stereogum", "https://www.stereogum.com/feed/"),
                       ("Know Your Meme", "https://knowyourmeme.com/newsfeed.rss"), ("The Guardian Culture", "https://www.theguardian.com/culture/rss"), ("Open Culture", "https://www.openculture.com/feed"),
                       ("Bant Mag", "https://bantmag.com/feed")],
    "hikaye": [("Longreads", "https://longreads.com/feed/"), ("Reasons to be Cheerful", "https://reasonstobecheerful.world/feed/"),
               ("Public Domain Review", "https://publicdomainreview.org/rss.xml"), ("Atlas Obscura", "https://www.atlasobscura.com/feeds/latest"), ("kottke.org", "https://feeds.kottke.org/main"),
               ("The Guardian Long Read", "https://www.theguardian.com/news/series/the-long-read/rss")],
    "teknoloji_ai": [("Stratechery", "https://stratechery.com/feed/"), ("Benedict Evans", "https://www.ben-evans.com/benedictevans?format=rss"),
                     ("Import AI", "https://jack-clark.net/feed/"), ("Platformer", "https://www.platformer.news/rss/"), ("One Useful Thing", "https://www.oneusefulthing.org/feed"),
                     ("WIRED Backchannel", "https://www.wired.com/feed/category/backchannel/latest/rss"), ("Simon Willison", "https://simonwillison.net/atom/everything/"),
                     ("Hackaday", "https://hackaday.com/blog/feed/"), ("Spiegel Netzwelt", "https://www.spiegel.de/netzwelt/index.rss"), ("heise", "https://www.heise.de/rss/heise-atom.xml"),
                     ("The Verge", "https://www.theverge.com/rss/index.xml")],
}
# Derin yayınlar (analiz, uzun okuma); ötekiler günlük haber akışı (Verge, heise, Spiegel, Guardian Culture, ticaret basını): keşifte kalır ama karışıma
# ham başlık olarak girmez, ancak açı elemesinde metni okunup somut bir ayrıntı bulunursa haber olur.
DERIN = {"11Freunde", "The Blizzard", "Spielverlagerung", "Josimar", "Swiss Ramble", "Opta Analyst", "Off The Pitch", "Training Ground Guru",
         "Adweek", "Muse by Clios", "It's Nice That", "Creative Review", "Dezeen", "LBB", "Design Week",
         "Aeon", "Manifold", "The Guardian Long Read", "The New Yorker", "The Atlantic", "Open Culture", "Longreads", "Public Domain Review", "Atlas Obscura",
         "kottke.org", "Ad Age", "Digiday", "Marketing Week", "Punch", "Eater", "Jancis Robinson", "Sprudge", "Monocle", "Hodinkee", "Wallpaper*", "Stratechery", "Benedict Evans", "Import AI", "Platformer", "One Useful Thing", "WIRED Backchannel", "Simon Willison", "Kantan.News"}


KAYNAK_DOSYA = KLASOR / "profil" / "kaynaklar.json"
DERIN_EK = set()


def kaynak_listesi():
    """Keşfin okuduğu kaynaklar (2026-10-29, Ghost herkese açılırken): profil/kaynaklar.json varsa o (kurulumda kullanıcının konularına göre
    yazılır, Profil → Kaynaklar'dan düzenlenir), yoksa yerleşik KAYNAKLAR. Dosya: {"alanlar": {alan kodu: [{"ad", "url" | "sorgu", "dil", "derin"}]},
    "trend": ["US", ...]}. 'sorgu' = Google Haberler araması (anahtar gerekmez). Döner: ({alan: [(ad, url)]}, derin adlar, trend bölgeleri)."""
    try:
        d = json.loads(KAYNAK_DOSYA.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return KAYNAKLAR, set(), ["TR", "DE"]
    out, derin = {}, set()
    for alan, L in (d.get("alanlar") or {}).items():
        for k in L if isinstance(L, list) else []:
            if not isinstance(k, dict) or not k.get("ad") or k.get("kapali"):
                continue
            url = str(k.get("url") or "").strip() or (_gn(str(k["sorgu"]), str(k.get("dil") or "en")) if k.get("sorgu") else "")
            if url.startswith("http"):
                out.setdefault(alan, []).append((str(k["ad"]), url))
                if k.get("derin"):
                    derin.add(str(k["ad"]))
    trend = [str(x).upper() for x in d.get("trend") or [] if str(x).strip()][:3]
    return out, derin, trend


def derin_mi(m):
    """Madde derin bir yayından ya da kişinin kendi kürasyonundan mı (bülten, Kantan, dinlediği yayın, izlediği hesap, arşiv)?"""
    return bool(m.get("kaynak") in DERIN or m.get("kaynak") in DERIN_EK or m.get("kesif_bulten") or m.get("kesif_kantan") or m.get("kesif_yayin") or m.get("x_hesap")
                or m.get("arsiv") or m.get("kesif_abonelik"))


MEDIA = "{http://search.yahoo.com/mrss/}"
ATOM = "{http://www.w3.org/2005/Atom}"


def _metin(t):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(t or "")))).strip()


def _tarih(t):
    try:
        return email.utils.parsedate_to_datetime(t).timestamp()
    except Exception:  # noqa: BLE001
        try:
            from datetime import datetime
            return datetime.fromisoformat(str(t).replace("Z", "+00:00")).timestamp()
        except Exception:  # noqa: BLE001
            return 0


SAGLIK = {}


def _akis(alan, kaynak, url, saat=36, baslangic=None):
    import requests
    try:
        r = requests.get(url, headers=UA, timeout=20)
        icerik = r.content.lstrip()                      # bazı akışlar XML bildiriminden önce boşluk gönderiyor (The Blizzard)
        try:
            kok = ET.fromstring(icerik)
        except ET.ParseError:                            # HTML varlıkları (&nbsp; gibi) XML'de tanımsız (Design Week)
            metin = icerik.decode(r.encoding or "utf-8", "replace")
            metin = re.sub(r"&([a-zA-Z]+);", lambda m: m.group(0) if m.group(1) in ("amp", "lt", "gt", "quot", "apos") else html.unescape(m.group(0)).replace("&", "&amp;"), metin)
            kok = ET.fromstring(metin.encode("utf-8"))
    except Exception as e:  # noqa: BLE001
        SAGLIK[url] = {"kaynak": kaynak, "alan": alan, "ok": False, "hata": str(e)[:120], "zaman": time.time()}
        return []
    sinir = baslangic or (time.time() - saat * 3600)
    out = []
    ogeler = kok.findall(".//item") or kok.findall(f".//{ATOM}entry")
    SAGLIK[url] = {"kaynak": kaynak, "alan": alan, "ok": bool(ogeler), "adet": len(ogeler), "hata": "" if ogeler else "akış boş", "zaman": time.time()}
    for it in ogeler[:40]:
        g = lambda ad: (it.findtext(ad) or it.findtext(ATOM + ad) or "")   # noqa: E731
        link = g("link") or ((it.find(ATOM + "link") is not None and it.find(ATOM + "link").get("href")) or "")
        z = _tarih(g("pubDate") or g("updated") or g("published"))
        if not z or z < sinir:        # 22 Ekim: tarihsiz madde de alınmaz (eski haber "yeni" sanılıyordu)
            continue
        resim = ""
        for m in it.findall(MEDIA + "content") + it.findall(MEDIA + "thumbnail"):
            if m.get("url") and (not resim or int(m.get("width") or 0) >= 400):
                resim = m.get("url")
        enc = it.find("enclosure")
        if not resim and enc is not None and "image" in (enc.get("type") or ""):
            resim = enc.get("url") or ""
        baslik = _metin(g("title"))
        kay = kaynak
        if "news.google.com" in url:          # Google News: başlık "X - Yayıncı"
            m = re.match(r"^(.*)\s+-\s+([^-]+)$", baslik)
            if m:
                baslik, kay = m.group(1).strip(), m.group(2).strip()
        if baslik and link:
            out.append({"alan": alan, "kaynak": kay, "baslik": baslik[:220], "ozet": _metin(g("description") or g("summary"))[:500], "link": link.strip(),
                        "resim": resim, "zaman": z or time.time()})
    return out


TRENDLER = []


def google_trendler(geo="TR"):
    """Google Trends 'şu an yükselenler' (yeni adres; eski daily RSS 404). Döner: [{terim, trafik}]."""
    import requests
    try:
        kok = ET.fromstring(requests.get(f"https://trends.google.com/trending/rss?geo={geo}", headers=UA, timeout=15).content)
        ns = "{https://trends.google.com/trending/rss}"
        return [{"terim": (it.findtext("title") or "").strip(), "trafik": (it.findtext(ns + "approx_traffic") or "").strip()} for it in kok.findall(".//item")][:25]
    except Exception:  # noqa: BLE001
        return []


ADWEEK_BOLUM = ("creativity", "brand-marketing", "agencies", "commerce", "social-marketing", "programmatic")   # TV reytingleri (tvnewser) ve 'ticker' yok


def adweek(saat=36, baslangic=None):
    """Adweek (kişinin ücretli üyeliği; tam metin abonelik.py ile okunur). RSS akışı çoğunlukla TV reytingleri (TVNewser) verdiği için yazı listesi
    sitenin kendi WordPress ucundan alınır ve yalnız yaratıcılık, marka, ajans, ticaret ve sosyal bölümleri tutulur (26 Ekim)."""
    import requests
    sinir = baslangic or (time.time() - saat * 3600)
    try:
        r = requests.get("https://www.adweek.com/wp-json/wp/v2/posts?per_page=60&_fields=link,title,date_gmt,excerpt", headers=UA, timeout=25)
        L = r.json() if r.status_code == 200 else []
    except Exception:  # noqa: BLE001
        L = []
    out = []
    for x in L if isinstance(L, list) else []:
        link = str(x.get("link") or "")
        bolum = link.split("adweek.com/")[-1].split("/")[0]
        if bolum not in ADWEEK_BOLUM:
            continue
        try:
            z = time.mktime(time.strptime(str(x.get("date_gmt"))[:19], "%Y-%m-%dT%H:%M:%S")) - time.timezone
        except ValueError:
            continue
        if z < sinir:
            continue
        out.append({"alan": "kreatif" if bolum == "creativity" else "reklamcilik", "kaynak": "Adweek", "baslik": _metin((x.get("title") or {}).get("rendered")), "ozet": _metin((x.get("excerpt") or {}).get("rendered"))[:400],
                    "link": link, "zaman": z, "resim": "", "kesif_abonelik": "Adweek"})
    SAGLIK["adweek:wp-json"] = {"kaynak": "Adweek", "alan": "reklamcilik", "ok": bool(out), "adet": len(out), "hata": "" if out else "yazı yok", "zaman": time.time()}
    return out


def topla(saat=36, baslangic=None):
    global TRENDLER, DERIN_EK
    kaynaklar, DERIN_EK, bolgeler = kaynak_listesi()
    isler = [(a, k, u) for a, L in kaynaklar.items() for k, u in L]
    with ThreadPoolExecutor(8) as h:
        sonuc = list(h.map(lambda x: _akis(*x, saat=saat, baslangic=baslangic), isler))
    try:                                                     # Adweek yalnız üyelik listesindeyse (ayarlar.json `abonelikler`)
        import abonelik
        if any("adweek.com" in a for a in abonelik.alanlar()):
            sonuc.append(adweek(saat=saat, baslangic=baslangic))
    except Exception:  # noqa: BLE001
        pass
    TRENDLER = [t for b in bolgeler for t in google_trendler(b)]
    try:
        KESIF.mkdir(parents=True, exist_ok=True)
        (KESIF / "saglik.json").write_text(json.dumps({"zaman": time.time(), "kaynaklar": SAGLIK, "trendler": TRENDLER}, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    gorulen, out = set(), []
    for L in sonuc:
        for x in L:
            anahtar = re.sub(r"\W+", "", x["baslik"].lower())[:60]
            if anahtar in gorulen:
                continue
            gorulen.add(anahtar); out.append(x)
    return out


def _konusulurluk(maddeler):
    """Aynı konuyu kaç AYRI kaynağın yazdığı (başlık kökü örtüşmesi ≥3): 'konuşuluyor mu?' sinyali. Maddelere 'kaynak_sayisi' ekler."""
    import paylasim
    kok = [paylasim._kokler(m["baslik"] + " " + m.get("ozet", "")[:120]) for m in maddeler]
    onceki = []                                          # önceki günlerin önerileri (kök kümeleri), yeniden yeniye
    for f in sorted(KESIF.glob("20*.json"))[-6:][::-1]:
        if f.stem == date.today().isoformat():
            continue
        try:
            onceki.append([paylasim._kokler(o["baslik"] + " " + o.get("ozet", "")[:120]) for o in json.loads(f.read_text(encoding="utf-8")).get("oneriler") or []])
        except Exception:  # noqa: BLE001
            break
    for i, m in enumerate(maddeler):
        kaynaklar, benzer = {m["kaynak"]}, []
        for j, n in enumerate(maddeler):
            if i != j and len(kok[i] & kok[j]) >= 3:
                if n["kaynak"] not in kaynaklar:
                    kaynaklar.add(n["kaynak"])
                benzer.append(f"{n['kaynak']}: {n['baslik']}")
        m["kaynak_sayisi"] = len(kaynaklar); m["benzer"] = benzer[:8]
        m["hikaye_gun"] = _hikaye_gunu(kok[i], onceki)
        bt = m["baslik"].lower()
        m["trend"] = next((t["terim"] for t in TRENDLER if len(t["terim"]) >= 4 and t["terim"].lower() in bt), "")
    return maddeler


def _hikaye_gunu(kokler, onceki):
    """Bu hikâye kaç gündür önerilerde var (önceki günlerde ≥3 kök örtüşmesi, ardışık): 'yeni' mi 'süren hikâye' mi."""
    n = 1
    for gun in onceki:
        if any(len(kokler & k) >= 3 for k in gun):
            n += 1
        else:
            break
    return n


def _onceki_basliklar(gun=4):
    out = set()
    for f in sorted(KESIF.glob("20*.json"))[-gun:]:
        try:
            out |= {o.get("baslik") for o in json.loads(f.read_text(encoding="utf-8")).get("oneriler") or []}
        except Exception:  # noqa: BLE001
            pass
    return out


def sec(maddeler, log=print, geri_bildirim=""):
    """Claude: hedef profile göre dengeli öneriler (platform, açı, story yazısı)."""
    import paylasim
    pr = paylasim.profil()
    hedef = pr.get("hedef") or {}
    onceki = _onceki_basliklar()
    red = [r for r in pr.get("kesif_red") or [] if isinstance(r, dict)][-12:]
    adaylar = [m for m in _konusulurluk(maddeler) if m["baslik"] not in onceki]
    say = {}
    for m in adaylar:
        say[m["alan"]] = say.get(m["alan"], 0) + 1
    adaylar = sorted(adaylar, key=lambda m: (0 if m.get("kesif_yayin") or m.get("kesif_bulten") or m.get("x_hesap") or m.get("kesif_kantan") else (1 if derin_mi(m) else 2),
                                             -m["zaman"]))   # kişinin kendi kürasyonu önce, sonra derin yayınlar, en son günlük haber akışları
    secilen, sinir = [], {}
    for m in adaylar:                        # alan başına en çok 22 aday (istem boyu)
        if sinir.get(m["alan"], 0) < 22:
            secilen.append(m); sinir[m["alan"]] = sinir.get(m["alan"], 0) + 1
    satir = "\n".join(f"[{i}] ({m['alan']} · {m['kaynak']}{' · derin yayın' if m.get('kaynak') in DERIN else ''}{' · görselli' if m['resim'] else ''}{' · ' + str(m.get('kaynak_sayisi')) + ' kaynak yazıyor' if m.get('kaynak_sayisi', 1) > 1 else ''}{' · Google’da yükseliyor' if m.get('trend') else ''}{' · dinlediği yayında konuşuldu' if m.get('kesif_yayin') else ''}{' · üye olduğu bültende geçti' if m.get('kesif_bulten') else ''}{' · Kantan.News seçkisinde (' + m['kesif_kantan'] + '; kişinin beğendiği küratör)' if m.get('kesif_kantan') else ''}{' · Almanca kaynak (Türk okur bilmiyor; Berlin bakışı)' if m.get('kaynak') in ALMANCA else ''}{' · bugün geçmişte: ' + str(m['arsiv'].get('yil')) if m.get('arsiv') else ''}{' · izlediği hesap @' + m['x_hesap'] + ' paylaştı (alıntılanabilir)' if m.get('x_hesap') else ''}) "
                      f"{m['baslik']} — {m['ozet'][:220]}" for i, m in enumerate(secilen))
    alanlar = "\n".join(f"- {a['kod']}: {a['ad']} (ağırlık {a.get('agirlik', 2)}): {a.get('not', '')[:260]}" for a in pr.get("alanlar") or [])
    c = paylasim._claude_json(
        f"Bugün {time.strftime('%d.%m.%Y')}. Bir kişisel marka editörüsün. Kişi: {pr.get('kimlik')}\nHEDEF PROFİL: {pr.get('hedef_profil', '')}\n"
        f"ALANLAR (ağırlığa göre dengeli dağıt; teknoloji_ai toplamın en çok dörtte biri):\n{alanlar}\nALANLARI BAĞLAYAN BAKIŞ: {pr.get('baglanti', '')}\n"
        f"KÖPRÜ ÖRNEKLERİ: {'; '.join(pr.get('kopru_ornekleri') or [])}\nKAÇINILACAKLAR: {'; '.join(pr.get('kacin') or [])}\n"
        f"PLATFORMLAR:\n" + "\n".join(f"- {k}: {v}" for k, v in (pr.get("platformlar") or {}).items()) +
        f"\n\nAşağıdaki güncel maddelerden 32 ADAY öneri çıkar (bir editör sonra açıları tek tek eleyecek, kod dengeleyecek; çoğu elenecek, bu yüzden geniş tut): HER ALANDAN en az 4 aday (DERİN malzeme varsa; yoksa o alanı günlük haberle doldurma), "
        "her adaya en uygun platform (x | linkedin) ve 1-10 puan. Seçim ölçütü: bu kişi bu konuya KENDİ gözüyle değer katan bir yorum getirebilir mi "
        "(arkasındaki tasarım kararı, insan hikâyesi, sistem, ikinci derece sonuç; ya da iki alanı bağlayan bir köprü). Sıradan sonuç/transfer dedikodusu, "
        "magazin, kriz-felaket haberi, Türkiye gündelik siyaseti ALMA.\n"
        "DERİNLİK (kişi, 26 Ekim: 'boş beleş haber sitelerinden günlük talk getiriyorsun; sadece sporda değil, genelde de böyle bak'): HER ALANDA günlük "
        "gündem haberini ALMA: maç önü/sonu, oyuncu ya da yönetici demeci, transfer söylentisi, sakatlık, ilk 11, istatistik listesi; ürün çıktı/fiyat/"
        "indirim kısa haberi; 'X açıkladı' kısa haberi; ünlü atışması; sıradan sonuç. AL: arkasında bir karar, yapı, iş modeli, tasarım, tarih ya da insan "
        "hikâyesi anlatan, okuyunca bir şey öğrenilen içerik. 'derin yayın' işaretli maddeler ve kişinin kendi kürasyonu (üye olduğu bültenler, Adweek "
        "üyeliği, Kantan seçkisi, dinlediği yayınlar, izlediği hesaplar) önce; günlük haber akışından ancak metni gerçekten derinse.\n"
        "KONUŞULURLUK: birden çok kaynağın yazdığı (şu an konuşulan) konular öne; tek kaynaklı "
        "konu ancak gerçekten paylaşmaya değer bir keşifse (insanların 'bunu gördünüz mü' diye paylaşacağı türden). Her öneri bağlantısıyla paylaşılacak; "
        "okurun 'neden şimdi?' sorusunun cevabı bağlantının kendisi olmalı.\n"
        + (f"KİŞİ AZ ÖNCEKİ ÖNERİ TURUNU BEĞENMEDİ: {geri_bildirim}\nBu yüzden bu kez farklı türde, farklı kaynaklardan konular seç.\n" if geri_bildirim else "")
        + paylasim._gelisim_blogu("konu") + __import__("ghost_rehber").oneri_blogu() + "\n"
        + ("KİŞİNİN DAHA ÖNCE BEĞENMEDİĞİ TURLAR (nedenleriyle; benzerlerini önerme):\n" + "\n".join(f"- {r.get('neden') or 'neden yok'}: {'; '.join(r.get('basliklar') or [])[:300]}" for r in red) + "\n" if red else "")
        + "GERÇEK BİR İNSANIN AKIŞI GİBİ KARIŞIK: X önerilerinde biçim (bicim) dağılımı aşağı yukarı: 1 uzun, 2 gozlem, 2 minik, 1 emoji (tek emoji ya da 1-3 "
        "kelimeyle paylaşmaya uygun, kendini anlatan içerik); ton da karışık (ciddi | eglenceli | samimi), tavır hep aynı.\n"
        "AÇI KURALI (22 Ekim, kişi: 'söyleye söyleye bunu mu söyledin derler'): her öneri için ÖNCE 'bariz' alanına bu haberi duyan akıllı herkesin aklına "
        "ilk gelecek yorumu yaz; sonra 'aci' o bariz yorumu SÖYLEMESİN: ikinci derece sonuç, beklenmedik bağlantı, karşı-sezgisel bir gözlem, işin arkasındaki "
        "karar ya da insan. Bariz olmayan, kişinin arkasında durabileceği bir açı bulamıyorsan o maddeyi ÖNERME. İSTİSNA: paylaşmanın değeri şeyin "
        "kendisindeyse (ilginç bir keşif, güzel bir iş, espri malzemesi) zorla tez kurma; aci o zaman neden ilginç bulduğu ya da kısa tepkisi olur.\n"
        "Her öneri: no (listedeki numara), alan (koddan), platform (x|linkedin), bicim (emoji|minik|gozlem|uzun; linkedin için boş), ton, puan (1-10), neden (bu kişi için neden ilginç; tek cümle), bariz (herkesin söyleyeceği yorum), aci (kişinin olası yorumu/"
        "açısı, onun sesiyle tek cümle; bariz olan değil; uydurma olgu yok), story_yazi (yalnız story için: görselin üstüne ≤90 karakter, samimi, onun sesi), kopru (iki alanı "
        "bağlıyorsa hangileri; yoksa boş).\n"
        'JSON: {"oneriler": [{"no": 0, "alan": "futbol", "platform": "x", "bicim": "gozlem", "ton": "ciddi", "puan": 7, "neden": "...", "bariz": "...", "aci": "...", "story_yazi": "", "kopru": ""}]}\n\nMADDELER:\n' + satir,
        model_adi="sonnet", zaman_asimi=300)
    out = []
    for o in c.get("oneriler") or []:
        try:
            m = secilen[int(o.get("no"))]
        except (TypeError, ValueError, IndexError):
            continue
        p = o.get("platform") if o.get("platform") in ("x", "linkedin") else "x"   # story yalnız Instagram'ın içinden (story_sec)
        try:
            puan = float(o.get("puan") or 5)
        except (TypeError, ValueError):
            puan = 5.0
        out.append({**m, "alan": o.get("alan") or m["alan"], "platform": p, "puan": puan,
                    "bicim": o.get("bicim") if o.get("bicim") in ("emoji", "minik", "gozlem", "uzun") else "", "ton": o.get("ton") if o.get("ton") in ("ciddi", "eglenceli", "samimi") else "", "neden": str(o.get("neden") or "")[:300], "aci": str(o.get("aci") or "")[:400], "bariz": str(o.get("bariz") or "")[:300],
                    "story_yazi": str(o.get("story_yazi") or "")[:140], "kopru": str(o.get("kopru") or "")[:120]})
    aday_sayi = len(out)
    try:
        out = aci_elemesi(out, pr, log)
    except Exception as e:  # noqa: BLE001
        log(f"Açı elemesi yapılamadı ({e}); adaylar elenmeden dengelenecek")
    out = _dengele(out, hedef, {a.get("kod"): a.get("agirlik", 2) for a in pr.get("alanlar") or []})
    try:
        import ghost_gelisim
        ghost_gelisim.asama("kesif.secim", len(maddeler), aday_sayi)
        ghost_gelisim.asama("kesif.aci_elemesi", aday_sayi, len(out))
    except Exception:  # noqa: BLE001
        pass
    log(f"Keşif: {len(maddeler)} madde → {aday_sayi} aday → {len(out)} öneri ({', '.join(f'{k} {v}' for k, v in sorted(say.items()))})")
    return out


SON_ELENEN = []


def _bugun_yazilanlar():
    """Bugünün keşif kaydında zaten yazılmış (taslağı olan) önerilerin başlık ve açısı: öğleden sonraki tur aynı hikâyeyi yeniden önermesin."""
    try:
        k = json.loads((KESIF / f"{date.today().isoformat()}.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    return [f"{o['baslik']} — {o.get('aci', '')[:140]}" for o in k.get("oneriler") or [] if o.get("platform") in ("x", "linkedin") and o.get("temel")]


def _icerden_mi(ayrinti, metin):
    """Ayrıntı metnin girişinden (ilk ~2 paragraf, ~600 karakter) sonra mı geçiyor? Ayrıntının en uzun 3 kelimesinin metindeki ilk yeri; bulunamazsa None."""
    m = (metin or "").lower()
    K = sorted({w for w in re.findall(r"\w{5,}", (ayrinti or "").lower())}, key=len, reverse=True)[:3]
    yerler = [m.find(w) for w in K if m.find(w) >= 0]
    if not yerler or not m:
        return None
    return min(yerler) > min(600, len(m) * 0.25)


def aci_elemesi(adaylar, pr, log=print):
    """Yazmadan ÖNCE açıları eler (opus, tek çağrı; 23 Ekim). Eskiden her öneri yazılıyor, 2-3 kez yeniden yazılıyor, sonra çoğu 'bariz açı' ya da
    'paylaşılmaz' diye eleniyordu (22 Ekim 14.00 turu: 8 öneri → 0 taslak). Burada: aynı hikâyeyi anlatan adaylar gruplanır (en iyisi kalır), her açı
    kişinin gözüyle puanlanır (tazelik, paylaşılabilirlik, ses), zayıf açı keskinleştirilir ya da elenir. Yalnızca geçenler yazılır."""
    import paylasim
    global SON_ELENEN
    SON_ELENEN = []
    yazilacak = [o for o in adaylar if o.get("platform") in ("x", "linkedin")]
    if not yazilacak:
        return adaylar
    red = [r for r in pr.get("kesif_red") or [] if isinstance(r, dict)][-8:]
    zayif_aci = [r for r in paylasim._red(pr, "aci")][-6:]   # 25 Ekim: konu iyi ama söylenen bariz bulunan taslaklar (açı örneği, konu reddi değil)
    tercihler = [t.get("tercih") for t in paylasim.tercihler() if isinstance(t, dict) and t.get("aktif", True) and t.get("tercih")][-12:]
    bugun = _bugun_yazilanlar()
    satir = "\n".join(f"[{i}] ({o['alan']} · {o['platform']} · {o['kaynak']}) {o['baslik']} — {o.get('ozet', '')[:200]}\n    BARİZ: {o.get('bariz', '')}\n    AÇI: {o.get('aci', '')}"
                      for i, o in enumerate(yazilacak))
    c = paylasim._claude_json(
        f"Bugün {time.strftime('%d.%m.%Y')}. Bu kişinin X hesabının en titiz editörüsün. Önünde günün haberlerinden çıkarılmış ADAY AÇILAR var. Henüz "
        "hiçbiri yazılmadı; senin işin hangilerinin yazılmaya DEĞDİĞİNE karar vermek. Kişi az ama iyi paylaşmak istiyor (kendi sözü: 'önce çok iyi "
        "içerik paylaşan bir hesap olayım'; bir açı için: 'çok sıkıcı bir bakış açısı; söyleye söyleye bunu mu söyledin derler').\n\n"
        f"KİM: {pr.get('kimlik', '')}\nHEDEF PROFİL: {pr.get('hedef_profil', '')}\nALANLARI BAĞLAYAN BAKIŞ: {pr.get('baglanti', '')}\n"
        f"{paylasim._persona_blogu(pr, kisa=True)}\n{__import__('ghost_rehber').oneri_blogu()}\n"
        + ("DÜZELTMELERİNDEN ÖĞRENİLEN TERCİHLER:\n" + "\n".join(f"- {t}" for t in tercihler) + "\n" if tercihler else "")
        + paylasim._gelisim_blogu("konu")
        + ("BEĞENMEDİĞİ ÖNERİ TURLARI:\n" + "\n".join(f"- {r.get('neden') or 'neden yok'}: {'; '.join(r.get('basliklar') or [])[:240]}" for r in red) + "\n" if red else "")
        + ("KİŞİNİN 'KONU İYİ AMA SÖYLENEN BARİZ' DEDİĞİ TASLAKLAR (bu düzeyde açı kurma):\n" + "\n".join(f"- {r.get('ilk', '')[:200]}" for r in zayif_aci) + "\n" if zayif_aci else "")
        + ("BUGÜN ZATEN YAZILDI (aynı hikâyeyi ya da aynı fikri yeniden önerme):\n" + "\n".join(f"- {b}" for b in bugun) + "\n" if bugun else "")
        + ("SON 7 GÜNDE YAZILANLAR (aynı düşünce ancak yeni bir kanıtla tekrar ele alınır):\n" + "\n".join(f"- {x}" for x in __import__("karisim").son_gunler(en_cok=40)) + "\n")
        + "\nKENDİ GÖNDERİLERİNDEN ÖRNEKLER (ne tür gözlemleri paylaştığını buradan anla):\n" + "\n---\n".join(paylasim._ornekler(pr, 10)) +
        "\n\nHer aday için İKİ ADIM:\n"
        "1) en_iyi_aci: bu haberden BU KİŞİ için çıkabilecek en taze açıyı kur. Verilen AÇI zaten iyiyse aynen yaz; değilse daha iyisini bul: kararın arkasındaki "
        "insan ve sistem, ikinci derece sonuç, beklenmedik bir bağlantı (başka alanla köprü, listedeki başka bir haberle birleşim), somut bir tezat, gözlemden "
        "mizah. Tek cümle, onun sesiyle; haberde olmayan olgu UYDURMA, kişisel anı uydurma. Bu haberden taze açı çıkmıyorsa boş bırak.\n"
        "2) Puanlar EN_IYI_ACI için (boşsa verilen açı için):\n"
        "grup: aynı haberi/hikâyeyi anlatan adaylara aynı kısa etiketi ver (farklı kaynak ya da dil olsa bile). Aynı gruptan yalnızca biri yazılacak.\n"
        "tazelik (1-5): BARİZ yorumdan gerçekten uzak mı, okur 'bunu böyle düşünmemiştim' der mi? Bariz yorumu başka kelimelerle söylüyorsa, haberi "
        "özetliyorsa ya da 'asıl mesele X değil Y' kalıbına sokulmuş sıradan bir tespitse en çok 2.\n"
        "paylasilir (1-5): bu kişi bunu kendi adıyla paylaşır mı, takipçisi 'yine iyi yakalamış' der mi? Dayanağı olmayan uzmanlık, iç şaka, kimsenin "
        "umursamayacağı ayrıntı, takipçisine çok uzak konu en çok 2. Günlük gündem haberi (demeç, maç önü/sonu, transfer söylentisi, istatistik "
        "listesi, ürün çıktı/fiyat haberi, 'X açıkladı') en çok 2: kişi bunlarla ilgilenmiyor, derinlik istiyor (26 Ekim).\n"
        "ses (1-5): örneklerdeki kişinin aklına gelecek türden bir gözlem mi? Kurumsal, ders veren, LinkedIn makalesi gibi bir bakışsa en çok 2.\n"
        "bicim: EN_IYI_ACI'ya uygun biçim: emoji (içerik kendini anlatıyor, tek emoji ya da 1-3 kelime yeter) | minik (tek kısa cümlelik tepki, ≤140 "
        "karakter) | gozlem (1-3 cümle; açının bir gerekçesi ya da tezadı varsa) | uzun (nadiren; gerçekten açılması gereken bir fikir). Açı birden fazla "
        "cümleyle anlatılıyorsa minik/emoji SEÇME.\n"
        "neden: tek cümle.\n"
        'JSON: {"adaylar": [{"no": 0, "en_iyi_aci": "...", "grup": "raye-mercury", "bicim": "gozlem", "tazelik": 4, "paylasilir": 4, "ses": 4, "neden": "..."}]}\n\nADAYLAR:\n' + satir,
        model_adi="opus", zaman_asimi=400)
    puanlar = {}
    for a in c.get("adaylar") or []:
        try:
            puanlar[int(a.get("no"))] = a
        except (TypeError, ValueError):
            continue
    if not puanlar:
        raise ValueError("eleme yanıtı okunamadı")
    # 1. aşama (opus): açıyı geliştir + grupla; kendi puanı yalnız umutsuzları ayıklar (kendi kurduğu açıya cömert davranıyor, 23 Ekim denemesi)
    on, elenen = [], []
    for i, o in enumerate(yazilacak):
        a = puanlar.get(i) or {}
        try:
            t, p, s = int(a.get("tazelik") or 0), int(a.get("paylasilir") or 0), int(a.get("ses") or 0)
        except (TypeError, ValueError):
            t = p = s = 0
        yeni = str(a.get("en_iyi_aci") or a.get("aci_yeni") or "").strip()
        if yeni and yeni != o.get("aci", "").strip():
            o["aci_ilk"] = o.get("aci", ""); o["aci"] = yeni[:400]
        if o.get("platform") == "x" and a.get("bicim") in ("emoji", "minik", "gozlem", "uzun"):
            o["bicim_ilk"] = o.get("bicim", ""); o["bicim"] = a["bicim"]
        o["eleme"] = {"editor": [t, p, s], "neden": str(a.get("neden") or "")[:240], "grup": str(a.get("grup") or "")[:60]}
        if t + p + s >= 9 and min(t, p) >= 3:
            on.append(o)
        else:
            elenen.append({**o, "eleme_neden": o["eleme"]["neden"]})
    # 1b. aşama (23 Ekim): haberin METNİ okunur, açı haberdeki SOMUT bir ayrıntıya dayandırılır. Başlık + iki satırlık özetten kurulan açılar genel
    # kalıyor, yazılmış metin okurda 'sıradan' (tazelik/değer 3) alıyordu; kişinin en iyi gönderileri somut ayrıntıdan çıkıyor (Raye: albüm adı = alerjen uyarısı).
    on = sorted(on, key=lambda o: -sum(o["eleme"]["editor"]))[:14]
    if on:
        def _oku(o):
            try:
                o["link"] = gn_coz(o["link"])
            except Exception:  # noqa: BLE001
                pass
            return sayfa_oku(o["link"])
        with ThreadPoolExecutor(7) as h:
            sayfalar = list(h.map(_oku, on))
        metinler = []
        for o, sy in zip(on, sayfalar):
            o["metin_ozu"] = sy["metin"][:3500]; o["_linkler"] = sy["linkler"]; o["_gorseller"] = sy["gorseller"]
            o["yayin_tarihi"] = sy["yayin"] or (time.strftime("%Y-%m-%d", time.localtime(o["zaman"])) if o.get("zaman") else "")
            if sy["url"]:
                o["link"] = sy["url"]
            metinler.append(sy["metin"])
        log(f"Açı elemesi: {sum(1 for m in metinler if m)}/{len(on)} haberin metni okundu")
        c2 = paylasim._claude_json(
            f"Bugün {time.strftime('%d.%m.%Y')}. Bu kişinin X hesabının editörüsün. Aşağıda yazılmaya aday haberler, haberin METNİ ve şimdiki açı var.\n"
            f"KİŞİ: {pr.get('kimlik', '')}\nALANLARI BAĞLAYAN BAKIŞ: {pr.get('baglanti', '')}\n{paylasim._persona_blogu(pr, kisa=True)}\n"
            "ÖRNEKLERİ:\n" + "\n---\n".join(paylasim._ornekler(pr, 8))
            + ("\n\nBUGÜN ZATEN YAZILDI (aynı fikri ya da aynı temayı, ör. aynı gün üçüncü kez 'yapay zekâ kanıtı', yeniden yazdırma; böyle adayın açısını boş bırak):\n"
               + "\n".join(f"- {x}" for x in bugun) if bugun else "") +
            "\n\nYazmadan önce her adayın İÇİNİ aç (kullanıcının editoryal yöntemi, 24 Ekim): kaynak nesnesi, olgu, beyan, ayrıntı, karar, katkı, sınır ayrı "
            "tutulur. 'Ajans satışları artırdık diyor' bağımsız sonuç değildir; ürün sitesi 'daha hızlı' diyorsa bu denenmiş bir şey değildir; bir teklif "
            "yürürlükteki kural değildir. Bugün yayımlanan bir yazı geçen yılki bir işi anlatıyor olabilir.\n"
            "\nBu kişinin en iyi gönderileri haberin İÇİNDEKİ somut bir ayrıntıdan çıkar: bir ad, bir sözcük seçimi, bir tasarım kararı, bir sayı, bir "
            "kural, beklenmedik bir insan ayrıntısı; ona bakıp sistemi ya da kararı görür (ör. Raye'in albümünün adı 'This Music May Contain Hope': "
            "'may contain' gıda paketlerindeki alerjen uyarısının kalıbı; Mickey'nin eldivenleri). Genel/makro yorum ('X'in faturasını Y ödüyor', 'asıl "
            "mesele …') zayıftır.\nHer aday için:\n"
            "nesne: tam olarak neyi konuşuyoruz (bir kampanya, ürün, araştırma, eser, kural, açıklama...; adıyla, tek satır)\n"
            "olgu: kaynak gerçekten ne söylüyor (doğrulanabilir kısım, tek cümle)\n"
            "beyan: metindeki iddialardan kimin KENDİ beyanı olanlar ('Ajans: satışlar %30 arttı' gibi; yoksa boş)\n"
            "ayrinti: haber metninde geçen, açının dayanacağı SOMUT ayrıntı (metinden; yoksa boş). OKUDUĞUNU GÖSTER: başlığı ve ilk iki paragrafı herkes "
            "okur; mümkünse ayrıntıyı METNİN İÇİNDEN (üçüncü paragraf ve sonrası: bir alıntı, bir yan not, bir yapımcı/yönetmen/tasarımcı adı) seç. "
            "İşin yaratıcısı (yönetmen, ajans, tasarımcı, yazar) metinde adıyla geçiyorsa 'yaratici' alanına yaz.\n"
            "karar: bu sonucu doğuran yaratıcı, teknik, ticari ya da kültürel karar (metinden çıkarılabiliyorsa; yoksa boş)\n"
            "aci: o ayrıntıdan çıkan, bariz olmayan tek cümlelik açı, onun sesiyle (metinde olmayan olgu UYDURMA). Somut ayrıntı yoksa ya da ayrıntıdan taze "
            "bir şey çıkmıyorsa boş bırak (aday elenir; zorlama).\n"
            "sinir: neyi BİLMİYORUZ ya da görmedik/denemedik (ör. 'yalnız ürün sayfası okundu, ürün denenmedi', 'sonuç ajansın beyanı'; tek cümle)\n"
            "olay_tarihi: anlatılan iş/olay ne zaman oldu (YYYY-MM; metin söylemiyorsa boş). Yayın tarihi değil.\n"
            "asil: DIŞ BAĞLANTILAR içinden asıl kaynağın numarası (kampanyanın/ürünün sahibi, şirketin açıklaması, araştırmanın kendisi, projenin sayfası/"
            "GitHub'ı, resmî kurum). Haber sitesinin kendisi zaten asıl kaynaksa ya da uygun bağlantı yoksa -1.\n"
            "gorsel: ayrıntı GÖRSEL bir unsur mu (renk, biçim, tasarım, ambalaj, afiş, kare)? true/false. Görsel ayrıntılar yazılmadan önce görsele bakılır.\n"
            'JSON: {"adaylar": [{"no": 0, "nesne": "...", "olgu": "...", "beyan": "", "ayrinti": "...", "karar": "", "aci": "...", "sinir": "...", '
            '"olay_tarihi": "", "asil": -1, "gorsel": false, "yaratici": ""}]}\n\nADAYLAR:\n'
            + "\n\n".join(f"[{j}] {o['baslik']} (yayın: {o.get('yayin_tarihi') or '?'})\nŞİMDİKİ AÇI: {o['aci']}\nMETİN: {(o.get('metin_ozu') or o.get('ozet', ''))[:3500]}"
                           + ("\nDIŞ BAĞLANTILAR:\n" + "\n".join(f"  ({k}) {u} — {t}" for k, (u, t) in enumerate((o.get('_linkler') or [])[:15])) if o.get("_linkler") else "")
                           for j, o in enumerate(on)),
            model_adi="opus", zaman_asimi=400)
        yeni = {}
        for x in c2.get("adaylar") or []:
            try:
                yeni[int(x.get("no"))] = x
            except (TypeError, ValueError):
                continue
        if yeni:
            kalan = []
            for j, o in enumerate(on):
                x = yeni.get(j) or {}
                if str(x.get("aci") or "").strip() and str(x.get("ayrinti") or "").strip():
                    if str(x["aci"]).strip() != o["aci"]:
                        o.setdefault("aci_ilk", o["aci"]); o["aci"] = str(x["aci"]).strip()[:400]
                    o["ayrinti"] = str(x["ayrinti"]).strip()[:300]
                    for k in ("nesne", "olgu", "beyan", "karar", "sinir"):
                        o[k] = str(x.get(k) or "").strip()[:300]
                    o["olay_tarihi"] = str(x.get("olay_tarihi") or "").strip()[:7]
                    o["yaratici"] = str(x.get("yaratici") or "").strip()[:120]
                    o["ayrinti_ic"] = _icerden_mi(o["ayrinti"], o.get("metin_ozu") or "")
                    o["_gorsel"] = bool(x.get("gorsel"))
                    try:
                        ai = int(x.get("asil"))
                    except (TypeError, ValueError):
                        ai = -1
                    o["_asil"] = (o.get("_linkler") or [])[ai][0] if 0 <= ai < len(o.get("_linkler") or []) else ""
                    kalan.append(o)
                else:
                    elenen.append({**o, "eleme_neden": "haberde açıya dayanak olacak somut ayrıntı yok"})
            on = kalan
    # 1c (24 Ekim, ChatGPT brifi 'asıl kaynağa dönüş' ve 'doğrulama'): asıl kaynak okunur ve gönderinin bağlantısı olur (keşif bağlantısı ayrıca saklanır);
    # görsel ayrıntı görsel açılıp incelenmeden yazılmaz; olay eskiyse 'yeni' gibi sunulmaz; ne okunduğu kayda geçer.
    if on:
        from urllib.parse import urlparse

        def _derin(o):
            okunan = ["haberin tam metni" if o.get("metin_ozu") else "yalnız başlık ve kısa özet"]
            if o.get("_asil"):
                sy = sayfa_oku(o["_asil"])
                if sy["metin"]:
                    o["kesif_link"], o["link"] = o["link"], sy["url"] or o["_asil"]
                    o["asil_metin"] = sy["metin"][:2500]
                    okunan.append("asıl kaynağın metni (" + re.sub(r"^www\.", "", urlparse(o["link"]).netloc) + ")")
                    o["_gorseller"] = (o.get("_gorseller") or []) + [g for g in sy["gorseller"] if g not in (o.get("_gorseller") or [])]
                else:
                    okunan.append("asıl kaynak açılamadı")
            if o.get("_gorsel"):
                gor, ne = _gorsel_bak(o, log)
                if gor is None:
                    return "görsel ayrıntı yazılacaktı ama görsele erişilemedi"
                if not gor:
                    return "görsel ayrıntı görselde doğrulanamadı"
                o["gorulen"] = ne; okunan.append("görsel incelendi")
            o["okunan"] = okunan
            ot = o.get("olay_tarihi") or ""
            if re.match(r"^\d{4}-\d{2}$", ot) and ot < time.strftime("%Y-%m", time.localtime(time.time() - 45 * 86400)):
                o["eski_is"] = True
            return ""
        with ThreadPoolExecutor(5) as h:
            nedenler = list(h.map(_derin, on))
        on2 = []
        for o, n in zip(on, nedenler):
            (elenen.append({**o, "eleme_neden": n}) if n else on2.append(o))
        log(f"Açı elemesi: asıl kaynak {sum(1 for o in on2 if o.get('kesif_link'))}, görsel incelenen {sum(1 for o in on2 if o.get('gorulen'))}, "
            f"görsel yüzünden elenen {sum(1 for n in nedenler if n)}")
        on = on2
    # 2. aşama: BAĞIMSIZ yargıç (sonnet; son okur kapısıyla aynı model ve ölçüt). Açıyı kimin kurduğunu bilmez; yalnız haber + açı.
    if on:
        hakem = paylasim._claude_json(
            f"Bugün {time.strftime('%d.%m.%Y')}. Bu alanları yakından izleyen, X'te neyin çok konuşulduğunu bilen, akıllı ama meşgul bir okursun; aynı zamanda "
            "aşağıdaki kişinin gönderilerini iyi tanıyan bir editörsün. Her satırda bir haber ve bu kişinin o habere getireceği AÇI var (henüz yazılmadı). "
            "Dürüstçe puanla (5 nadir verilir):\n"
            "tazelik (1-5): haberi duyan akıllı birinin aklına İLK gelecek ya da X'te zaten herkesin söylediği yorum mu? Öyleyse en çok 2. 4 ve üstü yalnızca "
            "'bunu böyle düşünmemiştim' dedirtiyorsa.\n"
            "paylasilir (1-5): iyi bir içerik üreticisi bunu kendi adıyla paylaşır mı; takipçisi durup okur mu? Uzak/umursanmayacak konu, dayanaksız uzmanlık, "
            "boş tespit en çok 2.\n"
            "ses (1-5): örneklerdeki kişinin yapacağı türden bir gözlem mi?\n"
            "neden: tek cümle.\n"
            'JSON: {"puanlar": [{"no": 0, "tazelik": 3, "paylasilir": 3, "ses": 3, "neden": "..."}]}\n\n'
            f"KİŞİ: {pr.get('kimlik', '')}\n{paylasim._persona_blogu(pr, kisa=True)}\nÖRNEKLERİ:\n" + "\n---\n".join(paylasim._ornekler(pr, 8)) + "\n\nAÇILAR:\n"
            + "\n".join(f"[{j}] HABER: {o['baslik']} — {o.get('ozet', '')[:160]}\n    AYRINTI: {o.get('ayrinti', '')}\n    AÇI: {o['aci']}" for j, o in enumerate(on)),
            model_adi="sonnet", zaman_asimi=300)
        hp = {}
        for x in hakem.get("puanlar") or []:
            try:
                hp[int(x.get("no"))] = x
            except (TypeError, ValueError):
                continue
    else:
        hp = {}
    gecen, gruplar = [], {}
    for j, o in enumerate(on):
        x = hp.get(j)
        if x is None:                                     # hakem yanıtı yoksa editörün puanı (eski davranış)
            t, p, s = o["eleme"]["editor"]
        else:
            try:
                t, p, s = int(x.get("tazelik") or 0), int(x.get("paylasilir") or 0), int(x.get("ses") or 0)
            except (TypeError, ValueError):
                t = p = s = 0
            o["eleme"]["hakem_neden"] = str(x.get("neden") or "")[:240]
        o["eleme"].update({"tazelik": t, "paylasilir": p, "ses": s})
        # son kapı yazılmış metinde tazelik ≥4 ve paylaşılabilirlik ≥4 ister; açıda tazelik ≥4 şart (yazım tazelik katmıyor), paylaşılabilirlik yazımla artabilir
        if t >= 4 and p >= 3 and s >= 3:
            o["puan"] = round(o.get("puan", 5) / 2 + t + p + s / 2, 1)      # eleme puanı ağır basar (dengeleme bu puanla sıralar)
            g = o["eleme"]["grup"] or o["baslik"]
            if g in gruplar:
                if o["puan"] > gruplar[g]["puan"]:
                    elenen.append({**gruplar[g], "eleme_neden": "aynı hikâye"}); gecen.remove(gruplar[g]); gruplar[g] = o; gecen.append(o)
                else:
                    elenen.append({**o, "eleme_neden": "aynı hikâye"})
                continue
            gruplar[g] = o; gecen.append(o)
        else:
            elenen.append({**o, "eleme_neden": o["eleme"].get("hakem_neden") or o["eleme"]["neden"]})
    SON_ELENEN = [{"baslik": o["baslik"], "alan": o["alan"], "aci": o.get("aci", ""), "neden": o["eleme_neden"], "puan": o["eleme"]} for o in elenen]
    log(f"Açı elemesi: {len(yazilacak)} aday → {len(gecen)} geçti" + (f"; elenen: " + "; ".join(f"{o['baslik'][:40]} ({o['eleme_neden'][:60]})" for o in elenen[:8]) if elenen else ""))
    return gecen + [o for o in adaylar if o.get("platform") not in ("x", "linkedin")]


IG = KLASOR / "kayitlar" / "ig_gorulen.json"
IG_GORSEL = KLASOR / "kayitlar" / "ig"


def ig_kaydet(gonderiler):
    """Uzantının Instagram'da (yalnızca okuyarak) gördüğü gönderiler. Görsel hemen indirilir (Instagram bağlantıları birkaç günde geçersiz olur).
    Döner: yeni gönderi sayısı."""
    import requests
    try:
        L = json.loads(IG.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        L = []
    var = {x["kod"] for x in L}
    yeni = 0
    IG_GORSEL.mkdir(parents=True, exist_ok=True)
    for g in gonderiler or []:
        kod = re.sub(r"[^\w-]", "", str(g.get("kod") or ""))[:40]
        if not kod or kod in var:
            continue
        try:
            r = requests.get(g["resim"], headers=UA, timeout=20) if str(g.get("resim") or "").startswith("https://") else None
            if r is not None and r.ok and len(r.content) > 5000:
                (IG_GORSEL / f"{kod}.jpg").write_bytes(r.content)
        except Exception:  # noqa: BLE001
            pass
        L.append({"onerilen": bool(g.get("onerilen")), "kod": kod, "url": str(g.get("url") or f"https://www.instagram.com/p/{kod}/")[:200], "yazar": re.sub(r"[^\w.]", "", str(g.get("yazar") or ""))[:40],
                  "metin": str(g.get("metin") or "")[:700], "alt": str(g.get("alt") or "")[:300], "tur": "reel" if g.get("tur") == "reel" else "post",
                  "tarih": str(g.get("tarih") or "")[:30], "gorulme": time.time(), "gorsel": (IG_GORSEL / f"{kod}.jpg").exists()})
        var.add(kod); yeni += 1
    sinir = time.time() - 14 * 86400
    L = [x for x in L if x.get("gorulme", 0) >= sinir][-1500:]
    IG.write_text(json.dumps(L, ensure_ascii=False, indent=1), encoding="utf-8")
    return yeni


IG_ARAYUZ = re.compile(r"^(•|Senin için önerilenler|Suggested for you|Takip Et|Follow|Çevirisine bak|See translation|devamı|more|… devamı|\.\.\. devamı|"
                       r"Orijinal ses|Original audio|Sponsorlu|Sponsored|ve|and|Ses|Reels)$|beğendi$|liked by|diğer kişi|others$", re.I)


def ig_temiz(metin, yazar=""):
    """Instagram'ın ekran yazılarını (kullanıcı adı tekrarları, '5s', 'Takip Et', beğeni sayıları) atıp gönderinin kendi açıklamasını bırakır."""
    out = []
    for satir in str(metin or "").splitlines():
        t = satir.strip()
        if not t or IG_ARAYUZ.search(t) or t == yazar or re.fullmatch(r"\d+\s?(s|d|dk|g|sa|h|hf|w|m|gün|hafta)", t, re.I) \
                or re.fullmatch(r"[\d.,]+\s?(B|Mn|K|M)?", t) or re.fullmatch(r"[\w.]{2,30}", t):
            continue
        out.append(t)
    m = " ".join(out)
    if yazar and m.startswith(yazar):
        m = m[len(yazar):].strip()
    return re.sub(r"\s+", " ", m).strip()


def story_sec(log=print, baslangic=None):
    """Story önerileri yalnızca Instagram'ın içinden (kullanıcı, 22 Ekim: "başka link saçma oluyor"): uzantının gördüğü gönderilerden, dün akşamdan beri
    görülen ve daha önce önerilmemiş olanlar arasından kişinin story'sinde paylaşacağı türden olanlar (Instagram'ın kendi 'story'ne ekle'siyle)."""
    try:
        L = json.loads(IG.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    baslangic = baslangic or (datetime.combine(date.today(), datetime.min.time()).timestamp() - 6 * 3600)
    onceki = set()
    for f in sorted(KESIF.glob("20*.json"))[-14:]:
        try:
            onceki |= {o.get("ig_kod") for o in json.loads(f.read_text(encoding="utf-8")).get("oneriler") or [] if o.get("ig_kod")}
        except Exception:  # noqa: BLE001
            pass
    # yalnız takip ettiği hesaplar: Instagram'ın araya soktuğu "Senin için önerilenler" (22 Ekim: spor dedikodu sayfaları buradan geliyordu) aday değil
    aday = [x for x in L if x.get("gorulme", 0) >= baslangic and x["kod"] not in onceki and x.get("gorsel")
            and not x.get("onerilen") and not re.search(r"Senin için önerilenler|Suggested for you", x.get("metin") or "", re.I)][-80:]
    if not aday:
        return []
    import paylasim
    pr = paylasim.profil()
    hedef = int((pr.get("hedef") or {}).get("story_gunluk") or 4)
    try:                                                     # Favoriler'deki (izlenen) Instagram hesapları önce ve işaretli (hesaplar.py, 24 Ekim)
        import hesaplar
        igh = hesaplar.ig_hesaplari()
    except Exception:  # noqa: BLE001
        igh = {}
    aday = sorted(aday, key=lambda x: 0 if x["yazar"].lower() in igh else 1)
    satir = "\n".join(f"[{i}] @{x['yazar']}{' (izlediği hesap)' if x['yazar'].lower() in igh else ''} ({x['tur']}): {ig_temiz(x['metin'], x['yazar'])[:300]} | görsel: {x['alt'][:120]}"
                      for i, x in enumerate(aday))
    alanlar = "; ".join(f"{a['kod']}: {a['ad']}" for a in pr.get("alanlar") or [] if isinstance(a, dict))
    red = [r for r in pr.get("story_red") or [] if isinstance(r, dict)][-15:]
    pay = [r for r in pr.get("story_paylasilan") or [] if isinstance(r, dict)][-10:]
    # 22 Ekim (kullanıcı: "benim stilime asla uymayacak öneriler"): ilk sürüm yalnız alan listesine bakıyordu; futbol dedikodusu, yorumcu atışması,
    # maç kutlaması ve podcast tanıtımı seçti, "helal olsun" gibi yazılar yazdı. Artık kişilik, gerçek gönderiler ve reddedilen örnekler veriliyor.
    c = paylasim._claude_json(
        f"Bir kişinin Instagram story'lerini seçen, onun zevkini çok iyi bilen bir editörsün.\nKİŞİ: {pr.get('kimlik')}\n"
        f"KİŞİLİĞİ VE YAZI İLKELERİ:\n{paylasim._persona_blogu(pr, kisa=True)}\nTAVRI: {pr.get('tavir', '')}\n"
        f"İLGİ ALANLARI: {alanlar}\nKAÇINDIKLARI: {'; '.join(pr.get('kacin') or [])}\n"
        "X'TEKİ GERÇEK GÖNDERİLERİNDEN ÖRNEKLER (zevkini ve üslubunu buradan anla):\n" + "\n---\n".join(paylasim._ornekler(pr, 6)) + "\n"
        + ("BEĞENMEDİĞİ STORY ÖNERİLERİ (benzerlerini ASLA önerme):\n" + "\n".join(f"- @{r.get('yazar')}: {r.get('gonderi', '')[:110]} → {r.get('neden')}" for r in red) + "\n" if red else "")
        + ("STORY'SİNDE PAYLAŞTIKLARI:\n" + "\n".join(f"- @{r.get('yazar')}: {r.get('gonderi', '')[:110]}" for r in pay) + "\n" if pay else "")
        + f"\nAşağıdakiler takip ettiği hesaplardan bugün gördüğü Instagram gönderileri. Bu kişinin kendi story'sinde Instagram'ın 'story'ne ekle' özelliğiyle "
        f"GERÇEKTEN paylaşacağı olanları seç (en çok {hedef}; hiçbiri uymuyorsa BOŞ liste — vasat öneri hiç öneri olmamasından kötü). Bu kişi düşünen, "
        "kreatif, ayrıntıya bakan biri: iyi bir iş, tasarım ya da zanaat, akıllı bir fikir, beklenmedik bir hikâye, güzel bir kare, sevdiği birinin ürettiği "
        "bir şey. ALMA: spor dedikodusu, yorumcu/hoca sözleri ve atışmaları, skor/gol/puan kutlaması, kulüp ya da marka duyurusu, podcast/bölüm tanıtımı, "
        "reklam, kampanya, magazin, siyaset, kriz, birinin özel hayatı. story_yazi: çoğu story yazısız paylaşılır; gerekiyorsa 1-5 kelime, kişinin sesiyle, "
        "klişesiz ('helal olsun', 'bir başka', 'konuşmamız lazım', 'muhteşem' YOK); emin değilsen boş bırak. neden: neden ONA uyduğu, tek cümle.\n"
        'JSON: {"oneriler": [{"no": 0, "alan": "kreatif", "puan": 8, "neden": "...", "story_yazi": ""}]}\n\nGÖNDERİLER:\n' + satir, model_adi="opus", zaman_asimi=240)
    out = []
    for o in c.get("oneriler") or []:
        try:
            x = aday[int(o.get("no"))]
        except (TypeError, ValueError, IndexError):
            continue
        out.append({"platform": "story", "ig_kod": x["kod"], "id": "ig_" + x["kod"], "link": x["url"], "kaynak": "Instagram", "yazar": x["yazar"],
                    "baslik": f"@{x['yazar']} · " + (ig_temiz(x["metin"], x["yazar"]) or x.get("alt") or "")[:140], "resim": f"/ig-gorsel/{x['kod']}.jpg", "alan": o.get("alan") or "",
                    "alan_ad": _alan_adi(o.get("alan") or ""), "puan": float(o.get("puan") or 5), "neden": str(o.get("neden") or "")[:300],
                    "story_yazi": str(o.get("story_yazi") or "")[:140], "zaman": time.time()})
    out = [o for o in out if o["puan"] >= 7]
    out.sort(key=lambda o: -o["puan"])
    log(f"Story: {len(aday)} Instagram gönderisinden {len(out[:hedef])} öneri")
    return out[:hedef]


def story_guncelle(log=print):
    """Bugünün keşif kaydındaki story'leri Instagram'dan yeniden seçer (yeni gönderiler biriktikçe); X/LinkedIn önerilerine dokunmaz."""
    yol = KESIF / f"{date.today().isoformat()}.json"
    try:
        kayit = json.loads(yol.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        kayit = {"tarih": date.today().isoformat(), "zaman": time.time(), "madde": 0, "oneriler": []}
    eski = [o for o in kayit.get("oneriler") or [] if o.get("platform") == "story" and o.get("ig_kod")]   # mevcut öneriler korunur, yenileri eklenir
    yeni = story_sec(log)
    kayit["oneriler"] = [o for o in kayit.get("oneriler") or [] if o.get("platform") != "story"] + eski + [o for o in yeni if o["id"] not in {e["id"] for e in eski}]
    kayit["story_zaman"] = time.time()
    KESIF.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps(kayit, ensure_ascii=False, indent=1), encoding="utf-8")
    return yeni


def _dengele(adaylar, hedef, agirlik):
    """Kodla denge: X'te alan başına en çok 2 ve yapay zekâ en çok dörtte biri; story'de alan başına en çok 2; LinkedIn 1-2.
    Alanlar ağırlık sırasıyla dönüşümlü (round-robin) doldurulur; her alanın içinde puan yüksek olan önce."""
    kotalar = {"x": int(hedef.get("x_gunluk", 4)) + 2, "story": int(hedef.get("story_gunluk", 4)) + 1, "linkedin": 2}
    out = []
    for plat, kota in kotalar.items():
        havuz = sorted([o for o in adaylar if o["platform"] == plat], key=lambda o: -(o.get("puan", 5) + min(2, o.get("kaynak_sayisi", 1) - 1) + (1 if o.get("trend") else 0)))
        alan_sira = sorted({o["alan"] for o in havuz}, key=lambda a: -agirlik.get(a, 2))
        secilen, say = [], {}
        ai_tavan = max(1, kota // 4)
        while len(secilen) < kota:
            ekledi = False
            for a in alan_sira:
                if len(secilen) >= kota:
                    break
                tavan = ai_tavan if a == "teknoloji_ai" else 2
                if say.get(a, 0) >= tavan:
                    continue
                aday = next((o for o in havuz if o["alan"] == a and o not in secilen), None)
                if aday:
                    secilen.append(aday); say[a] = say.get(a, 0) + 1; ekledi = True
            if not ekledi:
                break
        out += secilen
    return out


GN_ONB = KESIF / "gn_onbellek.json"


def gn_coz(url):
    """Google News yönlendirme bağlantısını asıl haber adresine çevirir (X önizleme kartı Google News değil haberin kendisi olsun).
    Sayfadaki imza + zaman damgasıyla Google'ın kendi çözümleme isteği; sonuç önbellekte. Olmazsa bağlantı olduğu gibi kalır."""
    if "news.google.com" not in str(url):
        return url
    onb = {}
    try:
        onb = json.loads(GN_ONB.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass
    if url in onb:
        return onb[url]
    import requests
    try:
        aid = re.search(r"/articles/([^?]+)", url).group(1)
        r = requests.get(f"https://news.google.com/rss/articles/{aid}", headers=UA, timeout=15)
        sg = re.search(r'data-n-a-sg="([^"]+)"', r.text).group(1); ts = re.search(r'data-n-a-ts="([^"]+)"', r.text).group(1)
        istek = ["Fbv4je", f'["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,null,0],"{aid}",{ts},"{sg}"]']
        r2 = requests.post("https://news.google.com/_/DotsSplashUi/data/batchexecute", headers={**UA, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
                           data="f.req=" + urllib.parse.quote(json.dumps([[istek]])), timeout=15)
        gercek = json.loads(json.loads(r2.text.split("\n\n")[1])[:-2][0][2])[1]
        if not str(gercek).startswith("http"):
            return url
        onb[url] = gercek
        GN_ONB.write_text(json.dumps(dict(list(onb.items())[-3000:]), ensure_ascii=False), encoding="utf-8")
        time.sleep(1.2)                                   # hız sınırına takılmamak için aralık
        return gercek
    except Exception:  # noqa: BLE001
        return url


SOSYAL = re.compile(r"(facebook|twitter|x\.com|instagram|linkedin|pinterest|reddit|whatsapp|t\.me|mailto:|tiktok|threads\.net|bsky|share|/tag/|/author/|"
                   r"/category/|/kategori/|/etiket/|subscribe|newsletter|privacy|cookie|login|signin|apps\.apple|play\.google|doubleclick|utm_)", re.I)


def sayfa_oku(url):
    """Haber sayfasını BİR kez okur (2026-10-24, ChatGPT brifi 'asıl kaynağa dönüş'): {url, baslik, metin, linkler [(url, yazı)], gorseller [url], yayin}.
    linkler: metnin içinden dışarı (başka siteye) verilen bağlantılar: kampanyanın sahibi, şirket açıklaması, araştırma, proje sayfası burada olur.
    Okunamazsa metin boş döner (hata fırlatmaz)."""
    import html as H
    from urllib.parse import urljoin, urlparse
    import requests
    out = {"url": url, "baslik": "", "metin": "", "linkler": [], "gorseller": [], "yayin": ""}
    try:
        import abonelik                                   # üyelik olan sitelerde (Adweek) Chrome oturumuyla tam yazı
        r = abonelik.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
                                                                 "Version/18.0 Safari/605.1.15", "Accept-Language": "tr,en;q=0.8"})
        if r.status_code >= 400:
            return out
        h, out["url"] = r.text, r.url
    except Exception:  # noqa: BLE001
        return out
    m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', h, re.I) or re.search(r"<title[^>]*>(.*?)</title>", h, re.I | re.S)
    if m:
        out["baslik"] = H.unescape(re.sub(r"\s+", " ", m.group(1))).strip()[:200]
    m = re.search(r'(?:article:published_time|datePublished)["\']?\s*(?:content=|:)\s*["\']([0-9]{4}-[0-9]{2}-[0-9]{2})', h, re.I)
    out["yayin"] = m.group(1) if m else ""
    for m in re.finditer(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', h, re.I):
        out["gorseller"].append(urljoin(out["url"], H.unescape(m.group(1))))
    govde = re.sub(r"(?is)<(script|style|noscript|nav|footer|header|aside|form)\b.*?</\1>", " ", h)
    a = re.search(r"(?is)<article\b.*?</article>", govde)
    govde = a.group(0) if a and len(a.group(0)) > 1500 else govde
    for m in re.finditer(r'(?is)<img\b[^>]*\bsrc=["\']([^"\']+)["\']', govde):
        u = urljoin(out["url"], H.unescape(m.group(1)))
        if u.startswith("http") and not re.search(r"(logo|icon|avatar|sprite|pixel|\.svg|\.gif)", u, re.I) and u not in out["gorseller"]:
            out["gorseller"].append(u)
    paragraflar = [re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", x))).strip() for x in re.findall(r"(?is)<(?:p|h2|h3|li)\b[^>]*>(.*?)</(?:p|h2|h3|li)>", govde)]
    metin = "\n".join(x for x in paragraflar if len(x) > 40)
    out["metin"] = metin[:40000] if len(metin) >= 400 else ""
    ev = urlparse(out["url"]).netloc.replace("www.", "")
    gor = set()
    for m in re.finditer(r'(?is)<a\b[^>]*href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', govde):
        u = urljoin(out["url"], H.unescape(m.group(1)))
        yazi = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))).strip()
        alan = urlparse(u).netloc.replace("www.", "")
        if not u.startswith("http") or not alan or alan == ev or alan.endswith("." + ev) or SOSYAL.search(u) or u in gor or len(yazi) < 2:
            continue
        gor.add(u); out["linkler"].append((u, yazi[:90]))
    out["gorseller"] = out["gorseller"][:6]; out["linkler"] = out["linkler"][:25]
    return out


def _gorsel_bak(o, log=print):
    """Görsel bir ayrıntı yazılacaksa görsel GERÇEKTEN açılıp incelenir (ChatGPT brifi 5: 'erişim yoksa ayrıntıyı uydurma'). Döner: (görünüyor_mu, görülen)."""
    import tempfile
    import requests
    import claude_yaz
    yollar = []
    for u in (o.get("_gorseller") or [])[:3]:
        try:
            r = requests.get(u, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            if r.ok and r.headers.get("content-type", "").startswith("image/") and len(r.content) > 8000:
                uz = ".png" if "png" in r.headers["content-type"] else ".jpg"
                f = tempfile.NamedTemporaryFile(delete=False, suffix=uz); f.write(r.content); f.close(); yollar.append(f.name)
        except Exception:  # noqa: BLE001
            continue
    if not yollar:
        return None, ""
    try:
        y = claude_yaz.sor_gorsel(
            "Bu görsel(ler) bir haberden. Haberin bahsettiği GÖRSEL ayrıntı şu: «" + str(o.get("ayrinti") or "") + "». Bu ayrıntı görsel(ler)de gerçekten görünüyor mu? "
            "Gördüğünü kısaca ve somut yaz (renk, biçim, yazı, nesne); görmediğin şeyi yazma. Yalnızca JSON: {\"gorunuyor\": true, \"gorulen\": \"...\"}",
            yollar, model_adi="sonnet", zaman_asimi=180)
        m = re.search(r"\{.*\}", y, re.S)
        j = json.loads(m.group(0)) if m else {}
        return bool(j.get("gorunuyor")), str(j.get("gorulen") or "")[:300]
    except Exception as e:  # noqa: BLE001
        log(f"Görsel incelenemedi ({o.get('baslik', '')[:40]}): {e}")
        return None, ""
    finally:
        for y_ in yollar:
            Path(y_).unlink(missing_ok=True)


def _alan_adi(kod):
    import paylasim
    return next((a["ad"] for a in paylasim.profil().get("alanlar") or [] if a.get("kod") == kod), kod)


def _resim_bul(o):
    """Story önerisinde görsel yoksa sayfanın og:image'ı (Google News yönlendirmesi çözülemez; atlanır)."""
    if o.get("resim") or "news.google.com" in o["link"]:
        return o.get("resim") or ""
    try:
        import requests
        r = requests.get(o["link"], headers=UA, timeout=12)
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', r.text, re.I)
        return html.unescape(m.group(1)) if m else ""
    except Exception:  # noqa: BLE001
        return ""


def arsiv_maddeleri(log=print):
    """'Bugün geçmişte' (24 Ekim; araştırma önerisi 'arşivden çıkarma'): Wikipedia'nın günün olayları/doğumlar/ölümler servisi (tr + en) → Claude
    (sonnet) kişinin alanlarına uyan en çok 3 kayıt seçer (futbol ve tuttuğu takım, reklam ve kampanyalar, tasarım, popüler kültür, teknoloji tarihi).
    Eski malzeme 'herkes yazdı' anlamında bayatlamaz; bugünün haberiyle birleşince şaşırtıcı gönderi çıkar. Günde bir kez (önbellek)."""
    import requests
    import paylasim
    gun = date.today()
    yol = KESIF / f"arsiv_{gun.isoformat()}.json"
    if yol.exists():
        try:
            return json.loads(yol.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    adaylar = []
    for dil in ("tr", "en"):
        try:
            j = requests.get(f"https://api.wikimedia.org/feed/v1/wikipedia/{dil}/onthisday/all/{gun.month:02d}/{gun.day:02d}",
                             headers={"User-Agent": "VideoHub/1.0 (kisisel arac)"}, timeout=25).json()
        except Exception:  # noqa: BLE001
            continue
        for tur in ("selected", "events", "births", "deaths"):
            for e in (j.get(tur) or [])[:60]:
                p = (e.get("pages") or [{}])[0]
                adaylar.append({"dil": dil, "tur": tur, "yil": e.get("year"), "metin": str(e.get("text") or "")[:220],
                                "sayfa": p.get("titles", {}).get("normalized") or p.get("title", ""),
                                "url": ((p.get("content_urls") or {}).get("desktop") or {}).get("page", "")})
    if not adaylar:
        return []
    TUR = {"selected": "olay", "events": "olay", "births": "doğum", "deaths": "ölüm"}
    try:
        c = paylasim._claude_json(
            f"Bugün {gun.strftime('%d.%m.%Y')}. Aşağıda Wikipedia'nın 'bugün geçmişte' kayıtları var. Bu kişinin X hesabı için (futbol ve özellikle tuttuğu takım, "
            "reklam ve kampanyalar, tasarım, popüler kültür ve sinema/müzik, teknoloji ve internet tarihi, toplum) bugün hatırlatmaya değer EN ÇOK 3 kayıt seç. "
            "Ölçüt: takipçilerinin ilgisini çeker, ya gülümsetir ya 'bunu bilmiyordum' dedirtir, bugünün gündemine bir köprü kurulabilir. Savaş, felaket, siyasi "
            "şiddet seçme. Hiçbiri uymuyorsa boş liste.\n"
            'JSON: {"secilen": [{"no": 0, "alan": "' + __import__("paylasim").alan_kodlari(haric=("kendi_arac", "futbol_teknoloji")) + '", "neden": "tek cümle"}]}\n\n'
            + "\n".join(f"[{i}] ({TUR.get(a['tur'], a['tur'])}, {a['yil']}) {a['metin']}" for i, a in enumerate(adaylar[:300])), model_adi="sonnet", zaman_asimi=180)
    except Exception as e:  # noqa: BLE001
        log(f"Arşiv seçilemedi: {e}"); return []
    out = []
    for s in c.get("secilen") or []:
        try:
            a = adaylar[int(s.get("no"))]
        except (TypeError, ValueError, IndexError):
            continue
        yil = a.get("yil")
        out.append({"alan": s.get("alan") if s.get("alan") in KAYNAKLAR else "hikaye", "kaynak": "Bugün geçmişte (Wikipedia)",
                    "baslik": f"Bugün, {yil}: {a['metin'][:160]}", "ozet": f"{a['metin']} ({TUR.get(a['tur'], a['tur'])}; {a['sayfa']})", "link": a["url"],
                    "zaman": time.time(), "resim": "", "arsiv": {"yil": yil, "neden": str(s.get("neden") or "")[:200]},
                    "olay_tarihi": str(yil) if yil else ""})
    yol.write_text(json.dumps(out[:3], ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"Bugün geçmişte: {len(out[:3])} kayıt")
    return out[:3]


YAYIN_KULLANILAN = KESIF / "yayin_kullanilan.json"


def yayin_konulari(log=print, saat=60):
    """Takip edilen yayınlardan (kullanıcının dinlediği podcast ve YouTube yayınları) KONU keşfi (24 Ekim, kullanıcının editoryal yöntemi 6):
    'yayında konu keşfet → konuşulan özgün işi bul → onu incele → ayrı bir gözlem geliştir'. Konuşmacının yorumu ALINMAZ; yalnız konuşulan somut iş
    (ürün, kampanya, araştırma, olay) ve onu bulacak arama. Her konu için haber araması yapılır, bulunan haber keşfin normal maddesi olur
    (açı elemesi, asıl kaynak, görsel denetimi aynen uygulanır). Bir bölüm bir kez kullanılır."""
    import paylasim
    from transkript import paragrafla
    try:
        kul = set(json.loads(YAYIN_KULLANILAN.read_text(encoding="utf-8")))
    except Exception:  # noqa: BLE001
        kul = set()
    bolumler = []
    for js in KLASOR.glob("transkript_*.json"):
        if js.stat().st_mtime < time.time() - saat * 3600 or js.stem in kul:
            continue
        try:
            d = json.loads(js.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        v = d["veri"]
        if not v.get("takip") or v.get("toplanti"):
            continue
        metin = "\n".join(f"{p['ad']}: {p['metin']}" for p in paragrafla(d["segmentler"], v.get("etiket") or {}))
        bolumler.append((js.stem, v, metin))
    if not bolumler:
        return []
    maddeler = []
    for temel, v, metin in bolumler[:3]:
        try:
            c = paylasim._claude_json(
                "Aşağıda bir YouTube yayınının (sohbet/haber programı) dökümü var. Görevin: yayında konuşulan SOMUT işleri listelemek (ürün, model, kampanya, "
                "araştırma, şirket kararı, olay, oyun, eser; adıyla). Sunucuların YORUMLARINI ve görüşlerini ALMA; yalnızca neyin konuşulduğunu. Her konu için "
                "asıl kaynağı (şirketin açıklaması, haber, proje sayfası) bulacak kısa bir haber araması yaz (2-6 kelime; İngilizce konularda İngilizce). En çok 6 "
                "konu, en somut ve en yeni olanlar.\n"
                'JSON: {"konular": [{"nesne": "...", "arama": "...", "dil": "en", "alan": "' + __import__("paylasim").alan_kodlari(haric=("kendi_arac", "futbol_teknoloji")) + '"}]}\n\n'
                f"YAYIN: {v.get('baslik', '')} ({v.get('kanal', '')})\nDÖKÜM:\n{metin[:14000]}", model_adi="sonnet", zaman_asimi=180)
        except Exception as e:  # noqa: BLE001
            log(f"Yayın konuları çıkarılamadı ({v.get('baslik', '')[:40]}): {e}"); continue
        program = f"{v.get('kanal') or ''} · {v.get('baslik', '')[:60]}"
        for k in (c.get("konular") or [])[:6]:
            q = str(k.get("arama") or "").strip()
            if not q:
                continue
            dil = "en" if k.get("dil") == "en" else "tr"
            try:
                L = _akis(k.get("alan") or "teknoloji_ai", "Yayından keşif", _gn(q, dil, "7d"), saat=24 * 7)
            except Exception:  # noqa: BLE001
                L = []
            if L:
                m = L[0]
                m["kesif_yayin"] = program; m["nesne"] = str(k.get("nesne") or "")[:200]
                if k.get("alan") in KAYNAKLAR:
                    m["alan"] = k["alan"]
                maddeler.append(m)
        kul.add(temel)
    YAYIN_KULLANILAN.write_text(json.dumps(sorted(kul)[-200:], ensure_ascii=False), encoding="utf-8")
    log(f"Yayınlardan konu keşfi: {len(bolumler[:3])} bölüm → {len(maddeler)} konu haberi")
    return maddeler


def calistir(log=print, yaz=True, geri_bildirim="", toplanti="", hemen=False):
    """Günün keşfi: topla → seç → (story görselleri) → X/LinkedIn taslaklarını yaz. Döner: kayıt sözlüğü.
    toplanti: 'sabah' | 'ogle' | 'elle' ise (ve ayar ghost_konu_toplantisi açıksa) yazım konu toplantısını bekler (konu_toplantisi.py); hemen=True bekletmez."""
    KESIF.mkdir(parents=True, exist_ok=True)
    gun = date.today().isoformat()
    # Günün gündemi gece 00.00'dan başlar (kullanıcı, 22 Ekim: "son 24 saat değil, her günün gündemi; eski kalmasın"). Sabah taraması 00.00'dan beri
    # 60 maddeden azını bulursa yalnızca dün akşam 18.00'e kadar geri gider (gece yayın yapmayan Türkçe kaynaklar için).
    gece = datetime.combine(date.today(), datetime.min.time()).timestamp()
    tum = topla(baslangic=gece - 6 * 3600)
    maddeler = [m for m in tum if (m.get("zaman") or 0) >= gece]
    pencere = "00.00"
    if len(maddeler) < 60:
        maddeler, pencere = tum, "dün 18.00"
    log(f"Gündem penceresi: {pencere}'dan beri, {len(maddeler)} madde")
    try:
        maddeler = maddeler + yayin_konulari(log)
        try:
            import bultenler
            if _ayar_acik("bultenler"):                    # Mail'deki bültenler; yeni kurulumlarda kapalı
                maddeler = maddeler + bultenler.konular(log)
        except Exception as e:  # noqa: BLE001
            log(f"Bülten keşfi yapılamadı ({e})")
    except Exception as e:  # noqa: BLE001
        log(f"Yayın konuları alınamadı: {e}")
    try:                                                   # Kantan.News küratörlüğü (kantan.py; kullanıcının beğendiği seçki, asıl kaynak bağlantısıyla)
        import kantan
        if _ayar_acik("kantan"):                           # yeni kurulumlarda kapalı (ayarlar.ornek.json); Türkçe seçki
            maddeler = maddeler + kantan.maddeler(log)
    except Exception as e:  # noqa: BLE001
        log(f"Kantan.News okunamadı: {e}")
    try:                                                   # bugün geçmişte (Wikipedia), günde bir kez
        maddeler = maddeler + arsiv_maddeleri(log)
    except Exception as e:  # noqa: BLE001
        log(f"Arşiv alınamadı: {e}")
    try:                                                   # izlenen X hesaplarının paylaştıkları (hesaplar.py; uzantı listeyi açınca okur)
        import hesaplar
        hm = [m for m in hesaplar.kesif_maddeleri() if (m.get("zaman") or 0) >= gece - 18 * 3600]
        maddeler = maddeler + hm
        log(f"İzlenen hesaplardan {len(hm)} gönderi")
    except Exception as e:  # noqa: BLE001
        log(f"İzlenen hesaplar alınamadı: {e}")
    try:                                                   # görüş defteri → fikir kartları: bugün hangi görüşü hangi haber çağırıyor
        import fikir_kartlari
        fikir_kartlari.eslestir(maddeler, log)
    except Exception as e:  # noqa: BLE001
        log(f"Fikir kartları eşleştirilemedi: {e}")
    oneriler = sec(maddeler, log, geri_bildirim)
    for o in oneriler:
        o["link"] = gn_coz(o["link"])
    try:
        storyler = story_sec(log)
    except Exception as e:  # noqa: BLE001
        storyler = []; log(f"Story seçilemedi: {e}")
    with ThreadPoolExecutor(6) as h:
        resimler = list(h.map(lambda o: _resim_bul(o) if o["platform"] == "story" else o.get("resim", ""), oneriler))
    for o, r in zip(oneriler, resimler):
        o["resim"] = r
        o["alan_ad"] = _alan_adi(o["alan"])
        o["id"] = re.sub(r"\W+", "", o["baslik"].lower())[:40] + "_" + o["platform"]
    oneriler += storyler
    yol = KESIF / f"{gun}.json"
    eski = {}
    if yol.exists():
        try:
            eski = {o["id"]: o for o in json.loads(yol.read_text(encoding="utf-8")).get("oneriler") or []}
        except Exception:  # noqa: BLE001
            pass
    eski = {k: o for k, o in eski.items() if o.get("platform") != "story" or o.get("ig_kod")}   # haberden story artık yok (yalnız Instagram)
    birlesik = list(eski.values()) + [o for o in oneriler if o["id"] not in eski]
    elenen_eski = []
    if yol.exists():
        try:
            elenen_eski = json.loads(yol.read_text(encoding="utf-8")).get("elenen_acilar") or []
        except Exception:  # noqa: BLE001
            pass
    birlesik = [{k: v for k, v in o.items() if not k.startswith("_")} for o in birlesik]   # sayfa bağlantı/görsel listeleri kayda girmez
    kayit = {"tarih": gun, "zaman": time.time(), "madde": len(maddeler), "pencere": pencere, "oneriler": birlesik,
             "elenen_acilar": (elenen_eski + SON_ELENEN)[-80:]}
    yol.write_text(json.dumps(kayit, ensure_ascii=False, indent=1), encoding="utf-8")
    if yaz:
        xh = [o for o in oneriler if o["platform"] == "x" and o.get("ayrinti")]
        if toplanti and not hemen and _ayar_acik("ghost_konu_toplantisi"):
            try:
                import konu_toplantisi
                if toplanti != "elle" and not konu_toplantisi.kullaniliyor():
                    log("Konu toplantısı atlandı: son toplantılarda hiç karar verilmedi; doğrudan yazılıyor")
                    __import__("ghost_tempo").atlandi("konu toplantısı", "son toplantılara dokunulmadı")
                elif konu_toplantisi.hazirla(maddeler, xh, birlesik, toplanti, log=log):
                    return kayit
            except Exception as e:  # noqa: BLE001
                log(f"Konu toplantısı kurulamadı, doğrudan yazılıyor: {e}")
        yazim_turu(maddeler, xh, birlesik, log=log)
    return kayit


def _ayar_acik(ad, varsayilan=True):
    try:
        return bool(json.loads((KLASOR / "ayarlar.json").read_text(encoding="utf-8")).get(ad, varsayilan))
    except Exception:  # noqa: BLE001
        return varsayilan


def yazim_turu(maddeler, haberler, birlesik, log=print, gorus_cevaplari=None):
    """Keşif turunun yazım yarısı: günün karışımı (X) + budama + LinkedIn taslakları. Konu toplantısı bitince de buradan yazılır."""
    gun = date.today().isoformat()
    if True:
        def _taslaksiz(o):
            if not o.get("temel"):
                return True
            try:
                return not (json.loads((KLASOR / "ghost" / f"{o['temel'][7:]}.json").read_text(encoding="utf-8"))["veri"].get("paylasim"))
            except Exception:  # noqa: BLE001
                return True
        # X: günün karışımı (karisim.py, 23 Ekim; kullanıcı: "günde 10-15 öneri, haber yorumlayan program havası olmasın"). Haberler karışımın yalnız bir
        # türü; açı elemesinden geçenler malzeme olur. LinkedIn eskisi gibi tek tek.
        try:
            import karisim
            import paylasim as _p
            import ghost_tempo
            profil_gunluk = int((_p.profil().get("hedef") or {}).get("x_gunluk") or 14)
            gunluk = ghost_tempo.gunluk_hedef(profil_gunluk)   # 27 Ekim: bakılmayan günlerde daha az (döndüğünde yeniden profildeki değer)
            if gunluk < profil_gunluk:
                log(f"Tempo: son günlerde önerilere {'bakılmadı' if ghost_tempo.durum()['mod'] == 'uzakta' else 'dokunulmadı'}; bugün {gunluk} öneri (profilde {profil_gunluk})")
            acik = karisim.acik_sayisi()
            # İlk turda günlük hedef kadar; sonraki turlarda eksik kadar + 3 aday daha yazılır, sonra günün en zayıf (dokunulmamış) taslakları bunlarla
            # DEĞİŞTİRİLİR (budama). Böylece öğleden sonra yeni bir paket değil, daha güçlü bir gün olur.
            karisim.calistir(maddeler, haberler,
                             hedef=max(4, min(14, gunluk - acik)) if not acik else max(3, min(14, gunluk - acik + 3)), log=log,
                             gorus_cevaplari=gorus_cevaplari or {})
            karisim.budama(gunluk, log=log)
        except Exception as e:  # noqa: BLE001
            log(f"Günün karışımı yazılamadı: {e}")
        if not __import__("ghost_tempo").yan_isler_uygun():
            __import__("ghost_tempo").atlandi("LinkedIn", "iki gündür bakılmadı"); birlesik = [o for o in birlesik if o["platform"] != "linkedin"]
        for o in [o for o in birlesik if o["platform"] == "linkedin" and _taslaksiz(o)]:
            try:
                taslak_yaz(gun, o["id"], log=log)
            except Exception as e:  # noqa: BLE001
                log(f"Keşif taslağı yazılamadı ({o['baslik'][:50]}): {e}")


def _bul(gun, oid):
    yol = KESIF / f"{gun}.json"
    k = json.loads(yol.read_text(encoding="utf-8"))
    return yol, k, next((o for o in k["oneriler"] if o["id"] == oid), None)


def taslak_yaz(gun, oid, yorum="", log=print):
    """Öneri → ghost kaydı + taslak (X ya da LinkedIn). yorum: kullanıcının kendi açısı (merkeze alınır)."""
    import paylasim
    yol, k, o = _bul(gun, oid)
    if not o:
        raise ValueError("Öneri bulunamadı")
    girdi = (f"HABER/İÇERİK ({o['kaynak']}): {o['baslik']}\n{o.get('ozet', '')}\nBAĞLANTI: {o['link']}\n"
             f"EDİTÖRÜN NOTU (neden bu kişi için ilginç): {o.get('neden', '')}\nÖNERİLEN AÇI (yalnız fikir; kişinin sesiyle yeniden kur): {o.get('aci', '')}\n"
             f"BARİZ YORUM (herkesin söyleyeceği; gönderi bunu SÖYLEMEMELİ): {o.get('bariz', '')}\n"
             + (f"AÇININ DAYANDIĞI SOMUT AYRINTI (gönderi bunun üstüne kurulur; ayrıntıyı adıyla an): {o['ayrinti']}\n" if o.get("ayrinti") else "")
             + (f"HABERİN METNİNDEN (olgular yalnızca buradan):\n{o['metin_ozu'][:3000]}\n" if o.get("metin_ozu") else "")
             + (f"KÖPRÜ: {o['kopru']}\n" if o.get("kopru") else "")
             + ("AYNI HİKÂYEYİ YAZAN DİĞER KAYNAKLAR (herkes bunu söylüyor; bunları TEKRAR ETME, farklı bir açı bul):\n" + "\n".join(f"- {b}" for b in o["benzer"][:6]) + "\n"
                if o.get("benzer") else "")
             + (f"BU HİKÂYE {o['hikaye_gun']}. GÜNÜNDE: haberi yeniden anlatma; gelişmeye ya da ikinci derece sonucuna odaklan.\n" if (o.get("hikaye_gun") or 1) > 1 else ""))
    if yorum.strip():
        girdi += f"\nKİŞİNİN KENDİ KARŞILIĞI (gönderinin merkezi bu; olduğu gibi kullan, büyütme):\n{yorum.strip()}\n"
    temel = paylasim.ghost_kaydi(girdi, "kesif", o["baslik"], o["link"], girdi, deneyim=yorum,
                                 ek={"gundem": {"kaynak_sayisi": o.get("kaynak_sayisi", 1), "gun": o.get("hikaye_gun", 1), "trend": o.get("trend", "")},
                                     "platform": o["platform"], "bicim": o.get("bicim", ""), "ton": o.get("ton", ""), "alan_kod": o["alan"], "alan_ad": o.get("alan_ad", ""), "kesif": f"{gun}:{oid}"})
    o["temel"] = temel; o["yorum"] = bool(yorum.strip())
    yol.write_text(json.dumps(k, ensure_ascii=False, indent=1), encoding="utf-8")
    paylasim.uret(KLASOR / "ghost" / f"{temel[7:]}.json", log=log)
    return temel


def story_isaretle(gun, oid, paylasildi=True, gizli=False, neden=""):
    yol, k, o = _bul(gun, oid)
    if o:
        if paylasildi and not o.get("paylasildi"):
            o["paylasildi"] = time.time()
            if o.get("ig_kod"):
                story_ogren("paylasilan", o)
        elif not paylasildi:
            o.pop("paylasildi", None)          # "Geri al" (eskiden hiçbir şeyi geri almıyordu)
        if not gizli:
            o.pop("gizli", None)
        if gizli:
            o["gizli"] = True
            if neden:
                o["red_nedeni"] = neden
            if o.get("ig_kod") and neden:
                story_ogren("red", o, neden)
        yol.write_text(json.dumps(k, ensure_ascii=False, indent=1), encoding="utf-8")


def story_ogren(tur, o, neden=""):
    """Story tercihleri profilde: 'story_red' (reddedilenler, nedeniyle) ve 'story_paylasilan'; her story seçimine örnek olarak girer."""
    import paylasim
    pr = paylasim.profil()
    anahtar = "story_red" if tur == "red" else "story_paylasilan"
    L = [x for x in pr.get(anahtar) or [] if isinstance(x, dict)]
    L.append({"yazar": o.get("yazar", ""), "gonderi": str(o.get("baslik") or "")[:160], "yazi": o.get("story_yazi", ""), "neden": neden, "tarih": time.strftime("%Y-%m-%d")})
    paylasim.profil_kaydet(**{anahtar: L[-30:]})


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "topla":
        L = topla()
        print(len(L), {a: sum(1 for x in L if x["alan"] == a) for a in KAYNAKLAR})
    else:
        r = calistir(yaz="--yazma" not in sys.argv)
        for o in r["oneriler"]:
            print(o["platform"], o["alan"], "|", o["baslik"][:80], "|", o.get("aci", "")[:100])


# ---------------------------------------------------------------- kaynağın X'teki gönderisi (2026-10-22; kullanıcı: "dış link veriyorsan, X içinde ana kaynak
# linki bulabiliyorsan onu da öner; belki dış linkle değil alıntılayarak atmayı tercih ederim"). Yalnızca okuma: haber sayfasına gömülü X gönderileri +
# sayfanın X hesabı (twitter:site/creator); gönderi metni X'in herkese açık gömme servisinden (publish.twitter.com/oembed, giriş yok).
_UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129 Safari/537.36"}


def x_gonderisi(url):
    """Herkese açık X gönderisinin metni (oEmbed). Döner: {id, url, kullanici, ad, metin} ya da None."""
    import html as _h
    m = re.search(r"(?:twitter|x)\.com/([A-Za-z0-9_]{1,15})/status(?:es)?/(\d{8,20})", url or "")
    if not m:
        return None
    try:
        r = requests.get("https://publish.twitter.com/oembed", params={"url": f"https://twitter.com/{m.group(1)}/status/{m.group(2)}", "omit_script": "1"},
                         headers=_UA, timeout=12)
        if r.status_code != 200:
            return None
        j = r.json()
        p = re.search(r"<p[^>]*>(.*?)</p>", j.get("html") or "", re.S)
        metin = _h.unescape(re.sub(r"<br\s*/?>", "\n", p.group(1)) if p else "")
        metin = re.sub(r"<[^>]+>", "", metin).strip()
        return {"id": m.group(2), "url": f"https://x.com/{m.group(1)}/status/{m.group(2)}", "kullanici": m.group(1),
                "ad": j.get("author_name") or m.group(1), "metin": metin[:600]}
    except Exception:  # noqa: BLE001
        return None


def x_kaynak(link, baslik=""):
    """Bağlantının X'teki karşılığı: sayfaya gömülü gönderiler (alıntılanabilir) ve yayıncı hesabında arama bağlantısı."""
    out = {"gonderiler": [], "hesap": "", "arama": "", "zaman": time.time()}
    if not str(link or "").startswith("http") or re.search(r"(?:twitter|x)\.com/", link):
        return out
    try:
        t = requests.get(link, headers=_UA, timeout=15).text
    except Exception:  # noqa: BLE001
        t = ""
    durumlar = list(dict.fromkeys(f"https://x.com/{u}/status/{i}" for u, i in
                                  re.findall(r"(?:twitter|x)\.com/([A-Za-z0-9_]{1,15})/status(?:es)?/(\d{8,20})", t) if u.lower() not in ("intent", "share", "i")))[:3]
    out["gonderiler"] = [g for g in (x_gonderisi(u) for u in durumlar) if g and g["metin"]]
    hesap = []                                           # önce yayıncı (twitter:site), yoksa yazar (twitter:creator)
    for ad in ("site", "creator"):
        hesap += (re.findall(r'<meta[^>]+(?:name|property)=["\']twitter:' + ad + r'["\'][^>]*content=["\']@?([A-Za-z0-9_]{1,15})', t)
                  + re.findall(r'content=["\']@?([A-Za-z0-9_]{1,15})["\'][^>]*(?:name|property)=["\']twitter:' + ad + r'["\']', t))
    if hesap and hesap[0].lower() in ("youtube", "tiktok", "instagram", "vimeo", "spotify", "twitter", "x", "facebook", "linkedin"):
        hesap = []                                       # platformun kendi hesabı; haberin yayıncısı değil
    if hesap:
        out["hesap"] = hesap[0]
        ara = " ".join([w for w in re.findall(r"[\wçğıöşüÇĞİÖŞÜ'’]+", baslik or "") if len(w) > 3][:4])
        out["arama"] = f"https://x.com/search?q={requests.utils.quote(('from:' + hesap[0] + ' ' + ara).strip())}&f=live"
    return out
