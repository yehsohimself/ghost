"""ghost_gelisim.py - Ghost'un kendini besleyen gelişim döngüsü (2026-10-24; kullanıcı: "kendi kendini besleyen, sürekli gelişen, sürekli yeni
özellikleri, gelişmeleri, güncellemeleri takip eden bir yapıya kavuştur").

Neden: 30 günde 63 öneriden 1'i paylaşılmıştı, kaldırılan 20 önerinin 15'i nedensiz toplu retti; Ghost çok yazıyor ama az öğreniyordu.

1) ÖLÇER  (`asama`, `olcum`): her aşamanın girdi/çıktısı (`kayitlar/ghost_asama.jsonl`), önerilerin akıbeti (paylaşıldı / değiştirilerek /
   kaldırıldı + neden / sistemce değiştirildi / dokunulmadı) alan ve tür bazında; konu toplantısının kullanımı; kişinin GHOST DIŞINDA kendi
   yazdığı gönderiler (en dürüst sinyal: gerçekten ne söylemek istemiş).
2) DÜŞÜNÜR (`ozdegerlendirme`, haftada bir, opus): ölçümden
   - güvenli AYARLAR kendiliğinden uygulanır, sınırlıdır ve geri alınabilir: alan ağırlığı (1-5, haftada ±1), günlük X hedefi (6-15, ±2),
     tür üst sınırı (karışım), isteğe bağlı denetim aşamasını kapatma/açma (yalnız `ACILIR_KAPANIR`);
   - NOTLAR (≤6) konu seçimi ve yazım istemlerine girer (`blok()`); bir haftalık DENEY;
   - kod değişikliği gerektiren ÖNERİLER kullanıcının onayına gider (Sesiniz → Gelişim). Kabul edilenler bir sonraki Claude Code oturumunun iş
     listesidir (`profil/gelisim.json` oneriler durum 'kabul'). Kod kendini DEĞİŞTİRMEZ.
3) İZLER (`takip`, haftada bir): X'in yeni özellik ve sıralama haberleri, içerik üreticisi araçları (GitHub, Hacker News), Claude/Anthropic
   güncellemeleri → sonnet "Ghost için ne anlama geliyor" süzgeci → öneri.
"""
import collections
import json
import re
import time
import urllib.parse
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
DOSYA = KLASOR / "profil" / "gelisim.json"
ASAMA = KLASOR / "kayitlar" / "ghost_asama.jsonl"
ACILIR_KAPANIR = {"not_provasi": "Topluluk Notu provası", "cevrede": "Çevrede söylendi denetimi",
                  "insan_testi": "Ayırt etme sınavı"}
SINIR = {"agirlik": (1, 5), "x_gunluk": (6, 15)}


# ---------------------------------------------------------------- kayıt
def oku():
    try:
        d = json.loads(DOSYA.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        d = {}
    d.setdefault("aktif", {}); d.setdefault("raporlar", []); d.setdefault("oneriler", []); d.setdefault("takip", {})
    return d


def yaz(d):
    DOSYA.parent.mkdir(parents=True, exist_ok=True)
    DOSYA.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def asama(ad, giren, cikan, **ek):
    """Bir aşamanın girdi/çıktı sayısı (ör. 'karisim.hakem', 22, 10). Haftalık değerlendirme hangi aşamanın ne elediğini buradan görür."""
    try:
        ASAMA.parent.mkdir(parents=True, exist_ok=True)
        with ASAMA.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.time(), "ad": ad, "giren": int(giren or 0), "cikan": int(cikan or 0), **ek}, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        pass


def acik(ad):
    """İsteğe bağlı denetim aşaması açık mı (öz değerlendirme hiçbir şeyi değiştirmeyen aşamayı kapatabilir; kullanıcı geri açabilir)."""
    return ad not in (oku()["aktif"].get("kapali_asamalar") or [])


def tur_ust(tur):
    """Karışımda türün öz değerlendirmeyle konan üst sınırı (yoksa None)."""
    v = (oku()["aktif"].get("tur_ust") or {}).get(tur)
    return int(v) if isinstance(v, (int, float)) else None


def bicim_ust(bicim):
    """Karışımda biçimin (emoji | minik | gozlem) günlük üst sınırı (yoksa None). 24 Ekim: toplu retlerin 14/15'i uzun 'gözlem' biçimiydi."""
    v = (oku()["aktif"].get("bicim_ust") or {}).get(bicim)
    return int(v) if isinstance(v, (int, float)) else None


