"""paylasim.py - Videodaki değerli bakış açılarından kullanıcının kendi sesiyle X (Twitter) paylaşım taslakları.

İlke: Her videoda zorla paylaşım üretilmez; gerçekten paylaşmaya değer en çok 3 konu seçilir (hiç yoksa boş döner).
Taslaklar kullanıcının kendi fikri/araştırması gibi okunur: videoya atıf yok ("bu videoda" denmez), ama istenirse
kaynak linki ayrı bir alanda verilir. Tarz profili: profil/x.json (tarz notu + kullanıcının yapıştırdığı örnek
paylaşımlar; Ayarlar → "X paylaşım tarzı"). Uzunluk konuya göre: kısa (≤280 karakter) ya da uzun (Premium; 600-1800).

uret(json, log) → [{"konu", "metin", "uzunluk": "kisa|uzun", "link_oner": bool, "neden"}]; veri["paylasim"] = {...}
Elle: python paylasim.py transkript_x.json
"""
import json
import re
from urllib.parse import urlparse
import sys
import time
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
sys.path.insert(0, str(KLASOR))
PROFIL = KLASOR / "profil" / "x.json"

VARSAYILAN_TARZ = (
    "Birinci tekil şahıs, sakin ve kendinden emin. Büyük resmi gören, hype'a hemen kapılmayan, bir şeyin başını ve sonunu "
    "düşünen biri. Açılışı konuya göre seçer (somut ayrıntı, doğrudan görüş, kısa sahne ya da espri); gereksiz giriş yapmaz. "
    "Emoji ve hashtag kullanmaz. 'Bence' bir görüşü sahiplenmek için yerinde kullanılır. Terimleri olduğu gibi kullanır "
    "(Türkçe içinde İngilizce iş terimleri doğal). Neyden bahsettiğini adıyla söyler; okur bağlamı bilmese de anlar. "
    "Tek ana düşünce; uzunluk düşünce kadar, düşünce bitince durur."
)


def profil():
    """Tüm profil (x.json) + varsayılanlar. 2026-10-18'den beri kullanıcının gerçek X gönderilerinden kurulu (kimlik, alanlar, tarz, örnekler)."""
    try:
        p = json.loads(PROFIL.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        p = {}
    p["tarz"] = (p.get("tarz") or "").strip() or VARSAYILAN_TARZ
    p["ornekler"] = [o for o in (p.get("ornekler") or []) if str(o).strip()][:20]
    p["takip_otomatik"] = bool(p.get("takip_otomatik", True)); p["her_video"] = bool(p.get("her_video", True))
    for an in ("alanlar", "kacin", "paylasilan", "reddedilen", "begenilen"):
        p[an] = p.get(an) or []
    p["kimlik"] = p.get("kimlik") or ""
    p["persona"] = p.get("persona") if isinstance(p.get("persona"), dict) else {}
    return p


# Editörlük kararları (2026-10-25; kullanıcının ChatGPT ile yaptığı değerlendirme: "cümlelerin biçiminden önce editörlük kararları: neyi söylemeye değer
# buluyor, hangi ayrıntıyı koruyor, nerede gerekçe arıyor, espriyi nerede açıklamadan bırakıyor, metni ne zaman bitiriyor"). Her yazım çağrısına girer.
EDITORLUK = """EDİTÖRLÜK KARARLARI (cümle biçiminden önce bunlar):
- Somut işi ya da olguyu söyle; kendini ya da işi değerlendiren sıfat ekleme ('vizyoner', 'heyecanla'). Kendini küçültme de ('ufak bir şey ama').
- Keskinlik cümleyi sertleştirmekten değil, belirleyici ayrımı bulmaktan gelir: ne çalışıyor, hangi iddia henüz sınanmadı, hangi koşulda fikir değişir.
  Şüpheyi otomatik tavır yapma; kanıtın sınırını göster.
- Büyük resmi gör ama metne yalnızca işine yarayan kadarını taşı. Bir duyuruyu geleceğin ekonomisi üzerine hükme çevirme.
- Sıcaklık ilişkiye göre: tanıdığına yazarken doğal sıcaklık yerinde; asistandan beklediği mesafeyi başkalarına yazdığı metne taşıma.
- Mizahı bağlamdan çıkar, espriyi açıklayarak tüketme. Bir kez işleyen espriden kural çıkarma.
- Kullanılan aracı (yapay zekâ dahil) metnin konusu ve okurun ihtiyacı kadar an.
- Türkçe düşün: kimin ne yaptığını fiille söyle, soyut isim yığma, İngilizce cümle sırasını Türkçe kelimelerle kurma; doğal kullanılan teknik sözcüğü zorla Türkçeleştirme.
- Her cümlenin ayrı işi olsun (bağlam, ayrıntı, sonuç); aynı düşünceyi iki kez söyleme. İlişki kuran bir cümle uzun olabilir.
- Düşünce bitince dur: genel ders, büyük gelecek cümlesi, özet ya da yapay bir soruyla kapatma. Gerçek bir soru ya da sonuç varsa söyle.
- Kısaltırken anlamı koru: ayırt edici özelliği, kullanım koşulunu, iddianın sınırını ve görüşün sahibini silme; tekrar eden açıklamayı, gösterişi ve
  eklenmiş büyük hikâyeyi çıkar.
- Görüş başkasınınsa onun olduğu belli olsun; başkasının düşüncesini kişiye mal etme."""


VARSAYILAN_ALANLAR = ("futbol", "futbol_teknoloji", "kreatif", "reklamcilik", "toplum", "populer_kultur", "hikaye", "gusto", "teknoloji_ai", "kendi_arac")


def alan_kodlari(ayrac=" | ", haric=()):
    """Profildeki alan kodları (istemlerde liste olarak; 26 Ekim: alanlar her istemde elle yazılıydı, yeni alan eklenince unutuluyordu)."""
    try:
        L = [a["kod"] for a in profil().get("alanlar") or [] if isinstance(a, dict) and a.get("kod")]
    except Exception:  # noqa: BLE001
        L = []
    return ayrac.join(k for k in (L or VARSAYILAN_ALANLAR) if k not in haric)


def _persona_blogu(pr, kisa=False, konu="", is_turu=None, platform="x", rehber=True):
    """Kullanıcının kendi tarif ettiği ses (profil/persona.md özetlenmiş hali, x.json 'persona') + editörlük kararları + kendi rehberinin
    bu metne uyan parçaları (ghost_rehber; 2026-10-26). Referans kadrosu artık bütün halinde girmez: rehber konuya uyan en çok 3 özelliği seçer
    ("bütün referans kadrosunu her taslağa yükleme"). rehber=False: okur gibi yalnız puanlayan çağrılar (onlara ghost_rehber.okur_blogu girer)."""
    import ghost_rehber
    ps = pr.get("persona") or {}
    b = (f"OLMAK İSTEDİĞİ SES: {ps.get('karakter', '')}\nSESİN MERKEZİ: {ps.get('merkez', '')}\nYAZI İLKELERİ:\n" + "\n".join(f"- {x}" for x in ps.get("ilkeler") or [])
         + "\n" if ps else "")
    b += EDITORLUK
    if rehber:
        b += "\n\nKENDİ REHBERİNDEN (bu metne uyan parçalar):\n" + ghost_rehber.blok(konu, is_turu, platform, kisa=kisa)
    return b


def profil_kaydet(tarz=None, ornekler=None, takip_otomatik=None, her_video=None, **ek):
    PROFIL.parent.mkdir(parents=True, exist_ok=True)
    p = profil()
    if tarz is not None:
        p["tarz"] = tarz.strip() or VARSAYILAN_TARZ
    if ornekler is not None:
        p["ornekler"] = [str(o).strip() for o in ornekler if str(o).strip()][:20]
    if takip_otomatik is not None:
        p["takip_otomatik"] = bool(takip_otomatik)
    if her_video is not None:
        p["her_video"] = bool(her_video)
    p.update({k: x for k, x in ek.items() if x is not None})
    PROFIL.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


# Geri bildirim türleri (2026-10-23; kullanıcının ChatGPT brifi: "'Bu ben değilim', 'bilgi yanlış', 'konu ilgimi çekmiyor', 'cümle kötü' ve 'bugün paylaşmak
# istemiyorum' farklı sinyallerdir; hepsini üslup tercihi diye kaydetme"). Kaldır menüsündeki neden → nereye öğrenilir.
RED_TURU = {"konu uymuyor": "konu", "açı zayıf": "aci", "ben değilim": "ses", "yazım benzemiyor": "yazim", "yazım kötü": "yazim", "bilgi yanlış": "bilgi", "bugün değil": "", "": ""}


def red_kaydet(taslak, neden):
    """Kaldırılan taslaktan yalnızca kendi türünde öğren. Döner: tür ('' = hiçbir şey öğrenilmedi)."""
    tur = RED_TURU.get(str(neden or "").strip(), "konu" if "konu" in str(neden) else "")
    kayit = {"konu": taslak.get("konu", ""), "ilk": taslak.get("metin", "")[:900], "neden": str(neden or "")[:120], "tur": tur, "zaman": time.time()}
    if tur in ("konu", "aci", "ses", "yazim"):
        ogren("reddedilen", kayit)
    elif tur == "bilgi":
        pr = profil(); profil_kaydet(bilgi_hatalari=([x for x in pr.get("bilgi_hatalari") or [] if isinstance(x, dict)] + [kayit])[-40:])
    return tur


def red_geri_al(taslak):
    """Kaldırma geri alındı (2026-10-27, elden geçirmede 'Geri al'): o taslaktan öğrenilen ret kaydı silinir."""
    ilk = str(taslak.get("metin") or "")[:900]
    pr = profil()
    for an in ("reddedilen", "bilgi_hatalari"):
        L = [x for x in pr.get(an) or [] if not (isinstance(x, dict) and x.get("ilk") == ilk)]
        if len(L) != len(pr.get(an) or []):
            profil_kaydet(**{an: L})


HAVUZ = KLASOR / "profil" / "ornek_havuzu.json"


def havuz():
    try:
        return json.loads(HAVUZ.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []


def havuza_ekle(taslak):
    """ONAYLI örnek: yalnızca kullanıcı 'Evet, paylaştım' dediğinde (kopyalamak, sessiz kalmak ya da taslak beğenilmiş sayılmaz). Bağlamıyla saklanır:
    tür (taraftar, ironi, haber...), platform, alan, kaynak, düzeltilip düzeltilmediği; 'neden' isteğe bağlı (kullanıcı tek dokunuşla ekler)."""
    L = [x for x in havuz() if x.get("metin") != taslak.get("metin")]
    L.append({"metin": str(taslak.get("metin") or "")[:2000], "platform": taslak.get("platform") or "x",
              "tur": taslak.get("karisim_tur") or taslak.get("bicim") or "", "alan": taslak.get("alan") or "", "konu": str(taslak.get("konu") or "")[:200],
              "kaynak": (taslak.get("kaynak") or {}).get("tur", "") if isinstance(taslak.get("kaynak"), dict) else "",
              "duzenlendi": bool(taslak.get("duzenlendi")), "ilk_metin": str(taslak.get("ilk_metin") or "")[:2000] if taslak.get("duzenlendi") else "",
              "neden": "", "zaman": time.time()})
    HAVUZ.parent.mkdir(parents=True, exist_ok=True)
    HAVUZ.write_text(json.dumps(L[-300:], ensure_ascii=False, indent=1), encoding="utf-8")


def havuz_neden(metin, neden):
    L = havuz()
    for x in L:
        if x.get("metin") == metin:
            x["neden"] = str(neden or "")[:120]
    HAVUZ.write_text(json.dumps(L, ensure_ascii=False, indent=1), encoding="utf-8")


def havuz_ornekleri(tur="", platform="x", n=4):
    """Bağlamı uyan onaylı örnekler: aynı tür ve platform önce; tek örnek evrensel kalıp olmasın diye en yeniler ve farklı alanlardan, en çok n."""
    L = [x for x in havuz() if (x.get("platform") or "x") == platform]
    uyan = [x for x in L if tur and x.get("tur") == tur][::-1]
    diger = [x for x in L if x not in uyan][::-1]
    out, alanlar = [], set()
    for x in uyan + diger:
        if len(out) >= n:
            break
        if x.get("alan") in alanlar and len(L) > n:
            continue
        alanlar.add(x.get("alan")); out.append(x)
    return out


def _red(pr, tur):
    """Belirli türdeki reddedilenler (eski kayıtlarda tür yoksa nedenden çıkarılır)."""
    out = []
    for r in pr.get("reddedilen") or []:
        if not isinstance(r, dict):
            continue
        t = r.get("tur") or RED_TURU.get(str(r.get("neden") or ""), "konu" if not r.get("neden") or "konu" in str(r.get("neden")) else "")
        if t == tur:
            out.append(r)
    return out


def ogren(tur, kayit):
    """Geri bildirim: 'paylasilan' (kullanıcının paylaştığı son metin; en güçlü örnek) ya da 'reddedilen' ({konu, ilk, neden})."""
    p = profil()
    L = [x for x in p[tur] if x != kayit] + [kayit]
    profil_kaydet(**{tur: L[-30:]})


def begeni(taslak, var=True):
    """Elden geçirirken 'Kalsın' (2026-10-27): zayıf olumlu sinyal; aynı metin bir kez, geri alınınca silinir (son 30)."""
    m = str(taslak.get("metin") or "")[:900]
    L = [x for x in profil().get("begenilen") or [] if isinstance(x, dict) and x.get("metin") != m]
    if var:
        L.append({"metin": m, "tur": taslak.get("karisim_tur") or taslak.get("bicim") or "", "alan": taslak.get("alan", ""), "zaman": time.time()})
    profil_kaydet(begenilen=L[-30:])


def _model_sor(istem, json_bekle=True, num_predict=2500):
    """Önce Claude (abonelikle, giriş yapılmışsa), olmazsa bilgisayardaki model."""
    import claude_yaz
    if claude_yaz.hazir():
        try:
            return claude_yaz.sor(istem, "Yanıtın YALNIZCA geçerli bir JSON nesnesi olsun; açıklama yazma." if json_bekle else "", zaman_asimi=300)
        except Exception:  # noqa: BLE001
            pass
    import marka
    return marka._sor_ham(istem, 16384, num_predict, json_bekle)


_CAGRI = []                 # (zaman, model): taslağı GERÇEKTE hangi model yazdı (25 Ekim; eskiden varsayılan model adı yazılıyordu)
_CAGRI_KILIT = __import__("threading").Lock()


def _cagri_yaz(model):
    with _CAGRI_KILIT:
        _CAGRI.append((time.time(), model))
        del _CAGRI[:-400]


def _yazan(bas=None):
    """bas verildiyse o andan beri yanıt veren modeller (ör. 'claude:opus+sonnet', Claude düştüyse 'yerel:gemma3:4b'); yoksa şu anki varsayılan."""
    if bas is not None:
        with _CAGRI_KILIT:
            M = [m for t, m in _CAGRI if t >= bas]
        if M:
            cl = sorted({m.split(":", 1)[1] for m in M if m.startswith("claude:")})
            yer = sorted({m for m in M if not m.startswith("claude:")})
            return "+".join(filter(None, ["claude:" + "+".join(cl) if cl else "", *yer]))
    import claude_yaz
    if claude_yaz.hazir():
        return "claude:" + claude_yaz.model()
    return __import__("marka").model_sec()


def _baglam(veri, segmentler):
    if veri.get("girdi_metin"):            # Ghost'a yapıştırılan yazı ya da fikir: transkript yok
        return (f"BAŞLIK: {veri.get('baslik') or '-'}\n", str(veri["girdi_metin"]))
    import marka
    return marka._baglam(veri, segmentler, en_cok_kelime=7000)


# ---------------------------------------------------------------- Ghost: doğrudan girdi (link, yazı, fikir)
GHOST = KLASOR / "ghost"
VIDEO_ALAN = re.compile(r"(youtube\.com|youtu\.be|vimeo\.com|instagram\.com|tiktok\.com|twitch\.tv|dailymotion\.com|facebook\.com/.*/videos|fb\.watch|"
                        r"loom\.com|spotify\.com/episode|podcasts\.apple\.com)", re.I)


def girdi_turu(girdi):
    """'video' | 'x' | 'yazi_link' | 'yazi' (uzun yapıştırılmış metin) | 'fikir' (kısa kendi düşüncesi)."""
    g = str(girdi or "").strip()
    if re.match(r"^https?://\S+$", g):
        if VIDEO_ALAN.search(g):
            return "video"
        if re.search(r"(^|//|\.)(x|twitter)\.com/", g):
            return "x"
        return "yazi_link"
    return "yazi" if len(g) > 600 else "fikir"


def sayfa_metni(url):
    """Makale linkinden başlık + düz metin (paragraflar). Okunamazsa ValueError."""
    import html as html_modulu
    import requests
    import abonelik
    r = abonelik.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
                                               "Accept-Language": "tr,en;q=0.8"})
    if r.status_code >= 400:
        raise ValueError(f"Sayfa açılmadı ({r.status_code}). Yazının metnini kopyalayıp yapıştırın.")
    h = r.text
    baslik = ""
    m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', h, re.I) or re.search(r"<title[^>]*>(.*?)</title>", h, re.I | re.S)
    if m:
        baslik = html_modulu.unescape(re.sub(r"\s+", " ", m.group(1))).strip()
    govde = re.sub(r"(?is)<(script|style|noscript|nav|footer|header|aside|form)\b.*?</\1>", " ", h)
    a = re.search(r"(?is)<article\b.*?</article>", govde)
    govde = a.group(0) if a and len(a.group(0)) > 1500 else govde
    paragraflar = [html_modulu.unescape(re.sub(r"<[^>]+>", " ", x)) for x in re.findall(r"(?is)<(?:p|h2|h3|li)\b[^>]*>(.*?)</(?:p|h2|h3|li)>", govde)]
    paragraflar = [re.sub(r"\s+", " ", x).strip() for x in paragraflar]
    metin = "\n".join(x for x in paragraflar if len(x) > 40)
    if len(metin) < 400:
        raise ValueError("Bu sayfanın metni okunamadı (giriş ya da abonelik isteyebilir). Yazının metnini kopyalayıp yapıştırın.")
    return baslik[:200], metin[:40000]


