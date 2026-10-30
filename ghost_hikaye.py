"""ghost_hikaye.py - Haftanın hikâyesi: araştırılmış, kaynaklı bir X zinciri (2026-10-24; Ghost büyük işi).

Neden: okurun en çok kaydettiği gönderi kişinin "arşivci" tarafı (Atlas'ın dört parmağı → Mickey Mouse'un eldivenleri: 19 yer imi; diğerleri 1-2).
Günlük akış bunu üretemiyor: her gün yeni haber, kısa tepki. Haftada bir (perşembe öğleden sonra) bir konu derinlemesine işlenir:
  1) aday konular: haftanın keşif maddeleri ve elenen açılar (hikâye, popüler kültür, kreatif, futbol kültürü), "bugün geçmişte" kayıtları,
     görüş defterindeki kültür/tasarım görüşleri → sonnet 3 konu seçer: bir tasarım kararının, bir adın, bir alışkanlığın ARKASINDAKİ NEDEN;
  2) araştırma: kaynak haberin metni + Wikipedia (tr ve en arama → makale metni) okunur;
  3) yazım (opus): 4-7 parçalık zincir, ilk parça kanca (≤260); her olgu parçası okunan metinden HARFİ HARFİNE bir dayanak cümlesi taşır, kod
     doğrular (karisim._kaynak_cumle mantığı); dayanaksız parça bir kez düzeltilir, yine olmazsa atılır; 3 parçadan azı kalırsa hikâye yazılmaz;
  4) Ghost kaydı (`kaynak_tur: hikaye`), Bugün'de öne çıkar, kartta "Zinciri paylaş".
"""
import json
import re
import time
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
ISARET = KLASOR / "kayitlar" / "ghost_hikaye.json"
ALANLAR = ("hikaye", "populer_kultur", "kreatif", "reklamcilik", "gusto", "futbol", "futbol_teknoloji", "toplum")


def _gecmis():
    try:
        return json.loads(ISARET.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"yazilan": []}


def adaylar(gun=7):
    import kesif
    import paylasim
    out = []
    for f in sorted(kesif.KESIF.glob("20*.json"))[-gun:]:
        try:
            k = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        for o in (k.get("oneriler") or []) + (k.get("elenen_acilar") or []):
            if o.get("alan") in ALANLAR and o.get("baslik") and o.get("link"):
                out.append({"baslik": o["baslik"][:200], "ozet": str(o.get("ozet") or "")[:240], "link": o["link"], "alan": o["alan"], "kaynak": o.get("kaynak", "")})
    for f in sorted(kesif.KESIF.glob("arsiv_*.json"))[-gun:]:
        try:
            for a in json.loads(f.read_text(encoding="utf-8")) or []:
                if isinstance(a, dict) and a.get("baslik"):
                    out.append({"baslik": a["baslik"][:200], "ozet": str(a.get("ozet") or "")[:240], "link": a.get("link", ""), "alan": a.get("alan", "hikaye"), "kaynak": "Wikipedia: bugün geçmişte"})
        except Exception:  # noqa: BLE001
            continue
    for g in paylasim.gorusler():
        if g.get("alan") in ("populer_kultur", "kreatif", "hikaye") and not g.get("yerine"):
            out.append({"baslik": "Görüşünüz: " + str(g.get("gorus") or "")[:200], "ozet": "", "link": "", "alan": g.get("alan"), "kaynak": "görüş defteri"})
    gorulen, U = set(), []
    for x in out:
        k = re.sub(r"\W+", "", x["baslik"].lower())[:60]
        if k not in gorulen:
            gorulen.add(k); U.append(x)
    return U[:140]


def _wiki(sorgu, dil):
    import requests
    try:
        j = requests.get(f"https://{dil}.wikipedia.org/w/api.php", params={"action": "query", "list": "search", "srsearch": sorgu, "format": "json", "srlimit": 1},
                         headers={"User-Agent": "VideoHub/1.0 (kisisel arac)"}, timeout=20).json()
        hit = (j.get("query", {}).get("search") or [None])[0]
        if not hit:
            return None
        j = requests.get(f"https://{dil}.wikipedia.org/w/api.php", params={"action": "query", "prop": "extracts", "explaintext": 1, "titles": hit["title"], "format": "json"},
                         headers={"User-Agent": "VideoHub/1.0 (kisisel arac)"}, timeout=20).json()
        sayfa = next(iter(j["query"]["pages"].values()))
        metin = str(sayfa.get("extract") or "")
        if len(metin) < 400:
            return None
        return {"baslik": hit["title"], "link": f"https://{dil}.wikipedia.org/wiki/" + hit["title"].replace(" ", "_"), "metin": metin[:14000]}
    except Exception:  # noqa: BLE001
        return None