def blok(yer="yazim"):
    """İstemlere giren gelişim notları: yer 'konu' (seçim/açı) ya da 'yazim'. Boşsa ''."""
    a = oku()["aktif"]
    N = [n["metin"] for n in a.get("notlar") or [] if isinstance(n, dict) and n.get("yer") in (yer, "ikisi") and n.get("metin")]
    dn = a.get("deney") or {}
    out = ""
    if N:
        out += "GEÇEN HAFTANIN ÖLÇÜMÜNDEN ÇIKAN NOTLAR (kişinin gerçek kararlarından; uy):\n" + "\n".join(f"- {n}" for n in N) + "\n"
    if dn.get("metin") and dn.get("bitis", 0) > time.time() and yer in (dn.get("yer") or "yazim", "ikisi"):
        out += f"BU HAFTANIN DENEYİ (ölçülecek): {dn['metin']}\n"
    if yer == "konu":
        try:
            import yerimleri
            out += yerimleri.ilgi_blogu()
        except Exception:  # noqa: BLE001
            pass
    if yer == "konu" and a.get("ihmal"):
        out += "AZ BESLENEN ALANLAR (kişi önemsiyor ama son günlerde hiç öneri çıkmadı; malzeme varsa bu alanlardan da aday çıkar): " + ", ".join(a["ihmal"]) + "\n"
    return out


# ---------------------------------------------------------------- ölçüm
def _taslaklar(gun):
    sinir = time.time() - gun * 86400
    out = []
    for js in list(KLASOR.glob("transkript_*.json")) + list((KLASOR / "ghost").glob("*.json")):
        if js.stat().st_mtime < sinir:
            continue
        try:
            v = json.loads(js.read_text(encoding="utf-8"))["veri"]
        except Exception:  # noqa: BLE001
            continue
        p = v.get("paylasim") or {}
        if v.get("toplanti") or (p.get("ilk_zaman") or p.get("zaman") or 0) < sinir:
            continue
        for t in p.get("taslaklar") or []:
            out.append({**t, "_kaynak_tur": v.get("kaynak_tur") or "video"})
    return out


def _akibet(t):
    if t.get("paylasildi"):
        return "değiştirilerek paylaşıldı" if t.get("duzenlendi") else "olduğu gibi paylaşıldı"
    if t.get("gizli"):
        if t.get("degistirildi"):
            return "sistem değiştirdi"
        n = str(t.get("red_nedeni") or "")
        return "toplu ret" if n.startswith("tur beğenilmedi") else ("kalite kapısı" if n.startswith("kalite kapısı") else "kaldırdı")
    if t.get("begendi"):
        return "kalsın dedi"
    if t.get("kopyalandi"):
        return "kopyaladı"
    if t.get("duzenlendi") or t.get("yorumlar"):
        return "üzerinde çalıştı"
    return "dokunulmadı"


def olcum(gun=7):
    """Son N günün Ghost ölçümü (yalnız sayılar ve kısa listeler; istemde ve arayüzde kullanılır)."""
    import paylasim
    pr = paylasim.profil()
    T = _taslaklar(gun)
    ak = collections.Counter(_akibet(t) for t in T)
    alan = collections.defaultdict(collections.Counter)
    tur = collections.defaultdict(collections.Counter)
    ad_kod = {a.get("ad"): a.get("kod") for a in pr.get("alanlar") or [] if isinstance(a, dict)}
    for t in T:
        a = t.get("alan_kod") or ad_kod.get(t.get("alan")) or t.get("alan") or "?"
        alan[a][_akibet(t)] += 1
        tur[t.get("karisim_tur") or t.get("bicim") or t["_kaynak_tur"]][_akibet(t)] += 1
    nedenler = collections.Counter(str(t.get("red_nedeni") or "")[:80] for t in T if t.get("gizli") and not t.get("degistirildi") and t.get("red_nedeni"))
    paylasilan = [t["metin"] for t in T if t.get("paylasildi")][:10]
    kaldirilan = [f"{t.get('red_nedeni') or '-'} | {t['metin'][:160]}" for t in T if t.get("gizli") and not t.get("degistirildi")][:14]
    yorumlar = [y.get("yorum") for t in T for y in t.get("yorumlar") or [] if isinstance(y, dict)][:12]
    # aşamalar
    sinir = time.time() - gun * 86400
    A = collections.defaultdict(lambda: [0, 0, 0])
    try:
        for s in ASAMA.read_text(encoding="utf-8").splitlines():
            x = json.loads(s)
            if x.get("t", 0) >= sinir:
                A[x["ad"]][0] += x.get("giren", 0); A[x["ad"]][1] += x.get("cikan", 0); A[x["ad"]][2] += 1
    except Exception:  # noqa: BLE001
        pass
    # kişinin kendi yazdıkları (Ghost'tan gelmeyen; uzantının okuduğu)
    kendi = []
    try:
        import performans
        for x in performans.liste(gun):
            if not x.get("ghost"):
                kendi.append({"metin": str(x.get("metin") or "")[:300], "goruntulenme": x.get("goruntulenme"), "yerimi": x.get("yerimi"), "begeni": x.get("begeni")})
    except Exception:  # noqa: BLE001
        pass
    # konu toplantısı
    kt = {"toplanti": 0, "konu": 0, "yaz": 0, "gec": 0, "cevap": 0}
    for f in (KLASOR / "kayitlar" / "ghost_toplanti").glob("*.json"):
        if f.name.endswith("_ek.json") or f.stat().st_mtime < sinir:
            continue
        try:
            k = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        kt["toplanti"] += 1
        for x in k.get("konular") or []:
            kt["konu"] += 1; kt["yaz"] += x.get("karar") == "yaz"; kt["gec"] += x.get("karar") == "gec"; kt["cevap"] += bool(x.get("cevap"))
    perf = {}
    try:
        import performans
        o = performans.ozet(gun)
        perf = {k: o.get(k) for k in ("adet", "medyan", "kisa_medyan", "uzun_medyan", "ghost_adet", "ghost_medyan")}
    except Exception:  # noqa: BLE001
        pass
    agirlik = {a.get("kod"): a.get("agirlik", 2) for a in pr.get("alanlar") or [] if isinstance(a, dict)}
    return {"gun": gun, "oneri": len(T), "akibet": dict(ak), "alan": {k: dict(v) for k, v in alan.items()}, "tur": {k: dict(v) for k, v in tur.items()},
            "nedenler": dict(nedenler.most_common(10)), "paylasilan": paylasilan, "kaldirilan": kaldirilan, "yorumlar": yorumlar,
            "asamalar": {k: {"giren": v[0], "cikan": v[1], "calisma": v[2]} for k, v in sorted(A.items())},
            "kendi_yazdiklari": kendi[:25], "konu_toplantisi": kt, "performans": perf, "agirlik": agirlik,
            "x_gunluk": (pr.get("hedef") or {}).get("x_gunluk"), "kapali_asamalar": oku()["aktif"].get("kapali_asamalar") or [],
            "tercih_sayisi": len(paylasim.tercihler()), "havuz": len(paylasim.havuz()), "yer_imi": _yerimi_sayisi(),
            # 25 Ekim: editörler ilk taslağı ne kadar değiştiriyor ve kişi kaç kez ilk hâli seçti (editörlerin aşırı müdahalesi)
            "ilk_taslak": {"degisen": sum(1 for t in T if t.get("ilk_taslak")), "ilk_secildi": sum(1 for t in T if t.get("ilk_daha_iyi"))},
            # 27 Ekim: kullanıcının ilgisi (ziyaret/etkileşim günleri) ve bakılmadığı için atlanan üretim (ghost_tempo)
            "tempo": __import__("ghost_tempo").ozet(gun)}


