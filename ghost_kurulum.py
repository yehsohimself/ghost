"""ghost_kurulum.py - Ghost'un ilk açılışı ve kaynak düzenleme (2026-10-29; Ghost herkese açık depo olarak çıkarken, kullanıcı: "kişiler kendilerine
göre kişiselleştirebilsin, diğer türlü bana özel gibi olur").

Kurulum bir kez: X kullanıcı adı, yazı dili, kendini bir cümleyle anlatma, yazmak istediği konular, kendi gönderilerinden örnekler, kaçınacağı
konular → tek Claude (opus) çağrısı profil/x.json'u (kimlik, tarz, persona, alanlar, kaçınılacaklar) ve profil/kaynaklar.json'u (her alan için RSS
akışları ve Google Haberler aramaları) yazar. Akışlar tek tek okunur; okunamayan atılır, kaynağı az kalan alana Google Haberler araması eklenir.
Sonradan: Profil → Kaynaklar'dan kaynak ekle/çıkar, yeni konu ekle (konu için kaynakları Claude önerir, aynı denetimden geçer).

Elle: python ghost_kurulum.py durum | kaynaklar
"""
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
PROFIL = KLASOR / "profil" / "x.json"
KAYNAK = KLASOR / "profil" / "kaynaklar.json"
DILLER = {"tr": "Türkçe", "en": "English", "de": "Deutsch", "es": "Español", "fr": "Français", "it": "Italiano", "pt": "Português", "nl": "Nederlands"}
BOLGE = {"tr": "TR", "en": "US", "de": "DE", "es": "ES", "fr": "FR", "it": "IT", "pt": "BR", "nl": "NL"}


