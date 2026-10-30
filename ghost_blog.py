"""ghost_blog.py - kişinin blogu için yazı konusu önerileri (2026-10-26; kişi: "Ghost'a blog konusu öneren ayrı bir akış kur: tema, sektörel çekirdek,
soru, başlangıç kaynağı ve bilinmeyenle; ilk yazılar genelden").

Kurallar `ghost_rehber.BLOG_KAPSAMI` ve `KONU_ONERME`'de: asıl mesele sektörel (reklam, yaratıcı iş, marka, iletişim, medya, yaratıcı süreçte teknoloji,
bağımsız çalışma); futbol, film, şehir gibi tema yalnız giriş ya da malzeme; blog kişinin kendi işleriyle sınırlı değil; blog yeni açıldı, ilk yazılar
nişten değil daha genel bir meseleden; öneri geniş başlık değil: belirli soru, başlanabilecek gözlem ya da kaynak, henüz bilinmeyen. Açı kişinin tezi
gibi yazılmaz; okumadığı, yaşamadığı, benimsemediği ona atfedilmez.

Malzeme (yalnız önbellek, ağ yok): son 5 günün keşif önerileri (`kayitlar/kesif/<gün>.json`), konu toplantısı konuları ve varsa kişinin oradaki kendi
cevabı (`kayitlar/ghost_toplanti`), son 10 günün ChatGPT seçkisi (`kayitlar/secki`). Kaynak bağlantısı yalnız malzemeden gelir (model uyduramaz).
Kayıt: `kayitlar/ghost_blog/oneriler.json` (en yeni önce; kişinin kararı 'begendim' | 'gec' ve isteğe bağlı nedeniyle; sonraki tura girer).

oner(yon="", log) → yeni öneriler; liste() → hepsi; isaretle(id, durum, neden).
"""
import datetime
import json
import re
import time
import uuid
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
KAYIT = KLASOR / "kayitlar" / "ghost_blog"
DOSYA = KAYIT / "oneriler.json"