def _yerimi_sayisi():
    try:
        import yerimleri
        return yerimleri.ozet()["adet"]
    except Exception:  # noqa: BLE001
        return 0


def ihmal_edilenler(gun=7):
    """Ağırlığı ≥3 olan ama son N günde hiç öneri çıkmayan alanlar (ör. futbol_teknoloji, 24 Ekim'de 0 taslak)."""
    import paylasim
    o = olcum(gun)
    out = []
    for a in paylasim.profil().get("alanlar") or []:      # görünür (kaldırılmamış) öneri çıkmayan alanlar da ihmal sayılır
        if not isinstance(a, dict) or a.get("agirlik", 2) < 3:
            continue
        x = o["alan"].get(a["kod"]) or {}
        if not sum(n for k, n in x.items() if k not in ("toplu ret", "kalite kapısı", "sistem değiştirdi")):
            out.append(a["kod"])
    return out


# ---------------------------------------------------------------- öz değerlendirme (haftada bir)
def _uygula(degisiklik, d, pr_kaydet, pr):
    """Tek güvenli ayarı uygular. Döner: {tur, hedef, eski, yeni, neden} ya da None (sınır dışı / tanınmayan)."""
    tur, neden = degisiklik.get("tur"), str(degisiklik.get("neden") or "")[:240]
    if tur == "agirlik":
        A = [dict(a) for a in pr.get("alanlar") or [] if isinstance(a, dict)]
        for a in A:
            if a.get("kod") == degisiklik.get("alan"):
                eski = a.get("agirlik", 2)
                yeni = max(SINIR["agirlik"][0], min(SINIR["agirlik"][1], int(degisiklik.get("yeni") or eski)))
                yeni = max(eski - 1, min(eski + 1, yeni))
                if yeni == eski:
                    return None
                a["agirlik"] = yeni; pr_kaydet(alanlar=A)
                return {"tur": tur, "hedef": a["kod"], "eski": eski, "yeni": yeni, "neden": neden}
        return None
    if tur == "x_gunluk":
        h = dict(pr.get("hedef") or {}); eski = int(h.get("x_gunluk") or 10)
        yeni = max(SINIR["x_gunluk"][0], min(SINIR["x_gunluk"][1], int(degisiklik.get("yeni") or eski)))
        yeni = max(eski - 2, min(eski + 2, yeni))
        if yeni == eski:
            return None
        h["x_gunluk"] = yeni; pr_kaydet(hedef=h)
        return {"tur": tur, "hedef": "x_gunluk", "eski": eski, "yeni": yeni, "neden": neden}
    if tur == "tur_ust":
        T = dict(d["aktif"].get("tur_ust") or {}); t = str(degisiklik.get("hedef") or "")
        if t not in ("taraftar", "ironi", "gorus", "haber", "akis") or not isinstance(degisiklik.get("yeni"), (int, float)):
            return None
        eski = T.get(t); T[t] = max(0, min(8, int(degisiklik["yeni"]))); d["aktif"]["tur_ust"] = T
        return {"tur": tur, "hedef": t, "eski": eski, "yeni": T[t], "neden": neden}
    if tur == "bicim_ust":
        B = dict(d["aktif"].get("bicim_ust") or {}); b = str(degisiklik.get("hedef") or "")
        if b not in ("emoji", "minik", "gozlem") or not isinstance(degisiklik.get("yeni"), (int, float)):
            return None
        eski = B.get(b); B[b] = max(0, min(10, int(degisiklik["yeni"]))); d["aktif"]["bicim_ust"] = B
        return {"tur": tur, "hedef": b, "eski": eski, "yeni": B[b], "neden": neden}
    if tur in ("asama_kapat", "asama_ac"):
        a = str(degisiklik.get("hedef") or "")
        if a not in ACILIR_KAPANIR:
            return None
        K = set(d["aktif"].get("kapali_asamalar") or []); eski = a in K
        (K.add if tur == "asama_kapat" else K.discard)(a)
        if (a in K) == eski:
            return None
        d["aktif"]["kapali_asamalar"] = sorted(K)
        return {"tur": tur, "hedef": a, "eski": eski, "yeni": a in K, "neden": neden}
    return None


