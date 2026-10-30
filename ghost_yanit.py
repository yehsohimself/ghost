"""ghost_yanit.py - Yanıt taslakları (2026-10-24; Ghost büyük işi; kullanıcı "bütün geliştirmeleri yap" dedi).

Kaliteli bir hesap yalnız kendi gönderileriyle değil, başkalarının gönderilerine yerinde yanıtlarla da kurulur. Malzeme yalnızca Chrome uzantısının
OKUDUKLARI (otomatik tarama yok): kişinin X'te AÇTIĞI gönderiler (`x_gorulen`, en güçlü işaret: ilgilenmiş), izlenen hesap listesindeki gönderiler
(`x_akis`) ve akışta gördüğü bağlantılı gönderiler (`x_kartli`), son 30 saat. Sonnet en çok 4 gönderi seçer: kişinin gerçekten KATABİLECEĞİ bir şey
varsa (görüş defterinden bir görüş, uzmanlığı, karşı bir gözlem). Yanıt ≤200 karakter, gönderiyi özetlemez, övgü/teşekkür/"harika tespit" yok,
kendini öne çıkarma yok. Kod denetimleri çalışır. Günde bir kez (öğleden sonra) ya da elle. Kartta yanıtlanan gönderi görünür; "X'te yanıtla"
X'in yanıt penceresini açar (`in_reply_to`), gönderme kişinindir.
"""
import json
import re
import time
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
KAYIT = KLASOR / "kayitlar"
ISARET = KAYIT / "ghost_yanit.json"


def _oku(ad):
    try:
        L = json.loads((KAYIT / ad).read_text(encoding="utf-8"))
        return L if isinstance(L, list) else list(L.values())
    except Exception:  # noqa: BLE001
        return []


def malzeme(saat=30, kullanici=""):
    kullanici = kullanici or __import__("ortak").kimlik()["x_kullanici"]
    s = time.time() - saat * 3600
    out, gorulen = [], set()
    for ad, isaret in (("x_gorulen.json", "açtığınız gönderi"), ("x_akis.json", "izlediğiniz hesap"), ("x_kartli.json", "akışınızda")):
        for x in sorted(_oku(ad), key=lambda x: -x.get("zaman", 0)):
            if x.get("zaman", 0) < s or not x.get("id") or x["id"] in gorulen or str(x.get("kullanici", "")).lower() == kullanici:
                continue
            if len(str(x.get("metin") or "")) < 30:
                continue
            gorulen.add(x["id"])
            out.append({"id": x["id"], "kullanici": x.get("kullanici", ""), "ad": x.get("ad", ""), "metin": str(x.get("metin") or "")[:600],
                        "kart": str(x.get("kart") or "")[:200], "isaret": isaret, "url": f"https://x.com/{x.get('kullanici')}/status/{x['id']}"})
    return out[:40]


def _onceki():
    try:
        return json.loads(ISARET.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"yanitlanan": [], "son": 0}


