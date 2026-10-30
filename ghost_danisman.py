"""ghost_danisman.py — Ghost'un iletişim danışmanı (2026-10-30; kullanıcı: "iletişim danışmanım gibi de role bürünebilmeli: neyi neden nasıl ne
zaman paylaşacağımı belirtmeli, yaklaşan gündemleri hatırlatmalı, gerçek uzmanlarla başlıyormuşum gibi sorular sormalı, mecralarımın kalitesini
sürekli puanlamalı, eksiklerimi ve aksiyon önerilerini söylemeli").

Dört parça:
1) GÖRÜŞME (`GORUSME`, `gorusme_kaydet`): üç uzman (stratejist, editör, X uzmanı) tek seçimli sorular sorar; cevaplar profilde `strateji` olur ve
   bütün yazım/seçim istemlerine `strateji_blogu()` ile girer. 90 günde bir yenilenir.
2) PUAN KARTI (`puan`): hesabın durumu KODLA ölçülür (model uydurmaz): düzen, çeşitlilik, derinlik, ses, okur tepkisi, tutarlılık; her boyutta
   0-10, dayandığı sayılar, eksik ve tek aksiyon. Veri azsa açıkça "yetersiz veri" der.
3) HAFTALIK NOT (`rapor`): puan + strateji + yaklaşan gündem + geçen haftanın akıbeti → danışman notu (2-3 cümle), en çok 3 eksik/aksiyon ve
   "bu hafta" planı (ne, neden, hangi gün, hangi mecra). Haftada bir (pazartesi) ya da istenince.
4) YAKLAŞAN GÜNDEM (`gundem`, `yaklasan`): kişinin konularında önümüzdeki 3 haftanın tarihli olayları (ödül töreni, lansman, konferans, yıl
   dönümü, final…) Claude'un web aramasıyla bulunur; Bugün'de 3 gün kala hatırlatılır, "Hazırlan" bir taslak fikri açar.
Kayıt: profil/ghost_danisman.json (strateji dışında), kayitlar/ghost_gundem.json. Meet'in kariyer danışmanı (danisman.py) ayrıdır.
"""
import collections
import json
import math
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
DOSYA = KLASOR / "profil" / "ghost_danisman.json"
GUNDEM = KLASOR / "kayitlar" / "ghost_gundem.json"
GORUSME_YENILEME_GUN = 90