def _kararli(d):
    """Daha önce karar verilmiş öneriler: istemde 'yeniden önerme' listesi (kabul, red, sonra, yapildi)."""
    K = [x for x in d["oneriler"] if x.get("durum") in ("kabul", "red", "sonra", "yapildi")][-30:]
    return ("DAHA ÖNCE KARAR VERİLEN ÖNERİLER (aynısını ya da benzerini yeniden önerme):\n"
            + "\n".join(f"- [{ {'kabul': 'yapılacak', 'red': 'reddedildi', 'sonra': 'sonraya bırakıldı', 'yapildi': 'yapıldı'}[x['durum']]}] {x['baslik']}" for x in K) + "\n") if K else ""


YASAK_NOT = re.compile(r"[\"'‘“].{2,30}[\"'’”][^.]{0,60}\b(kullanma|yasak|açma|başlama|yazma)\b|\b(kullanma|başlama)\b[^.]{0,40}[\"'‘“]", re.I)


def _celiskisiz(N, pr, log=print):
    """Öğrenilmiş notların süzgeci (25 Ekim): kelime/ifade yasaklayan notlar kodla atılır; kalanlar yazı ilkeleri, okur tepkisinden öğrenilenler ve
    düzeltme tercihleriyle çelişiyor mu diye sonnet ile denetlenir (ör. 'dikkatimi çekti ile başlama' notu, okur tepkisi o açılışı başarılı bulurken)."""
    import paylasim
    N = [n for n in N if not YASAK_NOT.search(n["metin"])]
    if not N:
        return []
    kaynak = [("ilke", x) for x in ((pr.get("persona") or {}).get("ilkeler") or [])] + [("okur tepkisi", x) for x in pr.get("performans_dersleri") or []] \
        + [("düzeltme", t.get("tercih")) for t in paylasim.tercihler() if isinstance(t, dict) and t.get("aktif", True) and t.get("tercih")][-10:]
    c = paylasim._claude_json(
        "Aşağıdaki YENİ NOTLAR bir yazım asistanına verilecek. Her not için, MEVCUT KURALLARDAN biriyle çelişiyor mu ya da bir ifadeyi/yapıyı kanıtsız "
        "yasaklıyor ya da tek örnekten genel kural mı çıkarıyor, bak. tut: true yalnızca çelişmiyorsa ve 'ne söylemeye değer' üzerine somut bir şey "
        'söylüyorsa.\nJSON: {"notlar": [{"no": 0, "tut": true, "neden": "..."}]}\n\nMEVCUT KURALLAR:\n'
        + "\n".join(f"- ({t}) {x}" for t, x in kaynak) + "\n\nYENİ NOTLAR:\n" + "\n".join(f"[{i}] {n['metin']}" for i, n in enumerate(N)),
        model_adi="sonnet", zaman_asimi=180)
    tut = {int(x.get("no")) for x in c.get("notlar") or [] if str(x.get("no", "")).isdigit() and x.get("tut")}
    if c.get("notlar"):
        atilan = [n["metin"][:60] for i, n in enumerate(N) if i not in tut]
        if atilan:
            log(f"Ghost gelişim: {len(atilan)} not çelişki/aşırı genelleme nedeniyle atıldı")
        N = [n for i, n in enumerate(N) if i in tut]
    return N


