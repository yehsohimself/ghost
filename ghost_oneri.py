"""ghost_oneri.py - dışarıdan gelen yazı önerileri (2026-10-31; kullanıcı: "ChatGPT/dot güçlü copywriting önerileri ve kaynaklı araştırma sağlayacak.
Bunlar nihai X taslağı olarak kilitlenmesin: içeriğin X, blog ya da başka bir formatta değerlendirilmesine Ghost karar versin ve son metni Ghost
hazırlasın. Gelen orijinal öneriyi değişmeden ayrı sakla; Ghost'un son sürümünü ve format kararını bununla ilişkilendir. Özgün kaynak URL'si, araştırma
notu, tarih ve üretici ayrı saklansın. Kaynak, açı ve tarih üzerinden tekrarları önle; kullanıcı düzeltmelerini asla ezme. Alınan öneriler kullanıcı
tarafından onaylanmış, seçilmiş ya da yayımlanmış sayılmasın; otomatik stil öğrenmesine katılmasın").

Kayıt: kayitlar/ghost_oneriler/<id>.json
  ozgun: {metin, baslik, not, arastirma_notu, kaynak_url, kaynaklar, tarih, uretici, kanal, ham_kimlik, kaynak_durum}  BİR KEZ yazılır; ozgun_sha ile korunur
  durum: geldi | yaziliyor | yazildi | elendi (Ghost yazdı, okur kapısından geçmedi) | gecildi | tekrar | hata
  karar: {format: x|zincir|linkedin|blog|gec, neden, uygunluk, zaman}
  surumler: [{zaman, format, temel?, blog?, aktif}]   Ghost'un son metni: x/zincir/linkedin → ghost/<id>.json kaydı (kaynak_tur 'dis_oneri'); blog → metin burada
  tekrar_of / benzer: tekrar ilişkisi

Kanallar (yeni bağlantı yok): (1) Drive'daki öneri havuzu tablosunun ZATEN var olan yerel kopyası kayitlar/secki/havuz.json (seckiler.havuz, salt okunur
rclone); (2) Ghost'ta "Gelen öneriler" kutusuna yapıştırma. Tablodaki "Durum" ya da "kişi beğenmiş" gibi notlar kullanıcı kararı SAYILMAZ: yalnız
kaynak_durum / arastirma_notu olarak saklanır.

Öğrenme ayrımı: orijinal öneri metni hiçbir öğrenmeye girmez; bu önerilerden çıkan Ghost taslakları (`dis_oneri` işaretli) kendiliğinden öğrenmeye
(düzenleme dersi, onaylı örnek havuzu, beğeni, paylaşılandan görüş, 'paylaşılan' ses örneği, X'te benzer gönderiden 'paylaşıldı' sayma) girmez:
paylasim.py ve performans.py bu modüldeki `ogrenme_disi(metin)` ile sorar. Kullanıcının açıkça yazdığı yorum ve ret nedeni çalışmaya devam eder.

Dışa aktarma: `disa_aktar(gun)` kullanıcının AÇIKÇA seçtiği, düzelttiği, paylaştığını onayladığı metinleri ve ayrı bölümde reddettiklerini verir.
"""
import datetime as dt
import hashlib
import json
import re
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

KLASOR = Path(__file__).resolve().parent
KAYIT = KLASOR / "kayitlar" / "ghost_oneriler"
FORMATLAR = ("x", "zincir", "linkedin", "blog", "gec")
FORMAT_AD = {"x": "X gönderisi", "zincir": "X zinciri", "linkedin": "LinkedIn", "blog": "Blog yazısı", "gec": "Paylaşmaya değmez"}
TARAMA = KLASOR / "kayitlar" / ".ghost_oneri_tarama.json"
_kilit = threading.RLock()
_dis_onbellek = {"t": 0.0, "kume": set()}


# ---------------------------------------------------------------- yardımcılar
def _norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^\wçğıöşü]+", " ", str(s or "").lower().replace("İ", "i").replace("I", "ı"))).strip()


def _kokler(s):
    return {w[:5] for w in _norm(s).split() if len(w) >= 4}


def _ortusme(a, b):
    A, B = _kokler(a), _kokler(b)
    return len(A & B) / max(1, min(len(A), len(B))) if A and B else 0.0


def url_norm(u):
    """Tekrar karşılaştırması için: şema, www, izleme ekleri (utm_*, fbclid...), parça ve sondaki / atılır."""
    u = str(u or "").strip()
    if not re.match(r"^https?://", u, re.I):
        return ""
    p = urlsplit(u)
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not re.match(r"^(utm_|fbclid|gclid|mc_|ref$|s$|igsh)", k, re.I)]
    host = p.netloc.lower().removeprefix("www.")
    return urlunsplit(("", host, p.path.rstrip("/") or "/", urlencode(q), "")).lstrip("/")