def ghost_kaydi(girdi, tur, baslik="", link="", metin="", deneyim="", ek=None):
    """ghost/<id>.json: transkript JSON'uyla aynı biçim (veri + boş segmentler); taslaklar veri.paylasim'a yazılır. Döner: temel ('ghost__<id>')."""
    import uuid
    GHOST.mkdir(exist_ok=True)
    kid = time.strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:4]
    if not baslik:
        ilk = re.split(r"(?<=[.!?…])\s", str(metin or girdi).strip())[0]
        baslik = (ilk[:80] + "…") if len(ilk) > 80 else ilk
    veri = {"baslik": baslik, "link": link, "ghost": True, "kaynak_tur": tur, "girdi_metin": str(metin or girdi)[:40000], "olusturma": time.time(),
            "deneyim": str(deneyim or "")[:2000], **(ek or {})}
    (GHOST / f"{kid}.json").write_text(json.dumps({"veri": veri, "segmentler": []}, ensure_ascii=False, indent=1), encoding="utf-8")
    return "ghost__" + kid



# Sınırlı düzenleme (2026-10-25; ChatGPT değerlendirmesi: "'Şöyle sadeleştirmiştim, bunu düzenle' dediğinde önünde zaten çok değerli bir karar var:
# neyi söyleyeceğini seçmiş. Düşünceyi, sırayı, gündelik ifadeleri koru; istenen eksiği ekle; maddi yanlışı düzelt; sonra dur. Kendi önceki önerine
# geri çekme"). İlk ölçüt: dublaj eklettirince metin yeniden özellik kataloğuna dönmesin.
DUZENLEME_ISTEGI = re.compile(r"\b(düzenle|düzelt|sadeleştir|toparla|elden geçir|kısalt|ekle|çıkar|cilala|parlat|iyileştir|son hali|"
                              r"şunu da|unutma|eksik|yerine)\w*", re.I)
BASTAN = re.compile(r"\b(baştan|sıfırdan|başka (bir )?açı|farklı (bir )?açı|yeniden yaz|tamamen değiştir)\w*", re.I)


def _norm_k(s):
    return re.sub(r"\W+", "", str(s or "").lower())


def taslak_ayir(girdi):
    """Yapıştırılan metin, kişinin KENDİ gönderi taslağı + düzenleme isteği mi? Döner (taslak, istek) ya da None. Taslak girdide harfi harfine
    geçmeli (model uydurmasın)."""
    g = str(girdi or "").strip()
    if len(g) < 60 or not DUZENLEME_ISTEGI.search(g):
        return None
    c = _claude_json("Aşağıdaki metin, bir kişinin kendi yazdığı bir sosyal medya gönderisi TASLAĞINI ve onu nasıl düzenletmek istediğine dair bir İSTEĞİ "
                     "birlikte içeriyor mu? İçeriyorsa taslak: taslağın kendisi, HARFİ HARFİNE (isteği ve tırnakları dahil etme); istek: ne istediği. "
                     "Metin bir fikir notu, makale ya da yalnızca bir istekse taslak boş kalsın.\n"
                     'JSON: {"taslak": "", "istek": ""}\n\nMETİN:\n' + g[:6000], model_adi="sonnet", zaman_asimi=120)
    t = str(c.get("taslak") or "").strip().strip('"“”')
    istek = str(c.get("istek") or "").strip()
    if len(t) < 30 or not istek or _norm_k(t)[:60] not in _norm_k(g):
        return None
    return t, istek


def sinirli_duzenle(metin, istek, pr=None, konu="", is_turu=None, kaynak=""):
    """Kişinin kendi metnine yalnızca istenen değişikliği yapar. Döner: {metin, notlar, degisim (0-1)}."""
    import difflib
    pr = pr or profil()
    c = _claude_json(f"{_ses_blogu(pr, konu or metin[:200], is_turu)}\n\n"
                     "Aşağıdaki metni BU KİŞİ yazdı; neyi söyleyeceğine ve nasıl söyleyeceğine o karar verdi. Görevin onu yeniden yazmak değil, yalnızca "
                     "istediği değişikliği yapmak:\n"
                     "- Düşünceyi, cümle sırasını ve bilinçli seçtiği gündelik ifadeleri koru; parlatma, resmîleştirme.\n"
                     "- İsteneni ekle ya da çıkar; eklediğin şey mevcut akışa bir yan cümle ya da kısa bir ifade olarak otursun. Özellik dökümüne, büyük "
                     "hikâyeye ya da yeni bir açıya çevirme; istemediği hiçbir şeyi geri getirme.\n"
                     "- Maddi bir yanlış ya da yazım hatası varsa düzelt. Başka bir şeye dokunma ve dur.\n"
                     f"{__import__('ghost_rehber').DUZENLEME}\n"
                     + (f"KAYNAK / BAĞLAM (olgular yalnızca buradan):\n{kaynak[:3000]}\n" if kaynak else "")
                     + f"İSTEĞİ: {istek}\n\nMETNİ:\n{metin}\n\n"
                     'JSON: {"metin": "...", "notlar": ["yaptığın her değişiklik, tek cümle"]}', model_adi="opus", zaman_asimi=240)
    yeni = re.sub(r"#\w+", "", str(c.get("metin") or "")).strip() if "#" not in metin else str(c.get("metin") or "").strip()
    if not yeni:
        raise ValueError("Düzenlenemedi")
    degisim = 1 - difflib.SequenceMatcher(None, metin, yeni).ratio()
    return {"metin": yeni, "notlar": [str(x)[:200] for x in c.get("notlar") or []][:5], "degisim": round(degisim, 2)}


def sinirli_mi(taslak, talimat):
    """Yorum, kişinin kendi düzenlediği metne ya da belirli bir küçük değişikliğe mi? (yeniden yazım yerine sınırlı düzenleme)"""
    if talimat in ("kisa", "keskin", "zincir", "tek") or BASTAN.search(talimat or ""):
        return False
    kendi = bool(taslak.get("ilk_metin")) and taslak.get("ilk_metin") != taslak.get("metin")
    return kendi or bool(DUZENLEME_ISTEGI.search(talimat or ""))


YASAK_ATIF = re.compile(r"\b(video(da|daki|yu|nun)?|izledi(ğim|m)|dinledi(ğim|m)|konuşmacı|podcast(te)?|programda|yayında)\b", re.I)
KLISE = re.compile(r"(sonuç şu|asıl ders|gerçek ders|haklı bir kaygı|diyenler var|bu tablo|çok daha rahatsız edici|kritik önem|önem taşı|"
                   r"oyunun kurallarını|yeni bir çağ|game.?changer|altını çiz|unutmamak gerek|şunu söylemek lazım|kısacası|özetle)", re.I)
DENEYIM = re.compile(r"(benim (akış|deneyim|gözlem|müşteri|ekib|ajans)\w*|gördüğüm kadarıyla|deneyimimde|denedim|kullandığımda|"
                     r"müşterilerim|bizim ajans|test ettim|bizzat|başıma geldi|tanıdığım|kurarken|öğrenmiştik|öğrendik|ajans tarafında|"
                     r"kendi (agent|ajan|sistem|akış|araç)\w*|çalıştığım|yaptığımız|bizde de|bizim tarafta|"
                     r"\w+(?:[dt][ae]n|lıktan|likten|luktan|lükten) biliyorum|yıllardır (gör|yaş|bil)\w*|sektörde (gör|yaş)\w*|tecrübeyle sabit)", re.I)
# 2026-10-22 (kullanıcı: "önerilen metinler hâlâ paylaşılabilir seviyede değil"): 86 gerçek gönderinin ortancası 232 karakter, %90'ı ≤280,
# 'Bence' ile başlayan 1, 'asıl ... değil' 2; taslakların hepsi 600-760 karakter ve 'Bence X'teki asıl ... değil' ile açılıyordu.
FORMUL = [
    # 25 Ekim (ChatGPT değerlendirmesi): 'bence' kelime yasağı kaldırıldı; sorun kelime değil tekrar ('aynı açılış' denetimi ve hakem yakalar)
    (r"\basıl (haber|mesele|karar|soru|iş|hikâye|konu|sorun|fark|ürün|satılan)\w*", "'asıl ...' çerçevesi kalıp gibi duruyor; kullanma"),
    # 25 Ekim: 'açıklamasına göre', 'iddiaya göre' çıkarıldı: beyanı kimin yaptığını söylemek kaynağa sadakat (ghost_kaynak); yalnız haberi özetleyen kalıplar kaldı
    (r"(haberine göre|haberlere göre|başlıklara göre|aktardığı habere göre|habere göre)", "haberi özetliyor; bağlantı kartı zaten gösteriyor, kendi gözlemini koy"),
    (r"\b(olmalı|gerekiyor|gerek)\b[^.]*\.\s*$", "öğüt/reçeteyle bitiyor; bu kişi ders vermez"),
    (r"\byok, çünkü\b|\bçünkü [^.]{0,40}\byok\.\s*$", "vecize gibi kapanış"),
    (r"\bbaşka, [^.]{0,60}\bbaşka\b", "'X başka, Y başka' karşıtlığı; yapay zekâ kalıbı"),
    (r"\b(\w{4,})(d[ıiuü])\b[^.]{0,30}\b\1m[ae]d[ıiuü]\b", "'X ucuzladı, Y ucuzlamadı' gibi simetrik karşıtlık; vecize kalıbı"),
]
# Birinci şahıs İŞ/DENEYİM iddiaları (2026-10-23; kullanıcının ChatGPT brifinden: "Transcript'e bir kapı ekledim gibi cümleler doğrulanmış bir geliştirmeye
# ya da kullanıcının beyanına dayanmalı"). Algı fiilleri ("dikkatimi çekti", "fark ettim") bağlantıya tepki olduğu için serbest.
BIRINCI_SAHIS = re.compile(r"\b(ekledim|ekledik|yaptım|yaptık|kurdum|kurduk|geliştirdim|geliştirdik|yazdım|yazdık|denedim|denedik|gördüm|okudum|izledim|"
                           r"çalıştım|çalıştık|tasarladım|ürettim|hazırladım|hazırladık|attım|gittim|konuştum|sordum|kullandım|kullanıyorum|yaşadım|"
                           r"yaşıyorum|müşterilerim\w*|ekibim\w*|projem\w*|ajansım\w*|bizim ekip\w*|bizde)\b", re.I)


def birinci_sahis_notu(metin, kanit=None):
    """Kanıtsız birinci şahıs iş/deneyim iddiası varsa not döner (yoksa ''). kanit: çalışma kaydı, kişinin beyanı ya da deneyimi."""
    bul = sorted({x.lower() for x in BIRINCI_SAHIS.findall(metin or "")})
    if bul and not kanit:
        return (f"Birinci şahıs iddia var ({', '.join(bul)}) ama dayanağı yok: kişi bunu söylemedi, çalışma kaydında da yok. Ona ait iş ya da deneyim "
                "gibi anlatma; gözlem ya da görüş olarak yaz.")
    return ""


GUN_ADI = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
# Türkçe yapay zekâ kokusu (Wikipedia "Signs of AI writing" + blader/humanizer kalıplarının Türkçe karşılıkları + bu projede görülenler).
# "X değil, Y" yeniden çerçevelemesi kullanıcının KENDİ hamlesi; yasak değil (yalnızca aynı gönderide iki kez kullanılırsa uyarı).
KOKU = [
    (r"\bsadece\b[^.!?]{0,60}\bdeğil\b[^.!?]{0,40}\baynı zamanda\b", "'sadece ... değil, aynı zamanda' kalıbı"),
    (r"\b(bu da gösteriyor ki|bu bize gösteriyor|işte tam da bu noktada|gerçek şu ki|bu bağlamda|son kertede|nihayetinde)\b", "çeviri/yapay zekâ bağlacı"),
    (r"\b(önemli bir rol oynuyor|kilit rol|dönüştürüyor|devrim niteliğinde|çığır açan|yeni bir dönem|oyun değiştirici|derinlemesine)\b", "şişirilmiş ifade"),
    (r"\b(sonuç olarak|kısacası|özetle|toparlamak gerekirse)\b", "makale kapanışı"),
    (r"(^|\n)\s*peki\b[^?\n]{0,80}\?", "'Peki ...?' retorik sorusu"),
    (r"\b\w+, \w+ ve \w+\b[^.]{0,20}\b\w+, \w+ ve \w+\b", "üçlü sıralama tekrarı"),
]


def _temiz(m):
    """Taslak metninin son temizliği: hashtag çıkar + kişinin rehberindeki anlamı değiştirmeyen dil düzeltmeleri (şapkalı a, düz yazıda '+')."""
    import ghost_rehber
    return ghost_rehber.dil_duzelt(re.sub(r"#\w+", "", str(m or "")))


def koku_notlari(m, ogrenilen=()):
    """Yapay zekâ kokusu (kodla, model yok): kalıplar + kullanıcının taslaklardan sık sildiği ifadeler."""
    n = []
    for desen, ad in KOKU:
        if re.search(desen, m, re.I | re.M):
            n.append(ad)
    if len(re.findall(r"\bdeğil\b[^.!?]{0,80}[.,]", m)) >= 2:
        n.append("'X değil Y' yapısı iki kez; bir kez yeter")
    for ifade in ogrenilen:
        if ifade and re.search(r"(?<!\w)" + re.escape(ifade) + r"(?!\w)", m, re.I):
            n.append(f"sık sildiğiniz ifade: '{ifade}'")
    return n


def sayi_notlari(m, kaynak):
    """Kodla olgu denetimi: gönderideki sayı/yıl/yüzde kaynakta geçmiyorsa uyarı (uydurma rakam riski). Kişinin kendi karşılığı kaynağa dahildir."""
    norm = lambda x: re.sub(r"[.,\s]", "", x)   # noqa: E731
    k = norm(str(kaynak or ""))
    out = []
    for sayi in re.findall(r"(?<![\w])%?\d[\d.,]*\s?(?:bin|milyon|milyar|%)?", m):
        cekirdek = re.sub(r"[^\d]", "", sayi)
        if len(cekirdek) >= 2 and cekirdek not in k:
            out.append(sayi.strip())
    return [f"kaynakta geçmeyen sayı: {x}" for x in dict.fromkeys(out)][:4]



def _claude_json(istem, model_adi=None, zaman_asimi=300):
    import claude_yaz
    import ozet as ozet_modulu
    if claude_yaz.hazir():
        try:
            c = claude_yaz.sor_json(istem, zaman_asimi=zaman_asimi, model_adi=model_adi)
            _cagri_yaz("claude:" + (model_adi or claude_yaz.model()))
            return c
        except Exception:  # noqa: BLE001
            pass
    c = ozet_modulu._json_coz(_model_sor(istem)) or {}
    _cagri_yaz("yerel:" + str(getattr(ozet_modulu, "SON_MODEL", "") or "model"))
    return c


DUR = set("ve ile ama için gibi daha çok bir bu şu o da de mi ki ne en her hiç kadar olarak olan olur oldu değil ise yani artık sonra önce bile hem "
           "the and of to in a is for on that with it this are be as at by an not".split())


def _kokler(t):
    """Kaba Türkçe kök: küçük harf, ilk 5 harf (sor.py ile aynı yaklaşım), durak sözcükler hariç."""
    t = str(t or "").replace("İ", "i").replace("I", "ı").lower()
    return {w[:5] for w in re.findall(r"[a-zçğıöşü0-9]{3,}", t) if w not in DUR}


def _gercek_gonderiler(pr):
    """Kullanıcının gerçek gönderileri: uzantının okuduğu X gönderileri + profil örnekleri + Ghost'tan paylaştıkları (tekrarsız, ≥40 karakter)."""
    L = []
    try:
        L = [x.get("metin") for x in json.loads((KLASOR / "profil" / "x_istatistik.json").read_text(encoding="utf-8")).values()]
    except Exception:  # noqa: BLE001
        pass
    L += list(pr.get("ornekler") or []) + [x for x in pr.get("paylasilan") or [] if isinstance(x, str)]
    gorulen, out = set(), []
    for m in L:
        m = str(m or "").strip()
        k = re.sub(r"\W+", "", m.lower())[:60]
        if len(m) >= 40 and k not in gorulen:
            gorulen.add(k); out.append(m)
    return out


# Örnekleri metnin İŞİNE göre seçmek (2026-10-25; ChatGPT değerlendirmesi: "iki metnin ikisi de AI hakkında olabilir; biri ürün duyurusu, diğeri şüpheli
# bir iddiaya eleştiri. Önce aynı işi yapan örnekleri seç: duyuruya duyuru, alıntı yoruma alıntı yorum"). Gerçek gönderiler bir kez sınıflanır (sonnet).
IS_TURLERI = {"duyuru": "kendi yaptığı işi, ürünü ya da haberini duyurur", "tepki": "bir habere, bağlantıya ya da içeriğe tepki",
              "alinti": "başka birinin gönderisine alıntı yorumu", "yanit": "birine yanıt", "gozlem": "bağımsız gözlem ya da görüş",
              "espri": "espri, ironi, tek satır", "taraftar": "takım/maç üzerine taraftar sesi", "dusunce": "birkaç paragraflık düşünce yazısı"}
ORNEK_TUR = KLASOR / "profil" / "x_ornek_turleri.json"
_TUR_SINIFLANIYOR = []


def _ornek_anahtar(m):
    import hashlib
    return hashlib.sha1(re.sub(r"\W+", "", str(m).lower())[:200].encode()).hexdigest()[:12]