def ozdegerlendirme(zorla=False, log=print):
    """Haftalık öz değerlendirme. Pazartesi sabahı (ya da zorla). Döner: rapor."""
    import paylasim
    d = oku()
    son = d["raporlar"][-1]["zaman"] if d["raporlar"] else 0
    if not zorla and time.time() - son < 6 * 86400:
        return None
    o = olcum(7)
    pr = paylasim.profil()
    alanlar = "\n".join(f"- {a.get('kod')}: {a.get('ad')} (ağırlık {a.get('agirlik', 2)})" for a in pr.get("alanlar") or [] if isinstance(a, dict))
    onceki = d["raporlar"][-1] if d["raporlar"] else {}
    c = paylasim._claude_json(
        "Bir kişinin X hesabı için gönderi taslakları hazırlayan bir sistemin (Ghost) haftalık öz değerlendirmesini yapıyorsun. Amaç: kişinin "
        "GERÇEKTEN paylaşacağı taslaklar üretmek (önce kalite; büyüme sonra). Ölçüm aşağıda. En dürüst sinyal 'kendi_yazdiklari': Ghost'u kullanmadan "
        "kendisi yazıp attığı gönderiler; konu ve ses olarak Ghost'un önerdikleriyle karşılaştır. 'dokunulmadı' ve 'toplu ret' yüksekse Ghost "
        "hedefi ıskalıyor demektir; sayıyı artırmak çözüm değildir.\n"
        "KANIT SIRASI (25 Ekim, kullanıcının düzeltmesi: 'bir taslağa bakmamam o konuyu istemediğim anlamına gelmez'): GÜÇLÜ sinyaller: paylaşılan taslaklar "
        "(olduğu gibi ya da değiştirilerek; değişikliğin kendisi), kişinin Ghost'suz kendi yazdıkları, NEDENİYLE kaldırılan taslaklar ve yorumlar. ZAYIF "
        "sinyaller: dokunulmadı, nedensiz toplu ret, kalite kapısı. Zayıf sinyalden tek başına alan ağırlığı düşürme, tür/biçim sınırı ya da yazım kuralı "
        "ÇIKARMA; en çok 'bakılacak' diye not et. Bir taslağı beğenmemenin nedeni uzunluk, açılış ya da kelime olmayabilir; çoğu zaman söylenen şeyin "
        "değeridir ('söyleye söyleye bunu mu söyledin' = değer itirazı, 'daha kısa yaz' değil).\n"
        "NOT KURALLARI: kelime ya da ifade YASAKLAMA ('bence', 'dikkatimi çekti' gibi; kötü olan ifade değil tekrarı); tek bir başarılı örneğin yapısını bütün "
        "bir alana yayma; her konuyu aynı açılış ya da kapanış davranışına zorlama; kişinin yazı ilkeleriyle (aşağıda) ÇELİŞEN not yazma. Notlar 'ne söylemeye "
        "değer' üzerine olsun, biçim üzerine değil.\n"
        f"KİŞİ: {pr.get('kimlik', '')}\nALANLAR:\n{alanlar}\n"
        + "YAZI İLKELERİ (bunlarla çelişen not ya da ayar önerme):\n" + "\n".join(f"- {x}" for x in ((pr.get("persona") or {}).get("ilkeler") or [])[:12]) + "\n"
        + (f"GEÇEN HAFTANIN DEĞERLENDİRMESİ: {onceki.get('ozet', '')}\nGEÇEN HAFTANIN DENEYİ: {(onceki.get('deney') or {}).get('metin', '-')}\n" if onceki else "")
        + "\nYAPABİLECEKLERİN:\n"
        "1) degisiklikler (kendiliğinden uygulanır, sınırlı, geri alınabilir; gerekmiyorsa boş bırak; her birine 'sinyal': guclu|zayif yaz, zayıf olanlar "
        "UYGULANMAZ): "
        "{tur: 'agirlik', alan: <kod>, yeni: 1-5 (en çok ±1)} | {tur: 'x_gunluk', yeni: 6-15 (en çok ±2)} | {tur: 'tur_ust', hedef: taraftar|ironi|gorus|haber|akis, yeni: 0-8} | "
        "{tur: 'bicim_ust', hedef: emoji|minik|gozlem, yeni: 0-10 (günde en çok kaç)} | "
        f"{{tur: 'asama_kapat'|'asama_ac', hedef: {'|'.join(ACILIR_KAPANIR)}}} (yalnız aşama ölçümü hiçbir şeyi değiştirmediğini gösteriyorsa kapat). Her birine neden.\n"
        "2) notlar: en çok 6 kısa kural, her biri yer: konu | yazim | ikisi. Somut, ölçüme dayalı (ör. 'Kişi bu hafta 4 kez kendi işini anlattı, Ghost hiç önermedi: "
        "çalışma kaydından haftada 2 kendi işi öner'). Genel yazım tavsiyesi verme; ölçümde dayanağı olmayan not yazma.\n"
        "3) deney: bir hafta denenecek TEK değişiklik ve nasıl ölçüleceği {metin, yer, olcu}.\n"
        "4) oneriler: kod değişikliği gerektiren en çok 3 ürün önerisi {baslik, neden, ne_yapilir}; yalnız ölçümün açıkça gösterdiği sorunlar için.\n"
        + _kararli(d) +
        "5) ozet: kişiye hitaben 2-3 cümle, 'siz' diliyle, sade Türkçe, teknik terim yok: bu hafta ne oldu, ne değiştiriyorum.\n"
        "Değişikliklerin 'neden'i, notlar ve deney de kişiye görünür: 'siz' diliyle yaz ('Bu hafta 7 gönderinizin 4'ü...', 'kişinin' değil); alan "
        "kodlarını (kendi_arac, teknoloji_ai gibi) yazma, alanın adını kullan (Kendi araçları, Teknoloji); kısa tut.\n"
        'JSON: {"ozet": "...", "degisiklikler": [], "notlar": [{"metin": "...", "yer": "konu"}], "deney": {"metin": "...", "yer": "yazim", "olcu": "..."}, "oneriler": []}\n\n'
        f"ÖLÇÜM (son 7 gün):\n{json.dumps(o, ensure_ascii=False, indent=0)[:24000]}", model_adi="opus", zaman_asimi=400)
    if not c.get("ozet"):
        log("Ghost gelişim: öz değerlendirme yanıtı boş"); return None
    yapilan = []
    def kaydet_(**ek):
        paylasim.profil_kaydet(**ek)
    for dg in c.get("degisiklikler") or []:
        if str(dg.get("sinyal") or "").lower() != "guclu":
            continue                                       # zayıf sinyalden ayar yok (dokunulmadı, nedensiz toplu ret)
        try:
            r = _uygula(dg, d, kaydet_, paylasim.profil())
        except Exception:  # noqa: BLE001
            r = None
        if r:
            yapilan.append(r)
    d["aktif"]["notlar"] = _celiskisiz([{"metin": str(n.get("metin"))[:300], "yer": n.get("yer") if n.get("yer") in ("konu", "yazim", "ikisi") else "ikisi"}
                                        for n in c.get("notlar") or [] if isinstance(n, dict) and str(n.get("metin") or "").strip()][:6], pr, log)
    dn = c.get("deney") or {}
    if dn.get("metin"):
        d["aktif"]["deney"] = {"metin": str(dn["metin"])[:300], "yer": dn.get("yer") or "yazim", "olcu": str(dn.get("olcu") or "")[:240],
                               "baslangic": time.time(), "bitis": time.time() + 7 * 86400}
    d["aktif"]["ihmal"] = ihmal_edilenler()
    for x in c.get("oneriler") or []:
        if isinstance(x, dict) and x.get("baslik"):
            d["oneriler"].append({"id": f"o{int(time.time())}{len(d['oneriler'])}", "baslik": str(x["baslik"])[:160], "neden": str(x.get("neden") or "")[:400],
                                  "ne_yapilir": str(x.get("ne_yapilir") or "")[:500], "kaynak": "öz değerlendirme", "durum": "bekliyor", "zaman": time.time()})
    rapor = {"zaman": time.time(), "tarih": time.strftime("%Y-%m-%d"), "ozet": str(c["ozet"])[:800], "degisiklikler": yapilan,
             "notlar": d["aktif"]["notlar"], "deney": d["aktif"].get("deney"), "olcum": {k: o[k] for k in ("oneri", "akibet", "konu_toplantisi", "performans")}}
    d["raporlar"] = (d["raporlar"] + [rapor])[-12:]
    d["oneriler"] = d["oneriler"][-40:]
    yaz(d)
    try:
        import kalite
        kalite.kaydet("ghost_gelisim", degisiklik=len(yapilan), notlar=len(rapor["notlar"]), oneri=o["oneri"], akibet=o["akibet"])
    except Exception:  # noqa: BLE001
        pass
    log(f"Ghost gelişim: {len(yapilan)} ayar, {len(rapor['notlar'])} not, deney: {(rapor.get('deney') or {}).get('metin', '-')[:80]}")
    return rapor