def _sha(ozgun):
    return hashlib.sha256(json.dumps(ozgun, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _yol(oid):
    if not re.fullmatch(r"[0-9a-z_]{6,40}", str(oid or "")):
        raise ValueError("geçersiz öneri kimliği")
    return KAYIT / f"{oid}.json"


def _oku(oid):
    try:
        return json.loads(_yol(oid).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _yaz(d):
    """Kaydı yazar. Orijinal (ozgun) hiçbir zaman değişmez: diskteki kayıt farklı bir ozgun taşıyorsa yazım reddedilir."""
    KAYIT.mkdir(parents=True, exist_ok=True)
    yol = _yol(d["id"])
    with _kilit:
        try:
            eski = json.loads(yol.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            eski = None
        if eski and (eski.get("ozgun") != d.get("ozgun") or eski.get("ozgun_sha") != d.get("ozgun_sha")):
            raise ValueError("gelen öneri değiştirilemez")
        if _sha(d["ozgun"]) != d.get("ozgun_sha"):
            raise ValueError("gelen önerinin parmak izi tutmuyor")
        tmp = yol.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(yol)
    _dis_onbellek["t"] = 0.0


def degistir(oid, fn):
    with _kilit:
        d = _oku(oid)
        if not d:
            return None
        fn(d)
        _yaz(d)
        return d


def liste(gun=60):
    if not KAYIT.exists():
        return []
    sinir = time.time() - gun * 86400
    L = []
    for f in KAYIT.glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (d.get("alinma") or 0) >= sinir:
            d["ozgun_saglam"] = _sha(d.get("ozgun") or {}) == d.get("ozgun_sha")
            L.append(d)
    return sorted(L, key=lambda d: -(d.get("alinma") or 0))


# ---------------------------------------------------------------- 1) içe alma ve tekrar önleme
def _tarih(t):
    t = str(t or "").strip()
    for bic in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return dt.datetime.strptime(t[:19] if "T" in t else t[:10], bic).date().isoformat()
        except ValueError:
            continue
    return ""


def _yayimlanan_baglantilar(gun=60):
    """Ghost'un mevcut taslaklarında kullanılan kaynak bağlantıları ve metinleri: [(url_norm, metin, paylasildi, zaman)]."""
    try:
        import kitaplik_onbellek
        kayitlar = kitaplik_onbellek.hepsi(ghost=True)
    except Exception:  # noqa: BLE001
        return []
    sinir = time.time() - gun * 86400
    out = []
    for k in kayitlar:
        p = (k["veri"].get("paylasim") or {})
        if (p.get("ilk_zaman") or p.get("zaman") or k["mtime"]) < sinir:
            continue
        for t in p.get("taslaklar") or []:
            kl = t.get("kaynak") if isinstance(t.get("kaynak"), dict) else {}
            u = url_norm(t.get("paylas_link") or kl.get("link") or k["veri"].get("link"))
            out.append((u, f"{t.get('konu') or ''} {t.get('metin') or ''}", bool(t.get("paylasildi")), p.get("ilk_zaman") or p.get("zaman") or 0))
    return out


def tekrar_mi(ozgun, haric=""):
    """Kaynak + açı + tarih üzerinden. Döner {tur: tekrar|baska_aci|yok, ile, neden}.
    Aynı kaynak ve benzer açı (kök örtüşmesi ≥0,5) → tekrar; aynı kaynak ama farklı açı → baska_aci (yazılır, not düşülür);
    kaynaksız öneride 30 gün içinde açısı çok benzeyen (≥0,6) öneri → tekrar."""
    u = url_norm(ozgun.get("kaynak_url"))
    aci = f"{ozgun.get('baslik') or ''} {ozgun.get('metin') or ''}"
    sinir = time.time() - 30 * 86400
    baska = None
    for d in liste(45):
        if d["id"] == haric or d.get("durum") == "tekrar":
            continue
        o = d.get("ozgun") or {}
        ou = url_norm(o.get("kaynak_url"))
        benz = _ortusme(aci, f"{o.get('baslik') or ''} {o.get('metin') or ''}")
        if u and ou == u:
            if benz >= 0.5:
                return {"tur": "tekrar", "ile": d["id"], "neden": "Aynı kaynaktan aynı açıyla bir öneri zaten var"}
            baska = baska or {"tur": "baska_aci", "ile": d["id"], "neden": "Aynı kaynaktan farklı bir açı"}
        elif not u and not ou and benz >= 0.6 and (d.get("alinma") or 0) >= sinir:
            return {"tur": "tekrar", "ile": d["id"], "neden": "Son 30 günde neredeyse aynı fikir önerildi"}
    for bu, metin, paylasildi, _z in _yayimlanan_baglantilar():
        if u and bu == u:
            if _ortusme(aci, metin) >= 0.5:
                return {"tur": "tekrar", "ile": "", "neden": "Bu kaynakla aynı açıda bir Ghost taslağı zaten var" + (" ve paylaşıldı" if paylasildi else "")}
            baska = baska or {"tur": "baska_aci", "ile": "", "neden": "Bu kaynak daha önce başka bir açıyla kullanıldı"}
    return baska or {"tur": "yok", "ile": "", "neden": ""}


def _olgular(L):
    """Önerinin ayrı verdiği olgular: {metin, kaynak, url, tarih}. Kaynağı olmayan satır saklanır ama olgu sayılmaz (bkz. ayrim)."""
    out = []
    for x in L if isinstance(L, list) else []:
        x = {"metin": x} if isinstance(x, str) else x if isinstance(x, dict) else {}
        m = str(x.get("metin") or "").strip()[:600]
        if m:
            u = str(x.get("url") or "").strip()
            out.append({"metin": m, "kaynak": str(x.get("kaynak") or "").strip()[:160], "url": u[:1000] if re.match(r"^https?://", u, re.I) else "",
                        "tarih": _tarih(x.get("tarih")) or str(x.get("tarih") or "")[:20]})
    return out[:12]


def ekle(metin, baslik="", not_="", arastirma_notu="", kaynak_url="", kaynaklar=None, tarih="", uretici="ChatGPT", kanal="yapistirma",
         ham_kimlik="", kaynak_durum="", editor_notu="", olgular=None):
    """Gelen öneriyi olduğu gibi kaydeder. Aynı ham kimlik ya da aynı orijinal metin daha önce geldiyse yeni kayıt açmaz. Döner (kayıt, yeni_mi).
    Aynı kimlikle daha yeni bir metin gelirse orijinal değişmez, `kaynak_degisti` olarak yanına yazılır; daha eski tarihli metin yok sayılır."""
    metin = str(metin or "").strip()
    if len(metin) < 8:
        raise ValueError("Öneri metni çok kısa")
    kaynaklar = [str(u).strip() for u in (kaynaklar or []) if re.match(r"^https?://", str(u).strip(), re.I)][:8]
    kaynak_url = str(kaynak_url or "").strip()
    if not re.match(r"^https?://", kaynak_url, re.I):
        kaynak_url = kaynaklar[0] if kaynaklar else ""
    ozgun = {"metin": metin[:8000], "baslik": str(baslik or "").strip()[:300], "not": str(not_ or "").strip()[:2000],
             "arastirma_notu": str(arastirma_notu or "").strip()[:4000], "kaynak_url": kaynak_url[:1000], "kaynaklar": kaynaklar,
             "tarih": _tarih(tarih) or str(tarih or "")[:20], "uretici": str(uretici or "ChatGPT").strip()[:60], "kanal": kanal,
             "ham_kimlik": str(ham_kimlik or "")[:80], "kaynak_durum": str(kaynak_durum or "")[:120]}
    if str(editor_notu or "").strip():
        ozgun["editor_notu"] = str(editor_notu).strip()[:2000]
    if _olgular(olgular):
        ozgun["olgular"] = _olgular(olgular)
    with _kilit:
        for d in liste(400):
            o = d.get("ozgun") or {}
            if _norm(o.get("metin")) == _norm(metin):
                return d, False
            if ham_kimlik and o.get("ham_kimlik") == ozgun["ham_kimlik"]:
                y, e = ozgun["tarih"], o.get("tarih")
                if not (y and e and y < e) and (d.get("kaynak_degisti") or {}).get("metin") != ozgun["metin"]:
                    degistir(d["id"], lambda x: x.update(kaynak_degisti={"metin": ozgun["metin"], "tarih": y, "zaman": time.time()}))
                    d = _oku(d["id"]) or d
                return d, False
        t = tekrar_mi(ozgun)
        oid = time.strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:4]
        d = {"id": oid, "ozgun": ozgun, "ozgun_sha": _sha(ozgun), "alinma": time.time(), "durum": "tekrar" if t["tur"] == "tekrar" else "geldi",
             "tekrar": t if t["tur"] != "yok" else None, "karar": None, "surumler": [], "hata": ""}
        _yaz(d)
    return d, True


def havuzdan_al():
    """Drive'daki öneri havuzunun yerel kopyası (seckiler.havuz zaten indiriyor) → gelen öneriler. Yeni bağlantı yok. Döner yeni kayıt sayısı."""
    yol = KLASOR / "kayitlar" / "secki" / "havuz.json"
    simdi = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        satirlar = json.loads(yol.read_text(encoding="utf-8"))
    except OSError:
        _tarama_yaz(son_deneme=simdi, kaynak_yok=True)
        return 0
    except ValueError:
        _tarama_yaz(son_deneme=simdi, son_hata="Öneri havuzunun kopyası okunamadı; kayıtlara dokunulmadı.", hata_zamani=simdi)
        return 0
    n = 0
    for r in satirlar if isinstance(satirlar, list) else []:
        if not str(r.get("oneri") or "").strip():
            continue
        try:
            _d, yeni = ekle(r.get("oneri"), baslik=r.get("oneri"), not_=" ".join(x for x in (r.get("ne"), ("En küçük test: " + r["test"]) if r.get("test") else "") if x),
                            arastirma_notu=r.get("kanit") or "", kaynak_url=r.get("kaynak") or "", tarih=r.get("tarih") or "", uretici="ChatGPT · Öneri Havuzu",
                            kanal="drive_havuz", ham_kimlik="havuz:" + str(r.get("id") or ""), kaynak_durum=r.get("durum") or "")
            n += yeni
        except ValueError:
            continue
    _tarama_yaz(son_deneme=simdi, son_basarili=simdi, son_hata=None, hata_zamani=None, kaynak_yok=False, yeni=n,
                kaynak_tarihi=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(yol.stat().st_mtime)))
    return n


def tarama_durumu():
    try:
        return json.loads(TARAMA.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _tarama_yaz(**ek):
    try:
        TARAMA.parent.mkdir(parents=True, exist_ok=True)
        TARAMA.write_text(json.dumps({**tarama_durumu(), **ek}, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


# ---------------------------------------------------------------- 2) Ghost'un format kararı ve son metni
KARAR_ISTEM = """Sen Ghost'sun: bu kişinin yazı ortağı ve editörüsün. Dışarıdan (bir yazı asistanından) bir öneri geldi. Bu öneri KİŞİNİN SÖZÜ DEĞİL;
onaylanmış, seçilmiş ya da yayımlanmış da değil. Önerideki cümleleri kopyalamayacaksın; yalnız fikri, kaynağı ve araştırma notunu kullanacaksın.

Görevin önce FORMAT kararı: bu malzeme kişinin sesinde en iyi nerede durur?
- x: tek X gönderisi (bir gözlem, bir tepki, tek ayrıntı; kaynak bağlantısıyla)
- zincir: X zinciri (2-4 parça; ancak gerçekten adım adım anlatılması gereken bir şey varsa)
- linkedin: LinkedIn (iş/sektör derslerinde, kişinin kendi işinden bir bağ kurulabiliyorsa)
- blog: blog yazısı (bir düşüncenin bağlamı ve karşı argümanı gerekiyorsa; tek gönderiye sıkıştırmak fikri öldürür)
- gec: paylaşmaya değmez (bariz, eskimiş, kaynağı zayıf, kişinin alanı dışında ya da kanıt sınırı izin vermiyor)
Kanıt sınırını aşan iddia gerektiren format seçme. Kişinin alanları, sesi ve stratejisi aşağıda.

{ses}

ALANLARI: {alanlar}
KAÇINDIKLARI: {kacin}

GELEN ÖNERİ (üretici: {uretici}, tarih: {tarih}):
{metin}
{not_}
ARAŞTIRMA NOTU / KANIT SINIRI: {arastirma}
KAYNAK: {kaynak}
{tekrar}

JSON: {{"format": "x|zincir|linkedin|blog|gec", "neden": "kişiye tek-iki cümle, neden bu format", "uygunluk": 1-5,
"aci": "Ghost'un kuracağı açı, tek cümle (önerinin cümlesini tekrarlama)"}}"""

BLOG_ISTEM = """Sen Ghost'sun ve bu kişinin blogu için yazıyorsun. Aşağıdaki malzeme dışarıdan bir yazı asistanının önerisi; KİŞİNİN SÖZÜ DEĞİL. Önerideki
cümleleri kopyalama; fikri, kaynağı ve araştırma notunu kullanıp kişinin sesinde baştan yaz. Kişiye yaşamadığı deneyim, okumadığı kitap, uydurma sayı ya
da alıntı atfetme. Araştırma notundaki kanıt sınırını aşma; bilinmeyeni bilinmeyen olarak bırak. Markdown: tek # başlık, 3-5 ## ara başlık, 700-1100
kelime, sonunda 'Kaynaklar' listesi (yalnız verilen bağlantılar). Tarih yazma, hashtag yok.

{ses}

AÇI: {aci}
GELEN ÖNERİ: {metin}
{not_}
ARAŞTIRMA NOTU / KANIT SINIRI: {arastirma}
KAYNAKLAR: {kaynaklar}

Yalnız yazının kendisini döndür."""


def _profil_bloku(platform="x"):
    import paylasim
    pr = paylasim.profil()
    alanlar = ", ".join(a.get("ad") for a in pr.get("alanlar") or [] if isinstance(a, dict) and (a.get("agirlik") or 0) > 0)
    return pr, paylasim._persona_blogu(pr, kisa=True, platform=platform) + "\n" + paylasim._strateji_blogu(), alanlar


def karar_ver(d):
    import paylasim
    o = d["ozgun"]
    pr, ses, alanlar = _profil_bloku()
    t = d.get("tekrar") or {}
    c = paylasim._claude_json(KARAR_ISTEM.format(
        ses=ses, alanlar=alanlar or "-", kacin=", ".join(map(str, pr.get("kacin") or [])) or "-", uretici=o.get("uretici"), tarih=o.get("tarih") or "-",
        metin=o["metin"], not_=_ek_bolumler(o, d), arastirma=o.get("arastirma_notu") or "-", kaynak=o.get("kaynak_url") or "yok",
        tekrar=("DİKKAT: " + t["neden"] + "; daha önce kullanılmayan bir açı seç.") if t.get("tur") == "baska_aci" else ""), model_adi="opus", zaman_asimi=300)
    fmt = str(c.get("format") or "").strip().lower()
    if fmt not in FORMATLAR:
        raise ValueError("Ghost format kararı veremedi")
    try:
        u = max(1, min(5, int(c.get("uygunluk") or 3)))
    except (TypeError, ValueError):
        u = 3
    return {"format": fmt, "neden": str(c.get("neden") or "")[:500], "uygunluk": u, "aci": str(c.get("aci") or "")[:400], "zaman": time.time()}


def _ek_bolumler(o, d=None):
    """Olgu, kanıtsız iddia ve editör notu ayrı başlıklarla: model bunları birbirine ve kişinin görüşüne karıştırmasın.
    d verilirse öneriye sonradan eklenen editör notu da girer (orijinal değişmez)."""
    a = _ayri_olgular(o)
    parca = []
    if a["olgular"]:
        parca.append("KAYNAKLI OLGULAR:\n" + "\n".join(f"- {x['metin']} ({x['kaynak'] or x['url']}{', ' + x['tarih'] if x['tarih'] else ''})" for x in a["olgular"]))
    notlar = [n for n in (o.get("editor_notu"), o.get("not")) if n]
    if notlar:
        parca.append("EDİTÖR NOTU (önerinin yorumu; kişinin görüşü değil, olgu da değil, ona atfetme): " + " ".join(notlar))
    if a["kaynaksiz"]:
        parca.append("KAYNAĞI OLMAYAN İDDİALAR (olgu sayma): " + " ".join(a["kaynaksiz"]))
    ek = ((d or {}).get("editor_notu_ek") or {}).get("metin")
    if ek:
        parca.append("SONRADAN EKLENEN EDİTÖR NOTU (önerinin yorumu; kişinin görüşü değil, olgu da değil, ona atfetme; önceki notla çelişirse bu geçerli): " + ek)
    return "\n\n".join(parca)


def _ayri_olgular(o):
    L = o.get("olgular") or []
    return {"olgular": [x for x in L if x.get("kaynak") or x.get("url")], "kaynaksiz": [x["metin"] for x in L if not (x.get("kaynak") or x.get("url"))]}


def _girdi(d, karar):
    """Ghost'un yazım hattına giden metin: önerinin fikri, kaynağı, kanıt sınırı ve Ghost'un açısı; önerinin cümlesi dayanak, kopyalanacak metin değil."""
    o = d["ozgun"]
    parca = [f"DIŞARIDAN GELEN ÖNERİ ({o.get('uretici')}; kişinin sözü değil, cümlelerini kopyalama):\n{o['metin']}"]
    if o.get("arastirma_notu"):
        parca.append("ARAŞTIRMA NOTU / KANIT SINIRI (bunun ötesini iddia etme): " + o["arastirma_notu"])
    if _ek_bolumler(o, d):
        parca.append(_ek_bolumler(o, d))
    if karar.get("aci"):
        parca.append("GHOST'UN AÇISI: " + karar["aci"])
    if karar["format"] == "zincir":
        parca.append("BİÇİM: 2-4 parçalık X zinciri olarak yaz.")
    if (d.get("tekrar") or {}).get("tur") == "baska_aci":
        parca.append("Bu kaynak daha önce başka bir açıyla kullanıldı; o açıyı tekrarlama.")
    return "\n\n".join(parca)


def _isaretle_taslaklar(yol, d, karar):
    """Ghost'un yazdığı taslaklara öneri bağı, format kararı ve kaynak satırı (kartta 'ChatGPT önerisi')."""
    import kayit_json
    o = d["ozgun"]

    def fn(k):
        p = k["veri"].setdefault("paylasim", {})
        for t in p.get("taslaklar") or []:
            t["dis_oneri"] = d["id"]
            t["format_karari"] = {"format": karar["format"], "neden": karar["neden"]}
            t["kaynak"] = {**(t.get("kaynak") if isinstance(t.get("kaynak"), dict) else {}), "tur": "ChatGPT önerisi" if "chatgpt" in o.get("uretici", "").lower()
                           else "Gelen öneri", "baslik": o.get("baslik") or o["metin"][:120], "tarih": o.get("tarih") or "", "link": o.get("kaynak_url") or ""}
    kayit_json.guncelle(yol, fn)


def _onceki_surumu_kapat(d):
    """Yeni sürüm gelince: dokunulmamış eski taslak gizlenir (öğrenme yok); kişinin dokunduğu (düzenlediği, yorumladığı, beğendiği, paylaştığı, kendi
    nedeniyle kaldırdığı) taslak OLDUĞU GİBİ kalır ve sürüm 'aktif' sayılmaya devam eder."""
    import kayit_json
    for s in d.get("surumler") or []:
        if not s.get("aktif") or not s.get("temel"):
            continue
        yol = KLASOR / "ghost" / f"{s['temel'][7:]}.json"
        dokunuldu = []

        def fn(k):
            for t in (k["veri"].get("paylasim") or {}).get("taslaklar") or []:
                if any(t.get(a) for a in ("duzenlendi", "yorumlar", "begendi", "paylasildi", "kopyalandi")) or (t.get("gizli") and not t.get("degistirildi")):
                    dokunuldu.append(1)
                    continue
                t.update(gizli=True, degistirildi=True, red_nedeni="gelen önerinin yeni sürümüyle değiştirildi", gizlenme=time.time())
        try:
            kayit_json.guncelle(yol, fn)
        except Exception:  # noqa: BLE001
            continue
        s["aktif"] = bool(dokunuldu)


def isle(oid, log=print, zorla=False):
    """Format kararı + son metin. Tekrar olan öneri `zorla` yoksa yazılmaz. Mevcut sürümler ezilmez; yeni sürüm eklenir."""
    d = _oku(oid)
    if not d:
        raise ValueError("Öneri bulunamadı")
    if d.get("durum") == "tekrar" and not zorla:
        return d
    import ghost_kurulum
    if not ghost_kurulum.kurulu_mu():
        raise ValueError("Ghost henüz kurulmadı")
    degistir(oid, lambda x: x.update(durum="yaziliyor", hata=""))
    try:
        karar = karar_ver(d)
        log(f"Gelen öneri: {FORMAT_AD[karar['format']]} ({karar['neden'][:80]})")
        surum = {"zaman": time.time(), "format": karar["format"], "aktif": True}
        if karar["format"] == "gec":
            surum["aktif"] = False
        elif karar["format"] == "blog":
            surum["blog"] = blog_yaz(d, karar)
        else:
            surum["temel"] = taslak_yaz(d, karar, log)
            v = json.loads((KLASOR / "ghost" / f"{surum['temel'][7:]}.json").read_text(encoding="utf-8"))["veri"].get("paylasim") or {}
            if not v.get("taslaklar"):                         # Ghost yazdı ama kendi okur kapısından geçmedi
                surum.update(aktif=False, elendi=str(((v.get("elenen") or [{}])[0] or {}).get("neden") or "okur kapısından geçmedi")[:300])

        def bitir(x):
            _onceki_surumu_kapat(x)
            x["karar"] = karar
            x["surumler"] = (x.get("surumler") or []) + [surum]
            x["durum"] = "gecildi" if karar["format"] == "gec" else "elendi" if surum.get("elendi") else "yazildi"
            x.update(hata="", hata_zamani=None, son_basarili=time.time())
        degistir(oid, bitir)
    except Exception as e:  # noqa: BLE001
        degistir(oid, lambda x: x.update(durum="hata", hata=str(e)[:300], hata_zamani=time.time()))
        raise
    return _oku(oid)


def taslak_yaz(d, karar, log=print):
    """x / zincir / linkedin: Ghost'un kendi yazım hattı (konu seçimi, yazım, doğrulama, okur kapısı) ile; kayıt kaynak_tur 'dis_oneri'."""
    import paylasim
    o = d["ozgun"]
    girdi = _girdi(d, karar)
    temel = paylasim.ghost_kaydi(girdi, "dis_oneri", (o.get("baslik") or o["metin"])[:120], o.get("kaynak_url") or "", girdi,
                                 ek={"dis_oneri": d["id"], "platform": "linkedin" if karar["format"] == "linkedin" else "x"})
    yol = KLASOR / "ghost" / f"{temel[7:]}.json"
    paylasim.uret(yol, log=log, en_cok=1)
    _isaretle_taslaklar(yol, d, karar)
    return temel


def blog_yaz(d, karar):
    import claude_yaz
    import paylasim
    o = d["ozgun"]
    _pr, ses, _a = _profil_bloku("blog")
    metin = claude_yaz.sor(BLOG_ISTEM.format(ses=ses, aci=karar.get("aci") or "-", metin=o["metin"], not_=_ek_bolumler(o, d),
                                             arastirma=o.get("arastirma_notu") or "-", kaynaklar=", ".join([o.get("kaynak_url")] + o.get("kaynaklar", [])) or "yok"),
                           model_adi="opus", zaman_asimi=600)
    metin = paylasim._temiz(str(metin or "").strip())
    if len(metin) < 400:
        raise ValueError("Blog yazısı yazılamadı")
    return {"metin": metin, "zaman": time.time()}


def blog_duzelt(oid, metin):
    """Kişinin blog metninde yaptığı düzeltme: Ghost'un metni ayrı kalır, kişinin metni 'kisi_metni' olarak yazılır (ezilmez)."""
    def fn(d):
        S = [s for s in d.get("surumler") or [] if s.get("blog")]
        if not S:
            raise ValueError("Blog sürümü yok")
        b = S[-1]["blog"]
        b["kisi_metni"] = str(metin or "").strip()[:40000]
        b["kisi_zaman"] = time.time()
    return degistir(oid, fn)


class Degisti(Exception):
    """Not, kutu açıldıktan sonra başka yerde değişti: yazılmaz, kişi yeni haliyle karar verir."""


def editor_notu_kaydet(oid, metin, eski=None):
    """Var olan öneriye editör notu ekler ya da onu düzenler. Yeni kayıt açmaz, orijinali (ozgun) değiştirmez; eski not `editor_notu_gecmis`te kalır.
    Kişinin görüşü sayılmaz: profil, görüş defteri ve fikir defterine yazılmaz, _dis_kume sayesinde öğrenmeye de girmez."""
    metin = str(metin or "").strip()[:2000]

    def fn(d):
        mev = (d.get("editor_notu_ek") or {}).get("metin") or ""
        if eski is not None and str(eski).strip() != mev:
            raise Degisti(mev)
        if metin == mev:
            return
        if mev:
            d["editor_notu_gecmis"] = (d.get("editor_notu_gecmis") or []) + [d["editor_notu_ek"]]
        d["editor_notu_ek"] = {"metin": metin, "zaman": time.time()} if metin else None
    return degistir(oid, fn)


def kisi_metni(d):
    """Kişinin blog metninde yaptığı son düzeltme; yeni Ghost sürümü gelse de kaybolmaz."""
    S = [s["blog"]["kisi_metni"] for s in d.get("surumler") or [] if (s.get("blog") or {}).get("kisi_metni")]
    return S[-1] if S else ""


def _taslak_kayitlari(d):
    """Her sürümün taslakları: (sürüm sırası, taslak). Yalnız okur; okunamayan dosya atlanır."""
    out = []
    for i, s in enumerate(d.get("surumler") or []):
        if not s.get("temel"):
            continue
        try:
            v = json.loads((KLASOR / "ghost" / f"{s['temel'][7:]}.json").read_text(encoding="utf-8"))["veri"]
        except (OSError, ValueError, KeyError):
            continue
        out += [(i, t) for t in (v.get("paylasim") or {}).get("taslaklar") or []]
    return out


def _sistem_gizledi(t):
    return bool(t.get("degistirildi")) or str(t.get("red_nedeni") or "").startswith(("kalite kapısı", "daha güçlü", "gelen önerinin yeni"))


def _taslak_onayi(d):
    """Bu önerinin taslaklarındaki kişi eylemleri. Yalnız açık eylem onaydır: kopyalamak, tablodaki 'beğenmiş' notu, X'te benzerini görmek onay değildir."""
    out = {"paylasildi": False, "duzeltildi": False, "secildi": False, "sistem_esledi": False, "kaldirildi": False, "surum": {}}

    def isle(ad, i):
        out[ad] = True
        out["surum"][ad] = i
    for i, t in _taslak_kayitlari(d):
        if t.get("paylasildi"):
            isle("sistem_esledi" if t.get("oto_tanindi") else "paylasildi", i)
        if t.get("duzenlendi"):
            isle("duzeltildi", i)
        if t.get("begendi"):
            isle("secildi", i)
        if t.get("gizli") and not _sistem_gizledi(t):
            isle("kaldirildi", i)
    return out


ONAY_METNI = {"yok": "Onaylamadınız. Bu öneri sizin sözünüz, seçiminiz ya da görüşünüz sayılmıyor.", "paylasildi": "Paylaştığınızı söylediniz.", "duzeltildi": "Metni düzelttiniz.",
              "secildi": "Beğendim dediniz.", "sistem_esledi": "X'te benzer bir gönderi görüldü; bu onay sayılmıyor.", "gecildi": "Geçtiniz.", "kaldirildi": "Taslağı kaldırdınız."}
ONAY_ETIKET = {"yok": "Onay yok", "paylasildi": "Paylaştınız", "duzeltildi": "Düzelttiniz", "secildi": "Beğendiniz", "sistem_esledi": "Onay yok", "gecildi": "Geçtiniz", "kaldirildi": "Kaldırdınız"}
KALITE_ETIKET = {"gecti": "Geçti", "notlu": "Bakılacak not var", "gecmedi": "Geçmedi", "yapilmadi": "Yapılmadı", "yok": "Kontrol edilmedi", "bekliyor": "Bekliyor", "bilinmiyor": "Sonuç kayıtlı değil"}
OKUR_ADI = (("anlasilir", "Anlaşılır"), ("tamlik", "Tamlık"), ("deger", "Değer"), ("ses", "Üslup"), ("tazelik", "Tazelik"), ("paylasilir", "Paylaşılır"))


def _calisiyor(d):
    return bool(d.get("calisiyor")) or d.get("durum") == "yaziliyor"


def _son_metinli(d):
    """En yeni metinli sürüm: (sıra, sürüm). Ghost'un sonradan 'yazmadım' demesi ya da başarısız deneme önceki metni yok saydırmaz."""
    S = d.get("surumler") or []
    for i in range(len(S) - 1, -1, -1):
        if S[i].get("blog") or (S[i].get("temel") and S[i].get("aktif") is not False):
            return i, S[i]
    return None, None


def _uretim(d):
    S, k, dur = d.get("surumler") or [], d.get("karar") or {}, d.get("durum")
    s = S[-1] if S else {}
    i_m, m = _son_metinli(d)
    fmt = (k.get("format") or s.get("format") or "") if S or k else ""
    ad = FORMAT_AD.get(fmt, fmt)
    u = {"format": fmt, "format_ad": ad, "neden": k.get("neden") or "", "aci": k.get("aci") or "", "surum": len(S), "zaman": s.get("zaman"),
         "temel": (m or {}).get("temel") or "", "onceki_metin": bool(m) and i_m < len(S) - 1}
    ghost_gecti = fmt == "gec" and bool(S)
    if _calisiyor(d):
        u.update(durum="calisiyor", etiket="Ghost çalışıyor", metin="Ghost karar verip yazıyor." + (" Önceki sürüm yerinde." if m else ""))
    elif dur == "hata":
        u.update(durum="hata", etiket="Tamamlanmadı", metin="Son deneme tamamlanmadı; önceki sürüm olduğu gibi duruyor." if m else "Son deneme tamamlanmadı; henüz bir metin yok.")
    elif dur == "tekrar":
        u.update(durum="tekrar", etiket="Yazılmadı", metin="Bu konu daha önce geldiği için yazılmadı.")
    elif dur == "elendi":
        u.update(durum="elendi", etiket="Metin çıkmadı", metin="Ghost denedi; metin kalite kontrolünden geçmediği için taslak çıkmadı." + (" Önceki sürümde sizin dokunduğunuz taslak yerinde." if m else ""))
    elif ghost_gecti:
        u.update(durum="yazilmadi", etiket="Ghost yazmadı", metin="Ghost bu öneriyi yazmadı: paylaşmaya değmez buldu." + (" Önceki sürümde sizin dokunduğunuz taslak yerinde." if m else ""))
    elif m:
        u.update(durum="yazildi", etiket="Yazıldı", metin=f"Ghost {ad[0].lower() + ad[1:] if fmt == 'blog' else ad} yazdı." + (f" Bu, {len(S)}. sürüm." if len(S) > 1 else ""))
    elif dur == "gecildi":
        u.update(durum="yazilmadi", etiket="Yazılmadı", metin="Siz geçtiğiniz için yazılmadı.")
    else:
        u.update(durum="bekliyor", etiket="Bekliyor", metin="Ghost henüz değerlendirmedi.")
    ek = d.get("editor_notu_ek") or {}
    u["not_sonra"] = bool(ek.get("metin") and S and (ek.get("zaman") or 0) > (s.get("zaman") or 0) and not _calisiyor(d))
    return u


def _kalite(d, u, kayitlar):
    """Ghost'un kendi kontrolü. Kişinin onayı değildir; metin yazılmadıysa, kontrol yapılmadıysa ya da sonuç kayıtlı değilse geçti denmez."""
    def sonuc(durum, metin, **ek):
        return {"durum": durum, "etiket": KALITE_ETIKET[durum], "metin": metin, "puanlar": [], "notlar": [], **ek}
    S = d.get("surumler") or []
    i_m, m = _son_metinli(d)
    if u["durum"] == "calisiyor":
        return sonuc("bekliyor", "Yazım bitince kontrol edilir.")
    if u["durum"] == "elendi":
        return sonuc("gecmedi", str((S[-1] if S else {}).get("elendi") or "Okur kontrolünden geçmedi."))
    if not m:
        return sonuc("yok", "Metin yazılmadığı için kontrol edilmedi.")
    onceki = u["durum"] == "hata" or i_m < len(S) - 1
    bas = "Bu sonuç önceki sürüme ait. " if onceki else ""
    if m.get("blog"):
        return sonuc("yapilmadi", bas + "Blog yazıları bu kontrolden geçmiyor; yayımlamadan önce kendiniz okuyun.", onceki=onceki)
    T = [t for i, t in kayitlar if i == i_m]
    if not T:
        return sonuc("bilinmiyor", bas + "Bu sürüm için kontrol sonucu okunamadı.", onceki=onceki)
    t = T[0]
    okur = t.get("okur") if isinstance(t.get("okur"), dict) else {}
    P = [{"ad": ad, "puan": okur[k]} for k, ad in OKUR_ADI if isinstance(okur.get(k), (int, float)) and okur[k]]
    N = [str(x) for x in (t.get("kod_notlari") or []) + (t.get("dogruluk") or []) if x]
    N += [f"Şüpheli iddia: {c.get('iddia')}" for c in t.get("iddialar") or [] if isinstance(c, dict) and c.get("iddia") and c.get("durum") in ("supheli", "yanlis")]
    N += [f"Kaynakla uyuşmuyor: {z.get('not') or z.get('iddia')}" for z in ((t.get("kaynak_denetimi") or {}).get("sorunlar") or []) if isinstance(z, dict) and (z.get("not") or z.get("iddia"))]
    if any(isinstance(o, dict) and o.get("rahatsiz") for o in t.get("panel") or []):
        N.append("Okur panelinde rahatsız olan var.")
    if t.get("zorla"):
        N.append("Okur eşiği atlanarak yazıldı.")
    if str(t.get("red_nedeni") or "").startswith("kalite kapısı"):
        return sonuc("gecmedi", bas + "Bu taslak sonradan kalite kapısından geçmedi.", puanlar=P, notlar=N[:6], onceki=onceki)
    sonra = " Bu sonuç Ghost'un ilk metni içindi; sizin düzeltmeniz yeniden kontrol edilmedi." if t.get("duzenlendi") else ""
    if N:
        return sonuc("notlu", bas + "Okur kontrolünden geçti ama bakmanız gereken notlar var." + sonra, puanlar=P, notlar=N[:6], onceki=onceki)
    if P:
        return sonuc("gecti", bas + "Okur kontrolünden geçti." + sonra, puanlar=P, onceki=onceki)
    return sonuc("bilinmiyor", bas + "Bu sürüm için okur sonucu kayıtlı değil." + sonra, onceki=onceki)


def _onay(d, T):
    S = d.get("surumler") or []
    durum = ("paylasildi" if T["paylasildi"] else "kaldirildi" if T["kaldirildi"] else "duzeltildi" if T["duzeltildi"] or kisi_metni(d) else "secildi" if T["secildi"] else
             "gecildi" if (d.get("kisi_karari") or {}).get("karar") == "gec" else "sistem_esledi" if T["sistem_esledi"] else "yok")
    i = T["surum"].get(durum)
    if durum == "duzeltildi" and i is None:
        i = max((n for n, s in enumerate(S) if (s.get("blog") or {}).get("kisi_metni")), default=None)
    onceki = i is not None and i < len(S) - 1
    metin = ONAY_METNI[durum]
    if onceki:
        metin += " Bu, önceki bir sürüm içindi; son sürüm için kararınız yok."
    elif durum == "gecildi" and d.get("durum") != "gecildi":
        metin = "Daha önce geçtiniz; sonra yeniden değerlendirme istendi. Son sürüm için kararınız yok."
        onceki = True
    return {"durum": durum, "metin": metin, "etiket": ONAY_ETIKET[durum], "onceki": onceki, "sizin": durum in ("paylasildi", "duzeltildi", "secildi") and not onceki}


def _ozet(u, q, y):
    """Kartın başındaki tek cümle: üç katmanla çelişmez; 'bitti' yalnız kişinin açık eylemiyle denir."""
    if u["durum"] == "calisiyor":
        return {"metin": "Ghost çalışıyor", "ton": "calisiyor"}
    if not y["onceki"]:
        if y["durum"] == "paylasildi":
            return {"metin": "Paylaştınız", "ton": "sizin"}
        if y["durum"] == "kaldirildi":
            return {"metin": "Kaldırdınız", "ton": "notr"}
        if y["durum"] == "gecildi":
            return {"metin": "Geçtiniz", "ton": "notr"}
    if u["durum"] == "hata":
        return {"metin": "Yazım tamamlanmadı", "ton": "sorun"}
    if u["durum"] == "elendi":
        return {"metin": "Metin çıkmadı", "ton": "uyari"}
    if u["durum"] in ("yazilmadi", "tekrar"):
        return {"metin": u["etiket"], "ton": "uyari" if u["durum"] == "tekrar" else "notr"}
    if u["durum"] == "bekliyor":
        return {"metin": "Değerlendirme bekliyor", "ton": "notr"}
    if not y["onceki"] and y["durum"] in ("duzeltildi", "secildi"):
        return {"metin": y["etiket"] + " · henüz paylaşmadınız", "ton": "sizin"}
    if q["durum"] in ("notlu", "gecmedi"):
        return {"metin": "Notlara bakıp karar verin", "ton": "uyari"}
    return {"metin": "Kararınızı bekliyor", "ton": "bekliyor"}


def ayrim(d):
    """Dört ayrı şey, kayda hiçbir şey yazmadan mevcut veriden: özgün öneri (kaynaklı olgu, metin, editör notu), üretim, kalite kontrolü, kişinin onayı."""
    o = d.get("ozgun") or {}
    K = _taslak_kayitlari(d)
    y = _onay(d, _taslak_onayi(d))
    u = _uretim(d)
    q = _kalite(d, u, K)
    return {**_ayri_olgular(o), "kaynak": {"url": o.get("kaynak_url") or "", "tarih": o.get("tarih") or "", "kanit_siniri": o.get("arastirma_notu") or ""},
            "oneri": {"metin": o.get("metin") or "", "notlar": [n for n in (o.get("editor_notu"), o.get("not"), (d.get("editor_notu_ek") or {}).get("metin")) if n], "uretici": o.get("uretici") or "", "tablo_durumu": o.get("kaynak_durum") or ""},
            "uretim": u, "kalite": q, "onay": y, "ozet": _ozet(u, q, y)}


def gec(oid, neden=""):
    return degistir(oid, lambda d: d.update(durum="gecildi", kisi_karari={"karar": "gec", "neden": str(neden or "")[:300], "zaman": time.time()}))


def bekleyenler(n=3):
    return [d["id"] for d in liste(14) if d.get("durum") == "geldi"][:n]


# ---------------------------------------------------------------- 3) öğrenme ayrımı
def _dis_kume():
    """Gelen önerilerin orijinal metinleri ve bunlardan çıkan taslakların her hali (Ghost'un metni, kişinin düzenlediği metin): normalleştirilmiş küme."""
    if time.time() - _dis_onbellek["t"] < 20:
        return _dis_onbellek["kume"]
    kume = set()
    for d in liste(3650):
        o = d.get("ozgun") or {}
        for a in ("metin", "not", "editor_notu", "arastirma_notu"):
            kume.add(_norm(o.get(a)))
        for x in o.get("olgular") or []:
            kume.add(_norm(x.get("metin")))
        for x in [d.get("editor_notu_ek")] + (d.get("editor_notu_gecmis") or []):
            kume.add(_norm((x or {}).get("metin")))
        for s in d.get("surumler") or []:
            if s.get("blog"):
                kume.add(_norm(s["blog"].get("metin"))); kume.add(_norm(s["blog"].get("kisi_metni")))
    try:
        import kitaplik_onbellek
        for k in kitaplik_onbellek.hepsi(ghost=True):
            for t in (k["veri"].get("paylasim") or {}).get("taslaklar") or []:
                if (t.get("dis_oneri") or k["veri"].get("kaynak_tur") == "dis_oneri"
                        or (k["veri"].get("kaynak_tur") == "secki" and not str(k["veri"].get("deneyim") or "").strip())):   # kişinin karşılığı olmayan seçki taslağı
                    for a in ("metin", "ilk_metin", "ogrenilen_metin", "ilk_taslak", "onceki"):
                        if t.get(a):
                            kume.add(_norm(t[a]))
                    for z in t.get("zincir") or []:
                        kume.add(_norm(z))
    except Exception:  # noqa: BLE001
        pass
    kume.discard("")
    _dis_onbellek.update(t=time.time(), kume=kume)
    return kume


def ogrenme_disi(*metinler):
    """Metinlerden biri gelen öneriden ya da ondan çıkan taslaktan geliyorsa True: kendiliğinden öğrenme o metinle çalışmaz."""
    K = _dis_kume()
    if not K:
        return False
    for m in metinler:
        n = _norm(m if isinstance(m, str) else (m or {}).get("metin") if isinstance(m, dict) else "")
        if n and (n in K or (len(n) > 80 and any(n[:80] == k[:80] for k in K))):
            return True
    return False


# ---------------------------------------------------------------- 4) dışa aktarma
def _ghost_taslaklari(gun):
    import kitaplik_onbellek
    sinir = time.time() - gun * 86400
    for k in kitaplik_onbellek.hepsi(ghost=True):
        v = k["veri"]
        p = v.get("paylasim") or {}
        if v.get("toplanti") or (p.get("ilk_zaman") or p.get("zaman") or k["mtime"]) < sinir:
            continue
        temel = ("ghost__" + k["temel"]) if Path(k["yol"]).parent.name == "ghost" else k["temel"]
        for i, t in enumerate(p.get("taslaklar") or []):
            yield temel, i, v, p, t


def disa_aktar(gun=90):
    """ChatGPT'ye geri verilebilecek dosya. Bölümler birbirine karışmaz; yalnız kişinin AÇIK eylemleri:
    secilen (Beğendim / Kalsın), duzeltilen (Ghost'un metni → kişinin son metni), paylasilan (kişinin 'paylaştım' onayı), reddedilen (kişinin nedeniyle
    kaldırdıkları; ayrı). Sistemin kendi değiştirdiği/elediği taslaklar ve X'te benzer gönderiden sistemin çıkardığı 'paylaşıldı' ayrı bir bölümde
    (sistem_eslestirdi) ve kişinin onayı sayılmaz. Gelen önerilerin orijinali, Ghost'un format kararı ve kişinin önerideki son sonucu `oneriler`'de."""
    oneriler = {d["id"]: d for d in liste(max(gun, 30) + 30)}
    out = {"sema": "ghost/kullanici-tercihleri@1", "uretim": dt.datetime.now().isoformat(timespec="seconds"), "gun": gun,
           "aciklama": "Kişinin açıkça seçtiği, düzelttiği, paylaştığını onayladığı ve reddettiği metinler. Bölümler birbirine karışmaz.",
           "secilen": [], "duzeltilen": [], "paylasilan": [], "reddedilen": [], "sistem_eslestirdi": [], "oneriler": []}
    sonuc = {}
    for temel, i, v, p, t in _ghost_taslaklari(gun):
        o = oneriler.get(t.get("dis_oneri") or v.get("dis_oneri"))
        kl = t.get("kaynak") if isinstance(t.get("kaynak"), dict) else {}
        kayit = {"anahtar": f"{temel}#{i}", "tarih": dt.date.fromtimestamp(p.get("ilk_zaman") or p.get("zaman") or time.time()).isoformat(),
                 "platform": t.get("platform") or "x", "alan": t.get("alan") or "", "tur": t.get("karisim_tur") or t.get("bicim") or "",
                 "kaynak": kl.get("link") or t.get("paylas_link") or "", "ghost_metni": t.get("ilk_metin") or t.get("metin") or "",
                 "son_metin": t.get("metin") or "", "gelen_oneri": o["id"] if o else ""}
        if t.get("gizli"):
            if t.get("degistirildi") or str(t.get("red_nedeni") or "").startswith(("kalite kapısı", "daha güçlü", "gelen önerinin yeni")) or t.get("geri_getirildi"):
                continue                                              # sistemin kararı, kişinin reddi değil
            if t.get("red_nedeni"):
                out["reddedilen"].append({**kayit, "neden": t.get("red_nedeni"), "neden_metni": str(t.get("neden_metin") or "")[:600]})
                sonuc[kayit["gelen_oneri"]] = "reddetti"
            continue
        if t.get("paylasildi"):
            if t.get("oto_tanindi"):
                out["sistem_eslestirdi"].append({**kayit, "not": "X'te benzer gönderi bulundu; kişi onaylamadı"})
            else:
                out["paylasilan"].append({**kayit, "duzeltildi": bool(t.get("duzenlendi")), "neden_iyi": t.get("neden_iyi") or ""})
                sonuc[kayit["gelen_oneri"]] = "paylasti"
        if t.get("duzenlendi") and t.get("ilk_metin") and _norm(t["ilk_metin"]) != _norm(t.get("metin")):
            out["duzeltilen"].append({**kayit, "yorumlar": [y.get("yorum") for y in t.get("yorumlar") or [] if isinstance(y, dict)][-3:]})
            sonuc.setdefault(kayit["gelen_oneri"], "duzeltti")
        if t.get("begendi"):
            out["secilen"].append(kayit)
            sonuc.setdefault(kayit["gelen_oneri"], "secti")
    for d in oneriler.values():
        if (d.get("alinma") or 0) < time.time() - gun * 86400:
            continue
        o = d.get("ozgun") or {}
        k = d.get("karar") or {}
        blog = next((s["blog"] for s in reversed(d.get("surumler") or []) if s.get("blog")), None)
        out["oneriler"].append({"id": d["id"], "uretici": o.get("uretici"), "tarih": o.get("tarih"), "kaynak": o.get("kaynak_url"), "orijinal": o.get("metin"),
                                "not": o.get("not"), "arastirma_notu": o.get("arastirma_notu"), "ghost_format": k.get("format"), "ghost_neden": k.get("neden"),
                                "tekrar": (d.get("tekrar") or {}).get("neden", ""), "blog_ghost": (blog or {}).get("metin", ""),
                                "blog_kisi": (blog or {}).get("kisi_metni", ""),
                                "kisinin_sonucu": "blogu duzeltti" if (blog or {}).get("kisi_metni") else
                                ("geçti: " + d["kisi_karari"]["neden"]) if (d.get("kisi_karari") or {}).get("karar") == "gec" else sonuc.get(d["id"], "dokunmadi")})
    return out


def disa_md(v):
    """Aynı içerik okunur metin olarak (ChatGPT'ye yapıştırmak için); bölümler ayrı başlıklarda."""
    s = [f"# Ghost: kullanıcının tercihleri ({v['uretim'][:10]}, son {v['gun']} gün)", "",
         "Bu dosyadaki metinleri yalnız kişinin AÇIK eylemleri belirler. Reddedilenler ayrı bölümdedir; onları örnek olarak kullanma.", ""]

    def bolum(baslik, L, fn):
        s.append(f"## {baslik} ({len(L)})")
        s.append("")
        s.extend(fn(x) for x in L) if L else s.append("_yok_")
        s.append("")
    bolum("Seçtikleri", v["secilen"], lambda x: f"- [{x['tarih']} · {x['platform']}] {x['son_metin']}")
    bolum("Düzelttikleri", v["duzeltilen"], lambda x: f"- [{x['tarih']}] Ghost: {x['ghost_metni']}\n  Kişi: {x['son_metin']}")
    bolum("Paylaştığını onayladıkları", v["paylasilan"], lambda x: f"- [{x['tarih']} · {x['platform']}] {x['son_metin']}")
    bolum("Gelen öneriler ve sonuçları", v["oneriler"], lambda x: f"- [{x['tarih'] or '-'} · {x['uretici']}] {x['orijinal'][:300]}\n  Ghost: {x['ghost_format'] or '-'}"
          f" ({(x['ghost_neden'] or '')[:160]}) · Kişi: {x['kisinin_sonucu']}" + (f" · Kaynak: {x['kaynak']}" if x["kaynak"] else ""))
    bolum("Reddettikleri (örnek değil)", v["reddedilen"], lambda x: f"- [{x['tarih']}] {x['son_metin']}\n  Neden: {x['neden']}" + (f" ({x['neden_metni']})" if x["neden_metni"] else ""))
    bolum("Sistemin eşleştirdikleri (kişi onaylamadı)", v["sistem_eslestirdi"], lambda x: f"- [{x['tarih']}] {x['son_metin']}")
    return "\n".join(s)
