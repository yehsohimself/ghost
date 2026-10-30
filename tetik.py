"""tetik.py - Bir gönderinin TETİĞİ: neye tepki olarak paylaşıldığı (2026-10-23).

Kullanıcı: "Kimse durup dururken böyle bir şey paylaşmaz. Bir şey görüp paylaşması lazım. Uygun bir link veya tweet bul ki onu alıntılayayım; yoksa insanlar
bağlamı anlayamaz. Sıfırdan yapılacak paylaşım ile alıntı aynı dilde olmamalı."

adaylar(konu, metin): görüşü tetikleyebilecek içerikler: Google News araması (son 7 gün; sorguları Claude çıkarır, tr + en) + kullanıcının X'te açıp okuduğu
gönderiler (uzantı, yalnız okuma). X'te otomatik arama YOK (hesap riski). Ayrı yargıç (sonnet) yalnızca bu görüşün GERÇEKTEN doğal bir tepki olacağı
adayları bırakır (uyum ≥4). Döner: [{tur: haber|tweet, baslik, metin, link, kaynak, tarih, uyum, neden}].
tepki_olarak_yaz(taslak, aday): metni o tetiğe TEPKİ dilinde yeniden yazar (haber → bağlantı kartıyla; tweet → alıntı). Sıfırdan paylaşım dili değil.
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import paylasim

KLASOR = Path(__file__).resolve().parent


def _x_gorulen(gun=3):
    try:
        L = json.loads((KLASOR / "kayitlar" / "x_gorulen.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    L = L if isinstance(L, list) else list(L.values())
    return [x for x in L if time.time() - (x.get("zaman") or 0) < gun * 86400 and x.get("metin")]


def adaylar(konu, metin, en_cok=3, log=print):
    import kesif
    q = paylasim._claude_json(
        "Bir kişi aşağıdaki görüşü X'te paylaşmak istiyor ama durup dururken değil, bir şeye TEPKİ olarak. Bu görüşü doğal olarak tetikleyebilecek GÜNCEL "
        "haberleri bulmak için Google News'te aranacak 4 kısa sorgu yaz: 2 Türkçe, 2 İngilizce; 2-5 kelime; görüşün kendisini değil, onu tetikleyecek "
        "olayı/haberi ara (ör. bir şirketin açıklaması, bir araştırma, bir ürün lansmanı, tartışılan bir olay).\n"
        'JSON: {"tr": ["...", "..."], "en": ["...", "..."]}\n\n'
        f"KONU: {konu}\nGÖRÜŞ: {metin}", model_adi="sonnet", zaman_asimi=90)
    sorgular = [(s, "tr") for s in (q.get("tr") or [])[:2]] + [(s, "en") for s in (q.get("en") or [])[:2]]
    haberler = []
    with ThreadPoolExecutor(4) as h:
        for L in h.map(lambda x: kesif._akis("arama", "Haberler", kesif._gn(str(x[0]), x[1], "7d"), saat=24 * 7), sorgular):
            haberler += L[:6]
    gorulen, A = set(), []
    for m in haberler:
        k = m["baslik"].lower()[:60]
        if k in gorulen:
            continue
        gorulen.add(k)
        A.append({"tur": "haber", "baslik": m["baslik"], "metin": (m.get("ozet") or "")[:300], "link": m.get("link", ""), "kaynak": m.get("kaynak", ""),
                  "tarih": time.strftime("%Y-%m-%d", time.localtime(m["zaman"])) if m.get("zaman") else ""})
    try:                                                   # izlenen hesapların son 3 gündeki gönderileri önce (hesaplar.py)
        import hesaplar
        izl = hesaplar.akis(72)[:40]
    except Exception:  # noqa: BLE001
        izl = []
    for x in izl + [y for y in _x_gorulen() if str(y.get("id")) not in {str(z.get("id")) for z in izl}]:
        A.append({"tur": "tweet", "baslik": f"@{x.get('kullanici', '')}", "metin": str(x.get("metin") or "")[:400],
                  "link": f"https://x.com/{x.get('kullanici')}/status/{x.get('id')}", "kaynak": "X", "tarih": str(x.get("tarih") or "")[:10],
                  "id": x.get("id"), "kullanici": x.get("kullanici")})
    if not A:
        return []
    c = paylasim._claude_json(
        "Aşağıdaki görüşü paylaşacak kişinin, bunu bir şeye TEPKİ olarak paylaşması gerekiyor (bağlantıyla ya da alıntıyla). Adaylardan hangileri bu görüş "
        "için DOĞAL bir tetik? Ölçüt: okur bağlantıyı ya da alıntıyı görünce 'bunu neden şimdi söylediği' anlaşılıyor mu; görüş o içeriğe gerçekten bir şey "
        "katıyor mu (aynısını tekrar etmiyor mu). Konu benzerliği yetmez; içerik görüşü ÇAĞIRMALI. AYRICA okur ilgisi: bu kişinin takipçileri (Türkiye'den; "
        "reklam, futbol, teknoloji ve popüler kültürle ilgilenen) bu içeriği tanır ya da ilgilenir mi? Yurt dışından küçük yerel haberler, kimsenin "
        "bilmediği siteler, niş sektör bültenleri en çok 2. uyum 1-5 (5 nadir), neden tek cümle. Yalnızca uyum ≥3 olanları yaz.\n"
        'JSON: {"secilen": [{"no": 0, "uyum": 4, "neden": "..."}]}\n\n'
        f"KONU: {konu}\nGÖRÜŞ: {metin}\n\nADAYLAR:\n"
        + "\n".join(f"[{i}] ({a['tur']} · {a['kaynak']} · {a['tarih']}) {a['baslik']} — {a['metin'][:220]}" for i, a in enumerate(A[:55])),
        model_adi="sonnet", zaman_asimi=120)
    out = []
    for s in c.get("secilen") or []:
        try:
            a = A[int(s.get("no"))]; u = int(s.get("uyum") or 0)
        except (TypeError, ValueError, IndexError):
            continue
        if u >= 4:
            out.append({**a, "uyum": u, "neden": str(s.get("neden") or "")[:200]})
    out.sort(key=lambda a: -a["uyum"])
    log(f"Tetik: {len(A)} aday → {len(out)} uygun")
    return out[:en_cok]


def _gercek_link(u):
    """Google News yönlendirmesini asıl habere çevirir (X kartı haberin kendisini göstersin)."""
    try:
        import kesif
        return kesif.gn_coz(u) if "news.google." in u else u
    except Exception:  # noqa: BLE001
        return u


def tepki_olarak_yaz(taslak, aday):
    """Taslağı seçilen tetiğe TEPKİ dilinde yeniden yazar. Döner: taslağa yazılacak alanlar."""
    if aday.get("tur") == "tweet" and aday.get("id"):
        return paylasim.alintiyla_yaz(taslak, {"id": aday["id"], "kullanici": aday.get("kullanici", ""), "metin": aday.get("metin", "")})
    pr = paylasim.profil()
    link = _gercek_link(aday.get("link", ""))
    try:                                                    # başlıktan değil haberin içinden: somut ayrıntıya bağlanabilsin
        metin_ozu = paylasim.sayfa_metni(link)[1][:3500]
    except Exception:  # noqa: BLE001
        metin_ozu = aday.get("metin", "")
    istem = (
        f"{paylasim._ses_blogu(pr, taslak.get('konu', ''), 'alinti' if aday.get('tur') == 'tweet' else 'tepki')}\n"
        "Bu kişi aşağıdaki haberi/yazıyı BAĞLANTISIYLA paylaşacak; okur metnin altında bağlantı kartını (başlık ve görsel) görecek. Mevcut taslak sıfırdan "
        "bir paylaşım gibi yazılmıştı; onu bu içeriğe TEPKİ olarak yeniden yaz. TEPKİ DİLİ sıfırdan paylaşımdan farklıdır: konuyu baştan kurma, haberi "
        "özetleme (kart zaten gösteriyor). İLK CÜMLE içerikteki SOMUT bir ayrıntıya (bir sayı, bir iddia, bir karar) bağlansın; okurun 'bunu neden şimdi "
        "söylüyor' sorusunun cevabı o ayrıntı olsun. Kendi okuma halini anlatma ('bana düşündürdü', 'okuyunca aklıma geldi', 'dikkatimi çeken'), 'Tam bu.', "
        "'Burada asıl ilginç olan' gibi kalıplar ve 'X değil, Y' vecizesiyle bitirme YOK. Görüşün özü korunsun; düşünce kadar kısa kalsın, düşünce bitince dur. "
        "Uydurma olgu yok; habere dair yalnızca aşağıdaki metindeki bilgi. Taslağın TONU ve BİÇİMİ korunsun: ironiyse ironi, tek satırsa tek satır, taraftar "
        "sesiyse taraftar sesi; haber anlatıcısına dönme.\n"
        f"BAĞLANTI: {aday.get('baslik')} ({aday.get('kaynak')}, {aday.get('tarih')})\nNEDEN UYGUN: {aday.get('neden')}\nİÇERİK:\n{metin_ozu}\n"
        f"MEVCUT TASLAK:\n{taslak.get('metin', '')}\n"
        'JSON: {"metin": "...", "kancalar": ["...", "..."]}')
    c = paylasim._claude_json(istem, model_adi="opus")
    m = str(c.get("metin") or "").strip()
    notlar = paylasim._kalip_notlari(m, []) + paylasim.sayi_notlari(m, metin_ozu + " " + str(taslak.get("metin") or ""))
    if m and notlar:                                        # kod denetimi: bir kez noktasal düzeltme
        c2 = paylasim._claude_json(istem + "\n\nTASLAĞIN ŞU NOKTALARINI DÜZELT, gerisine dokunma:\n" + "\n".join(f"- {x}" for x in notlar)
                                   + f"\nYAZDIĞIN:\n{m}", model_adi="opus")
        m = str(c2.get("metin") or m).strip()
    if not m:
        raise ValueError("Yazılamadı")
    return {"metin": m, "kancalar": [str(x).strip() for x in c.get("kancalar") or [] if str(x).strip()][:2], "karakter": len(m),
            "uzunluk": "kisa" if len(m) <= 280 else "uzun", "paylas_link": link, "link_oner": True, "alinti": None,
            "kaynak": {"tur": "haber", "baslik": aday.get("baslik", ""), "tarih": aday.get("tarih", ""), "link": link, "kanit": "",
                       "okunan": ["haberin tam metni" if metin_ozu and metin_ozu != aday.get("metin", "") else "yalnız başlık ve kısa özet"]},
            "tetik": {"tur": "haber", "neden": aday.get("neden", ""), "uyum": aday.get("uyum")}, "onceki": taslak.get("metin")}