def geri_al(zaman):
    """Bir raporun kendiliğinden yaptığı ayarları geri alır (notlar ve deney de kaldırılır)."""
    import paylasim
    d = oku()
    r = next((x for x in d["raporlar"] if abs(x.get("zaman", 0) - float(zaman)) < 1), None)
    if not r:
        return False
    pr = paylasim.profil()
    for dg in r.get("degisiklikler") or []:
        if dg["tur"] == "agirlik":
            A = [dict(a) for a in pr.get("alanlar") or [] if isinstance(a, dict)]
            for a in A:
                if a.get("kod") == dg["hedef"]:
                    a["agirlik"] = dg["eski"]
            paylasim.profil_kaydet(alanlar=A); pr = paylasim.profil()
        elif dg["tur"] == "x_gunluk":
            h = dict(pr.get("hedef") or {}); h["x_gunluk"] = dg["eski"]; paylasim.profil_kaydet(hedef=h); pr = paylasim.profil()
        elif dg["tur"] == "tur_ust":
            T = dict(d["aktif"].get("tur_ust") or {})
            if dg["eski"] is None:
                T.pop(dg["hedef"], None)
            else:
                T[dg["hedef"]] = dg["eski"]
            d["aktif"]["tur_ust"] = T
        elif dg["tur"] == "bicim_ust":
            B = dict(d["aktif"].get("bicim_ust") or {})
            if dg["eski"] is None:
                B.pop(dg["hedef"], None)
            else:
                B[dg["hedef"]] = dg["eski"]
            d["aktif"]["bicim_ust"] = B
        elif dg["tur"] in ("asama_kapat", "asama_ac"):
            K = set(d["aktif"].get("kapali_asamalar") or [])
            (K.add if dg["eski"] else K.discard)(dg["hedef"]); d["aktif"]["kapali_asamalar"] = sorted(K)
    if r.get("notlar") == d["aktif"].get("notlar"):
        d["aktif"]["notlar"] = []
    if r.get("deney") and r["deney"] == d["aktif"].get("deney"):
        d["aktif"]["deney"] = {}
    r["geri_alindi"] = time.time()
    yaz(d)
    return True