def _oku(yol, bos):
    try:
        return json.loads(yol.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return bos


def _yaz(yol, veri):
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_suffix(".json.tmp")
    gecici.write_text(json.dumps(veri, ensure_ascii=False, indent=1), encoding="utf-8")
    gecici.replace(yol)


def kurulu_mu():
    p = _oku(PROFIL, {})
    return bool(p.get("alanlar")) and bool(p.get("kimlik") or p.get("ornekler") or p.get("persona"))


def okunan_gonderiler():
    """Chrome uzantısının X profilinden okuduğu kendi gönderileri (performans.py, profil/x_istatistik.json), kurulumda örnek olarak önerilir."""
    d = _oku(KLASOR / "profil" / "x_istatistik.json", {})
    L = sorted((x for x in (d.values() if isinstance(d, dict) else d) if isinstance(x, dict)), key=lambda x: str(x.get("tarih") or ""), reverse=True)
    out = [str(x.get("metin") or "").strip() for x in L if len(str(x.get("metin") or "").strip()) > 25]
    return list(dict.fromkeys(out))[:60]


def durum():
    p = _oku(PROFIL, {})
    return {"kurulu": kurulu_mu(), "kullanici": p.get("kullanici") or "", "dil": p.get("dil") or "tr", "okunan": len(okunan_gonderiler()),
            "diller": DILLER}


def _ornekler(metin_ya_da_liste):
    if isinstance(metin_ya_da_liste, list):
        L = metin_ya_da_liste
    else:
        L = re.split(r"\n\s*(?:---+\s*)?\n", str(metin_ya_da_liste or ""))
    return [x.strip() for x in L if len(x.strip()) > 15][:60]


KUR_ISTEM = """Bir kişinin X (Twitter) hesabı için gönderi taslağı yazacak bir asistanı kuruyorsun. Asistan her gün kişinin konularındaki yayınları
okur, paylaşmaya değer bir ayrıntı bulur ve kişinin KENDİ sesiyle taslak yazar; kişi düzeltir, paylaşır ya da reddeder, asistan öğrenir.

KİŞİ: {kim}
X HESABI: @{kullanici}
YAZDIĞI DİL: {dil_ad}
YAZMAK İSTEDİĞİ KONULAR: {konular}
KAÇINDIĞI KONULAR: {kacin}

KENDİ GÖNDERİLERİNDEN ÖRNEKLER ({n} adet):
{ornekler}

İSTENEN (yalnızca JSON):
{{"kimlik": "kim olduğu, ne iş yaptığı, kime yazdığı; 2-3 cümle, yalnız verilenlerden",
 "tarz": "örneklerden gözlenen yazı tarzı: uzunluk, açılışlar, ton, mizah, sözcük seçimi, neyi yapmaz; 5-8 cümle. Örnek yoksa kişinin anlatımından kısa ve temkinli",
 "persona": {{"karakter": "olmak istediği ses, tek cümle", "merkez": "sesin merkezi: neyi nasıl söyler, tek cümle", "ilkeler": ["5-8 somut yazı ilkesi, örneklere dayanarak"]}},
 "alanlar": [{{"kod": "kisa_ascii_kod", "ad": "konunun adı ({dil_ad})", "agirlik": 1-3, "not": "bu konuda neyle ilgilenir, hangi açıdan bakar, neyi sıkıcı bulur; 1-3 cümle"}}],
 "kacin": ["kaçınılacak konu ya da tavır"],
 "kaynaklar": {{"<alan kodu>": [{{"ad": "yayın adı", "url": "RSS ya da Atom akış adresi", "derin": true}}, {{"ad": "arama adı", "sorgu": "Google Haberler araması", "dil": "en"}}]}},
 "trend": ["Google Trends bölge kodu, en çok 2 (ör. US, GB, DE, TR)"]}}

KURALLAR:
- Alanlar kişinin verdiği konulardan (3-8 alan); birbirinin aynısı olanları birleştir. Ağırlık: en çok yazmak istediği 3, ikincil 1-2.
- Her alan için 5-8 kaynak. ÖNCE gerçekten var olan ve RSS akışı bilinen yayınlar (dergiler, uzun okuma, analiz, bültenlerin Substack akışları,
  uzman blogları); her biri için bildiğin akış adresini yaz (ör. https://www.theverge.com/rss/index.xml, https://<ad>.substack.com/feed). Emin
  olmadığın adresi uydurma; onun yerine 'sorgu' (Google Haberler araması) kullan. Her alana en az bir 'sorgu' koy.
- 'derin': analiz, uzun okuma, yapı/karar anlatan yayınsa true; günlük haber akışıysa false. Günlük gündemden çok derin kaynak seç.
- Kaynakların dili kişinin dili ve İngilizce olabilir; kişinin ülkesine uygun yerel yayınlar ekle.
- Tarz ve ilkeler örneklerdeki GERÇEK alışkanlıkları söyler; genel 'net ve özgün yaz' cümleleri yazma. Örneklerdeki birinci şahıs deneyimi
  ('bu sabah denedim') ilke yapma: asistan kişinin yaşamadığı deneyimi yazamaz; bunun yerine kişinin neye dikkat ettiğini söyle. Kişi hakkında verilmeyen bilgi uydurma
  (unvan, şehir, yıl yok).
- İnsanlar okuyacak metinleri (kimlik, tarz, persona, alan adları ve notları) {dil_ad} yaz."""


def _akis_dene(alan, k):
    """Akış okunuyor mu? (kesif._akis, son 60 gün). Google Haberler araması her zaman geçerli sayılır."""
    import kesif
    if k.get("sorgu"):
        return True
    url = str(k.get("url") or "")
    if not url.startswith("http"):
        return False
    kesif._akis(alan, k.get("ad") or url, url, saat=24 * 60)
    return bool((kesif.SAGLIK.get(url) or {}).get("ok"))


def kaynaklari_denetle(kaynaklar, dil="en", log=print):
    """{alan: [kaynak]} → çalışanlar; kaynağı 2'den az kalan alana alan adıyla Google Haberler araması eklenir. Döner (temiz, atılanlar)."""
    isler = [(a, k) for a, L in kaynaklar.items() for k in (L if isinstance(L, list) else []) if isinstance(k, dict) and k.get("ad")]
    with ThreadPoolExecutor(8) as h:
        sonuc = list(h.map(lambda x: _akis_dene(*x), isler))
    temiz, atilan = {}, []
    for (a, k), ok in zip(isler, sonuc):
        if ok:
            temiz.setdefault(a, []).append({x: k[x] for x in ("ad", "url", "sorgu", "dil", "derin") if k.get(x) not in (None, "")})
        else:
            atilan.append(f"{k.get('ad')} ({a})")
    log(f"Kaynaklar: {sum(len(v) for v in temiz.values())} çalışıyor, {len(atilan)} okunamadı")
    return temiz, atilan


def kur(girdi, log=print):
    """girdi: {kullanici, dil, kim, ornekler (metin ya da liste), okunanlari_kullan, konular (liste ya da virgüllü), kacin}."""
    import claude_yaz
    dil = str(girdi.get("dil") or "tr")[:2]
    dil = dil if dil in DILLER else "en"
    ornekler = _ornekler(girdi.get("ornekler") or "")
    if girdi.get("okunanlari_kullan"):
        ornekler = list(dict.fromkeys(ornekler + okunan_gonderiler()))[:60]
    konular = girdi.get("konular") or []
    konular = [str(x).strip() for x in (konular if isinstance(konular, list) else str(konular).split(",")) if str(x).strip()][:12]
    if not konular:
        raise ValueError("En az bir konu seçin")
    kullanici = re.sub(r"[^A-Za-z0-9_]", "", str(girdi.get("kullanici") or ""))[:30]
    istem = KUR_ISTEM.format(kim=str(girdi.get("kim") or "(anlatmadı)")[:600], kullanici=kullanici or "-", dil_ad=DILLER[dil],
                             konular=", ".join(konular), kacin=str(girdi.get("kacin") or "-")[:400], n=len(ornekler),
                             ornekler="\n---\n".join(o[:600] for o in ornekler[:40]) or "(örnek yok)")
    log("Profil yazılıyor (Claude)")
    with claude_yaz.yazi_dili(None):                         # istem kendi içinde dili söylüyor
        j = claude_yaz.sor_json(istem, model_adi="opus", zaman_asimi=600)
    if not isinstance(j, dict) or not j.get("alanlar"):
        raise RuntimeError("Profil yazılamadı; yeniden deneyin")
    alanlar = []
    for a in j.get("alanlar") or []:
        kod = re.sub(r"[^a-z0-9_]", "", str(a.get("kod") or "").lower())[:30]
        if kod and kod not in [x["kod"] for x in alanlar]:
            alanlar.append({"kod": kod, "ad": str(a.get("ad") or kod)[:60], "agirlik": max(1, min(3, int(a.get("agirlik") or 2))), "not": str(a.get("not") or "")[:600]})
    kods = {a["kod"] for a in alanlar}
    temiz, atilan = kaynaklari_denetle({k: v for k, v in (j.get("kaynaklar") or {}).items() if k in kods}, dil, log)
    for a in alanlar:                                        # az kaynaklı alana arama
        if len(temiz.get(a["kod"], [])) < 2:
            temiz.setdefault(a["kod"], []).append({"ad": a["ad"], "sorgu": a["ad"], "dil": dil})
    eski = _oku(PROFIL, {})
    p = {k: v for k, v in eski.items() if k in ("paylasilan", "reddedilen", "begenilen", "takip_otomatik", "her_video")}
    p.update({"kullanici": kullanici, "dil": dil, "kimlik": str(j.get("kimlik") or "")[:1200], "tarz": str(j.get("tarz") or "")[:2000],
              "persona": j.get("persona") if isinstance(j.get("persona"), dict) else {}, "alanlar": alanlar,
              "kacin": [str(x)[:200] for x in j.get("kacin") or []][:12], "ornekler": ornekler[:20], "kurulum": {"zaman": time.time(), "konular": konular}})
    _yaz(PROFIL, p)
    trend = [str(x).upper()[:2] for x in j.get("trend") or [] if re.fullmatch(r"[A-Za-z]{2}", str(x))][:2] or [BOLGE.get(dil, "US")]
    _yaz(KAYNAK, {"alanlar": temiz, "trend": trend})
    if len(ornekler) >= 5:                                   # görüş defteri: kişinin gönderilerinde açıkça savunduğu görüşler (yeni gönderiler tutarlı kalsın)
        try:
            import paylasim
            g = paylasim.gorus_defteri_kur(log=lambda *_: None)
            log(f"Görüş defteri: {len(g)} görüş")
        except Exception as e:  # noqa: BLE001
            log(f"Görüş defteri kurulamadı ({e})")
    log(f"Kuruldu: {len(alanlar)} konu, {sum(len(v) for v in temiz.values())} kaynak")
    return {"alanlar": [{"kod": a["kod"], "ad": a["ad"], "kaynak": len(temiz.get(a["kod"], []))} for a in alanlar], "atilan": atilan}


# ----------------------------------------------------------------------------- kaynak düzenleme (Profil → Kaynaklar)
def _yerlesik():
    """profil/kaynaklar.json yoksa (kurulumdan önceki kurulumlar) yerleşik liste dosya biçiminde."""
    import kesif
    return {"alanlar": {a: [{"ad": k, "url": u, **({"derin": True} if k in kesif.DERIN else {})} for k, u in L] for a, L in kesif.KAYNAKLAR.items()},
            "trend": ["TR", "DE"]}


def kaynaklar():
    """Arayüz için: alanlar (profil adlarıyla) ve her alanın kaynakları + son taramadaki sağlık."""
    import paylasim
    d = _oku(KAYNAK, None) or _yerlesik()
    saglik = _oku(KLASOR / "kayitlar" / "kesif" / "saglik.json", {}).get("kaynaklar") or {}
    durum_ad = {}
    for v in saglik.values():
        durum_ad[v.get("kaynak")] = bool(v.get("ok"))
    adlar = {a.get("kod"): a.get("ad") for a in paylasim.profil().get("alanlar") or [] if isinstance(a, dict)}
    out = []
    for kod, L in d.get("alanlar", {}).items():
        out.append({"kod": kod, "ad": adlar.get(kod) or kod, "kaynaklar": [{**k, "tur": "arama" if k.get("sorgu") else "akis", "ok": durum_ad.get(k.get("ad"))} for k in L]})
    for kod, ad in adlar.items():
        if kod and kod not in d.get("alanlar", {}):
            out.append({"kod": kod, "ad": ad, "kaynaklar": []})
    return {"alanlar": out, "trend": d.get("trend") or [], "dosya": KAYNAK.exists()}


def kaynak_ekle(alan, ad="", url="", sorgu="", dil="en"):
    d = _oku(KAYNAK, None) or _yerlesik()
    alan = str(alan)
    k = {"ad": (ad or sorgu or url)[:80]}
    if sorgu:
        k.update({"sorgu": sorgu[:200], "dil": dil[:2]})
    else:
        if not re.match(r"https?://", url or ""):
            raise ValueError("Akış adresi http ile başlamalı")
        k["url"] = url.strip()
        if not _akis_dene(alan, k):
            raise ValueError("Bu adreste okunabilir bir RSS ya da Atom akışı yok")
        if not ad:
            k["ad"] = _akis_adi(k["url"]) or k["ad"]
    L = d.setdefault("alanlar", {}).setdefault(alan, [])
    if any(x.get("ad") == k["ad"] for x in L):
        raise ValueError("Bu adla bir kaynak zaten var")
    L.append(k)
    _yaz(KAYNAK, d)
    return k


def _akis_adi(url):
    """Akışın kendi başlığı (RSS channel/title ya da Atom feed/title)."""
    import requests
    import xml.etree.ElementTree as ET
    try:
        kok = ET.fromstring(requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15).content.lstrip())
        t = kok.findtext("channel/title") or kok.findtext("{http://www.w3.org/2005/Atom}title") or ""
        return re.sub(r"\s+", " ", t).strip()[:80]
    except Exception:  # noqa: BLE001
        return ""