def ornek_turleri(pr=None, siniflandir=False, log=print):
    """{gönderi metni: iş türü}. siniflandir=True ise sınıflanmamış gönderiler sonnet'e verilir (60'lık gruplar); yoksa yalnız önbellek okunur ve
    eksik varsa sınıflama arka planda bir kez başlatılır (yazım beklemez)."""
    pr = pr or profil()
    G = _gercek_gonderiler(pr)
    try:
        D = json.loads(ORNEK_TUR.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        D = {}
    eksik = [m for m in G if _ornek_anahtar(m) not in D]
    if eksik and not siniflandir:
        if not _TUR_SINIFLANIYOR:
            _TUR_SINIFLANIYOR.append(1)
            __import__("threading").Thread(target=lambda: ornek_turleri(pr, True, log=lambda *_: None), daemon=True).start()
    elif eksik:
        for i in range(0, len(eksik), 60):
            P = eksik[i:i + 60]
            c = _claude_json("Aşağıda bir kişinin kendi X gönderileri var. Her birinin İŞİNİ (konusunu değil) şu türlerden biriyle etiketle:\n"
                             + "\n".join(f"- {k}: {v}" for k, v in IS_TURLERI.items())
                             + '\nJSON: {"turler": [{"no": 0, "tur": "gozlem"}]}\n\n' + "\n\n".join(f"[{j}] {m[:700]}" for j, m in enumerate(P)),
                             model_adi="sonnet", zaman_asimi=240)
            for x in c.get("turler") or []:
                try:
                    if x.get("tur") in IS_TURLERI:
                        D[_ornek_anahtar(P[int(x.get("no"))])] = x["tur"]
                except (TypeError, ValueError, IndexError):
                    continue
        ORNEK_TUR.write_text(json.dumps(D, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"Örnek gönderiler türlerine ayrıldı: {len(eksik)} yeni")
    return {m: D.get(_ornek_anahtar(m)) for m in G}


def _ornekler(pr, en_cok=12, konu="", is_turu=None):
    """Ses örnekleri: iş türü verildiyse önce AYNI İŞİ yapan gerçek gönderiler (içlerinde konuya yakın olan önce), sonra konuya en benzer
    gönderiler (kelime kökü örtüşmesi), sonra paylaştıkları ve profil örnekleri. Örnekler kırpılmaz."""
    paylasilan = [x for x in pr.get("paylasilan") or [] if isinstance(x, str)][-6:]
    temel = paylasilan[::-1] + [o for o in pr.get("ornekler") or [] if o not in paylasilan]
    if not konu and not is_turu:
        return temel[:en_cok]
    hedef = _kokler(konu)
    G = _gercek_gonderiler(pr)
    ayni = []
    if is_turu:
        T = ornek_turleri(pr)
        ayni = sorted((m for m in G if T.get(m) == is_turu), key=lambda m: -len(hedef & _kokler(m)))[: en_cok // 2]
    puanli = sorted(((len(hedef & _kokler(m)), m) for m in G if m not in ayni), key=lambda x: -x[0])
    benzer = [m for p, m in puanli if p >= 2][: max(2, en_cok // 2 - len(ayni) // 2)]
    return (ayni + benzer + [m for m in temel if m not in ayni and m not in benzer])[:en_cok]


def taslak_is_turu(t):
    """Bir taslağın iş türü (örnek seçimi için)."""
    if t.get("yanit_to"):
        return "yanit"
    if t.get("alinti"):
        return "alinti"
    kt = t.get("karisim_tur")
    if kt:
        return {"taraftar": "taraftar", "ironi": "espri", "gorus": "gozlem", "haber": "tepki", "kendi": "duyuru", "akis": "alinti"}.get(kt, "gozlem")
    if t.get("platform") == "linkedin" or t.get("uzunluk") == "uzun":
        return "dusunce"
    if t.get("bicim") in ("emoji", "minik"):
        return "espri" if t.get("ton") == "eglenceli" else "tepki"
    return "tepki" if t.get("paylas_link") else "gozlem"


# ---------------------------------------------------------------- görüş defteri (kullanıcının savunduğu görüşler; tarihli, silinmez)
GORUS = KLASOR / "profil" / "gorusler.json"


def gorusler():
    try:
        return json.loads(GORUS.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []


def gorus_durumu(g):
    """onayli (kullanıcı onayladı) | kanitli (yayımlanmış gönderisinden sistemin çıkardığı; kanıt alıntısıyla) | red (kullanıcı 'benim görüşüm değil' dedi).
    2026-10-23: görüşler kullanıcı onayı olmadan kişiliğe dönüştürülmesin (ChatGPT brifi)."""
    if g.get("durum") in ("onayli", "kanitli", "red"):
        return g["durum"]
    return "onayli" if "onaylı" in str(g.get("kaynak") or "") else "kanitli"


def gorus_isaretle(gorus, islem, metin=""):
    """islem: onayla | red | duzelt (metin: görüşün kullanıcının kendi cümlesiyle hâli)."""
    L = gorusler()
    for g in L:
        if g.get("gorus") == gorus and not g.get("yerine"):
            if islem == "onayla":
                g["durum"] = "onayli"
            elif islem == "red":
                g["durum"] = "red"
            elif islem == "duzelt" and str(metin).strip():
                g["gorus_ilk"] = g.get("gorus_ilk") or g["gorus"]; g["gorus"] = str(metin).strip()[:400]; g["durum"] = "onayli"
            g["isaret_zaman"] = time.time()
    GORUS.write_text(json.dumps(L, ensure_ascii=False, indent=1), encoding="utf-8")


def ilgili_gorusler(konu, n=4):
    h = _kokler(konu)
    L = [(len(h & _kokler(g.get("konu", "") + " " + g.get("gorus", ""))), g) for g in gorusler() if not g.get("yerine") and gorus_durumu(g) != "red"]
    return [g for p, g in sorted(L, key=lambda x: -x[0]) if p >= 2][:n]


def gorus_defteri_kur(log=print):
    """Gerçek gönderilerden savunduğu görüşleri çıkarır (opus). Var olan defteri silmez; aynı konudaki eskiyi 'yerine' ile bağlar."""
    pr = profil()
    G = _gercek_gonderiler(pr)
    c = _claude_json("Aşağıda bir kişinin X'teki gerçek gönderileri var. Bu kişinin AÇIKÇA savunduğu görüşleri çıkar (haber aktarımı değil, kendi hükmü). "
                     "Her görüş: konu (2-5 kelime), gorus (onun hükmü, tek cümle, onun ifadesine sadık; sözünün sınırını AŞMA, genel ilke ya da danışmanlık "
                     "cümlesi ekleme: 'marka hikâyesi duygusal bağ kurmalıdır' gibi), alan (" + alan_kodlari() + "), kanit (gönderiden kısa alıntı, ≤120 karakter). Belirsiz/şaka/tek emojili gönderilerden "
                     'görüş çıkarma. En çok 40.\nJSON: {"gorusler": [{"konu": "...", "gorus": "...", "alan": "...", "kanit": "..."}]}\n\nGÖNDERİLER:\n'
                     + "\n---\n".join(m[:600] for m in G[:120]), model_adi="opus", zaman_asimi=400)
    yeni = [{**g, "tarih": time.strftime("%Y-%m-%d"), "kaynak": "x_gonderileri"} for g in c.get("gorusler") or [] if isinstance(g, dict) and g.get("gorus")]
    _gorus_yaz(yeni, log)
    return yeni


def _gorus_yaz(yeni, log=print):
    eski = gorusler()
    for g in yeni:
        for e in eski:
            if not e.get("yerine") and len(_kokler(e.get("konu", "")) & _kokler(g.get("konu", ""))) >= 2 and e.get("gorus") != g.get("gorus"):
                e["yerine"] = g.get("tarih")              # görüş değişti: eskisi silinmez, yenisine bağlanır
        if not any(e.get("gorus") == g.get("gorus") for e in eski):
            eski.append(g)
    GORUS.parent.mkdir(parents=True, exist_ok=True)
    GORUS.write_text(json.dumps(eski, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"Görüş defteri: {len([e for e in eski if not e.get('yerine')])} güncel görüş")


def gorus_ekle_paylasimdan(metin):
    """Paylaştığı bir gönderiden yeni görüşleri deftere ekler (sonnet; 0-2 görüş)."""
    c = _claude_json("Aşağıdaki gönderide yazarın AÇIKÇA savunduğu görüş varsa çıkar (en çok 2; yoksa boş). Her biri: konu (2-5 kelime), gorus (tek cümle, "
                     "onun sözüne sadık; genel ilke ya da öğüt EKLEME), alan, kanit (gönderiden HARFİ HARFİNE alıntı).\n"
                     'JSON: {"gorusler": []}\n\nGÖNDERİ:\n' + str(metin)[:2000], model_adi="sonnet")
    yeni = [{**g, "tarih": time.strftime("%Y-%m-%d"), "kaynak": "ghost_paylasim"} for g in c.get("gorusler") or [] if isinstance(g, dict) and g.get("gorus")]
    if yeni:
        _gorus_yaz(yeni)


def _norm_s(t):
    return re.sub(r"[^\w%]+", " ", str(t or "").replace("İ", "i").replace("I", "ı").lower()).strip()


def gorus_onar(log=print):
    """Görüş hafızasını kişinin ÖZGÜN sözüne bağlar (25 Ekim, ChatGPT değerlendirmesi: 'Super Furry Animals' görüşüne 'marka hikâyesi duygusal bağ
    kurmalıdır' gibi genel bir öğüt eklenmiş, kanıtı da başka bir gönderiden gelmişti). Her güncel görüş için: gerçek gönderilerinden en yakın 4'ü aday;
    sonnet ozgun (adaylardan HARFİ HARFİNE alıntı) + sadık özet (sözün sınırını aşmayan, öğütsüz) çıkarır; alıntı kodla doğrulanır. Özet değişirse eskisi
    `onceki_ozet`; dayanağı bulunamayan ve kanıtı uyuşmayan görüş `dayanak_yok` olur ve yazımda kullanılmaz. Döner: (onarılan, dayanaksız)."""
    pr = profil()
    P = _gercek_gonderiler(pr)
    D = gorusler()
    G = [g for g in D if not g.get("yerine")]
    onarilan = dayanaksiz = 0
    for b in range(0, len(G), 12):
        grup = G[b:b + 12]
        adaylar = []
        for g in grup:
            h = _kokler(str(g.get("gorus")) + " " + str(g.get("konu")) + " " + str(g.get("kanit")))
            adaylar.append([m for p_, m in sorted(((len(h & _kokler(m)), m) for m in P), key=lambda x: -x[0])[:4] if p_ >= 2])
        c = _claude_json(
            "Aşağıda bir kişinin görüş defterinden görüşler ve her biri için onun gerçek gönderilerinden adaylar var. Her görüş için:\n"
            "ozgun: adaylardan bu görüşü İFADE EDEN kısmı HARFİ HARFİNE kopyala (1-3 cümle; görüşü ifade eden aday yoksa boş).\n"
            "kanit_uyumlu: defterdeki mevcut 'kanit' bu görüşle aynı konuyu mu söylüyor (başka bir gönderiden/konudan geldiyse false).\n"
            "sadik_ozet: kişinin sözünün sınırını AŞMAYAN tek cümle özet; sözde olmayan genel ilke, öğüt, 'olmalıdır/gerekir' ya da genelleme EKLEME; somut "
            "ayrıntıyı (kişi, marka, olay) koru. Mevcut özet zaten sadıksa aynen yaz.\neklenen_genelleme: mevcut özet sözde olmayan genel bir ilke/öğüt "
            "ekliyor mu.\n"
            'JSON: {"gorusler": [{"no": 0, "ozgun": "", "kanit_uyumlu": true, "sadik_ozet": "...", "eklenen_genelleme": false}]}\n\n'
            + "\n\n".join(f"[{i}] GÖRÜŞ: {g.get('gorus')}\nKANIT: {g.get('kanit')}\nKAYNAK: {g.get('kaynak')}\nADAYLAR:\n"
                          + ("\n".join(f"  ({j}) {m[:700]}" for j, m in enumerate(adaylar[i])) or "  (aday yok)") for i, g in enumerate(grup)),
            model_adi="sonnet", zaman_asimi=300)
        for x in c.get("gorusler") or []:
            try:
                i = int(x.get("no")); g = grup[i]
            except (TypeError, ValueError, IndexError):
                continue
            oz = str(x.get("ozgun") or "").strip()
            if oz and not any(_norm_s(oz) in _norm_s(m) for m in adaylar[i]):
                oz = ""                                    # harfi harfine değilse alınmaz
            if oz:
                g["ozgun"] = oz[:600]
                if x.get("kanit_uyumlu") is False:
                    g["onceki_kanit"] = g.get("kanit"); g["kanit"] = oz[:300]      # başka gönderiden gelmiş kanıt yerine kendi sözü
            yeni = str(x.get("sadik_ozet") or "").strip()
            if yeni and yeni != g.get("gorus") and (x.get("eklenen_genelleme") or len(yeni) < len(str(g.get("gorus")))):
                g["onceki_ozet"] = g.get("gorus"); g["gorus"] = yeni[:300]; onarilan += 1
            if not oz and x.get("kanit_uyumlu") is False and g.get("kaynak") == "x_gonderileri":
                g["dayanak_yok"] = True; dayanaksiz += 1
            g["onarildi"] = time.strftime("%Y-%m-%d")
    tek = {}                                               # aynı özgün söze bağlanan ikinci görüş yineleme: eskisi yenisine bağlanır
    for g in [g for g in D if not g.get("yerine") and g.get("ozgun")]:
        k = _norm_s(g["ozgun"])[:200]
        if k in tek:
            g["yerine"] = time.strftime("%Y-%m-%d"); g["yineleme"] = True
        else:
            tek[k] = g
    GORUS.write_text(json.dumps(D, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"Görüş defteri onarıldı: {onarilan} özet sadeleşti, {dayanaksiz} görüşün dayanağı bulunamadı")
    return onarilan, dayanaksiz


def _gorus_blogu(konu):
    G = ilgili_gorusler(konu)
    if not G:
        return ""
    return ("GÖRÜŞLERİ (ilgiliyse dayan; tutarlı ol; görüşü değiştiyse bunu açıkça söyle). 'onaylı' = kendisi onayladı; 'gönderisinden' = yayımlanmış bir "
            "gönderisinden çıkarıldı, kanıtıyla; onu aynen tekrar etme, olduğundan güçlü ya da genel söyleme:\n"
            + "\n".join(f"- [{'onaylı' if gorus_durumu(g) == 'onayli' else 'gönderisinden'}] {g.get('konu')}: "
                         + (f"kendi sözü “{str(g.get('ozgun') or g.get('kanit'))[:220]}” (özet: {g.get('gorus')})" if (g.get("ozgun") or g.get("kanit")) else str(g.get("gorus")))
                         for g in G if not g.get("dayanak_yok")) + "\n")


# ---------------------------------------------------------------- dayanak kuralı: her taslak kişinin bir şeyine dayanmalı
def dayanak_belirle(veri, k, metin):
    """'kendi' (kişinin deneyimi/fikri), 'gorus' (defterdeki bir görüşüne dayanıyor) ya da '' (dayanaksız → soru sorulur)."""
    if veri.get("kaynak_tur") == "fikir" or str(veri.get("deneyim") or "").strip():
        return "kendi", ""
    G = ilgili_gorusler(f"{k.get('baglam', '')} {k.get('gorus', '')} {metin}", 1)
    if G and len(_kokler(metin) & _kokler(G[0].get("konu", "") + " " + G[0].get("gorus", ""))) >= 3:
        return "gorus", f"{G[0].get('konu')}: {G[0].get('gorus')}"
    return "", ""


def dayanak_sorusu(k, metin, pr):
    """Dayanaksız taslak için kişiye TEK soru: işinden/gözleminden bu konuya bağlanan somut bir karşılık (sonnet, ≤160 karakter)."""
    try:
        c = _claude_json(f"KİŞİ: {pr.get('kimlik')}\nAşağıdaki taslak gönderi bu kişinin kendi deneyimine ya da görüşüne dayanmıyor. Ona, gönderiyi "
                         "kendisine ait kılacak TEK bir soru sor: kendi işinden, bir projesinden, bir maçtan, bir kampanyadan ya da gündelik bir gözleminden "
                         "somut bir karşılık isteyen, bir cümleyle cevaplanabilecek, samimi bir soru (sen dili, ≤160 karakter). Genel 'ne düşünüyorsun' sorma.\n"
                         f'JSON: {{"soru": "..."}}\n\nKONU: {k.get("baglam", "")}\nTASLAK:\n{metin}', model_adi="sonnet", zaman_asimi=120)
        return str(c.get("soru") or "").strip()[:200]
    except Exception:  # noqa: BLE001
        return ""


def dayanakla_yaz(taslak, yorum):
    """Kişinin kendi karşılığıyla taslağı yeniden kurar (opus): gönderinin merkezi onun cümlesi olur; kaynak olgular dayanak olarak kalır."""
    pr = profil()
    platform = taslak.get("platform") or "x"
    c = _claude_json(f"{_ses_blogu(pr, taslak.get('konu', '') + ' ' + yorum, platform=platform)}\n{_gorus_blogu(taslak.get('konu', '') + ' ' + yorum)}\n"
                     f"Aşağıdaki {'LinkedIn yazısını' if platform == 'linkedin' else 'X gönderisini'} bu kişinin KENDİ KARŞILIĞI etrafında baştan kur. "
                     "Kişinin cümlesi gerçek ve onun; gönderinin merkezi o olsun (birinci tekil şahıs), konu ve kaynak olgular onu destekleyen bağlam olarak "
                     "kalsın. Cümlesini büyütme, ona deneyim/sayı/ad ekleme. Kurallar aynı: tek başına anlaşılır, konunun adı ilk iki cümlede, hashtag/emoji/kalıp yok."
                     + " Uzunluk düşünce kadar: kişinin cümlesi kısaysa metin de kısa kalabilir."
                     + f"\nKONU: {taslak.get('konu', '')}\nKAYNAK OLGULAR: {taslak.get('neden', '')}\nKİŞİNİN KARŞILIĞI: {yorum}\nMEVCUT TASLAK:\n{taslak.get('metin', '')}\n"
                     'JSON: {"metin": "...", "kancalar": ["...", "..."]}', model_adi="opus")
    m = _temiz(str(c.get("metin") or "")).strip()
    if not m:
        raise ValueError("Yazılamadı")
    return {"metin": m, "kancalar": [str(x).strip() for x in c.get("kancalar") or [] if str(x).strip()][:2], "zincir": [], "karakter": len(m),
            "uzunluk": "kisa" if len(m) <= 280 else "uzun", "dayanak": "kendi", "deneyim": yorum[:1000], "soru": "", "onceki": taslak.get("metin")}


def link_karari(json_yolu, log=print):
    """Kullanıcının Ghost'a verdiği bağlantı (makale ya da X gönderisi) için KARAR + son metin (2026-10-23; kullanıcı: "Ghost'a link attığımda ona bakıp ne
    diyerek paylaşacağını söyleyebilmeli; 'bunu alıntılayıp şöyle diyelim' ya da 'buradaki fikri bir tweete dönüştürelim' gibi karar verip final çıktıyı
    vermeli"). mod: alinti (bağlantı kartı ya da alıntı altta; TEPKİ dili) | fikir (içerikteki fikir onun sesiyle bağımsız gönderi; kaynak ilk yanıtta) |
    gec (paylaşmaya değmez, nedenini söyler). Ana metin + öbür yolun metni alternatif. Taslaklar veri.paylasim'a yazılır."""
    _bas = time.time()
    json_yolu = Path(json_yolu)
    d = json.loads(json_yolu.read_text(encoding="utf-8")); veri = d["veri"]
    pr = profil()
    link = str(veri.get("link") or "")
    tweet = veri.get("x_gonderi") if isinstance(veri.get("x_gonderi"), dict) else None
    icerik = (f"X GÖNDERİSİ (@{tweet.get('kullanici')}, {tweet.get('ad', '')}):\n{tweet.get('metin', '')}" if tweet
              else f"YAZI: {veri.get('baslik', '')}\n{str(veri.get('girdi_metin') or '')[:9000]}")
    konu_ipucu = (tweet or {}).get("metin", "") or veri.get("baslik", "")
    try:
        import karisim
        son7 = karisim.son_gunler(en_cok=30)
    except Exception:  # noqa: BLE001
        son7 = []
    c = _claude_json(
        f"{_ses_blogu(pr, konu_ipucu, 'alinti' if tweet else 'tepki')}\n{_gorus_blogu(konu_ipucu)}\n"
        "Bu kişi aşağıdaki içeriği X'te görmüş ve Ghost'a vermiş: bununla ne paylaşmalı? Önce KARAR ver, sonra son metni yaz.\n"
        "mod seçenekleri:\n"
        "- alinti: içeriği " + ("ALINTILAYARAK (quote)" if tweet else "BAĞLANTISIYLA") + " paylaşır; okur içeriği altta görür. Metin TEPKİ dilinde: içeriği özetleme, "
        "baştan kurma; içerikteki somut bir şeye bağlan ve kendi gözlemini/yorumunu koy. İçeriğin kendisi konuşulmaya değerse ve onun bir şey katabileceği "
        "netse bunu seç.\n"
        "- fikir: içerikteki FİKRİ kendi gönderisine dönüştürür (kaynak bağlantısı ilk yanıtta 'Kaynak:' ile verilir). İçerik bir fikre aracıysa, fikir tek başına "
        "daha güçlüyse ya da içerik takipçilerine uzaksa bunu seç. Metin SIFIRDAN dilde: konuyu kendisi kurar, okur içeriği görmeden anlamalı; içerikteki "
        "kişinin sözlerini kendisininmiş gibi söyleme, olgular içerikten.\n"
        "- gec: paylaşmaya değmez (söyleyeceği yeni bir şey yok, alanı dışında, eskimiş). O zaman metin boş, neden net.\n"
        "neden: tek cümle, ona hitaben ('Bunu alıntılayıp şunu söyleyin, çünkü…' / 'Buradaki fikri kendi gönderinize çevirin, çünkü…').\n"
        "metin: seçilen yolun SON metni (düşünce kadar; çoğu zaman 1-3 cümle, düşünce bitince dur). alternatif: ÖBÜR yolun metni (gec seçildiyse ikisi de "
        "boş olabilir). katki: onun bu içeriğe kattığı (tek cümle). Kurallar: kişiye ait deneyim/anı uydurma, uydurma olgu yok; okumadığın kısmı okumuş gibi "
        "ayrıntı ekleme. 'Bence' ya da 'dikkatimi çekti' yasak değil ama her metni onunla açma; okuma halini anlatan giriş ('okuyunca aklıma geldi') "
        "ancak ardından gerçekten ilginç bir ayrıntı geliyorsa. 'X'i göstermiyor, Y'yi gösteriyor' / 'asıl X değil Y' yapısı, vecize kapanış, hashtag yok.\n"
        + ("SON 7 GÜNDE YAZDIKLARI (aynı düşünceyi tekrar etme):\n" + "\n".join(f"- {x}" for x in son7) + "\n" if son7 else "")
        + 'JSON: {"mod": "alinti", "neden": "...", "metin": "...", "alternatif": "...", "katki": "...", "konu": "tek cümle", "alan": "kreatif"}\n\n' + icerik,
        model_adi="opus", zaman_asimi=300)
    mod = c.get("mod") if c.get("mod") in ("alinti", "fikir", "gec") else "alinti"
    karar = {"mod": mod, "neden": str(c.get("neden") or "").strip()[:300]}
    taslaklar = []
    alan_ad = {a.get("kod"): a.get("ad") for a in pr.get("alanlar") or [] if isinstance(a, dict)}

    def _taslak(metin, m_):
        metin = _temiz(str(metin or "")).strip()
        if not metin:
            return None
        notlar = _kalip_notlari(metin, []) + sayi_notlari(metin, icerik)
        if len(metin) > 900:
            notlar.append(f"{len(metin)} karakter; tekrar eden ya da düşünceye hizmet etmeyen kısımları at")
        if notlar:                                             # kod denetimi: bir noktasal düzeltme
            c2 = _claude_json(f"{_ses_blogu(pr, konu_ipucu)}\nAşağıdaki X gönderisinin YALNIZCA şu noktalarını düzelt, gerisine dokunma:\n"
                              + "\n".join(f"- {x}" for x in notlar) + f"\nİÇERİK:\n{icerik[:3000]}\nGÖNDERİ:\n{metin}\n" + 'JSON: {"metin": "..."}', model_adi="opus")
            metin = _temiz(str(c2.get("metin") or metin)).strip()
        t = {"platform": "x", "metin": metin, "karakter": len(metin), "konu": str(c.get("konu") or "")[:240], "katki": str(c.get("katki") or "")[:240],
             "alan": alan_ad.get(c.get("alan"), c.get("alan") or ""), "alan_kod": c.get("alan") or "", "bicim": "gozlem", "uzunluk": "kisa" if len(metin) <= 280 else "uzun",
             "kancalar": [], "zincir": [], "itirazlar": [], "iddialar": [], "panel": [], "kod_notlari": [], "dayanak": "", "neden": veri.get("baslik", ""),
             "karar": {**karar, "bu": m_, "ana": m_ == mod}, "link_oner": False, "ilk_yanit": "", "paylas_link": "", "okur": {},
             "kaynak": {"tur": "X gönderisi" if tweet else "yazı", "baslik": (tweet or {}).get("metin", "")[:160] if tweet else veri.get("baslik", ""), "tarih": "",
                        "link": link, "kanit": ""}}
        if m_ == "alinti":
            t["paylas_link"] = link; t["link_oner"] = True
            if tweet:
                t["alinti"] = {"id": tweet.get("id"), "kullanici": tweet.get("kullanici"), "metin": tweet.get("metin", "")[:400], "url": link}
        else:
            t["ilk_yanit"] = f"Kaynak: {link}" if link else ""
        return t
    if mod != "gec":
        ana = _taslak(c.get("metin"), mod)
        if ana:
            taslaklar.append(ana)
        alt = _taslak(c.get("alternatif"), "fikir" if mod == "alinti" else "alinti")
        if alt:
            taslaklar.append(alt)
    d = json.loads(json_yolu.read_text(encoding="utf-8"))
    d["veri"]["paylasim"] = {"taslaklar": taslaklar, "zaman": time.time(), "ilk_zaman": time.time(), "model": _yazan(_bas), "surum": 5, "karar": karar,
                             "elenen": ([{"konu": str(c.get("konu") or ""), "neden": karar["neden"], "son_metin": ""}] if mod == "gec" else [])}
    json_yolu.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"Link kararı: {mod} · {karar['neden'][:120]}")
    return karar, taslaklar


def alintiyla_yaz(taslak, tweet):
    """Taslağı, kullanıcının X'te açtığı bir gönderiyi ALINTILAYARAK paylaşılacak bir tepkiye çevirir (opus). Okur alıntılanan gönderiyi altında görür."""
    pr = profil()
    c = _claude_json(f"{_ses_blogu(pr, taslak.get('konu', '') + ' ' + tweet.get('metin', ''), 'alinti')}\n{_gorus_blogu(taslak.get('konu', ''))}\n"
                     "Bu kişi aşağıdaki X gönderisini ALINTILAYARAK (quote) paylaşacak; okur alıntılanan gönderiyi metnin altında görecek. Taslağı o gönderiye "
                     "bir TEPKİ olarak yeniden yaz: alıntılanan gönderiyi özetleme ya da tekrar etme, üstüne kendi hükmünü/bakışını koy; gerekiyorsa taslaktaki "
                     "bağlamı kullan. Alıntılanan kişiye saygılı ol, alay etme. Uzunluk düşünce kadar, çoğu zaman kısa. Hashtag/emoji/kalıp yok, uydurma olgu yok.\n"
                     f"ALINTILANAN (@{tweet.get('kullanici', '')}): {tweet.get('metin', '')}\nKONU: {taslak.get('konu', '')}\nMEVCUT TASLAK:\n{taslak.get('metin', '')}\n"
                     'JSON: {"metin": "...", "kancalar": ["...", "..."]}', model_adi="opus")
    m = _temiz(str(c.get("metin") or "")).strip()
    if not m:
        raise ValueError("Yazılamadı")
    url = f"https://x.com/{tweet.get('kullanici')}/status/{tweet.get('id')}"
    return {"metin": m, "kancalar": [str(x).strip() for x in c.get("kancalar") or [] if str(x).strip()][:2], "zincir": [], "karakter": len(m),
            "uzunluk": "kisa" if len(m) <= 280 else "uzun", "alinti": {"url": url, "kullanici": tweet.get("kullanici"), "metin": str(tweet.get("metin", ""))[:400]},
            "paylas_link": url, "onceki": taslak.get("metin")}


def _gelisim_acik(ad):
    try:
        import ghost_gelisim
        return ghost_gelisim.acik(ad)
    except Exception:  # noqa: BLE001
        return True


def _gelisim_blogu(yer):
    """Haftalık öz değerlendirmenin notları ve deneyi (ghost_gelisim.py); yoksa ''."""
    try:
        import ghost_gelisim
        return ghost_gelisim.blok(yer)
    except Exception:  # noqa: BLE001
        return ""


def _ses_blogu(pr, konu="", is_turu=None, platform="x"):
    dersler = [d for d in pr.get("duzeltme_dersleri") or [] if isinstance(d, str)]
    # 2026-10-26 (kişinin rehberi, 13. bölüm): okur verisi ve tek örnekten çıkan ders hipotezdir; ilkelerle çelişirse ilke önce gelir
    return (f"KİM: {pr.get('kimlik') or '-'}\nYAZIM TARZI (geçmiş gönderilerinin tarifi; kural değil, ilkelerle çelişirse ilke önce gelir): {pr['tarz']}\n"
            f"{_persona_blogu(pr, konu=konu, is_turu=is_turu, platform=platform)}\n"
            + ("KİŞİNİN TASLAKLARDA YAPTIĞI DÜZELTMELERDEN ÖĞRENİLENLER (bunlara mutlaka uy):\n" + "\n".join(f"- {d}" for d in dersler) + "\n" if dersler else "")
            + ("BU KONUYA YAKIN DÜZELTMELERİNDEN ÇIKAN TERCİHLERİ (kapsamı uyuyorsa uy; başka tür metne zorla taşıma; 'beklenmedik/taze' tercihi kaynağın "
               "desteklemediği şaşırtıcı yorum izni değil):\n"
               + "\n".join(f"- {t['tercih']}" + (f" (kapsam: {t['kapsam']})" if t.get("kapsam") else "") for t in ilgili_tercihler(konu, is_turu=is_turu)) + "\n"
               if konu and ilgili_tercihler(konu, is_turu=is_turu) else "")
            + ("OKURUN GERÇEK TEPKİSİNDEN ÖĞRENİLENLER (X'teki görüntülenme ve etkileşim verisinden; HİPOTEZ: görüntülenme beğeni değildir, tek örnekten "
               "kural çıkarma, her içerik bütün takipçi gruplarına hitap etmek zorunda değil; yazı ilkeleriyle çelişirse, ör. 'asıl haber bu değil' "
               "çerçevesi, ilke önce gelir):\n" + "\n".join(f"- {d}" for d in pr.get("performans_dersleri") or []) + "\n"
               if pr.get("performans_dersleri") else "")
            + ("'BU BEN DEĞİLİM' DEDİĞİ TASLAKLAR (bu bakış ve duruş ona ait değil; benzerini yazma):\n" + "\n".join(f"- {r['ilk'][:500]}" for r in _red(pr, "ses")[-5:]) + "\n"
               if _red(pr, "ses") else "")
            + ("YAZIMINI KÖTÜ BULDUĞU TASLAKLAR (bu cümle kuruluşundan kaçın):\n" + "\n".join(f"- {r['ilk'][:500]}" for r in _red(pr, "yazim")[-5:]) + "\n"
               if _red(pr, "yazim") else "")
            + ("ELDEN GEÇİRİRKEN 'KALSIN' DEDİKLERİ (paylaşmadı ama bu yönü beğendi; zayıf sinyal, kalıp yapma):\n"
               + "\n".join(f"- {x.get('metin', '')[:400]}" for x in [b for b in pr.get("begenilen") or [] if isinstance(b, dict)][-4:]) + "\n"
               if [b for b in pr.get("begenilen") or [] if isinstance(b, dict)] else "")
            + ("GHOST'TAN SEÇİP PAYLAŞTIKLARI (onaylı; bağlamı ve varsa neden beğendiğiyle; tek birini kalıp yapma):\n"
               + "\n".join(f"- ({x.get('tur') or '-'}, {x.get('alan') or '-'}{', düzelterek' if x.get('duzenlendi') else ''}{', neden: ' + x['neden'] if x.get('neden') else ''}) {x['metin'][:900]}"
                            for x in havuz_ornekleri(n=4)) + "\n" if havuz() else "")
            + _gelisim_blogu("yazim")
            + "KENDİ GÖNDERİLERİNDEN ÖRNEKLER (ses ve ritim böyle; uzunlukları ve açılışları kota ya da şablon değil; içlerindeki iddiaları yeniden "
            "kullanmadan önce doğrula; "
            + (f"ilk sıradakiler bu metinle AYNI İŞİ yapanlar ({IS_TURLERI.get(is_turu, is_turu)}), sonra konuya yakın olanlar" if is_turu
               else "ilk sıradakiler bu konuya en yakın olanlar")
            + "; konuları ve tek bir örneğin kalıbını kopyalama):\n" + "\n---\n".join(_ornekler(pr, 12, konu, is_turu)))


def _soguk_okur(metin, pr, link="", kart=""):
    """Konuyu hiç bilmeyen okur (ayrı model: sonnet). Ayrıca bu kişinin sesine benzerlik, kanca gücü ve TETİK (neden şimdi bunu söylüyor?)."""
    return _claude_json(
        "İki rolün var. (1) X'te gezinen, aşağıdaki gönderinin konusunu HİÇ bilmeyen, akıllı ama meşgul bir okursun; önünde yalnızca bu gönderi"
        + (f" ve altında paylaşılan bağlantının önizleme kartı var. KART: {kart or link}. Kartın söylediğini okur zaten görüyor. " if link else " var. ") +
        "(2) Bu kişinin gönderilerini iyi tanıyan bir editörsün (örnekleri aşağıda).\nDürüstçe puanla (5 nadir verilir):\n"
        "konu: gönderi neyle ilgili, kendi cümlenle (anlayamıyorsan 'anlaşılmıyor')\n"
        "anlasilir (1-5): konu, adı konmuş şeyler ve iddia ilk okumada anlaşılıyor mu; belirsiz gönderme ('o', 'bu olay', 'bir firma') var mı\n"
        "tamlik (1-5): (bağlantı kartıyla birlikte) neye tepki verdiği ve ne düşündüğü belli mi; havada kalan cümle var mı. Kısa olması eksiklik DEĞİLDİR: "
        "X'te iyi gönderi bir gözlem ve tek yorumdur, gerekçe paragrafı istemez. Ama durup dururken havadan bir hüküm gibi duruyorsa (ne bağlantı ne alıntı ne "
        "yaşanmış an) tamlik en çok 2 ve sorunlara 'tetik yok' yaz\n"
        "deger (1-5): bu alanı bilen birinin durup okuyacağı, herkesin bildiğini tekrar etmeyen bir görüş mü\n"
        "kanca (1-5): ilk cümle (uzun gönderide ilk 280 karakter) tek başına kaydırmayı durdurur mu\n"
        "ses (1-5): örneklerdeki kişinin gerçek gönderilerine benziyor mu (ritim, sohbet gibi Türkçe; uzunluk ve açılış konuya göre değişebilir, "
        "örneklerin uzunluğu kota değil); yapay zekâ yazısı, deneme, LinkedIn makalesi, 'Bence X'teki asıl mesele … değil' kalıbı, vecize ya da "
        "aforizma kapanış, haberi anlatma ya da aşağıdaki dil kurallarından birinin ihlali varsa en çok 2\n"
        "tazelik (1-5): gönderi bir görüş ileri sürüyorsa: konuyu duyan akıllı birinin aklına İLK gelecek yorumu mu söylüyor? (Gönderi ilginç bir keşfi "
        "paylaşıyor, kendi işini duyuruyor ya da espri yapıyorsa tez arama; paylaşılan şeyin ve tepkinin tazeliğini ölç.) Herkesin söyleyeceği, beklenen, 'söyleye söyleye bunu mu "
        "söyledin' dedirten bir bakışsa en çok 2 ve sorunlara 'bariz açı: …' diye yaz, uydurma olgu gerektirmeyen daha taze bir açı yönü öner. 4 ve üstü "
        "yalnızca okurun 'bunu böyle düşünmemiştim' diyeceği bir bakışsa. Tazelik dayanaktan gelir: kaynağın ya da bağlantı kartının desteklemediği "
        "şaşırtıcı bir yorum taze değil, dayanaksızdır (o zaman deger en çok 2 ve sorunlara 'dayanaksız: …')\n"
        "kisisel_ani (true/false): gönderi kişiye ait geçmiş bir anı, deneyim, duygu ya da alışkanlık anlatıyor mu ('beni durduran', 'yıllarca oynadım', "
        "'ben de denedim', 'bizim ekipte', 'yoruldum', 'sonuç aldım', yıl sayısı, unvan, aile ya da müşteri ayrıntısı gibi)? Varsa true ve sorunlara "
        "'kişisel anı' yaz\n"
        "paylasilir (1-5): editör olarak: takipçisi olan, yazısına özen gösteren İYİ bir içerik üreticisi bunu BU HALİYLE paylaşır mı? Şifreli/iç şaka gibi "
        "cümle, neye tepki verdiği anlaşılmayan yarım not ('… diyorlar', 'o genç yetenek'), sıradan ya da boş bir tespit, emek hissettirmeyen metin en çok 2. "
        "4 ve üstü yalnızca 'bunu ben de paylaşırdım' dedirtiyorsa\n"
        "sorunlar: somut düzeltmeler (en çok 3): yalnızca anlaşılmayı bozan ya da yapay zekâ kokan şeyler. Kartın zaten verdiği bilgiyi (kim, ne zaman, "
        "hangi model) yeniden isteme; ama metni anlamlı kılan bir bağlantı ya da gerekçe eksikse onu söyle. Açılış ya da kapanış için kalıp önerme ('X değil Y' gibi).\n"
        "JSON: {\"konu\": \"...\", \"anlasilir\": 4, \"tamlik\": 4, \"deger\": 4, \"kanca\": 4, \"ses\": 4, \"tazelik\": 4, \"kisisel_ani\": false, \"paylasilir\": 4, \"sorunlar\": [\"...\"]}\n\n"
        f"KİŞİNİN YAZI İLKELERİ:\n{_persona_blogu(pr, kisa=True, rehber=False)}\n\n{__import__('ghost_rehber').okur_blogu()}\n\nKİŞİNİN ÖRNEKLERİ:\n"
        + "\n---\n".join(_ornekler(pr, 8)) + f"\n\nGÖNDERİ:\n{metin}", model_adi="sonnet")


def _puanlar(h):
    try:
        return {k: int(h.get(k) or 0) for k in ("anlasilir", "tamlik", "deger", "kanca", "ses", "tazelik", "paylasilir")}
    except (TypeError, ValueError):
        return {k: 0 for k in ("anlasilir", "tamlik", "deger", "kanca", "ses", "tazelik", "paylasilir")}


def _gecti(h):
    p = _puanlar(h)
    # üslup kararı insan_testi'nde (gerçek gönderiler arasında fark edilir mi); okur yalnızca anlaşılırlık ve değer için (2026-10-22)
    # 2026-10-22 (kullanıcı: "Beş gün ücretsiz diyorlar…" için "hiçbir iyi içerik üreticisi böyle yazıp paylaşmaz"): paylaşılabilirlik ≥4 şart
    # 22 Ekim: FM 27 taslağı için "çok sıkıcı bir bakış açısı; söyleye söyleye bunu mu söyledin derler" → bariz açı geçmez (tazelik ≥4)
    return (p["anlasilir"] >= 3 and p["tamlik"] >= 3 and p["deger"] >= 3 and p["ses"] >= 3 and p["paylasilir"] >= 4 and p["tazelik"] >= 4
            and "anlaşılmıyor" not in str(h.get("konu")))


def _dogrula(metin, dayanak):
    """Olgusal iddiaları denetler (opus): videodaki konuşmacının hatası kullanıcıya mal olmasın (ör. olmayan 'IBM–Phoenix davası').
    Döner: (metin, notlar)."""
    c = _claude_json(
        "Aşağıdaki X gönderisindeki OLGUSAL iddiaları (olay, tarih, dava, rakam, kim ne yaptı) tek tek denetle. Görüşleri denetleme. Her iddia için "
        "genel bilgine göre: dogru | supheli (emin değilsin ya da bağlamsız) | yanlis. Kaynaktaki dayanak da verildi; dayanakta olması doğru olduğu "
        "anlamına GELMEZ (konuşmacı yanılmış olabilir). Yanlış ya da şüpheli iddia varsa gönderiyi düzelt: o iddiayı çıkar ya da doğru/yumuşak "
        "biçimde yaz; YENİ olgu ekleme; üslubu ve uzunluğu koru. Hepsi doğruysa 'duzeltilmis' boş kalsın.\n"
        "JSON: {\"iddialar\": [{\"iddia\": \"...\", \"durum\": \"dogru\", \"not\": \"...\"}], \"duzeltilmis\": \"\"}\n\n"
        f"DAYANAK (kaynaktan):\n{dayanak}\n\nGÖNDERİ:\n{metin}", model_adi="opus")
    sorunlu = [i for i in c.get("iddialar") or [] if isinstance(i, dict) and i.get("durum") in ("yanlis", "supheli")]
    yeni = str(c.get("duzeltilmis") or "").strip()
    global SON_IDDIALAR
    SON_IDDIALAR = [{"iddia": str(i.get("iddia", ""))[:200], "durum": i.get("durum"), "not": str(i.get("not", ""))[:200]} for i in c.get("iddialar") or [] if isinstance(i, dict)]
    return (yeni if sorunlu and yeni else metin), [f"{i.get('durum')}: {i.get('iddia')} ({i.get('not', '')})" for i in sorunlu]


SON_IDDIALAR = []


def _kalip_notlari(m, digerleri, konusmacilar=(), baslik="", kendi_deneyim=False):
    n = []
    dn = [] if kendi_deneyim else DENEYIM.findall(m)
    if dn:
        n.append(f"Kişisel deneyim/gözlem uyduruyor ({', '.join(sorted(set(x if isinstance(x, str) else x[0] for x in dn)))}); bu deneyim kişinin "
                 "değil, kaldır. Yalnızca görüş ve çıkarım yaz.")
    elif not kendi_deneyim:
        bs = birinci_sahis_notu(m)
        if bs:
            n.append(bs)
    for ad in konusmacilar:
        if ad and re.search(r"\b" + re.escape(ad) + r"\b", m) and ad.casefold() not in baslik.casefold():
            # 25 Ekim (ChatGPT değerlendirmesi): eskiden "adını çıkar, görüşü kişinin kendi görüşü olarak yaz" diyordu; başkasının düşüncesi kullanıcıya mal oluyordu
            n.append(f"Kaynaktaki konuşmacıyı ({ad}) adıyla anıyorsun; okur onu tanımıyor. Fikir onunsa ona ait olduğunu belli et (ör. 'videoda konuşan "
                     "kişi') ya da yalnızca kendi çıkarımını yaz. Başkasının düşüncesini kişinin kendi görüşüymüş gibi yazma.")
    k = KLISE.findall(m)
    if k:
        n.append(f"Klişe/kalıp ifade var ({', '.join(sorted(set(x if isinstance(x, str) else x[0] for x in k)))}); kendi cümlenle söyle.")
    ilk = " ".join(m.split()[:3]).lower()
    if any(" ".join(d.split()[:3]).lower() == ilk for d in digerleri):
        n.append("Bu gönderi diğer taslaklardan biriyle aynı açılışa sahip; farklı bir açılış kur.")
    cumle = len(re.findall(r"[.!?…]+(?=\s|$)", m.strip()))
    # 25 Ekim (ChatGPT değerlendirmesi): uzunluk düşünceye hizmet eder; cümle/paragraf sayısı tek başına hata değil, tekrar hata
    if cumle > 6 and len(m) <= 320:
        n.append(f"{cumle} kısa cümle; her cümle ayrı bir iş yapıyor mu? Aynı düşünceyi tekrar eden cümleleri at.")
    if m.count("\n\n") >= 3:
        n.append("Dört ya da daha çok paragraf; her paragraf yeni bir şey söylemiyorsa birleştir ya da at.")
    for desen, ad in FORMUL:
        if re.search(desen, m, re.I | re.M):
            n.append(ad + ".")
    kk = koku_notlari(m, profil().get("silinen_ifadeler") or [])
    if kk:
        n.append("Yapay zekâ kokusu: " + "; ".join(kk) + ". Bu kişinin doğal Türkçesiyle yeniden kur.")
    import ghost_rehber                                    # 2026-10-26: kişinin rehberindeki dil kuralları (tire, şapka, +, övücü sıfat, özel bilgi)
    dn = ghost_rehber.dil_notlari(m, kendi_deneyim)
    if dn:
        n.append("Dil kuralı: " + "; ".join(dn) + ".")
    return n


def kapidan_gecir(taslak, pr=None, log=print):
    """Var olan bir taslağı okur kapısından geçirir (paylaşılabilirlik dahil); geçmezse okurun notlarıyla en çok 2 kez yeniden yazar.
    Döner: (yeni alanlar sözlüğü ya da None = geçemedi, son okur puanları)."""
    pr = pr or profil()
    t = dict(taslak)
    for deneme in range(3):
        h = _soguk_okur(t["metin"], pr, t.get("paylas_link", ""), t.get("konu", ""))
        notlar = _kalip_notlari(t["metin"], [], kendi_deneyim=bool(t.get("deneyim")))
        if h.get("kisisel_ani") is True and not t.get("deneyim"):
            notlar.append("Kişiye ait bir anı/deneyim uyduruyor (kişi böyle bir şey söylemedi); anıyı çıkar, gözlem ya da çıkarım olarak yaz")
        if _gecti(h) and not notlar:
            return ({"metin": t["metin"], "karakter": len(t["metin"]), "okur": _puanlar(h)} | ({"ilk_metin": taslak.get("ilk_metin") or taslak["metin"]} if t["metin"] != taslak["metin"] else {})), _puanlar(h)
        if deneme == 2:
            return None, _puanlar(h)
        sorun = "; ".join(map(str, (h.get("sorunlar") or []) + notlar))[:700]
        log(f"      Kapı: {_puanlar(h)} → yeniden yazılıyor")
        t.update(yeniden_yaz(t, "Okurun ve editörün notlarına göre düzelt: " + sorun))
    return None, {}


def hizli_yaz(k, pr, bicim, link="", log=print):
    """Kısa biçimler (emoji / minik not): tek sonnet çağrısı, okur döngüsü yok (bağlantı ya da alıntı zaten bağlamı taşır); kod denetimleri var."""
    ton = k.get("ton") or ("eglenceli" if bicim == "emoji" else "ciddi")
    c = _claude_json(f"{_ses_blogu(pr, str(k.get('baglam')) + ' ' + str(k.get('gorus')), 'espri' if ton == 'eglenceli' else 'tepki')}\n"
                     f"Bu kişi aşağıdaki içeriği X'te {'bağlantısıyla' if link else ''} paylaşacak. BİÇİM: {(pr.get('bicimler') or {}).get(bicim, bicim)}\n"
                     f"TON: {ton} ({(pr.get('tonlar') or {}).get(ton, '')}). {pr.get('tavir', '')}\n"
                     "Gerçek bir insan gibi: bağlantı/alıntı kartı bağlamı veriyor, sen yalnızca tepkini koy. Açıklama, özet, hashtag yok. Uydurma olgu yok.\n"
                     "Kısa olsa da TEK BAŞINA anlamlı olmalı: neye tepki verdiğin adıyla belli olsun (kart görünmese de konu anlaşılsın); '… diyorlar', 'o genç "
                     "yetenek', 'bu olay' gibi belirsiz gönderme, şifreli ya da iç şaka gibi cümle yok. İyi bir içerik üreticisinin özenle paylaşacağı bir tepki olsun.\n"
                     f"KONU: {k.get('baglam')}\nAÇI: {k.get('gorus')}\n" + (f"BARİZ YORUM (SÖYLEME): {k.get('bariz')}\n" if k.get("bariz") else "") +
                     'JSON: {"metin": "...", "alternatifler": ["...", "..."]}', model_adi="sonnet", zaman_asimi=120)
    m = _temiz(str(c.get("metin") or "")).strip()
    if not m:
        return None
    alts = [str(x).strip() for x in c.get("alternatifler") or [] if str(x).strip()][:2]
    sinir = 140 if bicim == "minik" else 200
    for deneme in range(3):                           # okur denetimi: kısa notlar da tek başına anlamlı ve paylaşılabilir olmalı
        if len(m) > sinir:
            m = re.split(r"(?<=[.!?…])\s", m)[0][:sinir]
        h = _soguk_okur(m, pr, link, k.get("baglam") or "")
        notlar = _kalip_notlari(m, [])
        if h.get("kisisel_ani") is True and not k.get("deneyim"):
            notlar.append("Kişiye ait bir anı/deneyim uyduruyor; çıkar")
        if _gecti(h) and not notlar:
            return {"metin": m, "kancalar": alts, "zincir": [], "okur": _puanlar(h), "dogruluk": [], "uzun": False}
        if deneme == 2:
            log(f"      Kısa not geçmedi ({', '.join(f'{a} {b}' for a, b in _puanlar(h).items())}): {m[:120]!r} | {'; '.join(map(str, (h.get('sorunlar') or []) + notlar))[:200]}")
            return None
        sorun = "; ".join(map(str, (h.get("sorunlar") or []) + notlar))[:600]
        c = _claude_json(f"{_ses_blogu(pr, str(k.get('baglam')))}\nŞu kısa X notunu düzelt (BİÇİM: {bicim}, en çok {sinir} karakter). Okurun ve editörün notları: {sorun}\n"
                         f"KONU: {k.get('baglam')}\nAÇI: {k.get('gorus')}\nNOT: {m}\nTek başına anlaşılır, neye tepki verdiği adıyla belli, iyi bir içerik üreticisinin "
                         'paylaşacağı bir tepki olsun; uydurma olgu yok. JSON: {"metin": "..."}', model_adi="sonnet", zaman_asimi=120)
        m = _temiz(str(c.get("metin") or "")).strip() or m
    return None


def _istem_linkedin(k, pr):
    return (f"Bir kişinin LinkedIn yazısını onun ağzından yazıyorsun.\n{_ses_blogu(pr, str(k.get('baglam')) + ' ' + str(k.get('gorus')), 'dusunce', 'linkedin')}\n{_gorus_blogu(str(k.get('baglam')) + ' ' + str(k.get('gorus')))}\nLINKEDIN: {(pr.get('platformlar') or {}).get('linkedin', '')}\n"
            f"ALAN: {k.get('alan')}\nKONU: {k.get('baglam')}\nGÖRÜŞÜ: {k.get('gorus')}\nDAYANAK: {k.get('dayanak')}\n\n"
            "KURALLAR: uzunluk düşünce kadar (LinkedIn'de çoğu zaman birkaç kısa paragraf; karakter hedefi yok); açılış konuya göre (iddia, somut bir "
            "iş kararı ya da sahne; 'heyecanla paylaşıyorum' YOK); tek mesele; gerçek iş ve somut karar, kendini kutlama, kariyer vaazı, yapay başarı "
            "hikayesi yok. Düşünce bitince dur: ders, aforizma ya da düşündüren son cümle diye ayrıca kapanış yazma. Hashtag, emoji listesi, 'işte 5 ders' kalıbı, kurumsal klişe yok. "
            "Dayanakta olmayan olgu/sayı uydurma. Kişinin kendi karşılığı verildiyse yazıyı onun üstüne kur, başka deneyim ekleme.\n"
            'Ayrıca "kancalar": ilk cümle için 2 alternatif.\nJSON: {"metin": "...", "kancalar": ["...", "..."]}')


def _istem(k, pr, uzun, video_link=""):
    """2026-10-22 baştan: kısa kurallar + en benzer gerçek gönderiler. Eski istem 'Bence Gemini 4'teki asıl haber model değil…' örneğini
    veriyordu ve her taslak o kalıpla açılıyordu; 'gerekçesi, net sonucu' isteyen okur kısa taslakları eleyip uzun denemeye itiyordu."""
    konu = str(k.get("baglam")) + " " + str(k.get("gorus"))
    # 25 Ekim (ChatGPT değerlendirmesi): sabit karakter hedefi düşünceden bağımsız bir uzunluk dayatıyordu; artık düşünce kadar
    olcu = ("UZUN: düşünce bir bağlantı, gerekçe ya da geçmişle ilişki gerektiriyor; gerektiği kadar, ara basamakları silmeden (birkaç kısa paragraf). "
            "Ayrıca 'zincir': aynı içerik 2-4 parça (her biri ≤270 karakter)." if uzun
            else "Düşünce kadar: tek cümle yetiyorsa orada bitir; geçmiş gönderilerinin uzunluğu kota değil. Düşünce tamamlanınca dur; "
                 "uzunluğu doldurmak için yazma, gereken bağlantıyı da kısaltmak için silme.")
    bag = (f"Gönderi şu bağlantıyla BİRLİKTE paylaşılacak; okur altında önizleme kartını (başlık ve görsel) görecek: {k.get('paylas_link')}\n"
           "Kart ne olduğunu anlatıyor. Sen haberi anlatma; kartla birlikte okununca anlaşılacak kadar adını an, kendi gözlemini ya da yorumunu koy.\n"
           if k.get("paylas_link") else "Bağlantı yok: neye tepki verdiğin ilk cümlede adıyla anlaşılsın.\n")
    return ("Bir kişinin X gönderisini onun ağzından yazıyorsun. Ölçüt tek: bu gönderi onun gerçek gönderilerinin arasına konsa kimse ayırt edemesin.\n\n"
            f"{_ses_blogu(pr, konu, 'dusunce' if uzun else ('tepki' if k.get('paylas_link') else 'gozlem'))}\n\n{_gorus_blogu(konu)}\n"
            f"KONU: {k.get('baglam')}\nONUN AÇISI (aynen kopyalama, kendi cümlesiyle): {k.get('gorus')}\nDAYANAK (olgular yalnızca buradan): {k.get('dayanak')}\n"
            + (f"BARİZ YORUM (herkes bunu söyler; SÖYLEME, açın bundan farklı olsun): {k.get('bariz')}\n" if k.get("bariz") else "") +
            f"{bag}UZUNLUK: {olcu}\nTON: {k.get('ton') or 'ciddi'} ({(pr.get('tonlar') or {}).get(k.get('ton') or 'ciddi', '')}).\n\n"
            "NASIL YAZAR (yukarıdaki gerçek örneklerinden; 2026-10-26 kendi rehberi: hiçbir açılış ya da sıra şablon değil):\n"
            "- Açılışı konuya göre seçer: somut bir ayrıntı, doğrudan görüş, kısa bir sahne ya da espri. Bazen küçük harfle, sohbet eder gibi. "
            "Örneklerden birinin açılışını kalıp yapma.\n"
            "- Çoğu zaman bir gözlem ve tek yorum; bazen bir gelişmeyi geçmişiyle ilişkilendirip birkaç paragrafta düşünür. Yorum kendinden emin; metni "
            "anlamlı kılan bağlantıyı (neden, hangi koşulda) gerektiği kadar söyler, aynı şeyi yeniden anlatmaz, ders vermez.\n"
            "- Düşünce bitince durur. Kuru bir son ya da espri ancak gözlemden kendiliğinden çıkıyorsa; her metne espri ya da kapanış cümlesi koymaz.\n"
            "YAPMA:\n"
            "- 'Bence X'teki asıl … değil, …' kalıbı; 'asıl haber/asıl mesele/asıl karar' çerçevesi; her gönderiye aynı kelimeyle başlamak ('Bence' ve "
            "'dikkatimi çekti' yasak değil, işe yarıyorsa kullan).\n"
            "- Haberi özetlemek ('X'in haberine göre'); kart zaten gösteriyor. Ama bir iddiayı aktarıyorsan sahibine ver ('şirket diyor ki').\n"
            "- Paragraf paragraf deneme, öğüt/reçete ('şöyle olmalı'), vecize gibi kapanış ('Atlanacak kural yok, çünkü yetki yok.').\n"
            "- Ona ait olmayan deneyim ('kurarken görüyorum', 'ajansta öğrenmiştik', 'denedim'); videoya/konuşmacıya atıf.\n"
            "- Uydurma olgu ya da sayı; hashtag, emoji, ünlem, övücü sıfat, uzun tire, şapkalı a, düz yazıda '+'.\n"
            "Ayrıca 'kancalar': aynı gönderi için 2 farklı ilk cümle.\n"
            "JSON: {\"metin\": \"...\", \"kancalar\": [\"...\", \"...\"]" + (", \"zincir\": [\"...\", \"...\"]" if uzun else "") + "}")


def insan_testi(metin, pr):
    """Ayırt etme sınavı: taslak, kişinin uzunluğa yakın 4 gerçek gönderisi arasına karıştırılır; ayrı bir model (sonnet) 'hangisi yapay zekâ?' diye
    tahmin eder. Taslağı bulursa geçmez ve nedenini söyler. Döner: (gecti, neden)."""
    import random
    G = [g for g in _gercek_gonderiler(pr) if g.strip() != metin.strip()]
    if len(G) < 6:
        return True, ""
    hedef = _kokler(metin)
    yakin = sorted(G, key=lambda g: -len(hedef & _kokler(g)) * 40 + abs(len(g) - len(metin)))[:10]
    random.shuffle(yakin)
    L = yakin[:4] + [metin]
    random.shuffle(L)
    sira = L.index(metin) + 1
    c = _claude_json("Aşağıda bir kişinin X'teki gönderileri var. Bunlardan BİRİ o kişinin değil; yapay zekânın onun adına yazdığı bir taslak. Hangisi? "
                     "Konuya değil yazıya bak: açılış, uzunluk, ritim, kalıp, ton, Türkçesi. Gerçekten ayırt edemiyorsan 0 yaz.\n"
                     'JSON: {"tahmin": 3, "emin": 1-5, "neden": "yapay zekâ taslağını ele veren somut şey"}\n\n'
                     + "\n\n".join(f"[{n}]\n{x}" for n, x in enumerate(L, 1)), model_adi="sonnet", zaman_asimi=120)
    try:
        tahmin, emin = int(c.get("tahmin") or 0), int(c.get("emin") or 0)
    except (TypeError, ValueError):
        return True, ""
    yakalandi = tahmin == sira and emin >= 3
    return (not yakalandi), (str(c.get("neden") or "")[:300] if yakalandi else "")


def uret(json_yolu, log=print, en_cok=3):
    """Videodaki değerli bakış açılarından, kullanıcının KENDİ sesiyle (profil/x.json: gerçek gönderilerinden), tek başına anlaşılan X gönderileri.
    Akış (2026-10-18 sürüm 3; kullanıcı 'en iyi haline getir' dedi): (1) konu seçimi (opus): kullanıcının alanlarından biri olmalı, kaçınılacak
    konular yok, 'neden şimdi' cevabı olmalı (eski olay ancak güncel bir bağla), daha önce reddettikleri konular verilir; (2) yazım (opus):
    kanca önce + 2 alternatif açılış, uzunsa zincir; (3) doğruluk denetimi (opus); (4) kalıp/klişe/aynı açılış kodla; (5) soğuk okur + ses
    editörü (sonnet): anlaşılırlık, tamlık, değer, ses ≥4, kanca ≥3; olmazsa notlarla 2 kez yeniden yazım; kısa geçmezse bir kez uzun; yine
    geçmezse atılır. Link gönderiye değil 'ilk_yanit'a."""
    _bas = time.time()
    json_yolu = Path(json_yolu)
    d = json.loads(json_yolu.read_text(encoding="utf-8")); veri, seg = d["veri"], d["segmentler"]
    import ozet as ozet_modulu
    import claude_yaz
    if not claude_yaz.hazir() and not ozet_modulu.hazir():
        raise SystemExit("HATA: Yapay zekâ modeli hazır değil.")
    import ghost_kurulum
    if not ghost_kurulum.kurulu_mu():                      # sesi kurulmamış Ghost kimsenin adına yazmaz (2026-10-29)
        log("Ghost henüz kurulmadı; taslak yazılmadı")
        return []
    pr = profil()
    ozet, metin = _baglam(veri, seg)
    bugun = time.strftime("%d.%m.%Y")
    alanlar = pr.get("alanlar") or []
    alan_adlari = [a["ad"] for a in alanlar if isinstance(a, dict) and a.get("ad")]
    red = _red(pr, "konu")[-15:]                  # yalnız konu reddi konu seçimine girer (bilgi hatası ya da 'bugün değil' konu tercihi değil)
    link = veri.get("link") if str(veri.get("link") or "").startswith("http") else ""
    baslik = str(veri.get("baslik") or "")
    konusmacilar = sorted({str(a).split()[0] for a in (veri.get("etiket") or {}).values()
                           if a and not str(a).startswith("Konuşmacı") and len(str(a)) > 2})
    tur = veri.get("kaynak_tur") or "video"
    kaynak_ad = {"yazi": "bir yazının metni", "yazi_link": "bir yazının metni", "video": "bir videonun özeti ve transkripti",
                 "secki": "bir araştırma notu (kaynakları ve kanıt sınırıyla; ChatGPT'nin günlük okuma seçkisinden) ve varsa kişinin bu konudaki KENDİ "
                          "karşılığı. Kendi karşılığı verildiyse yalnızca onun etrafında TEK konu seç; gönderinin merkezi o gözlem olur, araştırma "
                          "notu dayanak olarak kalır. Kanıt sınırının ötesine geçen iddia seçme"}.get(tur, "bir videonun özeti ve transkripti")
    kendi_deneyim = tur == "fikir" or bool(str(veri.get("deneyim") or "").strip())
    platform = veri.get("platform") if veri.get("platform") in ("x", "linkedin") else "x"
    if tur == "taslak":                      # kişinin kendi taslağı + düzenleme isteği: konu seçimi, açı, okur döngüsü yok; yalnız istenen değişiklik
        log("      Taslağınız istediğiniz gibi düzenleniyor...")
        r = sinirli_duzenle(metin, str(veri.get("istek") or ""), pr, baslik)
        t = {"platform": "x", "metin": r["metin"], "karakter": len(r["metin"]), "konu": baslik[:240], "alan": "", "bicim": "gozlem",
             "uzunluk": "kisa" if len(r["metin"]) <= 280 else "uzun", "kancalar": [], "zincir": [], "itirazlar": [], "iddialar": [], "panel": [],
             "kod_notlari": [], "dayanak": "kendi", "deneyim": "", "neden": "", "link_oner": False, "ilk_yanit": "", "paylas_link": "", "okur": {},
             "kendi_taslak": metin, "duzenleme": {"tur": "sinirli", "istek": str(veri.get("istek") or "")[:500], **r},
             "kaynak": {"tur": "sizin taslağınız", "baslik": "", "tarih": "", "link": ""}}
        d = json.loads(json_yolu.read_text(encoding="utf-8"))
        d["veri"]["paylasim"] = {"taslaklar": [t], "zaman": time.time(), "ilk_zaman": time.time(), "model": _yazan(_bas), "surum": 1, "elenen": []}
        json_yolu.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"      Düzenlendi (metnin %{round(r['degisim'] * 100)}'i değişti)")
        return [t]
    if tur == "kesif":
        log("      Öneri gönderiye dönüştürülüyor...")
        secim = _claude_json(
            f"Bugün {bugun}. Aşağıdaki güncel içerik, bu kişinin {'LinkedIn' if platform == 'linkedin' else 'X'} hesabı için seçildi. Tek bir gönderi konusu olarak "
            f"çerçevele.\nKİŞİ: {pr.get('kimlik') or '-'}\nALANLARI BAĞLAYAN BAKIŞ: {pr.get('baglanti', '')}\n"
            "baglam: konuyu bilmeyene adıyla tek cümle. bariz: bu içeriği duyan akıllı herkesin aklına İLK gelecek yorum (verildiyse onu da dikkate al). "
            "gorus: bariz olanı SÖYLEMEYEN açı (kişinin kendi karşılığı verildiyse onu merkez al): ikinci derece sonuç, beklenmedik bağlantı, karşı-sezgisel "
            "gözlem, arkasındaki karar ya da insan; haberi tekrar etme. Okuyan 'söyleye söyleye bunu mu söyledin' demeli DEĞİL. Açı içerikteki olgulara dayanır: "
            "şaşırtıcı ama içeriğin desteklemediği bir yorum açı değildir. Böyle bir açı yoksa konular boş (her içerik gönderiye dönüşmek zorunda değil). "
            "dayanak: içerikteki somut olgular (yalnızca metinde olanlar). uzunluk: kisa ya da uzun.\n"
            'JSON: {"konular": [{"baglam": "...", "bariz": "...", "gorus": "...", "dayanak": "...", "neden_simdi": "...", "uzunluk": "kisa"}]}\n\nİÇERİK:\n' + metin[:6000],
            model_adi="opus")
        for k in secim.get("konular") or []:
            if isinstance(k, dict):
                k.update({"bicim": veri.get("bicim") or k.get("bicim"), "ton": veri.get("ton") or k.get("ton"),
                          "alan": veri.get("alan_ad") or "", "yas": "guncel", "link_oner": bool(veri.get("link")),
                          "neden_simdi": k.get("neden_simdi") or "güncel", "dayanak": (k.get("dayanak") or "") + "\n" + metin[:3000]})
        secim["konular"] = (secim.get("konular") or [])[:1]
        alan_adlari_secim = []
    elif tur == "fikir":
        log("      Fikriniz gönderiye dönüştürülüyor...")
        secim = _claude_json(
            f"Bugün {bugun}. Aşağıdaki kişi X'te paylaşmak için kendi fikrini not etti. Kişisel marka stratejisti olarak bu fikri tek bir gönderi konusu "
            f"olarak çerçevele; fikri DEĞİŞTİRME, keskinleştir. Fikirde olmayan olgu/sayı ekleme.\n\nKİŞİ: {pr.get('kimlik') or '-'}\n"
            + ("ALANLARI: " + "; ".join(alan_adlari) + "\n" if alan_adlari else "")
            + "JSON: {\"konular\": [{\"alan\": \"listeden en yakını ya da boş\", \"baglam\": \"konuyu bilmeyene tek cümle\", \"gorus\": \"fikrin keskin hali\", "
            "\"dayanak\": \"fikrin kendisi (aynen)\", \"neden_simdi\": \"kısa\", \"yas\": \"guncel\", \"uzunluk\": \"kisa ya da uzun\", \"link_oner\": false}]}\n\n"
            "FİKİR:\n" + metin[:4000], model_adi="opus")
        for k in secim.get("konular") or []:
            if isinstance(k, dict):
                k["dayanak"] = metin[:4000]; k["yas"] = "guncel"; k["neden_simdi"] = k.get("neden_simdi") or "kendi fikriniz"
                if alan_adlari and k.get("alan") not in alan_adlari:
                    k["alan"] = ""
        alan_adlari_secim = []
    else:
        alan_adlari_secim = alan_adlari
        log("      Paylaşmaya değer konular aranıyor...")
        secim = _claude_json(
        f"Bugün {bugun}. Aşağıda {kaynak_ad} var. Bir kişisel marka stratejisti olarak, aşağıdaki kişinin X'te KENDİ görüşü "
        f"olarak paylaşmaya değer bulacağı konuları seç.\n\nKİŞİ: {pr.get('kimlik') or '-'}\nHEDEF PROFİL: {pr.get('hedef_profil', '')}\n"
        f"ALANLARI BAĞLAYAN BAKIŞ: {pr.get('baglanti', '')}\n"
        + ("ALANLARI (yalnızca bunlardan birine giren konu seçilir):\n" + "\n".join(f"- {a['ad']}: {a.get('not', '')}" for a in alanlar if isinstance(a, dict)) + "\n" if alanlar else "")
        + (f"KAÇINILACAKLAR: {'; '.join(pr.get('kacin') or [])}\n" if pr.get("kacin") else "")
        + ("DAHA ÖNCE REDDETTİĞİ ÖNERİLER (benzerlerini önerme):\n" + "\n".join(f"- {r.get('konu', '')[:120]} ({r.get('neden') or 'neden belirtmedi'})" for r in red) + "\n" if red else "")
        + ("DAHA ÖNCE PAYLAŞTIKLARI (aynı fikri ya da aynı çerçevelemeyi TEKRAR ETMEYEN konu seç; önceki bir görüşüyle çelişiyorsa bunu 'neden_simdi'de belirt):\n"
           + "\n".join(f"- {str(x)[:160]}" for x in ([y for y in pr.get('paylasilan') or [] if isinstance(y, str)][-10:] + list(pr.get('ornekler') or [])[:6])) + "\n")
        + "\nSert ele: herkesin bildiği, reklam kokan, yalnızca konuşmacının kişisel hikâyesi olan, videonun dışında anlamı olmayan, ana öğesi "
        "kaynakta ADIYLA geçmeyen konuları alma. Bu kişinin bakışı: haberin kendisinden çok anlamı (hangi teşviki, iş modelini, güç dengesini, "
        "davranışı değiştiriyor); teknoloji iddiasını 'gerçekte neyi çözüyor, işte çalışıyor mu, bununla ne yapılabilir' diye sınar; ikinci derece "
        "düşünür (herkesin beklediği sonuç değil, onun sonucu). Değerli = başkalarının kaçırdığı ayrıntı, yeni bir bakış, ters köşe "
        "bir gerçek, beklenmedik bir bağlantı; hepsi kaynaktaki olgulara dayanır (dayanaksız şaşırtıcı yorum değerli değil).\nGÜNCELLİK: 'neden_simdi' alanına bu konunun BUGÜN neden konuşulmaya değer olduğunu yaz. Olay aylar ya "
        "da yıllar önce olduysa ve bugüne bağlayan bir şey yoksa 'yas': 'eski' yaz (paylaşılmaz).\nEn çok 3, hiç yoksa boş liste.\n"
        "Her konu için önce 'bariz': bunu duyan akıllı herkesin aklına ilk gelecek yorum; 'gorus' o bariz yorumu SÖYLEMESİN (okur 'söyleye söyleye bunu "
        "mu söyledin' dememeli); bariz olmayan bir açı yoksa konuyu alma. İSTİSNA: paylaşmanın değeri şeyin kendisindeyse (ilginç bir keşif, kendi işinin "
        "duyurusu, espri) zorla tez kurma; gorus o zaman yalnızca neden ilginç bulduğu ya da kısa tepkisidir.\n"
        "Her konu: alan (listeden aynen), baglam (bilmeyene adıyla tek cümle), bariz, gorus (keskin, savunulabilir; 1-2 cümle), dayanak (transkriptten "
        "somut olgular), neden_simdi, yas (guncel|eski), uzunluk (kisa varsayılan | uzun: yalnızca gerçekten gerekiyorsa, en çok 1), link_oner.\n"
        "JSON: {\"konular\": [{\"alan\": \"...\", \"baglam\": \"...\", \"bariz\": \"...\", \"gorus\": \"...\", \"dayanak\": \"...\", \"neden_simdi\": \"...\", "
        "\"yas\": \"guncel\", \"uzunluk\": \"kisa\", \"link_oner\": false, \"bicim\": \"gozlem\", \"ton\": \"ciddi\"}]}\n"
        "Her konuya bicim (emoji | minik | gozlem | uzun) ve ton (ciddi | eglenceli | samimi) da ver; hepsi aynı olmasın, gerçek bir insanın akışı gibi karışık.\n\n"
        + ozet + "\nTRANSKRİPT:\n" + metin[:14000], model_adi="opus")
    konular, elenen = [], []
    for k in secim.get("konular") or []:
        if not isinstance(k, dict) or not k.get("gorus") or not k.get("baglam"):
            continue
        if alan_adlari_secim and k.get("alan") not in alan_adlari_secim:
            log(f"      Alan dışı konu atlandı: {str(k.get('baglam'))[:80]}"); elenen.append({"k": k, "neden": "Alanlarınızdan birine girmiyor"}); continue
        if k.get("yas") == "eski" or not str(k.get("neden_simdi") or "").strip():
            log(f"      Güncel olmayan konu atlandı: {str(k.get('baglam'))[:80]}"); elenen.append({"k": k, "neden": "Güncel değil; bugüne bağlayan bir şey yok"}); continue
        konular.append(k)
    konular = konular[:en_cok]
    for k in [k for k in konular if k.get("uzunluk") == "uzun"][1:]:
        k["uzunluk"] = "kisa"
    if not konular:
        log("      Paylaşmaya değer konu bulunamadı.")
    taslaklar, son_deneme = [], {}
    for k in konular:                                    # bağlantı gönderinin İÇİNDE paylaşılır (X kartı); tetik görünür olsun (kullanıcı, 21 Ekim)
        if link and not k.get("paylas_link"):
            # birkaç haberi konuşan videoda (ör. DeepSeek videosundan Getty/Amazon konusu) video kartı gönderiyle eşleşmez: bağlantıyı kullanıcı ekler (2026-10-22)
            ortak = _kokler(baslik) & _kokler(str(k.get("baglam")) + " " + str(k.get("gorus")))
            if tur == "video" and len(ortak) < (2 if len(_kokler(baslik)) >= 4 else 1):
                k["baglanti_eklenecek"] = True
                continue
            k["paylas_link"] = link
    for i, k in enumerate(konular, 1):

        def _yaz(uzun):
            temel = _istem_linkedin(k, pr) if platform == "linkedin" else _istem(k, pr, uzun)
            if kendi_deneyim:
                temel += ("\n\nKİŞİNİN KENDİ KARŞILIĞI var (dayanakta 'KİŞİNİN KENDİ KARŞILIĞI' ya da fikrin kendisi): bu deneyim GERÇEK ve kişinin; birinci "
                          "tekil şahısla kullan, gönderiyi onun üstüne kur. Ona eklenti deneyim, sayı, müşteri adı uydurma; müşteri/marka adı verilmediyse anma.")
            log(f"      Paylaşım {i}/{len(konular)} yazılıyor{' (uzun)' if uzun else ''}...")
            c = _claude_json(temel, model_adi="opus")
            m = _temiz(str(c.get("metin") or "")).strip()
            if not m:
                return None
            ilk_taslak = m                     # 25 Ekim: editörlerden (doğrulama, okur, yeniden yazım) önceki hal
            m, dogruluk = _dogrula(m, k.get("dayanak") or "")
            if dogruluk:
                log(f"      Paylaşım {i}: doğruluk düzeltmesi: {'; '.join(dogruluk)[:200]}")
            h = {}
            gecen = None              # kapıdan geçmiş son sürüm: insan_testi geri bildirimiyle yapılan yeniden yazım kötüleşirse bu döner (23 Ekim)
            for deneme in range(3):
                h = _soguk_okur(m, pr, k.get("paylas_link", "") or ("(eklenecek)" if k.get("baglanti_eklenecek") else ""),
                                kart="kişi paylaşırken bu konunun haber bağlantısını ya da ilgili X gönderisini ekleyecek; kart o haberi gösterecek" if k.get("baglanti_eklenecek") else(f"{baslik} ({urlparse(k['paylas_link']).netloc.replace('www.', '')})"
                                                                      if k.get("paylas_link") and baslik else ""))
                notlar = _kalip_notlari(m, [t["metin"] for t in taslaklar], konusmacilar, baslik, kendi_deneyim)
                if h.get("kisisel_ani") is True and not kendi_deneyim:
                    notlar.append("Kişiye ait bir anı/deneyim uyduruyor (kişi böyle bir şey söylemedi); anıyı çıkar, gözlem ya da çıkarım olarak yaz.")
                notlar += sayi_notlari(m, str(k.get("dayanak") or "") + " " + str(veri.get("deneyim") or "") + " " + metin[:20000])
                if YASAK_ATIF.search(m) and not k.get("paylas_link"):   # bağlantı paylaşılıyorsa 'bu videoda' gibi gönderme doğal
                    notlar.append("Videoya/konuşmacıya atıf var; kaldır.")
                if not uzun and platform != "linkedin" and len(m) > 280:
                    uzun = True                   # 25 Ekim: düşünce 280'e sığmadıysa uzun gönderi olur (eskiden "kısalt" deniyor, gerekçe budanıyordu)
                if uzun and platform != "linkedin" and len(m) > 900:
                    notlar.append(f"Uzun gönderi {len(m)} karakter; tekrar eden ya da düşünceye hizmet etmeyen kısımları at.")
                if platform == "linkedin" and len(m) > 2500:     # 26 Ekim (rehber): karakter hedefi yok; yalnız aşırı uzunluk tekrar işaretidir
                    notlar.append(f"LinkedIn yazısı {len(m)} karakter; tekrar eden ya da düşünceye hizmet etmeyen kısımları at.")
                if _gecti(h) and not notlar:
                    gecen = {"metin": m, "kancalar": [str(x).strip() for x in c.get("kancalar") or [] if str(x).strip()][:2],
                             "zincir": [str(x).strip() for x in c.get("zincir") or [] if str(x).strip()][:4] if uzun else [],
                             "okur": {**_puanlar(h), "konu": h.get("konu")}, "dogruluk": dogruluk, "uzun": uzun, "ilk_taslak": ilk_taslak}
                if _gecti(h) and not notlar and platform != "linkedin" and deneme < 2:
                    # ayırt etme sınavı yalnızca geri bildirim: her yapay metin bir noktada yakalanıyor, engel olursa hiç taslak kalmıyor (2026-10-22 denemesi)
                    insan, neden = insan_testi(m, pr) if _gelisim_acik("insan_testi") else (True, "")   # kapalı test geçti sayılır (25 Ekim: eskiden başarısız sayılıyordu)
                    if not insan:
                        notlar.append(f"Gerçek gönderilerinin arasına karıştırıldı ve yapay zekâ yazısı olduğu anlaşıldı: {neden}. Bunu düzelt; "
                                      "daha fazla açıklama ekleyerek değil, daha sade ve onun gibi yazarak.")
                        log(f"      Paylaşım {i}: ayırt edildi ({neden[:120]})")
                if _gecti(h) and not notlar:
                    return {"metin": m, "kancalar": [str(x).strip() for x in c.get("kancalar") or [] if str(x).strip()][:2],
                            "zincir": [str(x).strip() for x in c.get("zincir") or [] if str(x).strip()][:4] if uzun else [],
                            "okur": {**_puanlar(h), "konu": h.get("konu")}, "dogruluk": dogruluk, "uzun": uzun, "ilk_taslak": ilk_taslak}
                if deneme == 2:
                    break
                if _gecti(h):
                    # okur geçirdi, yalnızca kod notları (kalıp, 'bence', sayı, insan testi) var: BAŞTAN yazma, yalnız o noktaları düzelt. Baştan yazım
                    # iyi taslağı bozuyordu (23 Ekim: sıcak dalgası taslağı 4/4/4/4 → 3'lere düştü ve elendi).
                    log(f"      Paylaşım {i}: okur geçirdi, yalnız şu noktalar düzeltiliyor: {'; '.join(notlar)[:200]}")
                    c = _claude_json(temel + f"\n\nTASLAK (iyi; okur testini geçti):\n{m}\n\nYALNIZCA ŞU NOKTALARI DÜZELT, geri kalan cümlelere, açıya ve "
                                     "uzunluğa dokunma:\n" + "\n".join(f"- {x}" for x in notlar), model_adi="opus") or c
                else:
                    notlar = list(h.get("sorunlar") or []) + notlar
                    log(f"      Paylaşım {i}: notlarla yeniden yazılıyor ({', '.join(f'{a} {b}' for a, b in _puanlar(h).items())})")
                    c = _claude_json(temel + f"\n\nÖNCEKİ TASLAK:\n{m}\n\nOKUR VE EDİTÖR NOTLARI (okur konuyu şöyle anladı: {h.get('konu')}):\n"
                                     + "\n".join(f"- {x}" for x in notlar) + "\nBaştan yaz. Notlar DAYANAK'ta olmayan bilgi isterse UYDURMA; iddiayı daralt.",
                                     model_adi="opus") or c
                m = _temiz(str(c.get("metin") or m)).strip()
            if gecen:
                log(f"      Paylaşım {i}: yeniden yazım kapıdan geçmedi; daha önce geçen sürüm kullanılıyor")
                return gecen
            son_deneme[i] = {"metin": m, "sorunlar": [str(x) for x in (h.get("sorunlar") or [])][:3], "okur": _puanlar(h)}
            log(f"      Paylaşım {i} geçmedi ({', '.join(f'{a} {b}' for a, b in _puanlar(h).items())}): {m[:120]!r} | "
                f"{'; '.join(map(str, h.get('sorunlar') or []))[:240]}")
            return None

        bicim = k.get("bicim") if k.get("bicim") in ("emoji", "minik", "gozlem", "uzun") else ("uzun" if k.get("uzunluk") == "uzun" else "gozlem")
        if bicim in ("emoji", "minik") and tur not in ("kesif",):     # 20 dakikalık videoya ya da kendi fikrine 3 kelimelik tepki anlamsız
            bicim = "gozlem"
        k["bicim"] = bicim
        if platform != "linkedin" and bicim in ("emoji", "minik"):
            log(f"      Paylaşım {i}/{len(konular)} ({bicim}) yazılıyor...")
            r = hizli_yaz(k, pr, bicim, k.get("paylas_link", ""), log=log)
        else:
            r = _yaz(platform == "linkedin" or bicim == "uzun")
        # eski 'kısa olmadı, uzun dene' kaçışı kaldırıldı (2026-10-22): kısa taslağı eleyen denetim deneme gibi uzun yazılar üretiyordu
        if r is None:
            sd = son_deneme.get(i) or {}
            elenen.append({"k": k, "neden": "Bilmeyen okur için yeterince açık değildi" + (f": {sd['sorunlar'][0]}" if sd.get("sorunlar") else ""),
                           "son_metin": sd.get("metin", ""), "okur": sd.get("okur")})
            continue
        kisa_bicim = k.get("bicim") in ("emoji", "minik") and platform != "linkedin"
        r["itirazlar"] = [] if kisa_bicim else _itirazlar(r["metin"], pr)
        iddialar = [] if kisa_bicim else list(SON_IDDIALAR)
        panel = [] if kisa_bicim else okur_paneli(r["metin"], pr, k.get("paylas_link", ""))
        dyn, dyn_ref = dayanak_belirle(veri, k, r["metin"])
        soru = "" if (dyn or kisa_bicim) else dayanak_sorusu(k, r["metin"], pr)
        taslaklar.append({"bicim": k.get("bicim"), "ton": k.get("ton") or "", "iddialar": iddialar, "panel": panel, "kod_notlari": sayi_notlari(r["metin"], str(k.get("dayanak") or "") + " " + metin[:20000]),
                          "dayanak": dyn, "dayanak_ref": dyn_ref, "soru": soru, "deneyim": str(veri.get("deneyim") or "")[:1000],
                          "platform": platform, "itirazlar": r["itirazlar"], "konu": str(k.get("baglam") or "")[:240], "alan": k.get("alan") or "", "neden_simdi": str(k.get("neden_simdi") or "")[:240],
                          "metin": r["metin"], "kancalar": r["kancalar"], "zincir": r["zincir"], "uzunluk": "uzun" if r["uzun"] else "kisa",
                          "link_oner": bool(k.get("paylas_link")), "ilk_yanit": "", "paylas_link": k.get("paylas_link", ""),
                          "neden": str(k.get("dayanak") or "")[:300], "karakter": len(r["metin"]), "okur": r["okur"], "dogruluk": r["dogruluk"],
                          **({"ilk_taslak": r["ilk_taslak"]} if r.get("ilk_taslak") and r["ilk_taslak"] != r["metin"] else {})})
    # dosyayı yeniden oku: bu sırada çeviri/paket gibi başka işler aynı dosyaya yazmış olabilir, yalnızca kendi alanımızı yaz
    d = json.loads(json_yolu.read_text(encoding="utf-8"))
    ilk = ((d["veri"].get("paylasim") or {}).get("ilk_zaman")) or time.time()     # önerinin günü (Ghost'ta gün gün); yeniden üretimde değişmez
    d["veri"]["paylasim"] = {"taslaklar": taslaklar, "zaman": time.time(), "ilk_zaman": ilk, "model": _yazan(_bas), "surum": 4,
                             "elenen": [{"konu": str(e["k"].get("baglam") or "")[:240], "gorus": str(e["k"].get("gorus") or "")[:300], "alan": e["k"].get("alan") or "",
                                         "neden": e["neden"], "k": e["k"], "son_metin": e.get("son_metin", ""), "okur": e.get("okur")} for e in elenen]}
    json_yolu.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"      {len(taslaklar)} paylaşım taslağı hazır")
    try:
        import kalite
        okur = [t.get("okur") or {} for t in taslaklar]
        kalite.kaydet("paylasim", surum=3, konu=len(konular), taslak=len(taslaklar),
                      ort_deger=sum(o.get("deger", 0) for o in okur) / len(okur) if okur else None,
                      ort_ses=sum(o.get("ses", 0) for o in okur) / len(okur) if okur else None)
    except Exception:  # noqa: BLE001
        pass
    return taslaklar


PANEL = [("Reklamcı", "Türkiye'de reklam/kreatif sektöründe çalışan, iyi işten anlayan, klişeden sıkılan"),
         ("Taraftar", "futbolu taktik ve kulüp işi tarafından da izleyen, kişinin tuttuğu takımın taraftarı"),
         ("Teknolojici", "yapay zekâ ve teknoloji haberlerini yakından izleyen, hype'tan yorulmuş"),
         ("Meşgul okur", "konuyu hiç bilmeyen, akıllı ama acelesi olan sıradan bir X kullanıcısı")]


def okur_paneli(metin, pr, link=""):
    """Sabit 4 okurdan oluşan panel (sonnet, tek çağrı): her biri tepkisini, kaydedip kaydetmeyeceğini, birine iletip iletmeyeceğini ve SESSİZE
    ALMA/ŞİKÂYET riskini söyler; emin değilse 'emin_degil'. Kalite kapısı; erişim tahmini değildir."""
    try:
        c = _claude_json("Aşağıdaki X gönderisini dört farklı okur olarak oku" + (f" (altında şu bağlantının kartı var: {link})" if link else "") + ". Her okur için "
                         "dürüst ol, 5 nadir verilir, gerçekten emin değilsen emin_degil: true. Konu o okurun ilgi alanında değilse ilgisiz: true ver ve puanlama "
                         "(kişinin her gönderisi bütün takipçi gruplarına aynı anda hitap etmek zorunda değil).\n" + "\n".join(f"- {a}: {t}" for a, t in PANEL) +
                         "\nHer okur: tepki (onun ağzından tek cümle), deger (1-5, durup okumaya değer mi), kaydeder (true/false), iletir (birine gönderir mi), "
                         "rahatsiz (true/false: sessize alır, 'ilgilenmiyorum' der ya da şikâyet eder mi), emin_degil.\n"
                         'JSON: {"okurlar": [{"ad": "Reklamcı", "ilgisiz": false, "tepki": "...", "deger": 3, "kaydeder": false, "iletir": false, "rahatsiz": false, "emin_degil": false}]}\n\n'
                         f"GÖNDERİ:\n{metin}", model_adi="sonnet", zaman_asimi=150)
        return [{k_: o.get(k_) for k_ in ("ad", "tepki", "deger", "kaydeder", "iletir", "rahatsiz", "emin_degil")} for o in c.get("okurlar") or []
                if isinstance(o, dict) and not o.get("ilgisiz")][:4]          # ilgisiz okur hesaba katılmaz
    except Exception:  # noqa: BLE001
        return []


TERCIH = KLASOR / "profil" / "duzeltme_tercihleri.json"


def tercihler():
    try:
        return json.loads(TERCIH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []


def ilgili_tercihler(konu, n=5, is_turu=None):
    """CIPHER yaklaşımı: tek tek düzeltmelerden çıkarılan tercihler, konuya en benzer bağlamlardan geri çağrılır (genel tek liste yerine).
    25 Ekim: aynı metin işinden (duyuru, yanıt, espri...) gelen tercih öne geçer."""
    h = _kokler(konu)
    L = [(len(h & _kokler(t.get("konu", "") + " " + t.get("tercih", ""))) + (3 if is_turu and t.get("is_turu") == is_turu else 0), t)
         for t in tercihler() if t.get("aktif", True)]
    yakin = [t for p, t in sorted(L, key=lambda x: -x[0]) if p >= 1][:n]
    genel = [t for p, t in L if t.get("genel")][:3]
    return list({id(t): t for t in yakin + genel}.values())[:n + 2]


def _itirazlar(metin, pr):
    """İtiraz provası: gönderiye gelebilecek en olası iki itiraz ve kişinin sakin, kısa cevabı (sonnet)."""
    try:
        c = _claude_json(f"{_persona_blogu(pr, kisa=True)}\n\nAşağıdaki X gönderisine gelebilecek EN OLASI iki itirazı yaz (alanı bilen, iyi niyetli ama karşı "
                         "görüşte biri). Her birine bu kişinin sesiyle, sakin ve kısa (≤220 karakter) bir cevap: savunmaya geçmeden, gerekiyorsa haklı tarafı "
                         "kabul ederek. Gönderide olmayan olgu uydurma.\nJSON: {\"itirazlar\": [{\"itiraz\": \"...\", \"cevap\": \"...\"}]}\n\nGÖNDERİ:\n" + metin,
                         model_adi="sonnet", zaman_asimi=120)
        return [{"itiraz": str(x.get("itiraz", ""))[:240], "cevap": str(x.get("cevap", ""))[:300]} for x in c.get("itirazlar") or [] if isinstance(x, dict)][:2]
    except Exception:  # noqa: BLE001
        return []


def elenen_yaz(json_yolu, j, log=print):
    """Elenen bir konuyu kullanıcı 'yine de yaz' dedi: okur eşiği olmadan yazılır (doğruluk denetimi ve kalıp kuralları yine geçerli)."""
    json_yolu = Path(json_yolu)
    d = json.loads(json_yolu.read_text(encoding="utf-8")); veri = d["veri"]
    p = veri.get("paylasim") or {}
    E = p.get("elenen") or []
    if not 0 <= j < len(E):
        raise ValueError("Elenen fikir bulunamadı")
    k, pr = E[j]["k"], profil()
    kendi = veri.get("kaynak_tur") == "fikir" or bool(str(veri.get("deneyim") or "").strip())
    uzun = k.get("uzunluk") == "uzun" or len(E[j].get("son_metin") or "") > 280
    istem = _istem(k, pr, uzun) + ("\n\nÖNCEKİ DENEME ve okurun itirazı (bunu gider; dayanakta olmayanı uydurma):\n" + E[j].get("son_metin", "") + "\n" + E[j].get("neden", "")
                                   if E[j].get("son_metin") else "")
    c = _claude_json(istem, model_adi="opus")
    m = _temiz(str(c.get("metin") or "")).strip()
    if not m:
        raise ValueError("Yazılamadı")
    m, dogruluk = _dogrula(m, k.get("dayanak") or "")
    h = _soguk_okur(m, pr)
    t = {"konu": str(k.get("baglam") or "")[:240], "alan": k.get("alan") or "", "neden_simdi": str(k.get("neden_simdi") or "")[:240], "metin": m,
         "kancalar": [str(x).strip() for x in c.get("kancalar") or [] if str(x).strip()][:2], "zincir": [str(x).strip() for x in c.get("zincir") or [] if str(x).strip()][:4] if uzun else [],
         "uzunluk": "uzun" if uzun else "kisa", "link_oner": False, "ilk_yanit": "", "neden": str(k.get("dayanak") or "")[:300], "karakter": len(m),
         "okur": {**_puanlar(h), "konu": h.get("konu")}, "dogruluk": dogruluk, "zorla": True, "itirazlar": _itirazlar(m, pr)}
    d = json.loads(json_yolu.read_text(encoding="utf-8"))
    pp = d["veri"].setdefault("paylasim", {"taslaklar": []})
    pp.setdefault("taslaklar", []).append(t)
    if 0 <= j < len(pp.get("elenen") or []):
        pp["elenen"][j]["yazildi"] = True
    json_yolu.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return t


KANIT_TURU = {"duzenledi": "kişi Ghost'un taslağını kendi düzenledi (paylaşmadan)", "paylasti": "kişi düzenleyip paylaştı",
              "dogrulandi": "düzenlenmiş hali X'te yayımlandığı doğrulandı", "yorum": "kişinin açık yorumu"}


def duzeltme_ogren(once, sonra, is_turu=None, kanit="duzenledi"):
    """Kullanıcı taslağı düzeltip paylaştı: çift saklanır; 3 yeni çift birikince Claude kalıpları 'düzeltme dersleri'ne çevirir (≤8 madde).
    25 Ekim (ChatGPT değerlendirmesi): her ders KAPSAMIYLA (hangi metin işi/ilişki için) ve kanıt türüyle saklanır; tek örnekten genel kural çıkarılmaz,
    kişinin söylemediği gerekçe onun söylediği gibi yazılmaz."""
    once, sonra = str(once or "").strip(), str(sonra or "").strip()
    if not once or not sonra or once == sonra:
        return
    pr = profil()
    L = [x for x in pr.get("duzeltmeler") or [] if isinstance(x, dict)] + [{"once": once[:2000], "sonra": sonra[:2000], "zaman": time.time()}]
    L = L[-30:]
    son = pr.get("duzeltme_dersleri_zaman") or 0
    profil_kaydet(duzeltmeler=L)
    try:                                                 # tek düzeltmeden tercih (CIPHER): konusuyla saklanır, benzer konularda geri çağrılır, geri alınabilir
        c1 = _claude_json("Bir kişi yapay zekânın yazdığı taslağı aşağıdaki gibi düzeltti" + (f" (metnin işi: {IS_TURLERI.get(is_turu, is_turu)})" if is_turu else "")
                          + ". Bu TEK düzeltme hangi yazım tercihini gösteriyor OLABİLİR? Tek seferlik içerik düzeltmesiyse (yanlış olgu, konuya özel ayrıntı) "
                          "ya da yalnızca bu metnin akışını korumaksa tercih boş kalsın. Tek örnekten geniş kural çıkarma: 'Claude anlatısını çıkardı' → doğru ders "
                          "'bu duyuruda ürünün işlevini öne çıkar', yanlış genelleme 'yapay zekâdan hiç bahsetme'. Kişi gerekçe söylemediyse tercihi kesin hüküm "
                          "gibi değil, gözlenen davranış olarak yaz. kapsam: tercihin geçerli olduğu metin işi ya da ilişki (ör. 'ürün duyurusu', 'tanıdığa "
                          "yanıt', 'futbol esprisi'); her yerde geçerliyse 'genel'. genel: true yalnızca kapsam gerçekten her metinse. "
                          "silinen: taslaktan sildiği ve bir daha görmek istemeyeceği kısa ifadeler (en çok 3, 1-4 kelime; yoksa boş).\n"
                          'JSON: {"tercih": "tek cümle, emir kipi", "konu": "2-5 kelime", "kapsam": "...", "genel": false, "silinen": []}\n\n'
                          f"TASLAK:\n{once}\n\nDÜZELTİLMİŞ:\n{sonra}", model_adi="sonnet")
        T = tercihler()
        if str(c1.get("tercih") or "").strip():
            T.append({"tercih": str(c1["tercih"]).strip()[:240], "konu": str(c1.get("konu") or "")[:80], "genel": bool(c1.get("genel")),
                      "kapsam": str(c1.get("kapsam") or "")[:80], "is_turu": is_turu or "", "kanit": kanit,
                      "zaman": time.time(), "aktif": True, "ornek_once": once[:300], "ornek_sonra": sonra[:300]})
            TERCIH.parent.mkdir(parents=True, exist_ok=True); TERCIH.write_text(json.dumps(T[-200:], ensure_ascii=False, indent=1), encoding="utf-8")
        sil = [str(x).strip().lower() for x in c1.get("silinen") or [] if 0 < len(str(x).split()) <= 4]
        if sil:
            pr2 = profil(); sayac = dict(pr2.get("silinen_sayac") or {})
            for x in sil:
                sayac[x] = sayac.get(x, 0) + 1
            profil_kaydet(silinen_sayac=sayac, silinen_ifadeler=sorted([x for x, n in sayac.items() if n >= 2]))
    except Exception:  # noqa: BLE001
        pass
    if sum(1 for x in L if x["zaman"] > son) < 3:
        return
    c = _claude_json("Bir kişi, yapay zekânın kendi adına yazdığı X gönderisi taslaklarını paylaşmadan önce aşağıdaki gibi düzeltti. Düzeltmelerden bu kişinin "
                     "TUTARLI tercihlerini çıkar (ne siliyor, ne ekliyor, hangi kelimeleri değiştiriyor, ritim, uzunluk, ton, açılış/kapanış). Tek seferlik "
                     "içerik düzeltmelerini (yanlış olgu) kural yapma. Yalnızca birden çok düzeltmede tekrar eden tercihleri al; her maddenin sonunda parantez "
                     "içinde kapsamını yaz (hangi tür metinde; ör. '(duyurularda)', '(genel)'). Kelime yasağı koyma; tekrar eden kalıbı söyle. En çok 8 madde, "
                     "her biri tek cümle, emir kipinde, somut.\n"
                     + (f"MEVCUT DERSLER (güncelle, çelişeni çıkar):\n" + "\n".join(f"- {x}" for x in pr.get('duzeltme_dersleri') or []) + "\n" if pr.get("duzeltme_dersleri") else "")
                     + "\n\n".join(f"TASLAK:\n{x['once']}\nPAYLAŞILAN:\n{x['sonra']}" for x in L[-12:])
                     + "\nJSON: {\"dersler\": [\"...\"]}", model_adi="sonnet")
    dersler = [str(x).strip() for x in c.get("dersler") or [] if str(x).strip()][:8]
    if dersler:
        profil_kaydet(duzeltme_dersleri=dersler, duzeltme_dersleri_zaman=time.time())


def yorum_ogren(taslak, yorum):
    """Kullanıcının taslağa yorumu. 2026-10-23: önce TÜRÜ ayrılır (kullanıcının ChatGPT brifi: her geri bildirim üslup tercihi değildir):
    uslup → kalıcı yazım tercihi (duzeltme_tercihleri, 'kaynak: yorum'); konu → konu reddi; bilgi → bilgi hatası kaydı; deneyim → kendi sözü olarak fikir
    defterine; tek → yalnız bu metne uygulanır, öğrenilmez. Döner: arayüzde gösterilecek kısa cümle ('' = öğrenilen bir şey yok)."""
    c = _claude_json("Bir kişi, yapay zekânın kendi adına yazdığı X gönderisi taslağına aşağıdaki yorumu yaptı. Yorumun TÜRÜNÜ belirle:\n"
                     "uslup: nasıl yazdığına dair KALICI bir tercih (uzunluk, açılış, ton, kelime seçimi, ne yazmaz); konu: bu tür konuları istemiyor; "
                     "bilgi: taslaktaki bir olgu yanlış ya da eksik; deneyim: kendi yaşadığı/yaptığı/düşündüğü bir şeyi anlatıyor (gönderiye malzeme); "
                     "tek: yalnızca bu metne özel bir düzeltme.\n"
                     "uslup ise tercih (tek cümle, emir kipi, somut; tek yorumdan geniş kural çıkarma), kapsam (geçerli olduğu metin işi ya da ilişki; ör. "
                     "'ürün duyurusu', 'tanıdığa yanıt'; her yerdeyse 'genel'), genel (kapsam gerçekten her metin mi), silinen (bir daha görmek istemediği "
                     "1-4 kelimelik ifadeler, en çok 3). "
                     "deneyim ise deneyim alanına onun sözünü olduğu gibi (büyütmeden) yaz.\n"
                     'JSON: {"tur": "uslup", "tercih": "", "konu": "2-5 kelime", "kapsam": "", "genel": false, "silinen": [], "deneyim": ""}\n\n'
                     f"TASLAK:\n{taslak.get('metin', '')}\n\nYORUMU:\n{yorum}", model_adi="sonnet")
    tur = str(c.get("tur") or "").strip()
    if tur == "konu":
        red_kaydet({**taslak, "konu": taslak.get("konu") or c.get("konu", "")}, "konu uymuyor")
        return "Bu tür konular daha az gelecek"
    if tur == "bilgi":
        red_kaydet(taslak, "bilgi yanlış")
        return "Bilgi hatası not edildi; zevkiniz sayılmadı"
    if tur == "deneyim" and str(c.get("deneyim") or yorum).strip():
        try:
            import ghost_defter
            ghost_defter.not_ekle(str(c.get("deneyim") or yorum).strip(), "yorum", ek={"taslak": str(taslak.get("metin") or "")[:300]})
            return "Anlattığınızı fikir defterine kendi sözünüz olarak ekledim"
        except Exception:  # noqa: BLE001
            return ""
    if tur != "uslup":
        return ""
    tercih = str(c.get("tercih") or "").strip()
    if tercih:
        T = tercihler()
        T.append({"tercih": tercih[:240], "konu": str(c.get("konu") or "")[:80], "genel": bool(c.get("genel")), "zaman": time.time(), "aktif": True,
                  "kapsam": str(c.get("kapsam") or "")[:80], "is_turu": taslak_is_turu(taslak), "kanit": "yorum", "kaynak": "yorum", "yorum": yorum[:400], "ornek_once": str(taslak.get("metin") or "")[:300]})
        TERCIH.parent.mkdir(parents=True, exist_ok=True); TERCIH.write_text(json.dumps(T[-200:], ensure_ascii=False, indent=1), encoding="utf-8")
    sil = [str(x).strip().lower() for x in c.get("silinen") or [] if 0 < len(str(x).split()) <= 4]
    if sil:
        pr2 = profil(); sayac = dict(pr2.get("silinen_sayac") or {})
        for x in sil:
            sayac[x] = sayac.get(x, 0) + 2                 # açıkça söylendi: tek yorum yeter
        profil_kaydet(silinen_sayac=sayac, silinen_ifadeler=sorted([x for x, n in sayac.items() if n >= 2]))
    return f"Öğrendiğim: {tercih}" if tercih else ""


def son_cumle_alternatifleri(taslak, n=3):
    """Son cümleyi parlatma (24 Ekim): gönderinin geri kalanı aynen kalır, yalnız son cümle için n farklı seçenek (kuru ironi, net hüküm, soru değil).
    Döner: [{"metin": tam gönderi, "son": yeni son cümle}]; kod denetiminden (kalıp, 'bence', 280) geçmeyenler atılır."""
    pr = profil()
    m = taslak.get("metin") or ""
    c = _claude_json(
        "Bu X gönderisinin YALNIZCA SON CÜMLESİNİ yeniden yaz; gerisine dokunma. " + str(n) + " farklı seçenek ver: biri daha kuru/ironik, biri daha net "
        "hüküm, biri daha kısa. Öğüt, vecize, soru, 'işte bu yüzden', 'unutmayın' YOK. Yeni olgu ekleme. Kişinin sesiyle.\n"
        + _persona_blogu(pr, kisa=True) + "\nKİŞİNİN ÖRNEKLERİ:\n" + "\n---\n".join(_ornekler(pr, 6, m))
        + f'\n\nGÖNDERİ:\n{m}\n\nJSON: {{"secenekler": [{{"son": "yeni son cümle", "metin": "gönderinin tamamı, son cümle değişmiş"}}]}}',
        model_adi="opus", zaman_asimi=200)
    out, gor = [], {m.strip()}
    for x in c.get("secenekler") or []:
        t = _temiz(str(x.get("metin") or "")).strip()
        if not t or t in gor or (len(m) <= 280 and len(t) > 280) or _kalip_notlari(t, [], kendi_deneyim=bool(taslak.get("dayanak") == "kendi")):
            continue
        gor.add(t); out.append({"metin": t, "son": str(x.get("son") or "").strip()[:280]})
    return out[:n]


def yeniden_yaz(taslak, talimat):
    """Karttaki tek tık yeniden yazımlar: kisa | keskin | zincir | tek | serbest metin. Döner: güncellenmiş taslak alanları.
    Serbest metin kişinin kendi düzenlediği taslağa ya da belirli bir değişikliğe ise sınırlı düzenleme (sinirli_duzenle) yapılır."""
    pr = profil()
    if sinirli_mi(taslak, talimat):
        r = sinirli_duzenle(taslak.get("metin", ""), talimat, pr, taslak.get("konu", ""), taslak_is_turu(taslak), str(taslak.get("neden") or ""))
        return {"metin": r["metin"], "zincir": taslak.get("zincir") or [], "karakter": len(r["metin"]),
                "uzunluk": "kisa" if len(r["metin"]) <= 280 else "uzun", "onceki": taslak.get("metin"), "duzenleme": {"tur": "sinirli", **r}}
    hedef = {"kisa": "Daha kısa yaz: en çok 280 karakter, tek keskin fikir.",
             "keskin": "Daha keskin yaz: belirleyici ayrımı netleştir; cümleyi sertleştirmek ya da açıyı değiştirmek değil. Bilgi sınırını gösteren "
                       "'olabilir', 'henüz' gibi sözcükleri silme; kaynağın desteklemediği iddia ekleme; uzunluk aynı kalsın.",
             "zincir": "X zincirine çevir: 2-4 parça, her biri ≤270 karakter, ilk parça tek başına kanca; 'zincir' alanını doldur.",
             "tek": "Tek gönderiye çevir: zinciri birleştir, en çok 500 karakter."}.get(
        talimat, f"KİŞİNİN BU TASLAĞA YORUMU (buna harfiyen uy; söylediğini yap, fazlasını ekleme). Bu bir yazım isteği olabilir ya da konu hakkındaki "
                 f"kendi karşılığı/deneyimi; karşılıksa gönderiyi onun etrafında kur, birinci tekil şahıs, büyütmeden: {talimat}\n"
                 "Ayrıca: 'Bence X'teki asıl … değil' kalıbı, haberi anlatmak, öğüt ve vecize kapanış yok; uzunluk düşünce kadar.\n"
                 + __import__("ghost_rehber").DUZENLEME)
    c = _claude_json(f"{_ses_blogu(pr, taslak.get('konu', ''), taslak_is_turu(taslak))}\n\nAşağıdaki X gönderisini bu kişinin sesiyle yeniden yaz. {hedef}\nKurallar aynı: tek başına anlaşılır, "
                     "konunun adı ilk iki cümlede, uydurma olgu yok, hashtag/emoji/kalıp yok, videoya atıf yok.\n"
                     f"KONU: {taslak.get('konu', '')}\nDAYANAK: {taslak.get('neden', '')}\nMEVCUT METİN:\n{taslak.get('metin', '')}\n"
                     + (f"MEVCUT ZİNCİR:\n" + "\n---\n".join(taslak.get("zincir") or []) + "\n" if taslak.get("zincir") else "")
                     + "JSON: {\"metin\": \"...\", \"zincir\": []}", model_adi="opus")
    m = _temiz(str(c.get("metin") or "")).strip()
    if not m:
        raise ValueError("Yeniden yazılamadı")
    z = [str(x).strip() for x in c.get("zincir") or [] if str(x).strip()][:4]
    return {"metin": m, "zincir": z if talimat != "tek" else [], "karakter": len(m), "uzunluk": "kisa" if len(m) <= 280 and not z else "uzun",
            "onceki": taslak.get("metin")}


def plan(taslaklar, gun=5):
    """Plan: günde hedef kadar X gönderisi (profil hedef.x_gunluk; sabah/öğle/akşam/gece), alanlar dengeli (aynı gün aynı alandan en çok 1,
    yapay zekâ toplamın en çok dörtte biri); LinkedIn taslakları 'Bu hafta'. Puan = okur değer+kanca+ses, tazelikle azalır."""
    pr = profil()
    g = max(1, int((pr.get("hedef") or {}).get("x_gunluk") or 1))
    def puan(t):
        o = t.get("okur") or {}
        yas_gun = (time.time() - (t.get("zaman") or time.time())) / 86400
        return (sum(int(o.get(k) or 3) for k in ("deger", "kanca", "ses")) - yas_gun * 0.5 + (3 if t.get("dayanak") else 0)   # kalite önce: dayanaklı taslak öne
        # 24 Ekim: çevrede zaten söylenmiş ya da maçtan hemen sonra/sert dille yazılmış taslak geride
        - (4 if t.get("cevrede") else 0) - (3 if t.get("sogusun") else 0)
        + (4 if t.get("begendi") else 0))                  # 27 Ekim: elden geçirirken "kalsın" dediği öne
    adaylar = sorted([t for t in taslaklar if not t.get("paylasildi") and (t.get("platform") or "x") == "x"], key=lambda t: -puan(t))
    ai = lambda t: bool(re.search(r"yapay|teknoloji ve|\bai\b", t.get("alan") or "", re.I))   # noqa: E731
    gunler, kalan = [], list(adaylar)
    for _n in range(gun):
        bugun, alanlar = [], set()
        for t in list(kalan):
            a = t.get("alan") or "-"
            ai_say = sum(1 for x in sum(gunler, []) + bugun if ai(x))
            alan_tavan = 1 if g <= 4 else -(-g // 3)          # 23 Ekim: günde 12-15 gönderi; alan başına en çok üçte biri
            bicim_tavan = 2 if g <= 4 else -(-g // 2)
            if sum(1 for x in bugun if (x.get("alan") or "-") == a) >= alan_tavan or (ai(t) and ai_say + 1 > max(1, (len(sum(gunler, [])) + len(bugun) + 1) // 4)) \
                    or sum(1 for x in bugun if (x.get("bicim") or "gozlem") == (t.get("bicim") or "gozlem")) >= bicim_tavan:
                continue
            bugun.append(t); alanlar.add(a); kalan.remove(t)
            if len(bugun) >= g:
                break
        if len(bugun) < g:                   # önce biçim sınırını gevşet (alan farklılığı ve yapay zekâ sınırı korunur)
            for t in list(kalan):
                if sum(1 for x in bugun if (x.get("alan") or "-") == (t.get("alan") or "-")) >= (1 if g <= 4 else -(-g // 3)):
                    continue
                if not ai(t) or sum(1 for x in sum(gunler, []) + bugun if ai(x)) < max(1, (len(sum(gunler, [])) + len(bugun) + 1) // 4):
                    bugun.append(t); kalan.remove(t)
                    if len(bugun) >= g:
                        break
        if len(bugun) < g:                   # alan çeşitliliği yetmezse kalanla doldur (yapay zekâ sınırı korunur)
            for t in list(kalan):
                if not ai(t) or sum(1 for x in sum(gunler, []) + bugun if ai(x)) < max(1, (len(sum(gunler, [])) + len(bugun) + 1) // 4):
                    bugun.append(t); kalan.remove(t)
                    if len(bugun) >= g:
                        break
        if not bugun:
            break
        gunler.append(bugun)
    bugun_no = time.localtime().tm_wday
    DILIM = ["Sabah", "Öğle", "Akşam", "Gece", "Gece", "Gece"]
    secilen = []
    for n, L in enumerate(gunler):
        for s_no, t in enumerate(L):
            t["plan_gun"] = "Bugün" if n == 0 else ("Yarın" if n == 1 else GUN_ADI[(bugun_no + n) % 7])
            t["plan_dilim"] = (DILIM[s_no] if g <= 4 else ["Sabah", "Öğle", "Akşam", "Gece"][min(3, s_no * 4 // len(L))]) if g > 1 else ""
            secilen.append(t)
    for t in sorted([t for t in taslaklar if not t.get("paylasildi") and t.get("platform") == "linkedin"], key=lambda t: -puan(t))[:3]:
        t["plan_gun"] = "Bu hafta"; t["plan_dilim"] = ""
        secilen.append(t)
    return secilen


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); raise SystemExit(1)
    for t in uret(sys.argv[1]):
        print(f"\n[{t['uzunluk']} · {t['karakter']} karakter]{' · link önerilir' if t['link_oner'] else ''}\n{t['metin']}")