def asama_ayarla(ad, acik_mi):
    d = oku()
    if ad not in ACILIR_KAPANIR:
        return False
    K = set(d["aktif"].get("kapali_asamalar") or [])
    (K.discard if acik_mi else K.add)(ad); d["aktif"]["kapali_asamalar"] = sorted(K); yaz(d)
    return True


def oneri_karar(oid, kabul=None, durum=None, notu=""):
    """durum: kabul | red | sonra (ikinci döneme; listede ayrı durur) | yapildi (geliştirme oturumu tamamladı, `notu` ne yapıldığı)."""
    d = oku()
    durum = durum or ("kabul" if kabul else "red")
    for x in d["oneriler"]:
        if x.get("id") == oid:
            x["durum"] = durum; x["karar_zaman"] = time.time()
            if notu:
                x["yapilan"] = str(notu)[:400]
            yaz(d)
            return x
    return None


def not_sil(i):
    d = oku()
    N = d["aktif"].get("notlar") or []
    if 0 <= i < len(N):
        N.pop(i); d["aktif"]["notlar"] = N; yaz(d); return True
    return False


# ---------------------------------------------------------------- gelişme takibi (haftada bir)
def _gn(q, dil="en"):
    bolge = {"tr": "TR"}.get(dil, "US")
    return f"https://news.google.com/rss/search?q={urllib.parse.quote(q + ' when:7d')}&hl={dil}&gl={bolge}&ceid={bolge}:{dil}"


TAKIP_KAYNAK = [
    ("platform", "X / Twitter", _gn('"X" (algorithm OR "new feature" OR "creator" OR "For You" OR Grok) twitter')),
    ("platform", "X / Twitter", _gn('X Twitter yeni özellik OR algoritma', "tr")),
    ("platform", "LinkedIn", _gn('LinkedIn algorithm OR "new feature" creators')),
    ("platform", "Instagram / Threads", _gn('Instagram OR Threads "new feature" creators')),
    ("model", "Anthropic / Claude", _gn('Anthropic Claude (release OR launches OR "new model" OR "Claude Code")')),
]


def _hn(q):
    import requests
    try:
        j = requests.get("https://hn.algolia.com/api/v1/search_by_date", params={"query": q, "tags": "story", "numericFilters": f"created_at_i>{int(time.time() - 7 * 86400)},points>20"},
                         timeout=15).json()
        return [{"tur": "arac", "kaynak": "Hacker News", "baslik": h.get("title", ""), "link": h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}",
                 "ozet": f"{h.get('points', 0)} puan"} for h in j.get("hits") or []][:10]
    except Exception:  # noqa: BLE001
        return []


def _github(q):
    import requests
    try:
        j = requests.get("https://api.github.com/search/repositories", params={"q": f"{q} pushed:>{time.strftime('%Y-%m-%d', time.localtime(time.time() - 21 * 86400))}",
                                                                              "sort": "stars", "order": "desc", "per_page": 8}, timeout=15,
                         headers={"Accept": "application/vnd.github+json"}).json()
        return [{"tur": "arac", "kaynak": "GitHub", "baslik": f"{r['full_name']} · {r.get('description') or ''}"[:220], "link": r["html_url"],
                 "ozet": f"{r.get('stargazers_count', 0)} yıldız"} for r in j.get("items") or []]
    except Exception:  # noqa: BLE001
        return []