def uret(zorla=False, log=print):
    """Döner: temel ya da None."""
    _bas = __import__('time').time()
    import paylasim
    o = _onceki()
    if not zorla and time.time() - o.get("son", 0) < 20 * 3600:
        return None
    pr = paylasim.profil()
    M = [x for x in malzeme(kullanici=pr.get("kullanici") or "") if x["id"] not in set(o.get("yanitlanan") or [])]
    if len(M) < 3:
        log(f"Yanıt: yeterli gönderi okunmadı ({len(M)}); X'te listenize ya da akışınıza bakınca birikir"); return None
    G = [f"- ({g.get('alan', '')}) {g.get('gorus')}" for g in paylasim.gorusler() if not g.get("yerine") and gorus_ok(g)][:40]
    c = paylasim._claude_json(
        f"{paylasim._ses_blogu(pr, ' '.join(x['metin'][:80] for x in M[:6]), 'yanit')}\n\n"
        "Bu kişi X'te başkalarının gönderilerine YANIT yazacak. Aşağıdaki gönderilerden, kişinin gerçekten bir şey KATABİLECEĞİ en çok 4 tanesini seç "
        "(görüş defterindeki bir görüşü, kreatif/futbol/teknoloji gözü, karşı ya da tamamlayıcı somut bir gözlem). Katkı yoksa seçme; az ve iyi.\n"
        "YANIT KURALLARI: en çok 200 karakter; gönderiyi özetleme ya da tekrar etme; övgü, teşekkür, 'harika tespit', 'kesinlikle katılıyorum' YOK; "
        "kendini, işini ya da hesabını öne çıkarma YOK; soru sorulabilir ama retorik değil; kavga, hakaret, siyaset yok. GENEL DERS CÜMLESİ YOK "
        "('… işin parçası olmalı', '… mantıklı', '… en çok ihtiyacı olan şey', '… bakmak gerek'): yanıt gönderinin söylediğine DOĞRUDAN somut bir şey "
        "katar (bir örnek, karşı bir ayrıntı, gerçek bir soru, kuru bir espri). 'Asıl mesele X değil' kalıbı yok. SAYI, bedel, tarih ve ad yalnızca "
        "gönderide geçiyorsa; yoksa yazma. Yanıt tek başına "
        "da anlaşılmalı ama gönderiye bağlı kalmalı (ona cevap veriyor). Yanıt HER ZAMAN doğal TÜRKÇE (28 Ekim ölçümü: kişinin 90 gerçek gönderisinin hiçbiri "
        "İngilizce değil; İngilizce yanıtlar onun sesi değildi). Gönderi İngilizceyse de Türkçe yaz.\n"
        + ("GÖRÜŞ DEFTERİ:\n" + "\n".join(G) + "\n" if G else "") +
        'JSON: {"yanitlar": [{"no": 0, "katki": "kişinin kattığı, tek cümle", "metin": "...", "alan": "' + paylasim.alan_kodlari("|", haric=("kendi_arac",)) + '"}]}\n\n'
        "GÖNDERİLER:\n" + "\n".join(f"[{i}] @{x['kullanici']} ({x['isaret']}): {x['metin']}" + (f" [kart: {x['kart']}]" if x["kart"] else "") for i, x in enumerate(M)),
        model_adi="sonnet", zaman_asimi=240)
    alan_ad = {a.get("kod"): a.get("ad") for a in pr.get("alanlar") or [] if isinstance(a, dict)}
    T = []
    for y in (c.get("yanitlar") or [])[:4]:
        try:
            x = M[int(y.get("no"))]
        except (TypeError, ValueError, IndexError):
            continue
        m = paylasim._temiz(str(y.get("metin") or "")).strip()
        if not m or len(m) > 240:
            continue
        kaynak = x["metin"] + " " + x["kart"]
        notlar = paylasim._kalip_notlari(m, [t["metin"] for t in T]) + paylasim.sayi_notlari(m, kaynak)
        if notlar:                                         # tek düzeltme turu; yine not kalırsa yanıt önerilmez
            c2 = paylasim._claude_json(f"{paylasim._persona_blogu(pr, kisa=True)}\nŞu X yanıtını editör notlarına göre düzelt; en çok 200 karakter, "
                                       f"gönderiye bağlı, olgu yalnız gönderiden. NOTLAR: {'; '.join(notlar)}\nGÖNDERİ (@{x['kullanici']}): {x['metin']}\n"
                                       f'YANIT: {m}\nJSON: {{"metin": "..."}}', model_adi="sonnet", zaman_asimi=120)
            m = paylasim._temiz(str(c2.get("metin") or m)).strip()
            notlar = paylasim._kalip_notlari(m, [t["metin"] for t in T]) + paylasim.sayi_notlari(m, kaynak)
            if notlar:
                log(f"Yanıt: @{x['kullanici']} için yazılan yanıt denetimden geçmedi ({'; '.join(notlar)[:120]})"); continue
        if re.search(r"(harika|süper|çok iyi) (tespit|paylaşım|yazı)|kesinlikle katılıyorum|teşekkürler", m, re.I):
            continue
        a = y.get("alan") if y.get("alan") in alan_ad else "toplum"
        T.append({"platform": "x", "karisim_tur": "yanit", "alan": alan_ad.get(a, a), "alan_kod": a, "bicim": "minik", "ton": "samimi",
                  "metin": m, "karakter": len(m), "konu": f"@{x['kullanici']}: {x['metin'][:160]}", "katki": str(y.get("katki") or "")[:240],
                  "yanit_to": {k: x[k] for k in ("id", "kullanici", "ad", "metin", "url")}, "paylas_link": "", "link_oner": False,
                  "kod_notlari": notlar, "kancalar": [], "zincir": [], "uzunluk": "kisa", "okur": {}, "itirazlar": [], "iddialar": [], "panel": [],
                  "dayanak": "", "kaynak": {"tur": "X gönderisi", "baslik": f"@{x['kullanici']}: {x['metin'][:150]}", "tarih": "", "link": x["url"],
                                            "okunan": ["gönderinin metni"]}})
    if T:                                                  # kaynak anlamı (ghost_kaynak): yanıt gönderinin söylediğini doğru okuyor mu, bilinmeyen nedeni olgu gibi kuruyor mu
        import ghost_kaynak
        for t in T:
            t["kaynak_baslik"], t["kaynak_metni"] = f"@{t['yanit_to']['kullanici']}", t["yanit_to"]["metin"]
        T, _ = ghost_kaynak.denetle(T, log)
        for t in T:
            t.pop("kaynak_metni", None); t.pop("kaynak_baslik", None)
    o["son"] = time.time()
    if not T:
        ISARET.write_text(json.dumps(o, ensure_ascii=False), encoding="utf-8")
        log("Yanıt: katkı yapılabilecek gönderi çıkmadı"); return None
    temel = paylasim.ghost_kaydi("yanitlar", "yanit", f"Yanıtlar · {time.strftime('%d.%m %H.%M')}", "", "", ek={"platform": "x"})
    yol = paylasim.GHOST / f"{temel[7:]}.json"
    v = json.loads(yol.read_text(encoding="utf-8"))
    v["veri"]["paylasim"] = {"taslaklar": T, "zaman": time.time(), "ilk_zaman": time.time(), "model": __import__("paylasim")._yazan(_bas), "surum": 1, "elenen": []}
    yol.write_text(json.dumps(v, ensure_ascii=False, indent=1), encoding="utf-8")
    o["yanitlanan"] = (list(o.get("yanitlanan") or []) + [t["yanit_to"]["id"] for t in T])[-300:]
    ISARET.parent.mkdir(parents=True, exist_ok=True); ISARET.write_text(json.dumps(o, ensure_ascii=False), encoding="utf-8")
    log(f"Yanıt: {len(T)} yanıt taslağı hazır")
    return temel


def gorus_ok(g):
    try:
        import paylasim
        return paylasim.gorus_durumu(g) != "red"
    except Exception:  # noqa: BLE001
        return True


if __name__ == "__main__":
    print(uret(zorla=True))