def liste():
    try:
        return json.loads(DOSYA.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []


def _yaz(L):
    KAYIT.mkdir(parents=True, exist_ok=True)
    DOSYA.write_text(json.dumps(L[:120], ensure_ascii=False, indent=1), encoding="utf-8")


def _gunler(n):
    bugun = datetime.date.today()
    return [(bugun - datetime.timedelta(days=i)).isoformat() for i in range(n)]


def _linkler(x):
    if isinstance(x, list):
        return [str(u) for u in x if str(u).startswith("http")]
    return re.findall(r"https?://[^\s'\",\]]+", str(x or ""))


SEKTOREL = ("reklamcilik", "kreatif", "gusto", "populer_kultur", "hikaye", "toplum", "futbol_teknoloji", "kendi_arac")


def malzeme(en_cok=60):
    """[{id, tur, baslik, ozet, link, kaynak, alan, kendi}] (tekrarsız; en yeni önce)."""
    M, gorulen = [], set()

    def ekle(tur, baslik, ozet, link, kaynak, alan="", kendi=""):
        a = re.sub(r"\W+", "", str(baslik).lower())[:60]
        if not baslik or a in gorulen:
            return
        gorulen.add(a)
        M.append({"id": f"m{len(M)}", "tur": tur, "baslik": str(baslik)[:200], "ozet": re.sub(r"\s+", " ", str(ozet or ""))[:420],
                  "link": str(link or ""), "kaynak": str(kaynak or "")[:80], "alan": str(alan or ""), "kendi": str(kendi or "")[:400]})
    for gun in _gunler(5):
        for f in sorted((KLASOR / "kayitlar" / "ghost_toplanti").glob(f"{gun}_*.json")):
            if f.name.endswith("_maddeler.json"):
                continue
            try:
                T = json.loads(f.read_text(encoding="utf-8")).get("konular") or []
            except Exception:  # noqa: BLE001
                T = []
            for k in T:
                ekle("haber", k.get("baslik"), k.get("ayrinti"), k.get("link"), k.get("kaynak"), k.get("alan"), k.get("cevap") or "")
        try:
            K = json.loads((KLASOR / "kayitlar" / "kesif" / f"{gun}.json").read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            K = {}
        for o in K.get("oneriler") or []:
            ekle("haber", o.get("baslik"), o.get("ozet"), o.get("link"), o.get("kaynak"), o.get("alan"))
    for gun in _gunler(10):
        try:
            s = json.loads((KLASOR / "kayitlar" / "secki" / f"{gun}.json").read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        for k in s.get("konular") or []:
            L = _linkler(k.get("kaynaklar"))
            ekle("arastirma", k.get("baslik"), str(k.get("metin") or "") + (f" KANIT SINIRI: {k['kanit_siniri']}" if k.get("kanit_siniri") else ""),
                 L[0] if L else "", "ChatGPT seçkisi")
    # sektöre yakın alanlar önce (çekirdek sektörel olacak); araştırma notları ayrı paydan, haber akışı onları itmesin
    H = sorted((m for m in M if m["tur"] == "haber"), key=lambda m: (m["alan"] not in SEKTOREL, bool(not m["kendi"])))
    A = [m for m in M if m["tur"] == "arastirma"]
    out = H[: en_cok - min(len(A), en_cok // 4)] + A[: en_cok // 4]
    for i, m in enumerate(out):
        m["id"] = f"m{i}"
    return out


def oner(yon="", log=print, n=5):
    """Yeni blog konusu önerileri (opus, tek çağrı). yon: kişinin bu tur için verdiği yön (isteğe bağlı). Döner: yeni öneriler."""
    import ghost_rehber
    import paylasim
    pr = paylasim.profil()
    M = malzeme()
    if not M:
        raise ValueError("Önerilecek malzeme yok: keşif ya da seçki henüz bir şey getirmedi.")
    onceki = liste()
    gecmis = "\n".join(f"- [{o.get('durum') or 'karar yok'}{': ' + o['neden'] if o.get('neden') else ''}] {o.get('cekirdek', '')} | {o.get('soru', '')[:160]}"
                       for o in onceki[:25])
    log(f"Blog konuları aranıyor ({len(M)} malzeme)...")
    c = paylasim._claude_json(
        f"Bugün {time.strftime('%d.%m.%Y')}. Bu kişinin yeni açılan blogu için yazı konusu öneriyorsun; yazıyı o yazacak, sen yalnız konu "
        f"öneriyorsun.\nKİŞİ: {pr.get('kimlik', '')}\n{paylasim._persona_blogu(pr, kisa=True, platform='blog')}\n\n{ghost_rehber.oneri_blogu('blog')}\n\n"
        + (f"KİŞİNİN BU TUR İÇİN YÖNÜ (buna uy): {yon}\n" if yon else "")
        + ("DAHA ÖNCE ÖNERİLENLER (aynısını ya da aynı çekirdeği yeniden önerme; 'gec' ve nedeni varsa o yönden kaçın, 'begendim' olanların türünden "
           "öğren ama kopyalama):\n" + gecmis + "\n" if gecmis else "")
        + f"\nEn çok {n} öneri. Malzemede sektörel bir çekirdeğe gerçekten bağlanan konu yoksa daha az öner; zorlama. Her öneri:\n"
        "- tema: yazının girişi ya da malzemesi (bir haber, film, maç, kitap, şehir ayrıntısı; sektörün kendisi de olabilir)\n"
        "- cekirdek: asıl sektörel mesele, tek cümle (reklam, yaratıcı iş, marka, iletişim, medya, yaratıcı süreçte teknoloji, bağımsız çalışma)\n"
        "- soru: yazının sorduğu belirli soru; geniş başlık değil, cevabı henüz belli olmayan\n"
        "- baslangic: başlanabilecek somut gözlem ya da kaynaktaki ayrıntı (yalnız o kaynakta yazanla; ilgisiz ikinci bir malzemeyi 'yan malzeme' diye "
        "ekleme, malzeme id'sini metne yazma)\n"
        "- kaynak: dayandığı malzemenin id'si (m…); birden çoksa ilki. Malzemeye dayanmıyorsa boş bırak ve baslangic'ta nereden başlanacağını söyle\n"
        "- bilinmeyen: henüz bilinmeyen ya da malzemenin söylemediği; yalnız başlık ya da özet okunduysa bunu da söyle\n"
        "- neden_genel: bu konunun blogun ilk yazıları için neden uygun bir genel giriş olduğu (niş değil, sektörü bilen geniş okura açık), tek cümle\n"
        "- kendi: malzemede kişinin kendi cevabı varsa ve bu öneri ona dayanıyorsa o cevap aynen; yoksa boş. Ona başka görüş ya da deneyim atfetme.\n"
        "Açıyı kişinin tezi gibi yazma ('bence', 'asıl mesele şu ki' yok); soru ve gözlem olarak yaz. Her konuyu yapay zekaya bağlama; önerilerin en çok "
        "biri yapay zeka üzerine olsun.\n"
        'JSON: {"oneriler": [{"tema": "", "cekirdek": "", "soru": "", "baslangic": "", "kaynak": "m0", "bilinmeyen": "", "neden_genel": "", "kendi": ""}]}\n\n'
        "MALZEME:\n" + "\n".join(f"[{m['id']}] ({m['tur']} · {m['kaynak']}{' · ' + m['alan'] if m['alan'] else ''}) {m['baslik']}: {m['ozet']}"
                                 + (f"\n    KİŞİNİN KENDİ CEVABI: {m['kendi']}" if m["kendi"] else "") for m in M),
        model_adi="opus", zaman_asimi=400)
    idx = {m["id"]: m for m in M}
    yeni = []
    for o in c.get("oneriler") or []:
        if not isinstance(o, dict) or not str(o.get("soru") or "").strip() or not str(o.get("cekirdek") or "").strip():
            continue
        m = idx.get(str(o.get("kaynak") or "").strip())
        kendi = str(o.get("kendi") or "").strip()
        if kendi and not (m and m["kendi"] and re.sub(r"\W+", "", kendi.lower())[:40] in re.sub(r"\W+", "", m["kendi"].lower())):
            kendi = ""                                      # kişinin sözü yalnız malzemede aynen varsa
        alan = {a: re.sub(r"\s*\(?\bm\d{1,2}\b\)?:?", "", paylasim._temiz(str(o.get(a) or ""))).strip()   # iç malzeme kimliği okura görünmesin
                for a in ("tema", "cekirdek", "soru", "baslangic", "bilinmeyen", "neden_genel")}
        notlar = sorted({x for a in ("soru", "baslangic", "cekirdek") for x in ghost_rehber.dil_notlari(alan[a], kendi_deneyim=bool(kendi))})
        yeni.append({"id": uuid.uuid4().hex[:8], "zaman": time.time(), **alan, "kendi": kendi, "yon": yon[:300],
                     "kaynak": ({"baslik": m["baslik"], "link": m["link"], "ad": m["kaynak"], "tur": m["tur"]} if m else None),
                     "notlar": notlar, "durum": None, "neden": ""})
    _yaz(yeni + liste())
    log(f"Blog: {len(yeni)} konu önerildi")
    return yeni


def isaretle(oid, durum, neden=""):
    """durum: 'begendim' | 'gec' | 'yazildi' | None (geri al)."""
    L = liste()
    for o in L:
        if o.get("id") == oid:
            o["durum"] = durum if durum in ("begendim", "gec", "yazildi") else None
            o["neden"] = str(neden or "")[:200]
            _yaz(L)
            return o
    raise ValueError("Öneri bulunamadı")


if __name__ == "__main__":
    for o in oner(" ".join(__import__("sys").argv[1:])):
        print(json.dumps(o, ensure_ascii=False, indent=1))