# Uzman görüşmesi: her soru tek seçim; `k` kayıtta saklanır, `ad` ekranda. Cevaplar bir istemde cümleye çevrilir (`strateji_blogu`).
GORUSME = [
    {"id": "amac", "uzman": "Stratejist", "soru": "Bu hesap sizin için en çok ne işe yarasın?",
     "secenekler": [{"k": "uzmanlik", "ad": "Alanımda bilinen bir ses olmak", "not": "uzmanlık ve güven"},
                    {"k": "is", "ad": "İş ve müşteri getirmek", "not": "görünürlük işe dönüşsün"},
                    {"k": "topluluk", "ad": "Benim gibi düşünenleri bulmak", "not": "sohbet ve çevre"},
                    {"k": "dusunce", "ad": "Düşüncelerimi düzene koymak", "not": "yazmak için yazmak"}]},
    {"id": "okur", "uzman": "Stratejist", "soru": "Kime yazıyorsunuz?",
     "secenekler": [{"k": "sektor", "ad": "Sektörümdeki kişilere", "not": "jargon serbest, bariz yorum yasak"},
                    {"k": "merakli", "ad": "Konuya meraklı herkese", "not": "bağlamı bir cümleyle kurmak gerekir"},
                    {"k": "musteri", "ad": "Olası müşteri ve iş ortaklarına", "not": "güven veren, somut işler"},
                    {"k": "cevre", "ad": "Tanıdıklarıma ve çevreme", "not": "doğal, sıcak"}]},
    {"id": "konum", "uzman": "Stratejist", "soru": "Sizi başkalarından ayıran bakış ne?",
     "secenekler": [{"k": "icerden", "ad": "İşin içinden gördüklerim", "not": "mutfaktan anlatmak"},
                    {"k": "baglayan", "ad": "Uzak alanları birbirine bağlamam", "not": "futbol ile teknoloji, reklam ile kültür gibi"},
                    {"k": "yapan", "ad": "Konuştuğum şeyi kendim de yapıyor olmam", "not": "kendi işlerinden örnek"},
                    {"k": "elestiren", "ad": "Herkesin sevdiği şeye şüpheyle bakmam", "not": "ters köşe, ama kanıtla"}]},
    {"id": "tempo", "uzman": "X uzmanı", "soru": "Haftada kaç gün paylaşmak istersiniz?",
     "secenekler": [{"k": "7", "ad": "Her gün", "not": "günde en az bir gönderi"},
                    {"k": "4", "ad": "Haftada 3-4 gün", "not": "düzenli ama baskısız"},
                    {"k": "2", "ad": "Haftada 1-2 gün", "not": "az ve seçici"}]},
    {"id": "saat", "uzman": "X uzmanı", "soru": "Günün hangi saatinde Ghost'a bakabilirsiniz?",
     "secenekler": [{"k": "sabah", "ad": "Sabah", "not": "öneriler 07.30'da hazır"},
                    {"k": "ogle", "ad": "Öğle arası", "not": "öğle turu 14.00"},
                    {"k": "aksam", "ad": "Akşam", "not": "günün önerileri biriksin"},
                    {"k": "degisir", "ad": "Değişir", "not": "bildirimle gelsin"}]},
    {"id": "keskinlik", "uzman": "Editör", "soru": "Ne kadar keskin olsun?",
     "secenekler": [{"k": "olculu", "ad": "Ölçülü", "not": "görüş var, kavga yok"},
                    {"k": "sivri", "ad": "Sivri", "not": "adını koyar, gerekirse çarpışır"},
                    {"k": "yumusak", "ad": "Yumuşak", "not": "gözlem ve merak; hüküm nadiren"}]},
    {"id": "uzun", "uzman": "Editör", "soru": "Uzun biçimler (zincir, LinkedIn) ne sıklıkla?",
     "secenekler": [{"k": "haftada", "ad": "Haftada bir", "not": "bir konuyu açmak için"},
                    {"k": "ayda", "ad": "Ayda bir", "not": "yalnız gerçekten değdiğinde"},
                    {"k": "hic", "ad": "Hiç", "not": "yalnız kısa X gönderileri"}]},
    {"id": "basari", "uzman": "Stratejist", "soru": "Altı ay sonra 'işe yaradı' dedirtecek şey ne?",
     "secenekler": [{"k": "takipci", "ad": "Daha çok okur", "not": "takipçi ve görüntülenme"},
                    {"k": "yanki", "ad": "Doğru kişilerden yankı", "not": "mesaj, davet, alıntılanma"},
                    {"k": "is", "ad": "Bir iş ya da teklif", "not": "görünürlüğün karşılığı"},
                    {"k": "duzen", "ad": "Düzenli yazan biri olmak", "not": "alışkanlığın kendisi"}]},
]
GORUSME_METIN = {
    "amac": {"uzmanlik": "hesabın amacı alanında bilinen bir ses olmak", "is": "hesabın amacı iş ve müşteri getirmek",
             "topluluk": "hesabın amacı benzer düşünenlerle çevre kurmak", "dusunce": "hesabın amacı düşüncelerini düzene koymak"},
    "okur": {"sektor": "okur sektördeki kişiler (jargon serbest, bariz yorum yasak)", "merakli": "okur konuya meraklı genel kitle (bağlam tek cümlede kurulur)",
             "musteri": "okur olası müşteri ve iş ortakları (güven veren, somut iş)", "cevre": "okur tanıdıkları ve çevresi (doğal, sıcak)"},
    "konum": {"icerden": "konumu: işin içinden gördüklerini anlatır", "baglayan": "konumu: uzak alanları birbirine bağlar",
              "yapan": "konumu: konuştuğu şeyi kendisi de yapar, kendi işinden örnek verir", "elestiren": "konumu: herkesin sevdiğine şüpheyle bakar, kanıtla"},
    "tempo": {"7": "her gün paylaşmak istiyor", "4": "haftada 3-4 gün paylaşmak istiyor", "2": "haftada 1-2 gün, az ve seçici"},
    "saat": {"sabah": "sabah bakar", "ogle": "öğle arası bakar", "aksam": "akşam bakar", "degisir": "saati değişir"},
    "keskinlik": {"olculu": "keskinlik ölçülü: görüş var, kavga yok", "sivri": "keskinlik sivri: adını koyar", "yumusak": "yumuşak: gözlem ve merak, hüküm nadiren"},
    "uzun": {"haftada": "uzun biçim haftada bir", "ayda": "uzun biçim ayda bir", "hic": "uzun biçim istemiyor"},
    "basari": {"takipci": "başarı ölçüsü: daha çok okur", "yanki": "başarı ölçüsü: doğru kişilerden yankı (mesaj, davet, alıntı)",
               "is": "başarı ölçüsü: bir iş ya da teklif", "duzen": "başarı ölçüsü: düzenli yazan biri olmak"},
}
HAFTALIK_HEDEF = {"7": 7, "4": 4, "2": 2}