def _kaynak_var(cumle, metinler):
    norm = lambda s: re.sub(r"[^\w%]+", " ", str(s).lower()).strip()      # noqa: E731
    k = norm(cumle)
    if len(k) < 12:
        return False
    havuz = norm(" ".join(metinler))
    if k in havuz:
        return True
    W = k.split()
    return len(W) >= 8 and any(" ".join(W[i:i + 8]) in havuz for i in range(len(W) - 7))


def uret(zorla=False, log=print):
    """Haftanın hikâyesini yazar. Döner: temel ya da None."""
    _bas = __import__('time').time()
    import paylasim
    gc = _gecmis()
    hafta = time.strftime("%G-%V")
    if not zorla and hafta in [x.get("hafta") for x in gc["yazilan"]]:
        return None
    A = adaylar()
    if not A:
        log("Hikâye: aday yok"); return None
    pr = paylasim.profil()
    once = "; ".join(x.get("konu", "") for x in gc["yazilan"][-10:])
    c = paylasim._claude_json(
        f"KİŞİ: {pr.get('kimlik', '')}\nOkurunun en çok kaydettiği gönderisi şuydu: Boston Dynamics'in robotu Atlas'ın dört parmağı ona Mickey Mouse'un "
        "neden dört parmaklı ve beyaz eldivenli çizildiğini anlatan eski bir yazıyı hatırlattı; sonra o yazıyı bulup paylaştı. Bu kişinin en değerli "
        "tarafı: bir tasarım kararının, bir adın, bir alışkanlığın ya da küçük bir insani ayrıntının ARKASINDAKİ NEDENİ bulup anlatmak.\n"
        "Aşağıdaki adaylardan bu tür bir HAFTANIN HİKÂYESİ olabilecek en iyi 3 konuyu seç. İyi konu: çoğu kişinin bilmediği, araştırılabilir (Wikipedia'da "
        "ya da kaynak haberde anlatılmış) bir 'neden'i olan; bugünün gündemine bir köprüsü varsa daha iyi. Kötü konu: haber özeti, görüş tartışması, siyaset.\n"
        + (f"DAHA ÖNCE YAZILANLAR (tekrar etme): {once}\n" if once else "")
        + "Her konu: no (aday numarası), konu (tek cümle: anlatılacak 'neden'), wiki_tr ve wiki_en (Wikipedia'da aranacak kısa ifade), kopru (bugünle bağı; yoksa boş).\n"
        'JSON: {"konular": [{"no": 0, "konu": "...", "wiki_tr": "...", "wiki_en": "...", "kopru": ""}]}\n\nADAYLAR:\n'
        + "\n".join(f"[{i}] ({x['alan']} · {x['kaynak']}) {x['baslik']} — {x['ozet']}" for i, x in enumerate(A)), model_adi="sonnet", zaman_asimi=240)
    for k in (c.get("konular") or [])[:3]:
        try:
            aday = A[int(k.get("no"))]
        except (TypeError, ValueError, IndexError):
            continue
        kaynaklar = []
        if aday.get("link", "").startswith("http"):
            try:
                import kesif
                link = kesif.gn_coz(aday["link"]) if "news.google." in aday["link"] else aday["link"]
                b, m = paylasim.sayfa_metni(link)
                kaynaklar.append({"baslik": b or aday["baslik"], "link": link, "metin": m[:12000]})
            except Exception:  # noqa: BLE001
                pass
        for dil, q in (("en", k.get("wiki_en")), ("tr", k.get("wiki_tr"))):
            if q:
                w = _wiki(q, dil)
                if w and all(w["link"] != x["link"] for x in kaynaklar):
                    kaynaklar.append(w)
        if sum(len(x["metin"]) for x in kaynaklar) < 1500:
            log(f"Hikâye: '{k.get('konu')}' için yeterli kaynak okunamadı"); continue
        t = _yaz(k, kaynaklar, pr, log)
        if not t:
            continue
        temel = paylasim.ghost_kaydi(k.get("konu", ""), "hikaye", "Haftanın hikâyesi · " + str(k.get("konu", ""))[:70], t.get("paylas_link", ""), "",
                                     ek={"platform": "x"})
        yol = paylasim.GHOST / f"{temel[7:]}.json"
        v = json.loads(yol.read_text(encoding="utf-8"))
        v["veri"]["paylasim"] = {"taslaklar": [t], "zaman": time.time(), "ilk_zaman": time.time(), "model": __import__("paylasim")._yazan(_bas), "surum": 1, "elenen": []}
        yol.write_text(json.dumps(v, ensure_ascii=False, indent=1), encoding="utf-8")
        gc["yazilan"] = (gc["yazilan"] + [{"hafta": hafta, "konu": k.get("konu", ""), "temel": temel, "zaman": time.time()}])[-40:]
        ISARET.parent.mkdir(parents=True, exist_ok=True); ISARET.write_text(json.dumps(gc, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"Hikâye hazır: {k.get('konu')} ({len(t['zincir'])} parça)")
        return temel
    log("Hikâye: bu hafta yazılabilecek, kaynağı yeterli bir konu çıkmadı")
    return None


def _denetle(Z, kaynaklar, log):
    """Her parçadaki her olgu kaynakta AÇIKÇA var mı (sonnet; dayanak cümlesinin varlığı yetmiyor: Drakula denemesinde dayanak doğruydu ama parça
    kaynakta olmayan bir tarih bağlantısı kuruyordu). Desteklenmeyen kısım çıkarılır; düzeltilemeyen parça atılır (kanca hariç: o yeniden kurulur)."""
    import paylasim
    blok = "\n\n".join(f"KAYNAK {i + 1}:\n{x['metin'][:9000]}" for i, x in enumerate(kaynaklar))
    c = paylasim._claude_json(
        "Aşağıdaki X zincirinin her parçasındaki OLGULARI (tarih, ad, olay, sayı, neden-sonuç ilişkisi, 'aynı gün' gibi bağlantılar) kaynaklarla karşılaştır. "
        "Görüş ve gözlem cümlelerini denetleme. Her parça: no, durum (tam: her olgu kaynakta açıkça var | kismen: bazı olgular kaynakta yok | yok), "
        "duzeltilmis (kismen ise desteklenmeyen kısmı çıkarılmış ya da kaynağa göre düzeltilmiş metin; YENİ olgu ekleme, üslubu koru; tam ise boş), not.\n"
        'JSON: {"parcalar": [{"no": 0, "durum": "tam", "duzeltilmis": "", "not": ""}]}\n\nZİNCİR:\n'
        + "\n".join(f"[{i}] {z['metin']}" for i, z in enumerate(Z)) + "\n\n" + blok, model_adi="sonnet", zaman_asimi=300)
    D = {int(x.get("no")): x for x in c.get("parcalar") or [] if isinstance(x, dict) and str(x.get("no", "")).isdigit()}
    out = []
    for i, z in enumerate(Z):
        x = D.get(i) or {}
        if x.get("durum") == "kismen" and str(x.get("duzeltilmis") or "").strip():
            log(f"Hikâye: {i + 1}. parça kaynağa göre düzeltildi ({str(x.get('not') or '')[:80]})")
            out.append({**z, "metin": str(x["duzeltilmis"]).strip(), "denetim": "düzeltildi"})
        elif x.get("durum") in ("kismen", "yok") and i > 0:
            log(f"Hikâye: {i + 1}. parça kaynakta yok, atıldı ({str(x.get('not') or '')[:80]})")
        else:
            out.append({**z, "denetim": x.get("durum") or "bakılamadı"})
    return out


def _yaz(k, kaynaklar, pr, log):
    import paylasim
    metinler = [x["metin"] for x in kaynaklar]
    blok = "\n\n".join(f"KAYNAK {i + 1}: {x['baslik']} ({x['link']})\n{x['metin'][:9000]}" for i, x in enumerate(kaynaklar))
    istem = (f"{paylasim._ses_blogu(pr, k.get('konu', ''))}\n\nBu kişi X'te HAFTANIN HİKÂYESİ zincirini paylaşacak. KONU: {k.get('konu')}\n"
             + (f"BUGÜNLE KÖPRÜ: {k.get('kopru')}\n" if k.get("kopru") else "") +
             "ONUN BU İŞTEKİ GERÇEK HALİ (okurun en çok kaydettiği gönderisi): 'Boston Dynamics’in tanıttığı Atlas’ın dört parmağı olması dikkatimi çekti. "
             "Bu bana Mickey Mouse ile ilgili uzun yıllar önce okuduğum bir yazıyı hatırlattı…' ve ardından 'Yazıyı buldum:' diye kaynağın kendisi. Yani: "
             "gözlemle açar, merakı kısa tutar, anlatıyı kaynağa taşır; uzun ders anlatmaz.\n"
             "Zincir 3-5 parça. 1. parça KANCA (en çok 260 karakter): onun gözlemi ya da merak uyandıran somut ayrıntı, konunun adıyla; 'bir zincir' / 'thread' / "
             "'🧵' deme. Bugünle tarih bağı varsa ('N yıl önce bugün') kancada kullan. Sonraki parçalar her biri en çok 270 karakter, tek ayrıntı; son parça "
             "kısa bir gözlem (öğüt, vecize değil). Kişinin sesiyle, sade Türkçe; çeviri kokusu, 'ilginç bir şekilde', 'peki neden?' kalıpları yok.\n"
             "ÇIKARIM UYDURMA: kaynakta açıkça yazmayan bağlantıyı (ör. iki tarihin aynı gün olması, 'bunu bilerek yaptı') olgu gibi kurma.\n"
             "OLGU KURALI: her olgu YALNIZCA aşağıdaki kaynaklardan. Her parçaya 'dayanak' alanına o parçadaki olguyu taşıyan cümleyi kaynaktan HARFİ HARFİNE "
             "kopyala (çeviri yok; kaynak İngilizceyse İngilizce cümle). Kancada ve son gözlemde olgu yoksa dayanak boş olabilir. Tarih, sayı, ad uydurma.\n"
             'JSON: {"zincir": [{"metin": "...", "dayanak": "..."}], "link": "en iyi kaynak bağlantısı"}\n\n' + blok)
    c = paylasim._claude_json(istem, model_adi="opus", zaman_asimi=500)
    for deneme in range(2):
        Z = [z for z in c.get("zincir") or [] if isinstance(z, dict) and str(z.get("metin") or "").strip()]
        kotu = [i for i, z in enumerate(Z) if 0 < i < len(Z) - 1 and not _kaynak_var(z.get("dayanak", ""), metinler)]
        uzun = [i for i, z in enumerate(Z) if len(z["metin"]) > 280]
        if not kotu and not uzun or deneme == 1:
            Z = [z for i, z in enumerate(Z) if i not in kotu]
            break
        log(f"Hikâye: {len(kotu)} parçanın dayanağı kaynakta yok, {len(uzun)} parça uzun; düzeltiliyor")
        c = paylasim._claude_json(istem + "\n\nÖNCEKİ DENEMEN:\n" + json.dumps(c, ensure_ascii=False)[:6000] +
                                  f"\nSORUNLAR: dayanağı kaynakta HARFİ HARFİNE bulunamayan parçalar {kotu}; 280'i aşan parçalar {uzun}. Yalnız bunları düzelt.",
                                  model_adi="opus", zaman_asimi=500)
    Z = _denetle(Z, kaynaklar, log)
    if len(Z) < 3:
        log("Hikâye: dayanağı doğrulanan parça yetmedi"); return None
    zincir = [paylasim._temiz(z["metin"]).strip()[:280] for z in Z]
    notlar = paylasim._kalip_notlari(zincir[0], [])
    link = str(c.get("link") or kaynaklar[0]["link"])
    if link not in [x["link"] for x in kaynaklar]:
        link = kaynaklar[0]["link"]
    if not any("http" in z for z in zincir):          # kaynak son parçada yoksa ona eklenir (onun 'Yazıyı buldum:' hamlesi)
        zincir[-1] = (zincir[-1] + "\n\n" + link)[:300]
    h = {}
    try:
        h = paylasim._puanlar(paylasim._soguk_okur(zincir[0], pr, link, k.get("konu", "")))
    except Exception:  # noqa: BLE001
        pass
    alan_ad = {a.get("kod"): a.get("ad") for a in pr.get("alanlar") or [] if isinstance(a, dict)}.get("hikaye", "Güzel hikâyeler")
    return {"platform": "x", "karisim_tur": "hikaye", "alan": alan_ad, "alan_kod": "hikaye", "bicim": "uzun", "ton": "samimi",
            "metin": zincir[0], "karakter": len(zincir[0]), "zincir": zincir, "konu": str(k.get("konu", ""))[:240], "uzunluk": "zincir",
            "paylas_link": "", "link_oner": False, "ilk_yanit": "", "okur": h, "kod_notlari": notlar, "kancalar": [],
            "itirazlar": [], "iddialar": [], "panel": [], "dayanak": "",
            "dayanaklar": [z.get("dayanak", "") for z in Z],
            "kaynak": {"tur": "haftanın hikâyesi", "baslik": " · ".join(x["baslik"] for x in kaynaklar)[:200], "tarih": time.strftime("%Y-%m-%d"), "link": link,
                       "okunan": [f"{len(kaynaklar)} kaynağın tam metni"]}}


if __name__ == "__main__":
    print(uret(zorla=True))