def kaynak_sil(alan, ad):
    d = _oku(KAYNAK, None) or _yerlesik()
    L = d.get("alanlar", {}).get(alan) or []
    d["alanlar"][alan] = [x for x in L if x.get("ad") != ad]
    _yaz(KAYNAK, d)


ALAN_ISTEM = """Bir kişinin X hesabına yeni bir konu ekleniyor. Kişi: {kimlik}
YENİ KONU: {konu}
Bu konu için 5-8 kaynak öner: önce RSS akışı bilinen gerçek yayınlar (analiz, uzun okuma, uzman blogları, Substack bültenleri), en az bir Google
Haberler araması. Emin olmadığın akış adresini uydurma, 'sorgu' kullan. Kaynak dilleri: {dil} ve İngilizce.
Yalnızca JSON: {{"kod": "kisa_ascii_kod", "ad": "konunun adı ({dil})", "not": "bu konuda neyle ilgilenir; kişinin anlatımına dayanarak 1-2 cümle",
"kaynaklar": [{{"ad": "...", "url": "...", "derin": true}}, {{"ad": "...", "sorgu": "...", "dil": "en"}}]}}"""


def alan_ekle(konu, log=print):
    import claude_yaz
    import paylasim
    pr = paylasim.profil()
    dil = pr.get("dil") or "tr"
    with claude_yaz.yazi_dili(None):
        j = claude_yaz.sor_json(ALAN_ISTEM.format(kimlik=pr.get("kimlik") or "-", konu=str(konu)[:200], dil=DILLER.get(dil, dil)), zaman_asimi=300)
    kod = re.sub(r"[^a-z0-9_]", "", str(j.get("kod") or "").lower())[:30] or f"konu{int(time.time()) % 10000}"
    p = _oku(PROFIL, {})
    if any(a.get("kod") == kod for a in p.get("alanlar") or []):
        kod += "2"
    p.setdefault("alanlar", []).append({"kod": kod, "ad": str(j.get("ad") or konu)[:60], "agirlik": 2, "not": str(j.get("not") or "")[:600]})
    _yaz(PROFIL, p)
    temiz, atilan = kaynaklari_denetle({kod: j.get("kaynaklar") or []}, dil, log)
    d = _oku(KAYNAK, None) or _yerlesik()
    d.setdefault("alanlar", {})[kod] = temiz.get(kod) or [{"ad": str(j.get("ad") or konu), "sorgu": str(konu), "dil": dil}]
    _yaz(KAYNAK, d)
    return {"kod": kod, "kaynak": len(d["alanlar"][kod]), "atilan": atilan}


def alan_sil(kod):
    p = _oku(PROFIL, {})
    p["alanlar"] = [a for a in p.get("alanlar") or [] if a.get("kod") != kod]
    _yaz(PROFIL, p)
    d = _oku(KAYNAK, None)
    if d:
        d.get("alanlar", {}).pop(kod, None)
        _yaz(KAYNAK, d)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "kaynaklar":
        print(json.dumps(kaynaklar(), ensure_ascii=False, indent=1))
    else:
        print(json.dumps(durum(), ensure_ascii=False, indent=1))