# ---------------------------------------------------------------- kayıt
def _oku():
    try:
        d = json.loads(DOSYA.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        d = {}
    return d if isinstance(d, dict) else {}


def _yaz(d):
    DOSYA.parent.mkdir(parents=True, exist_ok=True)
    DOSYA.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def _json_cek(metin):
    """Model yanıtındaki ilk JSON nesnesini/dizisini çıkarır (web aramalı yanıtlar düz metinle gelir)."""
    if isinstance(metin, (dict, list)):
        return metin
    s = str(metin or "")
    m = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", s, re.S)
    aday = m.group(1) if m else None
    if not aday:
        i = min([x for x in (s.find("{"), s.find("[")) if x >= 0] or [-1])
        aday = s[i:] if i >= 0 else ""
    for kes in range(len(aday), 0, -1):
        try:
            return json.loads(aday[:kes])
        except Exception:  # noqa: BLE001
            if aday[kes - 1] not in "}]":
                continue
    return {}


# ---------------------------------------------------------------- 1) uzman görüşmesi
def strateji():
    import paylasim
    s = paylasim.profil().get("strateji")
    return s if isinstance(s, dict) else {}


def gorusme_gerekli():
    s = strateji()
    return not s.get("cevaplar") or time.time() - (s.get("zaman") or 0) > GORUSME_YENILEME_GUN * 86400


def gorusme_kaydet(cevaplar, konum="", notlar=""):
    """Cevaplar {soru_id: seçenek_k}; konum: tek cümlelik kendi tarifi (isteğe bağlı); notlar: serbest ek."""
    import paylasim
    gecerli = {}
    for q in GORUSME:
        k = str((cevaplar or {}).get(q["id"]) or "")
        if any(o["k"] == k for o in q["secenekler"]):
            gecerli[q["id"]] = k
    if not gecerli:
        raise ValueError("Hiç cevap yok")
    s = {"cevaplar": gecerli, "konum": str(konum or "").strip()[:300], "notlar": str(notlar or "").strip()[:1000], "zaman": time.time(),
         "haftalik_hedef": HAFTALIK_HEDEF.get(gecerli.get("tempo", ""), 4)}
    paylasim.profil_kaydet(strateji=s)
    d = _oku(); d.pop("rapor", None); _yaz(d)                # eski not strateji değişince geçersiz
    return s


def strateji_blogu():
    """İstemlere giren kısa blok; görüşme yapılmadıysa ''."""
    s = strateji()
    if not s.get("cevaplar"):
        return ""
    c = [GORUSME_METIN.get(q, {}).get(k) for q, k in s["cevaplar"].items()]
    sat = "; ".join(x for x in c if x)
    out = f"İLETİŞİM STRATEJİSİ (kişinin kendi cevapları; konu seçimi ve ton buna hizmet eder): {sat}."
    if s.get("konum"):
        out += f"\nKENDİ KONUM CÜMLESİ: {s['konum']}"
    if s.get("notlar"):
        out += f"\nEK NOTU: {s['notlar']}"
    return out + "\n"


# ---------------------------------------------------------------- veri
def _paylasilan_taslaklar(gun=28):
    """Ghost'tan paylaşıldı işaretlenen taslaklar: {zaman, alan, dayanak, duzenlendi, platform, link, kaynak_tur}."""
    import kitaplik_onbellek
    sinir = time.time() - gun * 86400
    out = []
    for kayit in kitaplik_onbellek.hepsi(ghost=True):
        veri = kayit["veri"]
        p = veri.get("paylasim") or {}
        if veri.get("toplanti") or not p.get("taslaklar"):
            continue
        for t in p["taslaklar"]:
            z = t.get("paylasim_zaman") or 0
            if t.get("paylasildi") and z >= sinir:
                out.append({"zaman": z, "alan": t.get("alan") or "", "dayanak": t.get("dayanak") or "", "duzenlendi": bool(t.get("duzenlendi")),
                            "platform": t.get("platform") or "x", "link": bool(t.get("paylas_link") or t.get("alinti")), "kaynak_tur": veri.get("kaynak_tur") or "",
                            "metin": str(t.get("metin") or "")[:300]})
    return sorted(out, key=lambda x: -x["zaman"])


def _gercek_gonderiler(gun=28):
    try:
        import performans
        return performans.liste(gun)
    except Exception:  # noqa: BLE001
        return []


def _alan_tahmin(metin, pr):
    """Gerçek gönderinin alanı (uzantı metni; Ghost'tan çıkmadıysa): alan adı/kod sözcükleriyle kaba eşleşme, yoksa ''."""
    m = (metin or "").lower()
    for a in pr.get("alanlar") or []:
        if not isinstance(a, dict):
            continue
        for s in re.findall(r"\w{5,}", (str(a.get("ad") or "") + " " + str(a.get("not") or "")).lower())[:12]:
            if s[:5] in m:
                return a.get("kod") or ""
    return ""


# ---------------------------------------------------------------- 2) puan kartı
def _puan_duzen(G, P, hedef, gun):
    hafta = gun / 7
    sayi = len(G) if G else len(P)
    if not sayi:
        return {"kod": "duzen", "ad": "Düzen", "puan": None, "veri": f"Son {gun} günde ölçülmüş gönderi yok", "kaynak": "", "eksik": "", "aksiyon": {}}
    kaynak = "X profilinizden okunan gönderiler" if G else "Ghost'ta paylaşıldı dediğiniz taslaklar"
    gunler = {time.strftime("%Y-%m-%d", time.localtime(x["zaman"])) for x in (G or P)}
    haftalik = sayi / hafta
    oran = min(1.0, haftalik / max(1, hedef))
    duzen = len(gunler) / max(1, min(gun, hedef * hafta))
    p = round(10 * (0.7 * oran + 0.3 * min(1.0, duzen)), 1)
    veri = f"{sayi} gönderi / {gun} gün ≈ haftada {haftalik:.1f} (hedefiniz {hedef}); {len(gunler)} farklı gün"
    if haftalik < hedef * 0.6:
        eksik, aks = f"Hedefinizin yarısından azını paylaşıyorsunuz ({haftalik:.1f}/{hedef}).", {"ad": "Sabah önerilerden birini 2 dakikada seçin; düzen tempodan önemli", "g": "sekme", "s": "bugun"}
    elif len(gunler) < hafta * 2 and sayi >= 4:
        eksik, aks = "Gönderiler birkaç güne yığılıyor; aralar uzun.", {"ad": "Aynı gün iki gönderi yerine birini yarına bırakın", "g": "sekme", "s": "taslak"}
    else:
        eksik, aks = "", {}
    return {"kod": "duzen", "ad": "Düzen", "puan": p, "veri": veri, "kaynak": kaynak, "eksik": eksik, "aksiyon": aks}


def _puan_cesitlilik(G, P, pr):
    alanlar = [a for a in pr.get("alanlar") or [] if isinstance(a, dict) and (a.get("agirlik") or 0) > 0]
    kodlar = [a.get("kod") for a in alanlar]
    say = collections.Counter()
    for t in P:
        if t.get("alan") in kodlar:
            say[t["alan"]] += 1
    for x in G:
        if not x.get("ghost"):
            k = _alan_tahmin(x.get("metin"), pr)
            if k:
                say[k] += 1
    n = sum(say.values())
    if n < 4:
        return {"kod": "cesitlilik", "ad": "Çeşitlilik", "puan": None, "veri": f"{n} gönderi; alan dağılımı için en az 4 gerekir", "eksik": "", "aksiyon": {}}
    ent = -sum((c / n) * math.log(c / n) for c in say.values())
    norm = ent / math.log(max(2, min(len(kodlar), 6)))
    tepe, tepe_n = say.most_common(1)[0]
    p = round(10 * min(1.0, norm) * (0.6 if tepe_n / n > 0.6 else 1.0), 1)
    ad = {a.get("kod"): a.get("ad") for a in alanlar}
    bos = [ad[k] for k in kodlar if say[k] == 0 and (next(a for a in alanlar if a.get("kod") == k).get("agirlik") or 0) >= 3]
    veri = ", ".join(f"{ad.get(k, k)} {c}" for k, c in say.most_common(5))
    if tepe_n / n > 0.6:
        eksik, aks = f"Gönderilerin %{round(100 * tepe_n / n)}'i tek alanda ({ad.get(tepe, tepe)}); profiliniz tek konuya daralıyor.", {"ad": f"Bu hafta {bos[0] if bos else 'başka bir alandan'} bir gönderi seçin", "g": "sekme", "s": "taslak"}
    elif bos:
        eksik, aks = f"Önem verdiğiniz ama hiç yazmadığınız alanlar: {', '.join(bos[:3])}.", {"ad": f"{bos[0]} için Ghost'a bir fikir bırakın", "g": "sekme", "s": "bugun"}
    else:
        eksik, aks = "", {}
    return {"kod": "cesitlilik", "ad": "Çeşitlilik", "puan": p, "veri": veri, "eksik": eksik, "aksiyon": aks}


def _puan_derinlik(P):
    if len(P) < 3:
        return {"kod": "derinlik", "ad": "Derinlik", "puan": None, "veri": f"{len(P)} paylaşılan taslak; ölçmek için en az 3 gerekir", "eksik": "", "aksiyon": {}}
    kaynakli = sum(1 for t in P if t["link"] or t["dayanak"] in ("kendi", "gorus"))
    kendi = sum(1 for t in P if t["dayanak"] in ("kendi", "gorus"))
    p = round(10 * (0.6 * kaynakli / len(P) + 0.4 * kendi / len(P)), 1)
    veri = f"{kaynakli}/{len(P)} gönderide kaynak ya da kendi dayanağı; {kendi} tanesi kendi görüşünüze ya da işinize dayanıyor"
    if kendi / len(P) < 0.3:
        eksik, aks = "Paylaştıklarınızın çoğu habere tepki; kendi görüşünüzden ya da işinizden çıkanlar az.", {"ad": "Fikirler'deki görüş adaylarını onaylayın; Ghost onları habere bağlar", "g": "sekme", "s": "defter"}
    elif kaynakli / len(P) < 0.6:
        eksik, aks = "Bağlamsız gönderiler var: okur neye tepki verdiğinizi görmüyor.", {"ad": "Taslakta 'Bağlam yok' uyarısı varsa Tetik bul'u kullanın", "g": "sekme", "s": "taslak"}
    else:
        eksik, aks = "", {}
    return {"kod": "derinlik", "ad": "Derinlik", "puan": p, "veri": veri, "eksik": eksik, "aksiyon": aks}


def _puan_ses(P, pr, gun):
    red = [r for r in pr.get("reddedilen") or [] if isinstance(r, dict) and r.get("tur") == "ses" and (r.get("zaman") or 0) > time.time() - gun * 86400]
    if len(P) < 3 and not red:
        return {"kod": "ses", "ad": "Ses", "puan": None, "veri": "Henüz yeterli karar yok", "eksik": "", "aksiyon": {}}
    duz = sum(1 for t in P if t["duzenlendi"])
    oran = duz / max(1, len(P))
    p = round(max(0, 10 * (1 - 0.8 * oran) - min(3, 0.5 * len(red))), 1)
    veri = f"Paylaştığınız {len(P)} taslağın {duz}'ini önce değiştirdiniz; {len(red)} taslağa 'tarzım değil' dediniz"
    if oran > 0.5:
        eksik, aks = "Taslakların yarısından çoğunu paylaşmadan önce yeniden yazıyorsunuz; Ghost sesinizi henüz tam tutturmadı.", {"ad": "Düzelttiğiniz 3 taslakta 'Yorum yap' ile neyi değiştirdiğinizi söyleyin", "g": "sekme", "s": "taslak"}
    elif len(red) >= 3:
        eksik, aks = "'Tarzım değil' dediğiniz taslak çoğaldı.", {"ad": "Profil → Tarzınız'da örnek gönderilerinizi güncelleyin", "g": "sekme", "s": "ses"}
    else:
        eksik, aks = "", {}
    return {"kod": "ses", "ad": "Ses", "puan": p, "veri": veri, "eksik": eksik, "aksiyon": aks}


def _puan_okur(G, gun):
    if len(G) < 5:
        return {"kod": "okur", "ad": "Okur tepkisi", "puan": None, "veri": f"{len(G)} ölçülmüş gönderi; en az 5 gerekir (X profilinize bir kez bakın)", "eksik": "", "aksiyon": {}}
    gor = sum(x.get("goruntulenme") or 0 for x in G)
    deger = sum((x.get("yerimi") or 0) + (x.get("repost") or 0) for x in G) / max(1, gor) * 1000
    orta = time.time() - gun / 2 * 86400
    son = [x["goruntulenme"] for x in G if x["zaman"] >= orta]; once = [x["goruntulenme"] for x in G if x["zaman"] < orta]
    med = lambda xs: sorted(xs)[len(xs) // 2] if xs else 0   # noqa: E731
    egilim = (med(son) / med(once)) if son and once and med(once) else None
    p = round(min(10, 4 * min(2.5, deger)) * (1.1 if egilim and egilim > 1.15 else 0.9 if egilim and egilim < 0.7 else 1.0), 1)
    p = min(10, p)
    veri = f"Bin görüntülenmede {deger:.1f} kaydetme/iletme; medyan {med([x['goruntulenme'] for x in G])}" + (f"; son yarı öncekinin {egilim:.1f} katı" if egilim else "")
    if deger < 0.7:
        eksik, aks = "Okur görüyor ama saklamıyor ya da iletmiyor: gönderiler geçip gidiyor.", {"ad": "Bu hafta bir gönderide yalnız tek somut ayrıntı ve tek yorum deneyin", "g": "sekme", "s": "bugun"}
    elif egilim and egilim < 0.7:
        eksik, aks = "Son iki haftada görüntülenme düştü.", {"ad": "Profil → X'te nasıl gidiyor'daki dersleri okuyun", "g": "sekme", "s": "ses"}
    else:
        eksik, aks = "", {}
    return {"kod": "okur", "ad": "Okur tepkisi", "puan": p, "veri": veri, "eksik": eksik, "aksiyon": aks}


def _puan_tutarlilik(P):
    try:
        import paylasim
        G = [g for g in paylasim.gorusler() if isinstance(g, dict) and not g.get("yerine") and g.get("durum") != "red" and not g.get("dayanak_yok")]
    except Exception:  # noqa: BLE001
        G = []
    bagli = sum(1 for t in P if t["dayanak"] == "gorus")
    p = round(min(10, 5 * min(1.0, len(G) / 25) + 5 * min(1.0, bagli / max(1, len(P)) * 3)), 1) if (G or P) else None
    veri = f"Görüş defterinde {len(G)} görüş; paylaştıklarınızın {bagli} tanesi bir görüşünüze bağlı"
    if len(G) < 10:
        eksik, aks = "Görüş defteri ince: Ghost sizin adınıza tutarlı bir çizgi kuramıyor.", {"ad": "Fikirler → Görüşler'de adayları onaylayın ya da birkaç görüş yazın", "g": "sekme", "s": "defter"}
    elif P and bagli == 0:
        eksik, aks = "Görüşleriniz var ama gönderiler onlara bağlanmıyor.", {"ad": "Bugünün 'görüşünüzle ilgili haber' önerilerini önce okuyun", "g": "sekme", "s": "bugun"}
    else:
        eksik, aks = "", {}
    return {"kod": "tutarlilik", "ad": "Tutarlılık", "puan": p, "veri": veri, "eksik": eksik, "aksiyon": aks}


def puan(gun=28):
    import paylasim
    pr = paylasim.profil()
    s = strateji()
    P = _paylasilan_taslaklar(gun)
    G = _gercek_gonderiler(gun)
    hedef = s.get("haftalik_hedef") or 4
    B = [_puan_duzen(G, P, hedef, gun), _puan_cesitlilik(G, P, pr), _puan_derinlik(P), _puan_ses(P, pr, gun), _puan_okur(G, gun), _puan_tutarlilik(P)]
    dolu = [b["puan"] for b in B if b["puan"] is not None]
    genel = round(sum(dolu) / len(dolu), 1) if dolu else None
    return {"gun": gun, "genel": genel, "boyutlar": B, "yeterli": len(dolu) >= 4, "gonderi": len(G), "paylasilan": len(P), "zaman": time.time(),
            "eksikler": [b for b in B if b["eksik"]]}


# ---------------------------------------------------------------- 4) yaklaşan gündem
def _gundem_oku():
    try:
        d = json.loads(GUNDEM.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _gundem_yaz(d):
    GUNDEM.parent.mkdir(parents=True, exist_ok=True)
    GUNDEM.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def _madde_id(m):
    return re.sub(r"\W+", "", (str(m.get("tarih") or "") + str(m.get("ad") or "")).lower())[:60]


def gundem(zorla=False, log=print, gun_ileri=21):
    """Kişinin konularında önümüzdeki haftaların tarihli olayları (Claude web araması; 3 günde bir). Gizlenen ve hazırlanan işaretleri korunur."""
    import claude_yaz
    import paylasim
    d = _gundem_oku()
    if not zorla and time.time() - (d.get("zaman") or 0) < 3 * 86400 and d.get("maddeler") is not None:
        return d
    pr = paylasim.profil()
    alanlar = [a for a in pr.get("alanlar") or [] if isinstance(a, dict) and (a.get("agirlik") or 0) > 0]
    if not alanlar or not claude_yaz.hazir():
        return d
    bugun = date.today()
    son = bugun + timedelta(days=gun_ileri)
    sat = "\n".join(f"- {a.get('ad')}" + (f" ({str(a.get('not'))[:120]})" if a.get("not") else "") for a in alanlar)
    kimlik = __import__("ortak").kimlik()
    istem = (f"Bugün {bugun.isoformat()}. Aşağıdaki konularda {bugun.isoformat()} ile {son.isoformat()} arasında olacak, TARİHİ BELLİ olayları web'de ara: "
             "ödül törenleri ve kısa listeler, konferans ve fuarlar, ürün lansmanları ve duyuru tarihleri, sezon başı/finaller ve derbiler, yıl dönümleri, "
             "yasal yürürlük tarihleri, kitap/film/dizi çıkışları, rapor yayınları. Yalnız doğruladığın tarihleri yaz; emin olmadığını alma. "
             f"Kişi {kimlik.get('sehir') or 'Türkiye'}'de yaşıyor, Türkçe yazıyor; Türkiye ve küresel gündem birlikte. En çok 12 madde, konu başına en çok 3.\n"
             f"KONULAR:\n{sat}\n\n"
             'Yalnız şu JSON ile yanıt ver: {"maddeler": [{"tarih": "YYYY-MM-DD", "ad": "olayın adı", "alan": "<konu adı listeden>", '
             '"neden": "bu kişi için neden fırsat (tek cümle)", "hazirlik": "önceden ne yazabilir (tek cümle, somut)", "kaynak": "https://..."}]}')
    try:
        y = claude_yaz.sor(istem, model_adi="sonnet", zaman_asimi=420, araclar="WebSearch,WebFetch")
    except Exception as e:  # noqa: BLE001
        log(f"Gündem aranamadı: {e}")
        return d
    c = _json_cek(y)
    eski = {m.get("id"): m for m in d.get("maddeler") or []}
    ad_kod = {str(a.get("ad") or "").lower(): a.get("kod") for a in alanlar}
    yeni = []
    for m in (c.get("maddeler") if isinstance(c, dict) else c) or []:
        try:
            t = datetime.strptime(str(m.get("tarih"))[:10], "%Y-%m-%d").date()
        except Exception:  # noqa: BLE001
            continue
        if not (bugun - timedelta(days=1) <= t <= son) or not str(m.get("ad") or "").strip():
            continue
        x = {"tarih": t.isoformat(), "ad": str(m["ad"]).strip()[:140], "alan": ad_kod.get(str(m.get("alan") or "").lower(), ""), "alan_ad": str(m.get("alan") or "")[:60],
             "neden": str(m.get("neden") or "").strip()[:300], "hazirlik": str(m.get("hazirlik") or "").strip()[:300],
             "kaynak": str(m.get("kaynak") or "")[:400] if str(m.get("kaynak") or "").startswith("http") else ""}
        x["id"] = _madde_id(x)
        if x["id"] in eski:
            x.update({k: eski[x["id"]][k] for k in ("gizli", "hazirlandi") if k in eski[x["id"]]})
        yeni.append(x)
    # bugünden eskileri at, yeni listede olmayan ama tarihi gelmemiş eskileri koru
    for k, m in eski.items():
        if k not in {x["id"] for x in yeni} and str(m.get("tarih") or "") >= bugun.isoformat():
            yeni.append(m)
    yeni.sort(key=lambda m: m["tarih"])
    d = {"zaman": time.time(), "maddeler": yeni[:30], "kaynak": "Claude web araması"}
    _gundem_yaz(d)
    log(f"Yaklaşan gündem: {len(yeni)} madde")
    return d


def yaklasan(gun=3):
    bugun = date.today().isoformat(); son = (date.today() + timedelta(days=gun)).isoformat()
    return [m for m in _gundem_oku().get("maddeler") or [] if bugun <= str(m.get("tarih")) <= son and not m.get("gizli")]


def gundem_isaretle(mid, gizli=None, hazirlandi=None):
    d = _gundem_oku()
    for m in d.get("maddeler") or []:
        if m.get("id") == mid:
            if gizli is not None:
                m["gizli"] = bool(gizli)
            if hazirlandi is not None:
                m["hazirlandi"] = hazirlandi
    _gundem_yaz(d)
    return d


def hazirlik_girdisi(m):
    """'Hazırlan' → Ghost'un yazma kutusuna giden fikir metni (paylasim.girdi_turu bunu 'fikir' sayar)."""
    t = datetime.strptime(m["tarih"], "%Y-%m-%d").date()
    gun = (t - date.today()).days
    ne_zaman = "bugün" if gun == 0 else "yarın" if gun == 1 else f"{gun} gün sonra ({t.strftime('%d.%m')})"
    return (f"Yaklaşan olay: {m['ad']} ({ne_zaman}). {m.get('neden', '')} "
            f"Önceden paylaşmak için gözlem: {m.get('hazirlik', '')}")[:580]


# ---------------------------------------------------------------- 3) haftalık not
def rapor(zorla=False, log=print):
    import claude_yaz
    import paylasim
    d = _oku()
    r = d.get("rapor") or {}
    if not zorla and time.time() - (r.get("zaman") or 0) < 6 * 86400:
        return r
    if not claude_yaz.hazir():
        return r
    pr = paylasim.profil()
    P = puan()
    gd = gundem(log=log)
    try:
        import ghost_gelisim
        ak = ghost_gelisim.olcum(7).get("akibet") or {}
    except Exception:  # noqa: BLE001
        ak = {}
    boy = "\n".join(f"- {b['ad']}: {b['puan'] if b['puan'] is not None else 'veri yetersiz'}/10 — {b['veri']}" + (f" | EKSİK: {b['eksik']}" if b["eksik"] else "") for b in P["boyutlar"])
    yak = "\n".join(f"- {m['tarih']} {m['ad']} ({m.get('alan_ad') or m.get('alan')}): {m.get('neden', '')}" for m in (gd.get("maddeler") or [])[:10] if not m.get("gizli")) or "- yok"
    gunler = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
    istem = (f"Sen bu kişinin iletişim danışmanısın (stratejist + editör + X uzmanı, tek ses). Kişi: {pr.get('kimlik', '')}\n{strateji_blogu()}"
             f"PUAN KARTI (kodla ölçüldü, son {P['gun']} gün; {P['gonderi']} gerçek gönderi, Ghost'tan {P['paylasilan']} paylaşım):\n{boy}\n"
             f"GEÇEN HAFTA ÖNERİLERİN AKIBETİ: {json.dumps(ak, ensure_ascii=False)}\n"
             f"OKUR VERİSİNDEN DERSLER: {'; '.join(pr.get('performans_dersleri') or []) or '-'}\n"
             f"YAKLAŞAN GÜNDEM (bugün {date.today().isoformat()}, {gunler[date.today().weekday()]}):\n{yak}\n\n"
             "Görev: 'siz' diliyle, kısa ve dürüst. Sayı uydurma; yalnız yukarıdaki veriyi kullan. Övme, klişe yok ('harika', 'potansiyel').\n"
             "not: 2-3 cümle; bu hafta hesabın gerçekten neye ihtiyacı var.\n"
             "eksikler: en çok 3; her biri {baslik (≤6 kelime), neden (tek cümle, veriye bağlı), aksiyon (tek somut adım, bu hafta yapılabilir)}.\n"
             "hafta: 3-5 madde; her biri {gun (hafta günü adı), ne (hangi tür gönderi / konu), neden (stratejiye ya da gündeme bağlı tek cümle), "
             "mecra (X | zincir | LinkedIn)}; yaklaşan gündemden en az biri varsa tarihinden 1-2 gün önce planla; kişinin bakabildiği saate uy.\n"
             "kacin: tek cümle, bu hafta yapmaması gereken.\n"
             'JSON: {"not": "...", "eksikler": [...], "hafta": [...], "kacin": "..."}')
    try:
        c = paylasim._claude_json(istem, model_adi="sonnet", zaman_asimi=240)
    except Exception as e:  # noqa: BLE001
        log(f"Danışman notu yazılamadı: {e}")
        return r
    if not c.get("not"):
        return r
    r = {"zaman": time.time(), "not": str(c.get("not"))[:800], "kacin": str(c.get("kacin") or "")[:300],
         "eksikler": [{k: str(e.get(k) or "")[:300] for k in ("baslik", "neden", "aksiyon")} for e in (c.get("eksikler") or []) if isinstance(e, dict)][:3],
         "hafta": [{k: str(e.get(k) or "")[:300] for k in ("gun", "ne", "neden", "mecra")} for e in (c.get("hafta") or []) if isinstance(e, dict)][:5],
         "puan": P["genel"], "model": claude_yaz.SON_MODEL if hasattr(claude_yaz, "SON_MODEL") else ""}
    d["rapor"] = r
    d.setdefault("gecmis", []).append({"zaman": r["zaman"], "puan": P["genel"], "boyutlar": {b["kod"]: b["puan"] for b in P["boyutlar"]}})
    d["gecmis"] = d["gecmis"][-26:]
    _yaz(d)
    log("Danışman notu yazıldı")
    return r


def durum():
    d = _oku()
    return {"gorusme_gerekli": gorusme_gerekli(), "strateji": strateji(), "sorular": GORUSME, "puan": puan(), "rapor": d.get("rapor") or {},
            "gecmis": d.get("gecmis") or [], "gundem": [m for m in _gundem_oku().get("maddeler") or [] if str(m.get("tarih")) >= date.today().isoformat()],
            "gundem_zaman": _gundem_oku().get("zaman") or 0, "yaklasan": yaklasan(3)}


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["gundem"]:
        print(json.dumps(gundem(zorla=True), ensure_ascii=False, indent=1))
    elif sys.argv[1:] == ["rapor"]:
        print(json.dumps(rapor(zorla=True), ensure_ascii=False, indent=1))
    else:
        print(json.dumps(puan(), ensure_ascii=False, indent=1))
