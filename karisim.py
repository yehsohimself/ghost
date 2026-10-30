"""Günün karışımı (2026-10-23): günde 10-15 X önerisi, kişinin GERÇEK gönderi dağılımına göre.

Kullanıcı: "Günlük 1-2 öneri yetmez, 10-15 lazım. Önerilerin hâlâ günlük haberleri yorumlayan bir program havasında."
Ölçüm (88 gerçek gönderi): ancak ~20'si bir habere/bağlantıya tepki. Gerisi taraftar sesi (~20), tek cümlelik ironi (~18), zamansız
görüş (~10), kendi işi ve araçları (~8), akışta gördüğü gönderiye tepki. Eski hat her öneri için 10+ Claude çağrısıyla yalnızca haber
yorumu üretiyordu. Burada: bütün malzeme tek yazım çağrısına (opus) → toplu hakem (sonnet) → sınırdakiler toplu düzeltme + yeniden hakem.
Bir turda ~4 çağrı. Çıktı tek bir ghost kaydına (tur 'karisim') taslak listesi olarak yazılır; plan() günün sırasını kurar.
"""
import json
import random
import re
import subprocess
import time
from datetime import date, datetime
from pathlib import Path

import paylasim

KLASOR = Path(__file__).resolve().parent
KULLANILAN = KLASOR / "profil" / "karisim_kullanilan.json"

def _kimlik():
    import ortak
    return ortak.kimlik()


TURLER = {
    "taraftar": "{takim} taraftarı ve futbolu izleyen biri olarak tepki: kadro, ilk 11, rol çakışması, teknik direktör, transfer, rakip, maç anı. "
                "Analiz botu değil, taraftar sesi; bazen tek satır, bazen alt alta kısa satırlar.",
    "ironi": "Gündemde herkesin bildiği büyük bir konuya tek cümlelik kuru ironi ya da iğneleme. Kaynak YALNIZCA gündem (g…) ve gerçekten konuşulan "
             "konu ('konusulan': true). Espri konunun KENDİ mantığından çıkar; konuyu alakasız bir alana (futbola, rakip takıma, yapay zekâya) taşıyarak espri kurma.",
    "gorus": "Zamansız bir gözlem ya da görüş (futbol kültürü, marka, tasarım, toplum, yapay zekâ ve iş). Kaynak MUTLAKA görüş defterindeki bir görüş (o:…); "
             "gündem başlığından (g…) görüş yazma: başlığı özetleyip bir yorum eklemek habere tepkidir, görüş değil. Yeni bir açıdan, tekrar etmeden.",
    "haber": "Bir habere/içeriğe bağlantısıyla tepki: haberdeki somut ayrıntıdan çıkan gözlem. YALNIZCA MALZEME'deki 'haber' listesinden (id h…); "
             "gündem başlıklarından haber yorumu YAZMA.",
    "kendi": "Kendi yaptığı işten/araçlardan (MALZEME 'kendi' listesi: önce bu haftanın somut işleri, sonra günün kayıtları) kısa bir paylaşım, "
             "birinci ağızdan: o hafta kurduğu ya da taşıdığı şeyin, DIŞARIDAN BİRİNİN İŞİNE YARAYACAK fikri ya da gözlemi ('derdi' alanı varsa merkez odur). "
             "Duygu ya da yaşanmışlık ('canım çıktı', 'kafayı yedim') YALNIZCA 'derdi' alanında ya da kişinin kendi sözünde geçiyorsa; kişinin başka bir "
             "gönderisindeki ifadeyi yeni olaya taşıma. Tek başına bir hatanın düzeltilmesi paylaşmaya değer değildir; ölçülmemiş genel sonuç ('en çok kaybolan "
             "şey') çıkarma, ürünün ne yaptığını ve neden değerli bulduğunu söyle. "
             "Kendi serisine de bağlanabilir ('seri' alanı: 'vol. N'). Genel 'kendi aracını yap' fikri YAZMA (dokunulmuyor). 'paylasti' olan işi aynı "
             "açıdan yeniden anlatma. TEK FİKİR: özellik listesi değil (en çok bir özellik), sürüm notu değil; teknik ayrıntı (çözünürlük, ses seviyesi, saat, "
             "modül, dosya, test düzeni) okurun işine yaramaz, yazma. Kapattığı, yarım bıraktığı ya da yalnız kendisinin gördüğü bir aracı duyurma (okur onu "
             "hiç görmedi). Müşteri, kişi, şirket adı ve gizli bilgi YOK. Ürün ve proje adlarını çalışma kayıtlarındaki gibi yaz"
             + ((" (" + str(__import__("ortak").ayar(KLASOR).get("kendi_not")).strip() + ")") if __import__("ortak").ayar(KLASOR).get("kendi_not") else "")
             + ". Ghost'u anma.",
    "akis": "X'te açıp okuduğu bir gönderiye alıntı ya da yanıt olarak tepki.",
}