def takip(zorla=False, log=print):
    """Haftalık gelişme taraması. Döner: {tarih, maddeler}."""
    import kesif
    import paylasim
    d = oku()
    if not zorla and time.time() - (d["takip"].get("zaman") or 0) < 6 * 86400:
        return d["takip"]
    M = []
    for tur, ad, url in TAKIP_KAYNAK:
        for m in kesif._akis("gelisim", ad, url, saat=24 * 8)[:12]:
            M.append({"tur": tur, "kaynak": m["kaynak"], "baslik": m["baslik"], "link": m["link"], "ozet": m.get("ozet", "")[:200]})
    for q in ("ghostwriter social media", "twitter thread writer llm", "personal brand content agent", "x algorithm"):
        M += _hn(q)
    for q in ("social media agent llm", "twitter writing assistant", "x-algorithm OR twitter-algorithm"):
        M += _github(q)
    gorulen, U = set(), []
    for m in M:
        k = re.sub(r"\W+", "", m["baslik"].lower())[:70]
        if k and k not in gorulen:
            gorulen.add(k); U.append(m)
    if not U:
        log("Ghost gelişim takibi: kaynak gelmedi"); return d["takip"]
    eski = {x.get("baslik") for x in (d["takip"].get("maddeler") or [])}
    c = paylasim._claude_json(
        "Ghost, bir kişinin (" + (__import__("ortak").kimlik()["kimlik"][:200] or "programlama bilmeyen bir içerik üreticisi") + ") X ve LinkedIn gönderi "
        "taslaklarını hazırlayan kişisel bir araç. Ghost şunları yapıyor: haber ve bülten keşfi, kişinin sesiyle yazım, kalite kapısı, kişinin "
        "düzeltmelerinden öğrenme, X'teki kendi gönderilerinin sayılarını okuma (yalnız okur, otomatik paylaşmaz), canlı maç tepkisi, yanıt taslağı. "
        "Aşağıdaki son bir haftanın maddelerinden GHOST İÇİN GERÇEKTEN ÖNEMLİ olanları seç: (a) X/LinkedIn/Instagram'ın gönderilerin nasıl dağıtıldığını "
        "ya da yeni bir paylaşım biçimini değiştiren güncellemeleri, (b) Ghost'un kopyalayabileceği iyi bir fikri olan araç/açık kaynak proje, (c) Ghost'un "
        "kullandığı Claude'un yeni yetenekleri. Reklam, söylenti, genel haber alma. En çok 6 madde; hiçbiri önemli değilse boş liste.\n"
        "Her madde: no, tur (platform|arac|model), neden (Ghost için ne anlama geliyor, tek cümle), oneri (Ghost'ta ne yapılabilir, tek cümle; 'otomatik "
        "paylaşım', 'takipçi kasma', platform kurallarını çiğneyen öneri YOK).\n"
        + ("GEÇEN HAFTA ZATEN BİLDİRİLENLER (tekrarlama): " + "; ".join(list(eski)[:12]) + "\n" if eski else "") + _kararli(d)
        + 'JSON: {"maddeler": [{"no": 0, "tur": "platform", "neden": "...", "oneri": "..."}]}\n\nMADDELER:\n'
        + "\n".join(f"[{i}] ({m['tur']} · {m['kaynak']}) {m['baslik']} — {m['ozet']}" for i, m in enumerate(U[:90])), model_adi="sonnet", zaman_asimi=300)
    out = []
    for x in c.get("maddeler") or []:
        try:
            m = U[int(x.get("no"))]
        except (TypeError, ValueError, IndexError):
            continue
        if any(o.get("link") == m["link"] or o.get("baslik") == m["baslik"][:160] for o in d["oneriler"]):
            continue                                       # aynı haber/proje zaten önerilmiş (kararı verilmiş ya da bekliyor)
        out.append({**m, "tur": x.get("tur") or m["tur"], "neden": str(x.get("neden") or "")[:300], "oneri": str(x.get("oneri") or "")[:300]})
        d["oneriler"].append({"id": f"t{int(time.time())}{len(d['oneriler'])}", "baslik": m["baslik"][:160], "neden": str(x.get("neden") or "")[:400],
                              "ne_yapilir": str(x.get("oneri") or "")[:500], "kaynak": f"gelişme takibi · {m['kaynak']}", "link": m["link"],
                              "durum": "bekliyor", "zaman": time.time()})
    d["takip"] = {"zaman": time.time(), "tarih": time.strftime("%Y-%m-%d"), "taranan": len(U), "maddeler": out}
    d["oneriler"] = d["oneriler"][-40:]
    yaz(d)
    log(f"Ghost gelişim takibi: {len(U)} madde tarandı, {len(out)} önemli bulundu")
    return d["takip"]


def durum():
    """Arayüz için: son rapor, etkin notlar/deney, bekleyen öneriler, son takip, kısa ölçüm."""
    d = oku()
    o = olcum(7)
    return {"rapor": d["raporlar"][-1] if d["raporlar"] else None, "raporlar": [{k: r.get(k) for k in ("zaman", "tarih", "ozet", "geri_alindi")} for r in d["raporlar"][-6:]][::-1],
            "aktif": d["aktif"], "oneriler": [x for x in d["oneriler"] if x.get("durum") == "bekliyor"][-10:][::-1],
            "kabul": [x for x in d["oneriler"] if x.get("durum") == "kabul"][-10:][::-1],
            "sonra": [x for x in d["oneriler"] if x.get("durum") == "sonra"][-10:][::-1],
            "yapildi": [x for x in d["oneriler"] if x.get("durum") == "yapildi"][-10:][::-1], "takip": d["takip"],
            "olcum": {k: o[k] for k in ("oneri", "akibet", "konu_toplantisi", "asamalar", "performans", "yer_imi")} | {"kendi_yazdiklari": len(o["kendi_yazdiklari"])},
            "asamalar_ad": ACILIR_KAPANIR, "yerimi": _yerimi_ozet()}


def _yerimi_ozet():
    try:
        import yerimleri
        return yerimleri.ozet()
    except Exception:  # noqa: BLE001
        return {}


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "olc":
        print(json.dumps(olcum(int(sys.argv[2]) if len(sys.argv) > 2 else 7), ensure_ascii=False, indent=1)[:6000])
    elif len(sys.argv) > 1 and sys.argv[1] == "degerlendir":
        print(json.dumps(ozdegerlendirme(zorla=True), ensure_ascii=False, indent=1))
    elif len(sys.argv) > 1 and sys.argv[1] == "takip":
        print(json.dumps(takip(zorla=True), ensure_ascii=False, indent=1))
    else:
        print(json.dumps(durum(), ensure_ascii=False, indent=1)[:4000])