def _kullanilan():
    try:
        return json.loads(KULLANILAN.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _kullanildi(anahtarlar):
    d = _kullanilan()
    simdi = time.time()
    d = {k: t for k, t in d.items() if simdi - t < 14 * 86400}
    for a in anahtarlar:
        d[a] = simdi
    KULLANILAN.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def _git_kayitlari(saat=36):
    import ortak                                             # ayarlar.json `kendi_depolar` (yoksa bu depo; boş = kapalı)
    return ortak.git_kayitlari(f"{saat} hours ago", KLASOR, 15)


def _akis(saat=30):
    try:
        L = json.loads((KLASOR / "kayitlar" / "x_gorulen.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    L = L if isinstance(L, list) else list(L.values())
    return [x for x in L if time.time() - (x.get("zaman") or 0) < saat * 3600 and x.get("metin")][-10:]


def _alan_dengeli(L, n, ust):
    """Sırayı koruyarak ilk n'i seçer ama önce her alandan birer tane alır, bir alandan en çok `ust` (27 Ekim: ilk 6 haber hep kreatif/teknolojiydi,
    elemeyi geçen gusto ve reklamcılık haberleri yazıma hiç ulaşmıyordu)."""
    secilen, sayi = [], {}
    for tur in (1, ust):
        for o in L:
            a = o.get("alan", "")
            if len(secilen) >= n:
                break
            if o not in secilen and sayi.get(a, 0) < tur:
                secilen.append(o); sayi[a] = sayi.get(a, 0) + 1
    return sorted(secilen, key=L.index)


def malzeme(maddeler, haberler):
    """maddeler: günün keşif maddeleri (konuşulurluk alanlarıyla); haberler: açı elemesini geçmiş öneriler (ayrıntı + metin özüyle)."""
    kul = _kullanilan()
    M = {"haber": [], "gundem": [], "futbol": [], "gorus": [], "kendi": [], "akis": [], "geri": []}
    for o in _alan_dengeli(haberler, 8, 2):
        M["haber"].append({"id": "h" + str(len(M["haber"])), "baslik": o["baslik"], "kaynak": o.get("kaynak", ""), "link": o.get("link", ""),
                           "tarih": time.strftime("%Y-%m-%d %H:%M", time.localtime(o["zaman"])) if o.get("zaman") else "",
                           "alan": o.get("alan", ""), "ayrinti": o.get("ayrinti", ""), "aci": o.get("aci", ""), "metin": (o.get("metin_ozu") or o.get("ozet", ""))[:900],
                           # editoryal yöntem (24 Ekim): olgu / beyan / karar / sınır ayrı; asıl kaynak; olay tarihi; ne okundu
                           **{k: o[k] for k in ("nesne", "olgu", "beyan", "karar", "sinir", "olay_tarihi", "gorulen", "kesif_link", "kesif_yayin", "kesif_bulten", "kesif_kantan", "okunan", "x_gonderi", "arsiv", "yaratici") if o.get(k)},
                           **({"eski_is": True} if o.get("eski_is") else {}), **({"asil_metin": o["asil_metin"][:600]} if o.get("asil_metin") else {}),
                           # konu toplantısı (konu_toplantisi.py): kişi bu konuyu seçti ve/veya Ghost'un sorusuna kendi cevabını verdi
                           **({"kendi_yorum": o["kendi_yorum"]} if o.get("kendi_yorum") else {}), **({"secildi": True} if o.get("secildi") else {}),
                           **({"emsal": [{"is": a["kunye"], "neden": a["neden"]} for a in o["arsiv_emsal"]]} if o.get("arsiv_emsal") else {})})
    # 26 Ekim (kullanıcı: "boş beleş haber sitelerinden günlük talk; sadece sporda değil, genelde de böyle bak"): ham başlık malzemesi yalnız derin
    # yayınlardan ve kişinin kendi kürasyonundan (bültenleri, Adweek, Kantan, dinlediği yayınlar, izlediği hesaplar); günlük haber akışı ancak açı
    # elemesinde metni okunup somut bir ayrıntı bulunursa 'haber' olarak gelir.
    import kesif
    kur = lambda m: 0 if (m.get("kesif_bulten") or m.get("kesif_kantan") or m.get("kesif_yayin") or m.get("x_hesap")) else 1
    gundem = sorted([m for m in maddeler if not FUTBOL_ALAN.search(m.get("alan") or "") and kesif.derin_mi(m)],
                    key=lambda m: (kur(m), -(m.get("kaynak_sayisi") or 1), -(1 if m.get("trend") else 0)))
    for m in _alan_dengeli(gundem, 16, 3):
        M["gundem"].append({"id": "g" + str(len(M["gundem"])), "baslik": m["baslik"], "alan": m.get("alan", ""), "kaynak_sayisi": m.get("kaynak_sayisi", 1), "link": m.get("link", ""),
                            "konusulan": konusulan(m),
                            "kaynak": m.get("kaynak", ""), "ozet": (m.get("ozet") or "")[:220],
                            "tarih": time.strftime("%Y-%m-%d %H:%M", time.localtime(m["zaman"])) if m.get("zaman") else ""})
    _tk = __import__("ortak").kimlik().get("takim") or ""        # tuttuğu takım profilden (29 Ekim; kodda takım adı yok)
    gs = re.compile(r"derbi|derby|milli takım" + ("|" + re.escape(_tk) if _tk else ""), re.I)
    # 28 Ekim: 'bugün geçmişte' kaydı futbol listesine girmez (beyzbol kaydı 'futbol' etiketiyle gelip Kadıköy iğnelemesine bağlanmıştı)
    fut = sorted([m for m in maddeler if FUTBOL_ALAN.search(m.get("alan") or "") and kesif.derin_mi(m) and not m.get("arsiv")],
                 key=lambda m: (kur(m), 0 if gs.search(m["baslik"]) else 1, -(m.get("zaman") or 0)))
    for m in fut[:12]:
        M["futbol"].append({"id": "f" + str(len(M["futbol"])), "baslik": m["baslik"], "ozet": (m.get("ozet") or "")[:220], "link": m.get("link", ""),
                            "kaynak": m.get("kaynak", ""),
                            "tarih": time.strftime("%Y-%m-%d %H:%M", time.localtime(m["zaman"])) if m.get("zaman") else ""})
    G = [g for g in paylasim.gorusler() if not g.get("yerine") and paylasim.gorus_durumu(g) != "red" and ("o:" + g.get("konu", "")) not in kul]
    random.shuffle(G)
    try:                                                   # fikir kartları (fikir_kartlari.py): bugün haberi gelmiş görüşler önce ve tetiğiyle
        import fikir_kartlari
        TK = {e["gorus"]: e for e in fikir_kartlari.bugun()}
    except Exception:  # noqa: BLE001
        TK = {}
    G.sort(key=lambda g: 0 if g.get("gorus") in TK else 1)
    for g in G[:10]:
        e = TK.get(g.get("gorus"))
        M["gorus"].append({"id": "o:" + g.get("konu", ""), "konu": g.get("konu", ""), "gorus": g.get("gorus", ""), "alan": g.get("alan", ""),
                           "durum": "onaylı" if paylasim.gorus_durumu(g) == "onayli" else "gönderisinden çıkarıldı", "kanit": str(g.get("kanit") or "")[:160],
                           **({"tetik": {"baslik": e["madde"].get("baslik", ""), "link": e["madde"].get("link", ""), "neden": e["neden"], "iliski": e.get("iliski") or "destekler"},
                               "link": e["madde"].get("link", ""), "baslik": e["madde"].get("baslik", "")} if e else {})})
    gizli = re.compile(r"ghost|paylaşım|taslak|yazıcı|okur|hakem|\bx\b|kesif|keşif|açı|persona|tweet|gönderi|instagram|story|asana|müşteri|"
                       r"toplantı adı|kişi|" + "|".join(re.escape(x.lower()) for x in __import__("ortak").sirket_adlari()), re.I)   # gönderilerin araçla yazıldığını ve müşteri işlerini ifşa etmesin
    try:                                                   # bu haftanın somut işleri (ghost_kendi.py; 24 Ekim kabul edilen öneri): önce bunlar, sonra günün tek tek kayıtları
        import ghost_kendi
        for x in ghost_kendi.isler():
            if x["id"] not in kul:
                M["kendi"].append({k: v for k, v in x.items() if v not in ("", None, False)})
    except Exception:  # noqa: BLE001
        pass
    for h, tarih, s in _git_kayitlari():
        if gizli.search(s) or any(h in str(k.get("kayit", "")) for k in M["kendi"]):
            continue
        if ("k:" + s[:60]) not in kul:
            M["kendi"].append({"id": "k:" + s[:60], "is": s[:300], "kayit": h, "tarih": tarih})
    try:                                                   # izlenen hesapların bağlantısız gönderileri önce (hesaplar.py)
        import hesaplar
        izl = hesaplar.akis_malzemesi()
    except Exception:  # noqa: BLE001
        izl = []
    for x in izl + [y for y in _akis() if str(y.get("id")) not in {str(z.get("id")) for z in izl}]:
        if ("a:" + str(x.get("id"))) not in kul:
            M["akis"].append({"id": "a:" + str(x.get("id")), "hesap": x.get("kullanici", ""), "metin": x.get("metin", "")[:400],
                              "link": f"https://x.com/{x.get('kullanici')}/status/{x.get('id')}"})
    try:                                                   # geri dönüş defteri (ghost_defter.geri_donus_defteri): kendi tekrar eden bitleri ve tarihli iddiaları
        import ghost_defter
        gd = ghost_defter.geri_donus_defteri()
        for b in (gd.get("bitler") or [])[:8]:
            M["geri"].append({"id": "r:b:" + b["ad"][:40], "tur": "bit", "ad": b["ad"], "ozet": b["ozet"], "ornek": (b.get("ornekler") or [{}])[0]})
        for x in (gd.get("iddialar") or [])[:14]:
            M["geri"].append({"id": "r:i:" + x["url"].rsplit("/", 1)[-1], "tur": "iddia", "tarih": x["tarih"], "iddia": x["iddia"], "konu": x["konu"],
                              "metin": x["metin"], "url": x["url"]})
    except Exception:  # noqa: BLE001
        pass
    return M


def konusulan(m):
    """Gündem maddesi gerçekten konuşuluyor mu (ironi ancak o zaman anlaşılır): birden çok kaynak, Google'da yükselen, ya da kişinin kürasyonu."""
    return bool((m.get("kaynak_sayisi") or 1) >= 2 or m.get("trend") or m.get("kesif_kantan") or m.get("kesif_bulten") or m.get("x_hesap"))


OKUNAN = {"g": "yalnız haber başlığı (gündem)", "f": "haber başlığı ve kısa özeti", "a": "X gönderisinin metni", "o": "görüş defterindeki kendi görüşü",
          "k": "çalışma kaydı"}


FUTBOL_ALAN = re.compile(r"futbol|football|soccer", re.I)     # taraftar sesi: tuttuğu takımın sporu (profil alan kodu)


def _dagilim(M, hedef):
    """Türlere SABİT KOTA YOK (kullanıcının editoryal yöntemi, 24 Ekim: 'bugün iki futbol, üç AI diye mekanik dağıtmıyorum'); yalnız ÜST SINIRLAR:
    malzemesi olmayan tür yazılmaz, haber en çok elemeden geçen haber sayısı, kendi işi en çok 1, akış en çok 2, diğerleri en çok hedefin yarısı.
    Tek bir alanın (özellikle yapay zekâ) baskın olmasını yazım istemi ve plan() sınırlar."""
    var = {"taraftar": len(M["futbol"]), "ironi": len(M["gundem"]), "gorus": len(M["gorus"]), "haber": len(M["haber"]),
           "kendi": min(2 if any(k.get("derdi") or k.get("seri") for k in M["kendi"]) else 1, len(M["kendi"])), "akis": min(4, len(M["akis"]))}
    yari = max(2, (hedef + 1) // 2)
    D = {t: (n if t in ("haber", "kendi", "akis") else min(n, yari)) for t, n in var.items() if n}
    try:                                                   # haftalık öz değerlendirmenin koyduğu üst sınır (ghost_gelisim.py, geri alınabilir)
        import ghost_gelisim
        for t in list(D):
            u = ghost_gelisim.tur_ust(t)
            if u is not None:
                D[t] = min(D[t], u)
        D = {t: n for t, n in D.items() if n}
    except Exception:  # noqa: BLE001
        pass
    return D


def _turce_ornekler(pr):
    """Gerçek gönderilerden tür başına örnek (kısa olanlar önce): modele 'haber yorumu' dışındaki sesi göstermek için."""
    G = paylasim._gercek_gonderiler(pr)
    _tk = __import__("ortak").kimlik().get("takim") or ""
    fut = re.compile(r"ilk 11|lineup|kanat|forma|transfer|futbol|football|maç|match|derbi|derby|stoper|santrfor|striker|keeper|kaleci"
                     + ("|" + re.escape(_tk) if _tk else ""), re.I)
    taraftar = [g for g in G if fut.search(g) and len(g) <= 420]
    kisa = [g for g in G if len(g) <= 160 and g not in taraftar]
    orta = [g for g in G if 160 < len(g) <= 420 and g not in taraftar]
    random.shuffle(taraftar); random.shuffle(kisa); random.shuffle(orta)
    try:
        import ghost_kendi
        kendi = ghost_kendi.ornekler()
    except Exception:  # noqa: BLE001
        kendi = []
    try:                                         # 25 Ekim: gerçek gönderiler işine göre sınıflandıysa türler ona göre (duyuruya duyuru, alıntıya alıntı)
        T = paylasim.ornek_turleri(pr)
    except Exception:  # noqa: BLE001
        T = {}
    if sum(1 for v in T.values() if v) >= 30:
        ad = {"taraftar": "taraftar ve futbol", "espri": "kısa / ironi", "gozlem": "gözlem", "tepki": "habere ya da içeriğe tepki",
              "alinti": "alıntı yorumu", "duyuru": "kendi işini duyurma", "dusunce": "birkaç paragraflık düşünce"}
        out = {}
        for tur, baslik in ad.items():
            L = [m for m, t in T.items() if t == tur]
            random.shuffle(L)
            if L:
                out[baslik] = L[:10 if tur in ("taraftar", "espri") else 6]
        if kendi:
            out["kendi işi (birinci ağızdan, dertli ya da seri)"] = kendi
        return out
    return {"taraftar ve futbol": taraftar[:10], "kısa / ironi": kisa[:12], "gözlem": orta[:8], **({"kendi işi (birinci ağızdan, dertli ya da seri)": kendi} if kendi else {})}


def olcu(pr=None):
    """Kişinin gerçek gönderilerinin biçim ölçüsü (27 Ekim: taslaklarla karşılaştırma; her çağrıda güncel gönderilerden)."""
    G = [g.strip() for g in paylasim._gercek_gonderiler(pr or paylasim.profil()) if g and g.strip()]
    if len(G) < 20:
        return {}
    L = sorted(len(g) for g in G)
    oran = lambda k: round(100 * sum(1 for g in G if k(g)) / len(G))   # noqa: E731
    return {"n": len(G), "ortanca": L[len(L) // 2], "kisa140": oran(lambda g: len(g) <= 140), "alt280": oran(lambda g: len(g) <= 280),
            "kucuk": oran(lambda g: g[:1].islower()), "paragraf": oran(lambda g: "\n" in g)}


def _olcu_metni(pr):
    o = olcu(pr)
    if not o:
        return ""
    return (f"- UZUNLUK VE RİTİM (kişinin {o['n']} gerçek gönderisinden ölçüldü): ortanca {o['ortanca']} karakter; 140 karakterin altında kalanlar "
            f"yüzde {o['kisa140']}, 280'in altında kalanlar yüzde {o['alt280']}. Eski taslaklar bundan uzun ve açıklayıcıydı (beşte biri 280'i aşıyordu). Yani 280'i "
            "aşan gönderi günde EN ÇOK BİR, o da yalnız 'kendi' ya da gerçekten katmanlı bir görüş. Bir gözlem ve en çok bir dönüş: gözlemi 'bu ne "
            "demek' diye açıklayan, tahmin yürüten ya da 'açık kalan şu' diye toparlayan ikinci-üçüncü cümleyi YAZMA; okur bağlantıyı kendisi kurar, kart "
            "haberi zaten gösteriyor.\n"
            f"- YAZIM GEVŞEKLİĞİ: küçük harfle başlayan gerçek gönderiler yüzde {o['kucuk']} (taraftar, ironi, kısa gözlemlerde "
            "özel adlar da çoğu zaman küçük), bazen konuşma dili ('yırtılıyo'). Bu türlerde küçük harf ve gündelik dil doğal; 'kendi' ve "
            "uzun görüşler düzgün yazımla. Taraftar gönderilerinde alt alta kısa satırlar olağan.\n")


YORUMCU = re.compile(r"\b(açık kalan (soru|şu|nokta)|önümüzdeki (günlerde|dönemde|aylarda)|asıl soru|bunun anlamı|işte bu yüzden|ilginç olan şu|"
                     r"şunu gösteriyor|göreceğiz)\b", re.I)
UZUN_SERBEST = ("kendi",)                       # 280'i aşabilen türler (görüş ancak 420'ye kadar)


def _yaz(M, dagilim, pr, bugun_yazilanlar, ek="", hedef=12):
    ornek = _turce_ornekler(pr)
    toplam = round(hedef * 1.8)                    # hakem eleyecek (ilk denemede 15'ten 5'i geçti); bol yaz
    return paylasim._claude_json(
        f"Bugün {time.strftime('%d.%m.%Y %A')}. Bir kişinin X hesabı için bugünün gönderilerini onun ağzından yazıyorsun. Toplam {toplam} gönderi.\n\n"
        f"KİM: {pr.get('kimlik', '')}\nTAVIR: {pr.get('tavir', '')}\n{paylasim._persona_blogu(pr, kisa=True)}\n"
        + ("DÜZELTMELERİNDEN ÖĞRENİLENLER:\n" + "\n".join(f"- {t.get('tercih')}" for t in paylasim.tercihler() if isinstance(t, dict) and t.get("aktif", True) and t.get("tercih"))[:1800] + "\n")
        + ("KONUSU İYİ AMA SÖYLENENİ BARİZ BULDUĞU TASLAKLAR (bu düzeyde gözlem yazma):\n" + "\n".join(f"- {r.get('ilk', '')[:200]}" for r in paylasim._red(pr, "aci")[-5:]) + "\n"
           if paylasim._red(pr, "aci") else "")
        + "\nGERÇEK GÖNDERİLERİ (ses, uzunluk, ritim böyle; dikkat: çoğu habere tepki DEĞİL. Taraftar sesi, tek satır ironi, zamansız görüş, kendi işi):\n"
        + "\n".join(f"== {baslik} ==\n" + "\n---\n".join(L) for baslik, L in ornek.items())
        + ("\n== Ghost'tan seçip paylaştıkları (onaylı; türü ve varsa neden beğendiği) ==\n" + "\n---\n".join(
            f"[{x.get('tur') or '-'}{', neden: ' + x['neden'] if x.get('neden') else ''}] {x['metin'][:900]}" for x in paylasim.havuz_ornekleri(n=6))
           if paylasim.havuz() else "") +
        "\n\nTÜRLER (her türden EN ÇOK kaç tane; sabit kota YOK: malzemenin gücüne göre seç, zayıf türü hiç yazmamak serbest. Tek bir alan, "
        "özellikle yapay zekâ, toplamın üçte birini geçmesin; her konuyu yapay zekâya bağlama):\n" + "\n".join(f"- {t} (en çok {n}): {TURLER[t].format(takim=_kimlik()['takim'] or 'takımının')}" for t, n in dagilim.items()) +
        "\n\nKURALLAR:\n"
        "- Gerçek bir insanın bir günlük akışı gibi: biçim, uzunluk, ton ve açılış her gönderide farklı; tek satırlıklar olağan. "
        "Düşünce bitince dur; her gönderiye espri ya da kapanış cümlesi koyma.\n"
        + _olcu_metni(pr) +
        "- Habere bağlı olmayan türlerde (taraftar, ironi, görüş, kendi) haberi anlatma, bağlantı verme; konu zaten konuşuluyor ya da zamansız.\n"
        "- DERİNLİK (kişi, 26 Ekim): günlük talk yazma. Oyuncu/yönetici demecine, maç önü istatistiğine, transfer söylentisine, ürün fiyatına, 'X açıkladı' "
        "haberine tepki gönderisi YOK; malzemede yalnız derin yayınlar ve kişinin kendi kürasyonu var, onların içindeki karar, yapı ya da hikâyeye bağlan. "
        "Malzeme bir türü taşımıyorsa o türü yazma.\n"
        "- TETİK: Kimse durup dururken paylaşmaz; bir şey görür ve ona tepki verir (kullanıcı, 23 Ekim). 'kendi' türü DIŞINDAKİ her gönderi MALZEME'deki bir "
        "içeriğe (haber h…, gündem g…, futbol f…, X gönderisi a…) TEPKİDİR ve 'kaynak' alanına onun id'si yazılır; okur o içeriği bağlantı kartı ya da "
        "alıntı olarak altında görecek. Zamansız bir görüş (görüş defterinden) ancak onu ÇAĞIRAN bir içerik bulursan yazılır; bulamazsan kaynak 'o:…' "
        "kalsın, sistem sonra tetik arayacak.\n"
        "- TEPKİ DİLİ sıfırdan paylaşımdan farklıdır: konuyu baştan kurma, içeriği özetleme (kart/alıntı gösteriyor); içerikteki bir şeye doğrudan bağlan, "
        "kendi gözlemini koy. Sıfırdan dil yalnızca 'kendi' türünde (kendi işini o anlatır).\n"
        "- ÖNCE SEÇ, SONRA YAZ: her gönderi için önce 'katki' alanına kullanıcının bu konuya kattığını tek cümleyle yaz (gözlemi, zevki, karşılaştırması, "
        "taraftar hissi, yaptığı iş). Katkı 'haberi duyurmak' ise o gönderiyi YAZMA; zayıf konuyu güzel cümleyle kurtarmaya çalışma.\n"
        "- Birinci şahıs İŞ/DENEYİM iddiası (ekledim, yaptım, denedim, gördüm, müşterilerimde...) YALNIZCA 'kendi' türünde ve çalışma kaydına dayanarak; "
        "diğer türlerde kullanıcıya ait iş ya da anı uydurma. 'Dikkatimi çekti' gibi tepki serbest.\n"
        "- YER TUTUCU ASLA ('[oyuncu adı]', '[X]' gibi). Malzemede gereken bilgi yoksa o gönderiyi YAZMA, başka bir konu seç.\n"
        "- HABERİN İÇİ (haber listesinde): olgu, beyan ve yorum ayrı. 'beyan' alanındaki iddiayı olgu gibi yazma, sahibine ver ('ajans diyor ki…', "
        "'şirketin iddiası'); 'sinir' alanındakini biliyormuş, denemiş ya da görmüş gibi yazma. 'eski_is' işaretliyse iş yeni yapılmış gibi sunma (olay tarihi "
        "'olay_tarihi'nde). Görsel ayrıntıyı yalnızca 'gorulen' alanında yazanla anlat. 'karar' varsa açı çoğu zaman oradadır: sonucu doğuran tasarım/iş tercihi.\n"
        "- 'kesif_bulten' alanı olan haber kişinin okuduğu bir bültende geçti: bültene ya da yazarına gönderme yapma, bültenin yorumunu tekrar etme.\n"
        "- 'kesif_kantan' alanı olan haber Kantan.News'in seçkisinden; bağlantı asıl kaynağa gidiyor. Kantan'a ya da 'seçkide gördüm'e gönderme yapma, "
        "Kantan'ın özetini tekrar etme; gözlem asıl haberden.\n"
        "- 'kesif_yayin' alanı olan haber, kişinin dinlediği bir yayında (podcast/YouTube programı) konuşulmuştu: yayına, sunuculara ya da onların "
        "yorumuna GÖNDERME YAPMA, onların fikrini yeniden anlatma; gözlemin asıl işe/habere ve kullanıcının kendi bakışına dayansın.\n"
        "- EMSAL: 'emsal' kişinin KENDİ ödüllü reklam arşivinden (Cannes, D&AD, Clio analizleri) bu habere gerçekten benzeyen iş. Karşılaştırma gözlemi "
        "keskinleştiriyorsa an ('aynı hamleyi 2025'te X yapmıştı, fark şu'); markayı, işi ve yılı doğru yaz; zorlama, her kreatif gönderiye emsal koyma.\n"
        "- KONU TOPLANTISI: 'secildi' olan haber mutlaka yazılır. 'kendi_yorum' olan öğede (haber ya da görüş) gönderinin ÇEKİRDEĞİ kişinin o cevabıdır: "
        "olduğu gibi kullan, büyütme, başka bir açıya kayma; yalnız X diline ve kişinin sesine sok. Bu gönderilerin katkısı o cevaptır.\n"
        "- 'gorus' öğesinde 'tetik' varsa bugün o görüşü çağıran bir haber çıktı: gönderiyi o habere TEPKİ olarak yaz (okur bağlantı kartını görecek; haberi "
        "özetleme, ilk cümle haberdeki somut noktaya bağlansın, görüş onun üstüne). Bu, görüş türünün en iyi hali; tetikli görüşleri öncelikle yaz. "
        "tetik.iliski 'sinar' ise haber görüşü ZORLUYOR: görüşü aynen tekrarlama; haberdeki olgunun görüşü nasıl sınadığını dürüstçe düşün, gerekiyorsa "
        "görüşün değiştiğini ya da inceldiğini söyle (tutarlılık her gelişmeye aynı hükmü vermek değildir).\n"
        "- GERİ DÖNÜŞ NADİR ('geri' listesi): kişi gerçek gönderilerinde neredeyse hiç 'şunu yazmıştım/söylemiştim' demez (90'da 0). Günde EN ÇOK BİR "
        "gönderi kendi eski sözüne dönebilir, o da bugünün içeriği listedeki tarihli bir iddiayı gerçekten sınıyorsa; 'geri' alanına id'sini yaz. Listede "
        "olmayan bir eski sözü ('haziranda yazmıştım', 'ağustosta çekincem vardı') ASLA uydurma. Siyasi iddiaları kullanma.\n"
        "- ARŞİV ('arsiv' alanı olan haber, Wikipedia'nın 'bugün geçmişte' kaydı): 'bugün N yıl önce' çerçevesi serbest; kayıt kendi alanında kalır, başka "
        "bir alanın (takımının, rakibin) esprisine malzeme olmaz. Köprü kuramıyorsan kısa ve meraklı kalsın.\n"
        "- OKUDUĞUNU GÖSTER: haber türünde mümkünse haberin GİRİŞİNDE değil İÇİNDE geçen bir ayrıntıyı kullan; işin yaratıcısı (ajans, yönetmen, tasarımcı, "
        "geliştirici, araştırmacı) metinde adıyla geçiyorsa (malzemede 'yaratici') adını an.\n"
        "- Olgu yalnızca MALZEME'den. Skor, istatistik, transfer bedeli, tarih uydurma. Kişiye ait anı/deneyim uydurma (yalnız 'kendi' türü, çalışma kayıtlarına dayanır).\n"
        "- 'Bence' ve 'dikkatimi çekti' yasak değil: görüşü sahiplenmek ya da gerçekten ilginç bir ayrıntıya girmek için kullan, aynı açılışı tekrar etme. "
        "'asıl X değil Y' kalıbı, vecize kapanış, öğüt, haberi özetleme, 'haberine göre', uzun tire, şapkalı a, düz yazıda '+', övücü sıfat, hashtag YOK. "
        "Emoji en çok bir gönderide.\n"
        "- Herkesin aklına ilk gelecek, söylene söylene eskimiş yorum YOK; ama zorlama zekâ da yok. Taraftar tepkisi samimi olabilir.\n"
        "- TEK AYRINTI (28 Ekim, kullanıcı: 'ekstra saçma bilgiler'): bağlantı kartı haberi zaten gösteriyor. Gönderide en çok BİR somut ayrıntı (bir sayı, "
        "bir ad, bir karar) ve onun üstüne kullanıcının sözü; ayrıntı yığma, rakam sıralama, yöntem anlatma. Gerçek gönderilerinin neredeyse hiçbiri üç sayı içermez.\n"
        "- ÇEKİNCE YAZMA: 'birebir aynı şey olmayabilir', 'bilmiyorum', 'haber henüz cevap vermiyor', 'ayrı bir soru', 'şimdilik' gibi kapanışlar bu kişinin "
        "sesi değil (90 gönderisinin birinde var). Emin değilsen o iddiayı yazma; emin olduğunu söyle ve dur.\n"
        "- ZORLAMA KÖPRÜ YOK: konuyu alakasız bir alana (oyunu futbola, beyzbolu rakip takıma, her şeyi yapay zekâya) bağlayarak espri ya da görüş kurma. "
        "Köprü ancak iki şeyde gerçekten aynı mantık varsa. Aynı rakibe iğneleme günde en çok bir kez.\n"
        "- ÖZET + TEK CÜMLE YOK: kaynağı anlatıp sonuna kısa bir yorum eklemek katkı değildir; ilk cümle kullanıcının kendi gözlemi ya da hükmü olsun.\n"
        "- Kaçınılacaklar: " + "; ".join(pr.get("kacin") or []) + "\n"
        + ("BUGÜN ZATEN YAZILDI (tekrar etme, aynı temayı üçüncü kez açma):\n" + "\n".join(f"- {b}" for b in bugun_yazilanlar[:30]) + "\n" if bugun_yazilanlar else "")
        + ("SON 7 GÜNDE YAZILANLAR (aynı DÜŞÜNCEYİ başka cümleyle ya da aynı haberin başka başlığıyla yeniden yazma; yalnızca YENİ bir kanıt ya da farklı bir "
           "katkı varsa ele al ve bu durumda katkı alanında neyin yeni olduğunu söyle):\n" + "\n".join(f"- {x}" for x in son_gunler()) + "\n" if son_gunler() else "")
        + ek + paylasim._gelisim_blogu("yazim") + _bicim_siniri_metni() + _alan_tabani_metni(M) +
        "\nHer gönderi: tur, alan (" + paylasim.alan_kodlari() + "), bicim (emoji | minik | gozlem), "
        "ton (ciddi | eglenceli | samimi), metin, kaynak (dayandığı malzemenin id'si; yoksa boş), link (yalnız haber türünde haberin linki; akis türünde gönderinin "
        "linki; diğerlerinde boş), konu (okurun anlayacağı tek cümle), katki (kullanıcının kattığı, tek cümle), geri (kullandıysan 'geri' id'si; yoksa boş).\n"
        'JSON: {"gonderiler": [{"tur": "taraftar", "alan": "futbol", "bicim": "minik", "ton": "samimi", "katki": "...", "metin": "...", "kaynak": "f3", "kaynak_cumle": "...", "link": "", "konu": "..."}]}\n\n'
        "kaynak_cumle: gönderinin dayandığı olguyu taşıyan cümle, MALZEME'deki kaynağın metninden HARFİ HARFİNE kopyalanmış (en çok 30 kelime; çeviri yok, "
        "kısaltma yok). Kaynak yalnız başlıksa başlığı yaz. Kendi görüşü, taraftar sesi gibi olguya dayanmayan gönderide boş bırak.\n"
        f"MALZEME:\n{json.dumps(M, ensure_ascii=False, indent=0)}", model_adi="opus", zaman_asimi=600)


TABAN_ALANLAR = ("reklamcilik", "gusto")


def _alan_tabani_metni(M):
    """Kullanıcı (26-27 Ekim): reklamcılık ve gusto da kategori olmalı. Malzemede o alandan içerik varsa en az bir gönderi denenir."""
    var = [a for a in TABAN_ALANLAR if any(x.get("alan") == a for k in ("haber", "gundem", "gorus") for x in M.get(k) or [])]
    if not var:
        return ""
    ad = {a["kod"]: a["ad"] for a in paylasim.profil().get("alanlar") or []}
    return ("\nALAN TABANI: malzemede " + ", ".join(f"'{ad.get(a, a)}' ({a})" for a in var) + " alanından içerik var. Bu alanların her birinden EN AZ BİR "
            "gönderi yaz (kullanıcı bunları ayrı kategori olarak istiyor). Reklam sektörünün kendisi (ajans, holding, pitch, medya, marka-ajans ilişkisi) "
            "'reklamcilik'; tek bir kampanya ya da tasarım işinin kendisi 'kreatif'; yemek, içecek, mekân, nesne, zanaat, niş merak 'gusto'.\n")


def _hakem(gonderiler, pr, gundem=()):
    ornek = paylasim._ornekler(pr, 10)
    c = paylasim._claude_json(
        "İki rolün var: (1) X'te gezinen, akıllı ama meşgul bir okur; (2) aşağıdaki kişinin gönderilerini iyi tanıyan bir editör. Her gönderiyi tek tek, "
        "dürüstçe puanla (5 nadir):\n"
        "anlasilir (1-5): bağlantı kartı varsa onunla birlikte, neye tepki verdiği ve ne dediği anlaşılıyor mu (taraftar ve ironi türünde konu gündemde "
        "olduğundan kısa gönderme yeterli; ama hiç kimsenin çözemeyeceği iç şaka 2)\n"
        "paylasilir (1-5): iyi bir içerik üreticisi bunu bu haliyle paylaşır mı; boş, sıradan ya da zorlama ise en çok 2\n"
        "tazelik (1-5): herkesin aklına ilk gelen, söylene söylene eskimiş yorum mu (öyleyse 2)\n"
        "ses (1-5): örneklerdeki kişinin gerçek gönderilerine benziyor mu; yapay zekâ yazısı, haber yorumlayan bot, LinkedIn tonu, vecize kapanış ya da "
        "aşağıdaki dil kurallarının ihlali en çok 2\n"
        "tazelik dayanaktan gelir: kaynağın desteklemediği şaşırtıcı yorum taze değil, dayanaksızdır (paylasilir en çok 2)\n"
        "biçim (27 Ekim ölçümü): kişinin gönderileri kısa (ortanca ~230 karakter, neredeyse hepsi 280 altında); gözlemi açıklayan, tahmin yürüten, "
        "toparlayan yorumcu cümleleri ve gereksiz uzunluk ses en çok 3. Küçük harfle başlamak ve gündelik yazım ses kusuru DEĞİLDİR\n"
        "zorlama köprü: konu alakasız bir alana (oyun → futbol, beyzbol → rakip takım, her şey → yapay zekâ) taşınarak espri/görüş kurulmuşsa paylasilir en çok 2\n"
        "özet: gönderinin çoğu kaynağı aktarıyor, kullanıcının sözü sona eklenmiş tek cümleyse tazelik en çok 2; ayrıntı yığıyorsa (birden çok sayı, yöntem "
        "anlatımı, çekinceli kapanış) ses en çok 2\n"
        "sorun: tek cümle somut düzeltme (yoksa boş)\n"
        'JSON: {"puanlar": [{"no": 0, "anlasilir": 4, "paylasilir": 4, "tazelik": 4, "ses": 4, "sorun": ""}]}\n\n'
        f"KİŞİ: {pr.get('kimlik', '')}\n{__import__('ghost_rehber').okur_blogu()}\nÖRNEKLERİ:\n" + "\n---\n".join(ornek)
        + ("\n\nBUGÜN KONUŞULANLAR (gerçek okur gündemi bilir; kısa gönderiler bunlara göndermeyle anlaşılabilir):\n" + "\n".join(f"- {x}" for x in gundem) if gundem else "")
        + "\n\nGÖNDERİLER:\n"
        + "\n".join(f"[{i}] ({g.get('tur')}{' · bağlantı kartı: ' + g['kart'] if g.get('kart') else ''}{' · kullanıcının katkısı: ' + g['katki'] if g.get('katki') else ''}) {g['metin']}" for i, g in enumerate(gonderiler)),
        model_adi="sonnet", zaman_asimi=300)
    P = {}
    for x in c.get("puanlar") or []:
        try:
            P[int(x.get("no"))] = x
        except (TypeError, ValueError):
            continue
    return P


def _puan(x):
    try:
        return {k: int(x.get(k) or 0) for k in ("anlasilir", "paylasilir", "tazelik", "ses")}
    except (TypeError, ValueError):
        return {k: 0 for k in ("anlasilir", "paylasilir", "tazelik", "ses")}


def _gecti(g, p):
    # Kalibrasyon (23 Ekim): aynı hakem kişinin 24 gerçek gönderisinden 15'ini 'her puan ≥4' kuralıyla eliyordu ("Savaşı da kişisel gelişim unsuru
    # haline getirelim." anlaşılırlık 2). 'Her puan ≥3 ve toplam ≥13' gerçeklerin üçte ikisini geçiriyor, ilk turun zayıf taslaklarının hepsini eliyor.
    if g.get("_kendi"):                                     # kişinin kendi cevabıyla yazılan (konu toplantısı): çekirdek onun sözü, eşik bir kademe yumuşak
        return min(p.values()) >= 2 and sum(p.values()) >= 11
    return min(p.values()) >= 3 and sum(p.values()) >= 13


GERI_SOZ = re.compile(r"\b(yazmıştım|söylemiştim|demiştim|yazdıklarımın|dediğim gibi|umduğumu yazmıştım|çekince(m|mi) (vardı|koymuştum)|"
                      r"(ocak|şubat|mart|nisan|mayıs|haziran|temmuz|ağustos|eylül|ekim|kasım|aralık)(ta|te|da|de) (da )?(yaz|söyle|de)\w*)", re.I)
CEKINCE = re.compile(r"\b(olmayabilir|bilmiyorum|henüz (bir )?(cevap|yanıt) vermiyor|ayrı bir soru|şimdilik rafa|emin değilim|bu veri .{0,20}göstermiyor)", re.I)
TEKNIK = re.compile(r"(\b\d{3,4}\s?x\s?\d{3,4}\b|\bfps\b|\blufs\b|\bmodül|\bport\b|\bcommit|\bjson\b|\bapi\b|\b\d{2}[.:]\d{2}'?(e|a|ye|ya)\b|yüklenmiyor|veritabanı)", re.I)
SAYI = re.compile(r"\d+(?:[.,]\d+)*")


def _kod_notlari(g, kaynak_metni, idx=None):
    m = g["metin"]
    kaynak = (idx or {}).get(str(g.get("kaynak") or "")) or {}
    kanit = kaynak.get("kayit") if g.get("tur") == "kendi" else None        # yalnız çalışma kaydı (git) birinci şahıs işi doğrular
    kanit = kanit or kaynak.get("kendi_yorum")                              # ya da konu toplantısında kişinin kendi cevabı
    n = paylasim._kalip_notlari(m, [], kendi_deneyim=bool(kanit))
    if not str(g.get("katki") or "").strip():
        n.append("Kullanıcının katkısı belirtilmemiş; katkısı yoksa bu gönderi atılır")
    n += paylasim.sayi_notlari(m, kaynak_metni)
    if len(m) > 700:                                   # 25 Ekim: sabit 280 sınırı gerekçeyi budatıyordu; artık yalnız aşırı uzunluk
        n.append(f"{len(m)} karakter; tekrar eden ya da düşünceye hizmet etmeyen kısımları at")
    elif g.get("tur") not in UZUN_SERBEST and len(m) > (420 if g.get("tur") == "gorus" else 280):
        # 27 Ekim ölçümü: gerçek gönderilerin %99'u 280 altında, taslakların beşte biri üstündeydi; fazlası çoğunlukla açıklama cümlesi
        n.append(f"{len(m)} karakter; bu kişinin bu türdeki gönderileri 280'in altında. Gözlemi ve tek dönüşü bırak, açıklayan cümleleri at")
    y = YORUMCU.search(m) if g.get("tur") != "kendi" else None
    if y:
        n.append(f"Yorumcu cümlesi ('{y.group(0)}'): gözlemi açıklama ya da tahmin yürütme; söyleyip bırak")
    if re.search(r"\[[^\]]{2,}\]", m):
        n.append("yer tutucu var; doldurulamıyorsa bu gönderi atılır")
    # 28 Ekim (kullanıcı: "içerik seçimi, bakış açısı, karakter tutarlılığı, ekstra saçma bilgiler"; ölçüm: 90 gerçek gönderide geri dönüş 0,
    # çekince 1, üç ve üstü sayı 6; son iki günün 32 taslağında 3, 6, 4)
    gs = GERI_SOZ.search(m)
    if gs and not str(g.get("geri") or "").startswith("r:"):
        n.append(f"Kişinin eski bir sözüne dönüyor ('{gs.group(0)}') ama dayanağı geri dönüş defterinde yok; bu gönderme uydurma olabilir, çıkar")
    if g.get("tur") != "kendi":
        c = CEKINCE.search(m)
        if c:
            n.append(f"Çekinceli cümle ('{c.group(0)}'): bu kişinin sesi değil; emin olmadığın iddiayı çıkar, emin olduğunu söyle ve dur")
        if len(SAYI.findall(m)) >= 3:
            n.append("Üç ya da daha fazla sayı var; bağlantı kartı ayrıntıyı veriyor, en önemli tek ayrıntıyı bırak")
    else:
        t = TEKNIK.search(m)
        if t:
            n.append(f"Teknik ayrıntı ('{t.group(0)}') okurun işine yaramaz; ne işe yaradığını tek cümleyle söyle")
        if re.search(r"\b(kapattım|kapatıldı|artık yüklenmiyor|rafa kaldırdım)\b", m, re.I):
            n.append("Okurun hiç görmediği bir aracın kapanışını duyuruyor; bu gönderi atılır ya da yalnız işe yarayan fikir kalsın")
    d = DUYGU.search(m)                                    # 25 Ekim: kişiye mal edilen duygu/yaşanmışlık yalnızca kaynağında varsa
    if d and _norm_tr(d.group(0)) not in _norm_tr(" ".join(str(kaynak.get(a) or "") for a in ("derdi", "kendi_yorum", "gorus", "kanit", "is"))):
        n.append(f"Kişiye kaynakta olmayan bir duygu/yaşanmışlık mal ediyor ('{d.group(0)}'); çıkar, ne yapıldığını ve neden değerli olduğunu yaz")
    return n


DUYGU = re.compile(r"\b(canım çıktı|kafayı yedim|delirdim|çıldırdım|sinir oldum|sinirden|bayıldım|aşık oldum|gözümde büyü\w*|uykularım kaçtı|"
                   r"saçımı başımı yoldum|ağlayacaktım|çok uğraştım|günlerimi aldı)\b", re.I)


def _norm_tr(t):
    return str(t or "").replace("İ", "i").replace("I", "ı").lower()


def _bicim_ust(b):
    try:
        import ghost_gelisim
        return ghost_gelisim.bicim_ust(b)
    except Exception:  # noqa: BLE001
        return None


def _bicim_siniri_metni():
    S = {b: _bicim_ust(b) for b in ("emoji", "minik", "gozlem")}
    S = {b: n for b, n in S.items() if n is not None}
    return ("BİÇİM SINIRI (kişinin kararlarından): " + ", ".join(f"{b} en çok {n}" for b, n in S.items())
            + ". Sınırı aşan biçimde yazma; o fikri daha kısa bir biçimle kur ya da hiç yazma.\n") if S else ""


def _kaynak_denetimi(gecen, idx, haberler, log):
    """Her taslağı dayandığı kaynağın metniyle denetler (ghost_kaynak). Kaynak: haberde okunmuş metin, gündem/futbolda bağlantının metni, X
    gönderisinde gönderi, tetikte tetik içeriği, kendi işinde çalışma kaydı (+ varsa derdi), görüşte kişinin kendi sözü. Döner: geçenler."""
    import concurrent.futures
    import ghost_kaynak
    tam = {f"h{i}": (o.get("metin_ozu") or o.get("ozet") or "") for i, o in enumerate(haberler[:6])}

    def kaynak(g):
        src = idx.get(str(g.get("kaynak") or "")) or {}
        kid = str(g.get("kaynak") or "")
        if g.get("tetik_kaynak"):
            t = g["tetik_kaynak"]
            return t.get("baslik", ""), ghost_kaynak.kaynak_metni_bul(t.get("link", ""), t.get("baslik", ""))
        if kid.startswith("h"):
            return src.get("baslik", ""), (src.get("baslik", "") + "\n" + (tam.get(kid) or src.get("metin", "")))
        if kid.startswith("k:"):
            return "Çalışma kaydı", f"Yaptığı iş: {src.get('is', '')}\nZorlandığı yer: {src.get('derdi') or 'kayıtta yok (duygu ya da zorluk iddiası dayanaksız)'}"
        if kid.startswith("o:"):
            return "Görüş defteri", f"Kişinin görüşü: {src.get('gorus', '')}\nKendi sözü: {src.get('kanit', '')}" + (f"\nTetik haber: {src.get('baslik', '')}" if src.get("tetik") else "")
        if kid.startswith("a:"):
            return f"@{src.get('hesap', '')}", src.get("metin", "")
        yedek = src.get("baslik", "") + ("\n" + src.get("ozet", "") if src.get("ozet") else "")
        return src.get("baslik", ""), ghost_kaynak.kaynak_metni_bul(g.get("link") or src.get("link", ""), yedek)
    with concurrent.futures.ThreadPoolExecutor(4) as ex:
        K = list(ex.map(kaynak, gecen))
    for g, (b, m) in zip(gecen, K):
        g["kaynak_baslik"], g["kaynak_metni"] = b, m
    ok, atilan = ghost_kaynak.denetle(gecen, log)
    for g in atilan:
        g["kaynak_yanlis"] = True
    for g in gecen:
        g.pop("kaynak_metni", None)
    return ok


def _asama(ad, giren, cikan, **ek):
    try:
        import ghost_gelisim
        ghost_gelisim.asama(ad, giren, cikan, **ek)
    except Exception:  # noqa: BLE001
        pass


def calistir(maddeler, haberler, hedef=12, log=print, gorus_cevaplari=None):
    """Günün karışımını yazar, hakemden geçirir, ghost kaydına koyar. Döner: (temel, geçen taslak sayısı)."""
    _bas = __import__('time').time()
    import kesif
    pr = paylasim.profil()
    M = malzeme(maddeler, haberler)
    try:                                                   # reklam arşivi (reklam_arsivi.py): kreatif haberlere kişinin ödüllü işler arşivinden emsal
        import reklam_arsivi
        kr = [h for h in M["haber"] if h.get("alan") in ("kreatif", "reklamcilik", "populer_kultur") and "emsal" not in h]
        if kr:
            B = reklam_arsivi.benzerleri_sec([{"id": h["id"], "metin": f"{h['baslik']}. {h.get('ayrinti', '')} {h.get('aci', '')}"} for h in kr], log)
            for h in kr:
                if B.get(h["id"]):
                    h["emsal"] = [{"is": reklam_arsivi.kisa(b["is"])[:220], "neden": b["neden"]} for b in B[h["id"]]]
    except Exception as e:  # noqa: BLE001
        log(f"Reklam arşivi emsali alınamadı: {e}")
    for g in M["gorus"]:                                   # konu toplantısında görüşe verilen cevap (konu_toplantisi.py)
        if (gorus_cevaplari or {}).get(g["gorus"]):
            g["kendi_yorum"] = gorus_cevaplari[g["gorus"]]
    dag = _dagilim(M, hedef)
    bugun = kesif._bugun_yazilanlar() + _bugun_karisim()
    log(f"Karışım: hedef {hedef}, dağılım {dag}")
    c = _yaz(M, dag, pr, bugun, hedef=hedef)
    kaynak_metni = json.dumps(M, ensure_ascii=False)
    idx = {x["id"]: x for L in M.values() for x in L}
    G, _ret = [], []
    for g in c.get("gonderiler") or []:
        m = paylasim._temiz(str(g.get("metin") or "")).strip()
        if not m or re.search(r"\[[^\]]{2,}\]", m):        # yer tutucu: malzeme yetmemiş, doldurmak uydurmak olur
            continue
        g["metin"] = m; g["yazar_ilk"] = m          # 25 Ekim: editörlerden önceki ilk hal (ilk taslak mı daha iyiydi, karşılaştırılabilsin)
        g["tur"] = g.get("tur") if g.get("tur") in TURLER else "gorus"
        src = idx.get(str(g.get("kaynak") or ""))
        if g["tur"] == "haber" and not str(g.get("kaynak") or "").startswith("h"):
            continue                                        # haber türü yalnız açı elemesinden geçmiş, metni okunmuş haberlerden (gündem başlığından haber yorumu = bot havası)
        # 28 Ekim: türün kaynağı doğru mu. Son iki günün 'görüş' taslaklarının çoğu gündem başlığından yazılmıştı (başlığı özetle + yorum ekle + ayrıntı yığ);
        # ironi gerçekten konuşulan bir konuya, taraftar sesi futbola dayanır.
        k1 = str(g.get("kaynak") or "")
        if g["tur"] == "gorus" and k1[:1] in ("h", "f"):
            g["tur"] = "haber" if k1[:1] == "h" else "taraftar"     # habere ya da futbol haberine tepki, adı doğru konsun
        if (g["tur"] == "gorus" and k1[:2] != "o:") or (g["tur"] == "ironi" and not (k1[:1] in ("g", "a") and (k1[:1] == "a" or (src or {}).get("konusulan")))) \
                or (g["tur"] == "taraftar" and k1[:1] not in ("f", "a")):
            _ret.append({"konu": g.get("konu", ""), "neden": "türün kaynağı uymuyor", "son_metin": m, "alan": g.get("alan", "")})
            continue
        kid = str(g.get("kaynak") or "")
        link = (src or {}).get("link", "") if (kid[:1] in ("h", "g", "f", "a") or (kid[:2] == "o:" and (src or {}).get("tetik"))) and g["tur"] != "kendi" else ""
        if kid[:1] == "g" and "news.google." in link:
            try:
                import kesif
                link = kesif.gn_coz(link)
            except Exception:  # noqa: BLE001
                pass
        g["link"] = link
        g["kart"] = (src or {}).get("baslik", "") if link else ""
        g["_kendi"] = bool((src or {}).get("kendi_yorum"))
        G.append(g)
    if not G:
        log("Karışım: yazım yanıtı boş"); return None, 0
    gundem = [x["baslik"] for x in M["gundem"][:10] + M["futbol"][:8]]
    P = _hakem(G, pr, gundem)
    gecen, duzelt = [], []
    for i, g in enumerate(G):
        p = _puan(P.get(i) or {})
        notlar = _kod_notlari(g, kaynak_metni, idx)
        g["okur"] = p
        if _gecti(g, p) and not notlar:
            gecen.append(g)
        elif min(p.values()) >= 2 and sum(p.values()) >= 12:
            g["notlar"] = ([str((P.get(i) or {}).get("sorun") or "")] if (P.get(i) or {}).get("sorun") else []) + notlar
            duzelt.append(g)
    log(f"Karışım: {len(G)} yazıldı → {len(gecen)} doğrudan geçti, {len(duzelt)} düzeltilecek")
    _asama("karisim.yazim", c and len(c.get("gonderiler") or []), len(G))
    _asama("karisim.hakem", len(G), len(gecen), duzeltilecek=len(duzelt))
    if duzelt:
        c2 = paylasim._claude_json(
            f"Aşağıdaki X gönderileri bir kişinin ağzından yazıldı; editör notlarına göre her birini düzelt. Notların istemediği yere dokunma, uzatma, açıklama "
            f"ekleme. Olgu uydurma.\n{paylasim._persona_blogu(pr, kisa=True)}\nGERÇEK ÖRNEKLERİ:\n" + "\n---\n".join(paylasim._ornekler(pr, 8)) +
            '\nJSON: {"gonderiler": [{"no": 0, "metin": "..."}]}\n\n'
            + "\n\n".join(f"[{i}] ({g['tur']}) {g['metin']}\nNOTLAR: {'; '.join(g['notlar'])}" for i, g in enumerate(duzelt)),
            model_adi="opus", zaman_asimi=400)
        for x in c2.get("gonderiler") or []:
            try:
                g = duzelt[int(x.get("no"))]
            except (TypeError, ValueError, IndexError):
                continue
            if str(x.get("metin") or "").strip():
                g["onceki"] = g["metin"]; g["metin"] = paylasim._temiz(str(x["metin"])).strip()
        P2 = _hakem(duzelt, pr, gundem)
        for i, g in enumerate(duzelt):
            p = _puan(P2.get(i) or {})
            g["okur"] = p
            if _gecti(g, p) and not _kod_notlari(g, kaynak_metni, idx):
                gecen.append(g)
        log(f"Karışım: düzeltmeden sonra toplam {len(gecen)} geçti")
        _asama("karisim.duzeltme", len(duzelt), sum(1 for g in duzelt if g in gecen))
    # GERİ DÖNÜŞ (24 Ekim): bağlantısı yoksa kendi eski gönderisini alıntılar (tetik o olur)
    for g in gecen:
        r = idx.get(str(g.get("geri") or "")) or {}
        if r:
            g["geri_kayit"] = r
            if not g.get("link") and r.get("url"):
                g["alinti"] = {"id": r["url"].rsplit("/", 1)[-1], "kullanici": _kimlik()["x_kullanici"], "metin": r.get("metin", ""), "url": r["url"]}
                g["link"] = r["url"]
    # TETİK (23 Ekim): 'kendi' dışındaki her gönderi bir içeriğe tepki olmalı; bağlantısız kalanlara tetik aranır, bulunamazsa o gün çıkmaz
    tetiksiz = [g for g in gecen if g["tur"] != "kendi" and not g.get("link")]
    if tetiksiz:
        import tetik
        for g in tetiksiz[:5]:
            try:
                A = tetik.adaylar(g.get("konu") or "", g["metin"], en_cok=1, log=log)
            except Exception as e:  # noqa: BLE001
                A = []; log(f"Karışım: tetik aranamadı ({e})")
            if not A:
                gecen.remove(g); g["tetik_yok"] = True
                continue
            try:
                y = tetik.tepki_olarak_yaz({"metin": g["metin"], "konu": g.get("konu", "")}, A[0])
            except Exception:  # noqa: BLE001
                gecen.remove(g); g["tetik_yok"] = True
                continue
            g["onceki"] = g["metin"]; g["metin"] = y["metin"]; g["link"] = y.get("paylas_link", ""); g["alinti"] = y.get("alinti")
            g["tetik_kaynak"] = y.get("kaynak") or {"tur": "X gönderisi", "baslik": A[0].get("metin", "")[:200], "tarih": A[0].get("tarih", ""), "link": A[0].get("link", ""), "kanit": ""}
            g["kart"] = A[0].get("baslik", "")
        for g in tetiksiz[5:]:
            gecen.remove(g); g["tetik_yok"] = True
        log(f"Karışım: tetiği olmayan {sum(1 for g in tetiksiz if g.get('tetik_yok'))} gönderi bugün çıkmadı")
        _asama("karisim.tetik", len(tetiksiz), sum(1 for g in tetiksiz if not g.get("tetik_yok")))
    # KAYNAK ANLAMI (25 Ekim, ChatGPT değerlendirmesi): yorumun dayandığı olgu kaynakla tutarlı mı; kim ne yaptı doğru mu (ghost_kaynak.py)
    if gecen:
        n0 = len(gecen)
        try:
            gecen = _kaynak_denetimi(gecen, idx, haberler, log)
        except Exception as e:  # noqa: BLE001
            log(f"Karışım: kaynak denetimi yapılamadı ({e})")
        _asama("karisim.kaynak_denetimi", n0, len(gecen))
    # SON DENETİMLER (24 Ekim, araştırma önerileri): Topluluk Notu provası, çevrede söylendi, maç sonrası soğuma. "Çekinceleri güçlendirme" 25 Ekim'de
    # KALDIRILDI: kaynak denetiminden SONRA çalışıp "neden belli değil" gibi bilinmeyene dair çekinceleri silebiliyordu; ölçümde hiçbir taslağı değiştirmemişti.
    for adim in (_not_provasi, _cevrede):
        ad = adim.__name__.strip("_")
        if not paylasim._gelisim_acik(ad):                # öz değerlendirme bir şey değiştirmeyen aşamayı kapatabilir (geri alınabilir)
            continue
        once = [(g["metin"], bool(g.get("cevrede"))) for g in gecen]; n0 = len(gecen)
        try:
            adim(gecen, pr, idx, kaynak_metni, log)
        except Exception as e:  # noqa: BLE001
            log(f"Karışım: {adim.__name__} yapılamadı ({e})")
        degisen = n0 - len(gecen) + sum(1 for g in gecen if (g["metin"], bool(g.get("cevrede"))) not in once)
        _asama(f"karisim.{ad}", n0, len(gecen), degisen=degisen)
    for g in gecen:
        _soguma(g)
    _gunluk_sinirlar(gecen, log)
    for b in ("emoji", "minik", "gozlem"):                 # biçim üst sınırı (gelişim; 24 Ekim kabul edilen öneri): fazlası en zayıftan atılır
        u = _bicim_ust(b)
        B = [g for g in gecen if (g.get("bicim") if g.get("bicim") in ("emoji", "minik", "gozlem") else "gozlem") == b]
        if u is not None and len(B) > u:
            for g in sorted(B, key=lambda g: sum((g.get("okur") or {}).values()))[:len(B) - u]:
                gecen.remove(g); g["bicim_siniri"] = True
            _asama(f"karisim.bicim_ust.{b}", len(B), u)
            log(f"Karışım: {b} biçiminde {len(B) - u} gönderi sınır nedeniyle çıkmadı")
    if not gecen:
        return None, 0
    alan_ad = {a.get("kod"): a.get("ad") for a in pr.get("alanlar") or [] if isinstance(a, dict)}
    taslaklar = []
    for g in gecen:
        p = g["okur"]
        src = idx.get(str(g.get("kaynak") or "")) or {}
        taslaklar.append({
            "platform": "x", "karisim_tur": g["tur"], "alan": alan_ad.get(g.get("alan"), g.get("alan") or ""), "alan_kod": g.get("alan") or "",
            "bicim": g.get("bicim") if g.get("bicim") in ("emoji", "minik", "gozlem") else "gozlem", "ton": g.get("ton") or "",
            "metin": g["metin"], "karakter": len(g["metin"]), "konu": str(g.get("konu") or "")[:240],
            "okur": {"anlasilir": p["anlasilir"], "tamlik": p["anlasilir"], "deger": p["paylasilir"], "kanca": p["paylasilir"], "ses": p["ses"],
                     "tazelik": p["tazelik"], "paylasilir": p["paylasilir"]},
            "paylas_link": g.get("link") or "", "link_oner": bool(g.get("link")), "ilk_yanit": "", "kancalar": [], "zincir": [], "uzunluk": "kisa",
            "itirazlar": [], "iddialar": [], "panel": [], "kod_notlari": [],
            "dayanak": "kendi" if src.get("kendi_yorum") else ("gorus" if str(g.get("kaynak") or "").startswith("o:") else ("kendi" if g["tur"] == "kendi" else "")),
            **({"kendi_yorum": src["kendi_yorum"]} if src.get("kendi_yorum") else {}),
            **({"emsal": src["emsal"]} if src.get("emsal") else {}),
            "alinti": g.get("alinti") or ({"id": str(g["kaynak"])[2:], "kullanici": src.get("hesap", ""), "metin": src.get("metin", ""), "url": src.get("link", "")}
                                          if str(g.get("kaynak") or "").startswith("a:") and src else None),
            "neden": (src.get("baslik") or src.get("gorus") or src.get("is") or src.get("metin") or "")[:300],
            "katki": str(g.get("katki") or "")[:240],
            **({"kaynak_cumle": _kaynak_cumle(g, src)} if _kaynak_cumle(g, src) else {}),
            **({"x_alinti_onerisi": src["x_gonderi"]} if src.get("x_gonderi") and not g.get("alinti") else {}),
            **{k: g[k] for k in ("guclendi", "not_provasi", "cevrede", "sogusun", "kaynak_denetimi", "kaynak_oncesi") if g.get(k)},
            **({"ilk_taslak": g["yazar_ilk"]} if g.get("yazar_ilk") and g["yazar_ilk"] != g["metin"] else {}),
            **({"geri": {k: g["geri_kayit"].get(k) for k in ("tur", "ad", "tarih", "iddia", "url") if g["geri_kayit"].get(k)}} if g.get("geri_kayit") else {}),
            # kaynak, tarih ve (varsa) kanıt taslağın yanında görünür (2026-10-23)
            "kaynak": {"tur": {"h": "haber", "g": "gündem", "f": "futbol haberi", "o": "görüş defteri", "k": "çalışma kaydı", "a": "X gönderisi", "r": "geri dönüş defteri"}.get(str(g.get("kaynak") or "")[:1], ""),
                       "baslik": (src.get("baslik") or src.get("konu") or src.get("is") or src.get("metin") or "")[:200],
                       "tarih": src.get("tarih", ""), "link": src.get("link", ""), "kanit": src.get("kayit", "") or src.get("kanit", ""),
                       # köken (24 Ekim): nereden keşfedildi, ne okundu, kimin beyanı, ne bilinmiyor, olay ne zaman
                       **{k: src[k] for k in ("kesif_link", "kesif_yayin", "kesif_bulten", "kesif_kantan", "okunan", "beyan", "sinir", "olay_tarihi", "nesne", "yaratici") if src.get(k)},
                       **({} if src.get("okunan") else {"okunan": [OKUNAN.get(str(g.get("kaynak") or "")[:1], "")] if OKUNAN.get(str(g.get("kaynak") or "")[:1]) else []}),
                       **({"eski_is": True} if src.get("eski_is") else {})} if src and not g.get("tetik_kaynak") else g.get("tetik_kaynak"),
        })
    temel = paylasim.ghost_kaydi(json.dumps(M, ensure_ascii=False)[:20000], "karisim", f"Günün akışı · {time.strftime('%d.%m %H.%M')}", "", "",
                                 ek={"platform": "x"})
    yol = paylasim.GHOST / f"{temel[7:]}.json"
    d = json.loads(yol.read_text(encoding="utf-8"))
    d["veri"]["paylasim"] = {"taslaklar": taslaklar, "zaman": time.time(), "ilk_zaman": time.time(), "model": paylasim._yazan(_bas), "surum": 5,
                             "elenen": [{"konu": g.get("konu", ""), "neden": "tetik bulunamadı" if g.get("tetik_yok") else "biçim sınırı" if g.get("bicim_siniri") else g["sinir"] if g.get("sinir") else "kaynağı yanlış okuyordu" if g.get("kaynak_yanlis") else ("Topluluk Notu riski" if (g.get("not_provasi") or {}).get("risk", 0) >= 4 else "hakem"), "okur": g.get("okur"), "son_metin": g["metin"], "alan": g.get("alan", "")}
                                        for g in G if g not in gecen] + _ret}
    yol.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    _kullanildi([str(g.get("kaynak")) for g in gecen if str(g.get("kaynak") or "")[:2] in ("o:", "k:", "a:")])
    log(f"Karışım: {len(taslaklar)} taslak hazır ({', '.join(f"{t} {sum(1 for g in gecen if g['tur'] == t)}" for t in TURLER if any(g['tur'] == t for g in gecen))})")
    return temel, len(taslaklar)


def _gunluk_sinirlar(gecen, log=print):
    """28 Ekim: karakter tutarlılığı ve alan dengesi kodla. Geri dönüş (eski sözüne gönderme) günde en çok bir; yapay zekâ alanı toplamın üçte birini
    geçmez (istem söylüyordu ama 28 Ekim sabahı 15 taslağın 5'i yapay zekâydı). Fazlası en zayıftan atılır."""
    guc = lambda g: sum((g.get("okur") or {}).values())
    bugun = _bugun_karisim()
    geri = sorted([g for g in gecen if g.get("geri") or GERI_SOZ.search(g["metin"])], key=guc, reverse=True)
    onceki_geri = sum(1 for x in bugun if GERI_SOZ.search(x))
    for g in geri[max(0, 1 - onceki_geri):]:
        gecen.remove(g); g["sinir"] = "geri dönüş günde en çok bir"
    ai = sorted([g for g in gecen if g.get("alan") == "teknoloji_ai"], key=guc, reverse=True)
    ust = max(1, (len(gecen) + 2) // 3)
    for g in ai[ust:]:
        gecen.remove(g); g["sinir"] = "yapay zekâ üçte biri geçmesin"
    n = sum(1 for g in geri + ai if g.get("sinir"))
    if n:
        log(f"Karışım: {n} gönderi günlük sınır nedeniyle çıkmadı (geri dönüş, yapay zekâ payı)")


def son_gunler(gun=7, en_cok=60):
    """Son N günün Ghost konuları (paylaşılan önce): düşünce düzeyinde tekrar kontrolü için. ['[paylaşıldı] konu — metin']."""
    sinir = time.time() - gun * 86400
    pay, tas = [], []
    for f in sorted(paylasim.GHOST.glob("*.json"), key=lambda f: -f.stat().st_mtime):
        if f.stat().st_mtime < sinir:
            break
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        for t in (d["veri"].get("paylasim") or {}).get("taslaklar") or []:
            satir = f"{(t.get('konu') or '')[:90]} — {(t.get('metin') or '')[:90]}"
            (pay if t.get("paylasildi") else tas).append(("[paylaşıldı] " if t.get("paylasildi") else "[taslak] ") + satir)
    return (pay + tas)[:en_cok]


def _bugun_karisim():
    """Bugün yazılmış karışım taslakları (öğleden sonraki tur tekrar etmesin)."""
    out = []
    gun = date.today().strftime("%Y%m%d")
    for f in sorted(paylasim.GHOST.glob(f"{gun}*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        for t in (d["veri"].get("paylasim") or {}).get("taslaklar") or []:
            out.append(t.get("metin", "")[:140])
    return out


def _dokunulmus(t):
    """Kullanıcının üzerinde çalıştığı taslak: düzenlendi, yorum yapıldı, kopyalandı, paylaşıldı ya da kendisi kaldırdı. Budamada asla değişmez."""
    return bool(t.get("ilk_metin") or t.get("yorumlar") or t.get("kopyalandi") or t.get("paylasildi") or t.get("geri_getirildi")
                or (t.get("gizli") and not t.get("degistirildi")))


def budama(gunluk, log=print):
    """Gün içinde yeni paket değil, DEĞİŞTİRME (kullanıcının editoryal yöntemi, 24 Ekim: 'sonraki kontrollerde baştan yeni paket üretmek yerine daha güçlü
    adayla değişiklik'). Bugünün açık (gizli olmayan) karışım taslakları günlük hedefi aşarsa, dokunulmamış olanların en zayıfı (okur puanı toplamı)
    gizlenir: 'daha güçlü bir öneriyle değiştirildi'. Kullanıcının dokunduğu taslaklar hiç değişmez. Döner: değiştirilen sayısı."""
    gun = date.today().strftime("%Y%m%d")
    kayitlar = []
    for f in sorted(paylasim.GHOST.glob(f"{gun}*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if d["veri"].get("kaynak_tur") == "karisim":
            kayitlar.append((f, d))
    acik = [(f, d, i, t) for f, d in kayitlar for i, t in enumerate((d["veri"].get("paylasim") or {}).get("taslaklar") or [])
            if not t.get("gizli") and t.get("platform", "x") == "x"]
    fazla = len(acik) - gunluk
    if fazla <= 0:
        return 0
    puan = lambda t: sum(int(v or 0) for k, v in (t.get("okur") or {}).items() if k in ("anlasilir", "paylasilir", "tazelik", "ses"))  # noqa: E731
    adaylar = sorted([x for x in acik if not _dokunulmus(x[3])], key=lambda x: (puan(x[3]), -x[0].stat().st_mtime))[:fazla]
    degisen = set()
    for f, d, i, t in adaylar:
        t["gizli"] = True; t["degistirildi"] = True; t["red_nedeni"] = "daha güçlü bir öneriyle değiştirildi"; t["gizlenme"] = time.time()
        degisen.add(f)
    for f, d in kayitlar:
        if f in degisen:
            f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    if adaylar:
        log(f"Karışım: {len(adaylar)} zayıf taslak daha güçlü önerilerle değiştirildi (" + "; ".join(x[3].get("metin", "")[:40] for x in adaylar) + ")")
    return len(adaylar)


def acik_sayisi():
    """Bugünün açık (gizli olmayan) karışım X taslağı sayısı."""
    gun = date.today().strftime("%Y%m%d")
    n = 0
    for f in paylasim.GHOST.glob(f"{gun}*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if d["veri"].get("kaynak_tur") == "karisim":
            n += sum(1 for t in (d["veri"].get("paylasim") or {}).get("taslaklar") or [] if not t.get("gizli"))
    return n


# ---------------------------------------------------------------- son denetimler (24 Ekim)
HARARET = re.compile(r"(rezalet|utanç|istifa|defol|yazıklar olsun|kahrolsun|s[ıi]kt[ıi]r|aptal|salak|şerefsiz|hain|beceriksiz|yerin dibine|kovun|gitsin artık)", re.I)


def _kaynak_ozeti(g, idx):
    s = idx.get(str(g.get("kaynak") or "")) or {}
    return (s.get("baslik") or s.get("gorus") or s.get("is") or s.get("metin") or "")[:200] + " " + (s.get("olgu") or s.get("metin") or s.get("ozet") or "")[:400]


def _not_provasi(gecen, pr, idx, kaynak_metni, log):
    """Topluluk Notu provası: adil bir not yazarı bu gönderiye bağlam notu düşer mi? (Not düşülen gönderi yeniden paylaşımın ~%46'sını kaybediyor,
    PNAS 2025.) Risk ≥4: önerilen düzeltme kod denetiminden geçerse uygulanır, geçmezse gönderi o gün çıkmaz; risk 3: Ayrıntılar'da not."""
    aday = [g for g in gecen if g["tur"] not in ("taraftar", "ironi", "kendi")]
    if not aday:
        return
    c = paylasim._claude_json(
        "X'te Topluluk Notları yazan, adil ve titiz birisin. Aşağıdaki gönderilerden hangisine 'okurların bilmesi gereken bağlam' notu düşerdin? Ölçüt: "
        "olgu hatası, bağlamından koparılmış iddia, beyanı olgu gibi sunmak, eski bir olayı yeniymiş gibi sunmak, yanıltıcı karşılaştırma. Görüş ve espri "
        "not gerektirmez. risk 1-5 (5: kesin not düşülür), neden (tek cümle), duzeltme (risk ≥3 ise aynı sesle, en az değişiklikle düzeltilmiş metin; yoksa boş).\n"
        'JSON: {"gonderiler": [{"no": 0, "risk": 1, "neden": "", "duzeltme": ""}]}\n\n'
        + "\n\n".join(f"[{i}] {g['metin']}\nDAYANAK: {_kaynak_ozeti(g, idx)}" for i, g in enumerate(aday)), model_adi="sonnet", zaman_asimi=240)
    atilan = 0
    for x in c.get("gonderiler") or []:
        try:
            g = aday[int(x.get("no"))]; r = int(x.get("risk") or 0)
        except (TypeError, ValueError, IndexError):
            continue
        if r < 3:
            continue
        g["not_provasi"] = {"risk": r, "neden": str(x.get("neden") or "")[:200]}
        if r >= 4:
            d = paylasim._temiz(str(x.get("duzeltme") or "")).strip()
            eski = g["metin"]
            if d and d != eski:
                g["metin"] = d
                if not _kod_notlari(g, kaynak_metni, idx):
                    g["not_provasi"]["duzeltildi"] = eski; continue
                g["metin"] = eski
            if g in gecen:
                gecen.remove(g); atilan += 1
    if atilan:
        log(f"Karışım: Topluluk Notu riski yüksek {atilan} gönderi bugün çıkmadı")


def _cevrede(gecen, pr, idx, kaynak_metni, log):
    """Çevrede zaten söylendi mi: izlenen 100 hesabın son 48 saatteki gönderileriyle AYNI NOKTAYI söyleyen taslak işaretlenir (konu benzerliği yetmez);
    kartta 'bunu @x zaten söyledi · onu alıntıla' çıkar ve plan sırada geri alır."""
    import hesaplar
    P = hesaplar.akis(48)[:70]
    aday = [g for g in gecen if g["tur"] != "kendi" and not g.get("alinti")]
    if not P or not aday:
        return
    c = paylasim._claude_json(
        "Aşağıda bir kişinin taslak X gönderileri ve onun takipçilerinin büyük ihtimalle gördüğü, son 48 saatte paylaşılmış gönderiler var. Hangi taslak, "
        "bu gönderilerden birinin söylediği NOKTAYI (aynı gözlem ya da aynı espri) tekrar ediyor? Aynı konu yetmez; aynı söz olmalı. Yoksa yazma.\n"
        'JSON: {"eslesme": [{"taslak": 0, "gonderi": 3, "neden": "tek cümle"}]}\n\nTASLAKLAR:\n'
        + "\n".join(f"[{i}] {g['metin']}" for i, g in enumerate(aday)) + "\n\nGÖNDERİLER:\n"
        + "\n".join(f"[{j}] @{p['kullanici']}: {p.get('metin', '')[:280]}" for j, p in enumerate(P)), model_adi="sonnet", zaman_asimi=200)
    n = 0
    for e in c.get("eslesme") or []:
        try:
            g = aday[int(e.get("taslak"))]; p = P[int(e.get("gonderi"))]
        except (TypeError, ValueError, IndexError):
            continue
        g["cevrede"] = {"id": p["id"], "kullanici": p["kullanici"], "metin": p.get("metin", "")[:400], "url": f"https://x.com/{p['kullanici']}/status/{p['id']}",
                        "neden": str(e.get("neden") or "")[:200]}
        n += 1
    if n:
        log(f"Karışım: {n} taslağın söylediği izlenen hesaplarda zaten söylenmiş (işaretlendi)")


def _soguma(g):
    """Maç sonrası soğuma: futbol taslağı sert dille yazıldıysa ya da takımın maçının bitişinden sonraki ilk saatlerde yazıldıysa 'sabah bir daha bak'.
    Şikâyet ve sessize alma, beğeniden çok daha ağır olumsuz sinyal (X sıralama kodu)."""
    if not FUTBOL_ALAN.search(g.get("alan") or "") and g["tur"] != "taraftar":
        return
    if HARARET.search(g["metin"]):
        g["sogusun"] = "sert dil"; return
    try:
        import ghost_defter
        m = ghost_defter.mac_gunu()
        if m.get("var") and m.get("saat"):
            h, dk = [int(x) for x in re.split(r"[.:]", m["saat"])]
            bas = datetime.combine(date.today(), datetime.min.time()).timestamp() + h * 3600 + dk * 60
            if bas + 100 * 60 <= time.time() <= bas + 5 * 3600:
                g["sogusun"] = "maçtan hemen sonra yazıldı"
    except Exception:  # noqa: BLE001
        pass


def _kaynak_cumle(g, src):
    """Modelin verdiği kaynak cümlesi kaynakta GERÇEKTEN geçiyor mu (boşluk/tırnak/büyük-küçük harf farkı yok sayılır); geçmiyorsa atılır.
    Kartta 'Kaynakta: “…”' olarak görünür (Ghost büyük işi 4, 24 Ekim): okur bilgisinin neye dayandığı tek bakışta doğrulanır."""
    k = re.sub(r"\s+", " ", str(g.get("kaynak_cumle") or "")).strip(' "“”\'')
    if len(k) < 12 or not src:
        return ""
    havuz = " ".join(str(src.get(a) or "") for a in ("baslik", "metin", "ozet", "olgu", "asil_metin", "gorus", "is", "iddia", "beyan", "ayrinti"))
    norm = lambda s: re.sub(r"[^\w%]+", " ", s.lower()).strip()      # noqa: E731
    if norm(k) in norm(havuz):
        return k[:300]
    W = norm(k).split()                                    # en az 8 kelimelik kesintisiz bir parça geçiyorsa (model baş/sonu kırpmış olabilir)
    for i in range(0, max(1, len(W) - 7)):
        if len(W) >= 8 and " ".join(W[i:i + 8]) in norm(havuz):
            return k[:300]
    return ""
