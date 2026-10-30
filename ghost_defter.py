"""ghost_defter.py - Ghost'un "kişinin kendi malzemesi" katmanı (2026-10-21; araştırma: kalite başkasının içeriğinden değil kişinin kendi
deneyim ve görüşünden gelir). Hepsi kullanıcının KENDİ sözleri; toplantılardan yalnızca onun cümleleri ve genelleştirilmiş hâlleri, onayıyla.

- Fikir defteri (`profil/fikir_defteri.json`): sesli notlar, yazılı fikirler, günün sorularına cevaplar, maç notları. Ham malzeme.
- Günün soruları (`kayitlar/ghost_sorular/<tarih>.json`): o günün malzemesinden (toplantıları, Video Hub'da yaptıkları, maç, gündem, eski bir
  görüşü) çıkan 3 soru; cevap (yazı ya da 20 sn sesli not) → gönderi.
- Görüş adayları (`profil/gorus_adaylari.json`): toplantılarda ve notlarda kendi söylediklerinden çıkan görüşler; tek dokunuşla deftere.
- Maç günü (`profil/mac_defteri.json`): tuttuğu takımın (profil `takim`) maçı varsa maç öncesi tahmin, düdük sonrası tepki; ikisi de gönderiye dönebilir.
- Birleştirme önerileri: birbirinden uzak iki notun birlikte bir gönderi olması (alanlar arası bağlam).
"""
import json
import re
import subprocess
import time
from datetime import date, datetime, timedelta
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
DEFTER = KLASOR / "profil" / "fikir_defteri.json"
ADAY = KLASOR / "profil" / "gorus_adaylari.json"
MAC = KLASOR / "profil" / "mac_defteri.json"
SORU = KLASOR / "kayitlar" / "ghost_sorular"
BIRLES = KLASOR / "kayitlar" / "ghost_birlestirme.json"


def _oku(yol, bos):
    try:
        return json.loads(Path(yol).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return bos


def _yaz(yol, veri):
    Path(yol).parent.mkdir(parents=True, exist_ok=True)
    Path(yol).write_text(json.dumps(veri, ensure_ascii=False, indent=1), encoding="utf-8")


def _ayar():
    return _oku(KLASOR / "ayarlar.json", {})


# ---------------------------------------------------------------- fikir defteri
def notlar(n=60):
    return _oku(DEFTER, [])[-n:][::-1]


def not_ekle(metin, tur="yazi", soru="", ek=None):
    metin = str(metin or "").strip()
    if len(metin) < 4:
        return None
    L = _oku(DEFTER, [])
    x = {"id": time.strftime("%Y%m%d%H%M%S") + f"{len(L) % 100:02d}", "zaman": time.time(), "tur": tur, "metin": metin[:4000], "soru": soru[:400], **(ek or {})}
    L.append(x); _yaz(DEFTER, L[-1000:])
    return x


def not_sil(nid):
    _yaz(DEFTER, [x for x in _oku(DEFTER, []) if x.get("id") != nid])


def not_kullanildi(nid, temel):
    L = _oku(DEFTER, [])
    for x in L:
        if x["id"] == nid:
            x.setdefault("gonderiler", []).append(temel)
    _yaz(DEFTER, L)


# ---------------------------------------------------------------- günün soruları
def _bugun_toplantilar():
    """Bugünkü toplantılar: yalnızca kısa özetin ilk paragrafı (müşteri adı istemde gizlenir). 2026-10-23: müşteri toplantıları kişisel paylaşım
    üretiminin VARSAYILAN olarak dışında (ChatGPT brifi); ayar `ghost_toplanti_sorular` açıkça açılırsa kullanılır."""
    try:
        if not json.loads((KLASOR / "ayarlar.json").read_text(encoding="utf-8")).get("ghost_toplanti_sorular", False):
            return []
    except Exception:  # noqa: BLE001
        return []
    out, bas = [], time.mktime(date.today().timetuple())
    for js in KLASOR.glob("transkript_*.json"):
        try:
            if js.stat().st_mtime < bas:
                continue
            v = json.loads(js.read_text(encoding="utf-8"))["veri"]
        except Exception:  # noqa: BLE001
            continue
        if v.get("toplanti") and (v.get("kisaca") or {}).get("ozet"):
            out.append(str(v["kisaca"]["ozet"][0])[:600])
    return out


def _bugun_yaptiklari():
    try:
        return "\n".join(k for _, _, k in __import__("ortak").git_kayitlari("midnight", KLASOR))[:1500]
    except Exception:  # noqa: BLE001
        return ""


def sorular(gun=None, zorla=False, log=print):
    """Günün 3 sorusu (sonnet). Müşteri adı, gizli iş bilgisi sorulmaz; cevabı bir iki cümle ya da 20 saniyelik sesli not olabilecek somut sorular."""
    gun = gun or date.today().isoformat()
    yol = SORU / f"{gun}.json"
    if yol.exists() and not zorla:
        return _oku(yol, {})
    import paylasim
    pr = paylasim.profil()
    eski = [g for g in paylasim.gorusler() if not g.get("yerine")]
    eski = sorted(eski, key=lambda g: g.get("tarih", ""))[:5]
    mac = mac_gunu()
    gundem = ""
    try:
        k = json.loads((KLASOR / "kayitlar" / "kesif" / f"{gun}.json").read_text(encoding="utf-8"))
        gundem = "\n".join(f"- [{o.get('alan_ad')}] {o['baslik']}" for o in (k.get("oneriler") or [])[:8])
    except Exception:  # noqa: BLE001
        pass
    malzeme = (("BUGÜNKÜ TOPLANTILARI (gizli; müşteri adı ve iş sırrı SORMA, yalnızca genel dersi sor):\n" + "\n".join(f"- {t}" for t in _bugun_toplantilar()) + "\n")
               if _bugun_toplantilar() else "") \
        + (f"BUGÜN KENDİ ARAÇLARINDA YAPTIKLARI (Video Hub geliştirme kayıtları):\n{_bugun_yaptiklari()}\n" if _bugun_yaptiklari() else "") \
        + (f"BUGÜN MAÇ VAR: {mac.get('baslik')}\n" if mac.get("var") else "") \
        + (f"GÜNDEM:\n{gundem}\n" if gundem else "") \
        + ("ESKİ GÖRÜŞLERİ (biri hakkında 'hâlâ öyle mi düşünüyorsun?' sorulabilir):\n" + "\n".join(f"- [{g.get('tarih')}] {g.get('konu')}: {g.get('gorus')}" for g in eski) + "\n" if eski else "")
    c = paylasim._claude_json(
        f"KİŞİ: {pr.get('kimlik')}\nHEDEF: {pr.get('hedef_profil', '')}\nBu kişiye bugün 3 SORU sor; cevapları onun kendi gözleminden, işinden, maçtan, "
        "şehirden ya da eski bir görüşünden çıkan özgün gönderilere dönüşecek. Kurallar: somut ve tek konuya odaklı; bir iki cümleyle ya da 20 saniyelik "
        "sesli notla cevaplanabilir; 'ne düşünüyorsun' gibi genel soru yok; biri iş/araç, biri futbol ya da kültür, biri derinliği olan bir mesele olsun "
        "(sorular 'siz' diliyle: 'çevirdiniz', 'demiştiniz'; 'sen' dili yok) "
        "(malzemeye göre); müşteri adı ve gizli iş bilgisi geçmesin. Sen dili, samimi, kısa (≤160 karakter).\n"
        'JSON: {"sorular": [{"soru": "...", "neden": "bu soru neye dayanıyor (kısa)", "alan": "' + __import__("paylasim").alan_kodlari("|") + '"}]}\n\n'
        + malzeme, model_adi="sonnet")
    S = [{"soru": str(x.get("soru"))[:220], "neden": str(x.get("neden") or "")[:200], "alan": x.get("alan") or "", "cevap": "", "temel": ""}
         for x in c.get("sorular") or [] if isinstance(x, dict) and x.get("soru")][:3]
    kayit = {"tarih": gun, "zaman": time.time(), "sorular": S}
    _yaz(yol, kayit)
    log(f"Günün soruları: {len(S)}")
    return kayit


def soru_cevapla(gun, i, cevap, temel=""):
    yol = SORU / f"{gun}.json"
    k = _oku(yol, {})
    if not 0 <= i < len(k.get("sorular") or []):
        return None
    s = k["sorular"][i]; s["cevap"] = cevap; s["temel"] = temel; s["zaman"] = time.time()
    _yaz(yol, k)
    not_ekle(cevap, "soru_cevap", s["soru"], {"alan": s.get("alan", "")})
    return s


# ---------------------------------------------------------------- görüş adayları (kendi sözlerinden)
def _kendi_sozleri(gun=14, en_cok=12000):
    ben = (_ayar().get("benim_adim") or "").strip().lower()
    if not ben:
        return ""
    sinir = time.time() - gun * 86400
    parca = []
    for js in sorted(KLASOR.glob("transkript_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            if js.stat().st_mtime < sinir:
                continue
            d = json.loads(js.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        v = d["veri"]
        if not v.get("toplanti"):
            continue
        et = {str(k): str(a).lower() for k, a in (v.get("etiket") or {}).items()}
        benim = [s.get("metin", "") for s in d.get("segmentler") or [] if et.get(str(s.get("k")), "").split(" ")[:1] == ben.split(" ")[:1]]
        if benim:
            parca.append(" ".join(benim))
        if sum(len(p.split()) for p in parca) > en_cok:
            break
    return "\n---\n".join(parca)[: en_cok * 7]


def gorus_adaylari_tara(log=print):
    import paylasim
    sozler = _kendi_sozleri()
    notlar_ = "\n".join(f"- {x['metin']}" for x in _oku(DEFTER, [])[-40:])
    if not sozler and not notlar_:
        return []
    mevcut = "\n".join(f"- {g.get('konu')}: {g.get('gorus')}" for g in paylasim.gorusler() if not g.get("yerine"))
    import claude_yaz
    with claude_yaz.toplanti():
        if not claude_yaz.hazir():
            return []
        c = paylasim._claude_json(
            "Aşağıda bir kişinin toplantılarda KENDİ söyledikleri ve kendi notları var. Kamuya açık bir hesapta savunabileceği, GENELLEŞTİRİLMİŞ görüşleri "
            "çıkar: müşteri adı, kişi adı, rakam, iş sırrı OLMADAN (ör. 'Müşteriler yapay zekâyı maliyet aracı sanıyor, asıl değer karar hızında'). "
            "Zaten defterde olanları tekrar etme. Her biri: konu (2-5 kelime), gorus (tek cümle, onun sözüne sadık), alan, kanit (kendi sözünden kısa, "
            'adsız). En çok 8.\nJSON: {"adaylar": [{"konu": "...", "gorus": "...", "alan": "...", "kanit": "..."}]}\n\n'
            f"DEFTERDEKİ GÖRÜŞLER:\n{mevcut}\n\nTOPLANTILARDA KENDİ SÖYLEDİKLERİ:\n{sozler[:60000]}\n\nNOTLARI:\n{notlar_}", model_adi="sonnet", zaman_asimi=300)
    eski = _oku(ADAY, [])
    var = {a.get("gorus") for a in eski}
    yeni = [{**a, "zaman": time.time(), "durum": "bekliyor"} for a in c.get("adaylar") or [] if isinstance(a, dict) and a.get("gorus") and a["gorus"] not in var]
    _yaz(ADAY, (eski + yeni)[-200:])
    log(f"Görüş adayları: {len(yeni)} yeni")
    return yeni


def adaylar():
    return [{**a, "i": i} for i, a in enumerate(_oku(ADAY, [])) if a.get("durum") == "bekliyor"][::-1]


def aday_karar(i, kabul):
    import paylasim
    L = _oku(ADAY, [])
    if not 0 <= i < len(L):
        return
    L[i]["durum"] = "kabul" if kabul else "red"
    _yaz(ADAY, L)
    if kabul:
        paylasim._gorus_yaz([{"konu": L[i].get("konu"), "gorus": L[i].get("gorus"), "alan": L[i].get("alan"), "kanit": L[i].get("kanit"),
                              "tarih": time.strftime("%Y-%m-%d"), "kaynak": "kendi sözlerinden (onaylı)"}])


# ---------------------------------------------------------------- maç günü
def mac_gunu(gun=None):
    """Bugün takımın maçı var mı (keşif başlıklarından; ≥4 kaynak); varsa {var, baslik, rakip, saat}. Günlük önbellek."""
    gun = gun or date.today().isoformat()
    yol = KLASOR / "kayitlar" / "mac" / f"{gun}.json"
    if yol.exists():
        return _oku(yol, {"var": False})
    try:                                                   # 24 Ekim: önce fikstür (ESPN; oranlar.py), başlıklardan tahmin yalnız yedek
        import oranlar
        m = oranlar.mac(gun)
        if m.get("var"):
            sonuc = {k: m[k] for k in ("var", "rakip", "saat", "turnuva", "ev_sahibi", "bas", "espn_id") if k in m}
            sonuc["baslik"] = f"{_takim()} – {m['rakip']} · {m['saat']} · {m['turnuva']}"
            _yaz(yol, sonuc)
            return sonuc
    except Exception:  # noqa: BLE001
        pass
    try:
        k = json.loads((KLASOR / "kayitlar" / "kesif" / f"{gun}.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"var": False}
    import kesif
    try:
        maddeler = kesif.topla(saat=24)
    except Exception:  # noqa: BLE001
        maddeler = []
    # 22 Ekim hatası: 21 Ekim'deki maçın haberleri ertesi sabah da 24 saatlik pencerede kaldı, "bugün maç var" denildi. Artık: yalnız bugün yayımlanan
    # başlıklar, oynanmış maç (sonuç, gol, galibiyet...) sinyali taşıyanlar sayılmaz, modele tarih ve saatle sorulur, saat belli değilse kart çıkmaz.
    gece = datetime.combine(date.fromisoformat(gun), datetime.min.time()).timestamp()
    sonra_r = r"(kazandı|kaybetti|yenildi|yendi|berabere|mağlup|galibiyet|yenilgi|maç sonucu|golleri|maçın ardından|maç sonrası|puan durumu|sonrasında|açıklama yaptı|tepki)"
    mac = [m for m in maddeler if (m.get("zaman") or 0) >= gece and re.search(re.escape(_takim() or "\x00"), m["baslik"], re.I)
           and re.search(r"(maçı|maç|vs\.?|\s-\s|karşı)", m["baslik"], re.I)
           and re.search(r"(bugün|bu akşam|ne zaman|saat kaçta|canlı|ilk 11|muhtemel 11|şifresiz)", m["baslik"], re.I)
           and not re.search(sonra_r, m["baslik"], re.I)]
    if len(mac) < 4:
        sonuc = {"var": False}
    else:
        import paylasim
        satir = "\n".join(f"[{datetime.fromtimestamp(m.get('zaman') or 0).strftime('%d.%m %H:%M')}] {m['baslik']}" for m in mac[:20])
        c = paylasim._claude_json(f"Bugünün tarihi {gun}. Aşağıdaki haber başlıklarına (yayın zamanıyla) göre {_takim()}'ın BUGÜN, henüz oynanmamış ya da şu an "
                                  "oynanan bir maçı var mı? Başlıklar dünkü ya da geçmiş bir maçı anlatıyorsa var=false. Saat (TSİ) başlıklarda yoksa boş bırak. "
                                  'JSON: {"var": true, "rakip": "...", "saat": "21.45", "turnuva": "...", "neden": "kısa"}\n\n' + satir, model_adi="sonnet")
        sonuc = {"var": bool(c.get("var")), "rakip": str(c.get("rakip") or ""), "saat": str(c.get("saat") or ""), "turnuva": str(c.get("turnuva") or "")}
        if sonuc["var"] and not re.match(r"^\d{1,2}[.:]\d{2}$", sonuc["saat"]):
            sonuc["var"] = False; sonuc["neden"] = "saat belli değil"
        sonuc["baslik"] = f"{_takim()} – {sonuc['rakip']}" + (f" · {sonuc['saat']}" if sonuc["saat"] else "") + (f" · {sonuc['turnuva']}" if sonuc["turnuva"] else "")
    _yaz(yol, sonuc)
    return sonuc


def mac_not(tur, metin, gun=None):
    gun = gun or date.today().isoformat()
    L = _oku(MAC, [])
    m = mac_gunu(gun)
    x = {"tarih": gun, "tur": tur, "metin": metin.strip()[:2000], "zaman": time.time(), "mac": m.get("baslik", "")}
    L.append(x); _yaz(MAC, L[-300:])
    not_ekle(metin, "mac_oncesi" if tur == "once" else "mac_sonrasi", "", {"mac": m.get("baslik", "")})
    return x


def mac_notlari(gun=None):
    gun = gun or date.today().isoformat()
    return [x for x in _oku(MAC, []) if x["tarih"] == gun and x.get("tur") in ("once", "sonra")]


def mac_girdisi(tur, gun=None):
    """Maç notundan Ghost girdisi: maç öncesi tahmin ya da sonrası tepki (öncesi varsa 'maç öncesi şunu demiştim' bağı)."""
    N = mac_notlari(gun)
    once = [x for x in N if x["tur"] == "once"]; sonra = [x for x in N if x["tur"] == "sonra"]
    m = mac_gunu(gun)
    if tur == "once" and once:
        return f"MAÇ: {m.get('baslik', '')}\nMAÇ ÖNCESİ KENDİ TAHMİNİ/DÜŞÜNCESİ (gönderinin merkezi): {once[-1]['metin']}"
    if tur == "sonra" and sonra:
        return (f"MAÇ: {m.get('baslik', '')}\nDÜDÜK SONRASI KENDİ TEPKİSİ (gönderinin merkezi): {sonra[-1]['metin']}"
                + (f"\nMAÇ ÖNCESİ ŞUNU DEMİŞTİ (tuttuysa ya da tutmadıysa dürüstçe bağla): {once[-1]['metin']}" if once else ""))
    return ""


# ---------------------------------------------------------------- birleştirme önerileri (iki not → bir gönderi)
def birlestirme_onerileri(zorla=False, log=print):
    k = _oku(BIRLES, {})
    if k and not zorla and time.time() - k.get("zaman", 0) < 3 * 86400:
        return k
    N = _oku(DEFTER, [])[-60:]
    if len(N) < 4:
        return {"oneriler": [], "zaman": time.time()}
    import paylasim
    pr = paylasim.profil()
    G = [g for g in paylasim.gorusler() if not g.get("yerine")][:30]
    satir = "\n".join(f"[N{i}] ({x.get('tur')}) {x['metin'][:300]}" for i, x in enumerate(N)) + "\n" + "\n".join(f"[G{i}] {g.get('konu')}: {g.get('gorus')}" for i, g in enumerate(G))
    c = paylasim._claude_json(f"KİŞİ: {pr.get('kimlik')}\nALANLARI BAĞLAYAN BAKIŞ: {pr.get('baglanti', '')}\nAşağıda kişinin kendi notları (N) ve görüşleri (G) var. "
                              "Birbirinden UZAK iki parçanın (farklı alanlardan) birlikte özgün bir gönderi olacağı en iyi 3 eşleşmeyi bul (ör. bir reklam notu + bir futbol "
                              "anı). Zorlama bağlantı önerme; yoksa az öner. Her biri: a, b (N3/G5 gibi), fikir (gönderinin tek cümlelik tezi).\n"
                              'JSON: {"oneriler": [{"a": "N3", "b": "G5", "fikir": "..."}]}\n\n' + satir, model_adi="sonnet")
    def coz(ref):
        try:
            return ("Not: " + N[int(ref[1:])]["metin"]) if ref.startswith("N") else ("Görüşü: " + G[int(ref[1:])]["gorus"])
        except (ValueError, IndexError):
            return ""
    O = [{"a": coz(o.get("a", "")), "b": coz(o.get("b", "")), "fikir": str(o.get("fikir") or "")[:300]} for o in c.get("oneriler") or [] if isinstance(o, dict)]
    k = {"zaman": time.time(), "oneriler": [o for o in O if o["a"] and o["b"]][:3]}
    _yaz(BIRLES, k)
    log(f"Birleştirme önerileri: {len(k['oneriler'])}")
    return k



# ---------------------------------------------------------------- geri dönüş defteri (24 Ekim; komedi yazar odalarından "callback")
GERI = KLASOR / "profil" / "geri_donus.json"


def geri_donus_defteri(zorla=False, log=print):
    """Gerçek X gönderilerinden (uzantının okuduğu, tarihli) tekrar eden espriler/temalar ve tarihli tahminler/iddialar → `profil/geri_donus.json`.
    Uygun bir haber çıkınca Ghost 'bunu mart ayında demiştiniz' türü bir geri dönüş önerebilir; uzun süreli takipçiyi ödüllendirir, yapay zekâ taklit edemez.
    Ayda bir yenilenir. Tarih ve söz YALNIZCA gerçek gönderiden (uydurma yok)."""
    d = _oku(GERI, {})
    if not zorla and d.get("zaman", 0) > time.time() - 30 * 86400:
        return d
    import paylasim
    try:
        X = json.loads((KLASOR / "profil" / "x_istatistik.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        X = {}
    G = sorted([x for x in X.values() if x.get("metin") and x.get("tarih")], key=lambda x: x["tarih"])
    if len(G) < 15:
        return d
    c = paylasim._claude_json(
        "Aşağıda bir kişinin gerçek X gönderileri tarihleriyle var. İki şey çıkar:\n"
        "1) bitler: TEKRAR EDEN espriler, takıntılar, temalar, lakaplar (en az 2 gönderide geçen). Her biri: ad (kısa), ozet (tek cümle), ornekler (gönderi "
        "numaraları).\n"
        "2) iddialar: ileriye dönük TAHMİN ya da net iddia içeren gönderiler (ör. bir oyuncu, şirket, teknoloji hakkında 'olacak/olmayacak'). Her biri: no, "
        "iddia (tek cümle, onun sözüne sadık), konu (aranacak 2-4 kelime).\n"
        "Uydurma yok; yalnız listede olanlar.\n"
        'JSON: {"bitler": [{"ad": "...", "ozet": "...", "ornekler": [3, 17]}], "iddialar": [{"no": 5, "iddia": "...", "konu": "..."}]}\n\nGÖNDERİLER:\n'
        + "\n".join(f"[{i}] ({g['tarih'][:10]}) {g['metin'][:300]}" for i, g in enumerate(G[-200:])), model_adi="opus", zaman_asimi=400)
    G = G[-200:]
    bitler = []
    for b in c.get("bitler") or []:
        orn = [G[i] for i in (b.get("ornekler") or []) if isinstance(i, int) and 0 <= i < len(G)]
        if len(orn) >= 2:
            bitler.append({"ad": str(b.get("ad") or "")[:60], "ozet": str(b.get("ozet") or "")[:200],
                           "ornekler": [{"tarih": o["tarih"][:10], "metin": o["metin"][:240], "url": f"https://x.com/i/status/{o['id']}"} for o in orn[:3]]})
    iddialar = []
    for x in c.get("iddialar") or []:
        try:
            g = G[int(x.get("no"))]
        except (TypeError, ValueError, IndexError):
            continue
        iddialar.append({"tarih": g["tarih"][:10], "iddia": str(x.get("iddia") or "")[:240], "konu": str(x.get("konu") or "")[:60],
                         "metin": g["metin"][:280], "url": f"https://x.com/i/status/{g['id']}"})
    d = {"zaman": time.time(), "bitler": bitler[:15], "iddialar": iddialar[:25]}
    _yaz(GERI, d)
    log(f"Geri dönüş defteri: {len(d['bitler'])} tekrar eden bit, {len(d['iddialar'])} tarihli iddia")
    return d


# ---------------------------------------------------------------- maç tahmin karnesi (24 Ekim; tahmin isabeti Brier puanıyla)
def _takim():
    import oranlar
    return oranlar._takim()


def sonuc_adi(k):
    return {"G": f"{_takim()} kazanır", "B": "berabere", "M": f"{_takim()} kaybeder"}.get(k, k)


SONUC_AD = {"G": "kazanır", "B": "berabere", "M": "kaybeder"}


def mac_tahmin(secim, guven, gun=None):
    """Maç öncesi: G|B|M ve güven (%40-95). Olasılık: seçilene güven, diğer ikisine kalan eşit."""
    gun = gun or date.today().isoformat()
    secim = secim if secim in SONUC_AD else "G"
    g = max(0.34, min(0.95, float(guven or 60) / 100))
    p = {k: round((g if k == secim else (1 - g) / 2), 3) for k in SONUC_AD}
    L = [x for x in _oku(MAC, []) if not (x.get("tarih") == gun and x.get("tur") == "tahmin")]
    try:                                                   # bahis piyasasının o anki olasılığı (karşılaştırma için; oranlar.py)
        import oranlar
        piyasa = oranlar.piyasa_kaydet(gun).get("piyasa_once")
    except Exception:  # noqa: BLE001
        piyasa = None
    L.append({"tarih": gun, "tur": "tahmin", "secim": secim, "guven": round(g * 100), "olasilik": p, "zaman": time.time(), "mac": mac_gunu(gun).get("baslik", ""),
              **({"piyasa": {k: piyasa[k] for k in SONUC_AD}} if piyasa else {})})
    _yaz(MAC, L[-300:])
    return L[-1]


def mac_sonuc(sonuc, gun=None):
    gun = gun or date.today().isoformat()
    if sonuc not in SONUC_AD:
        raise ValueError("sonuç G, B ya da M")
    L = [x for x in _oku(MAC, []) if not (x.get("tarih") == gun and x.get("tur") == "sonuc")]
    L.append({"tarih": gun, "tur": "sonuc", "sonuc": sonuc, "zaman": time.time()})
    _yaz(MAC, L[-300:])
    return karne()


def karne():
    """Tahmin karnesi: maç sayısı, isabet (seçilen sonuç oldu mu), ortalama Brier puanı (0 kusursuz, 0,667 hep yazı-tura, 2 en kötü)."""
    L = _oku(MAC, [])
    T = {x["tarih"]: x for x in L if x.get("tur") == "tahmin"}
    S = {x["tarih"]: x["sonuc"] for x in L if x.get("tur") == "sonuc"}
    maclar = []
    for gun, t in sorted(T.items()):
        if gun not in S:
            continue
        o = S[gun]
        brier = round(sum((t["olasilik"][k] - (1 if k == o else 0)) ** 2 for k in SONUC_AD), 3)
        P = t.get("piyasa")
        pb = round(sum((P[k] - (1 if k == o else 0)) ** 2 for k in SONUC_AD), 3) if P else None
        maclar.append({"tarih": gun, "mac": t.get("mac", ""), "secim": t["secim"], "guven": t["guven"], "sonuc": o, "isabet": t["secim"] == o, "brier": brier,
                       **({"piyasa_brier": pb, "piyasa_secim": max(SONUC_AD, key=lambda k: P[k])} if P else {})})
    n = len(maclar)
    pm = [m for m in maclar if m.get("piyasa_brier") is not None]
    return {"n": n, "isabet": sum(m["isabet"] for m in maclar), "brier": round(sum(m["brier"] for m in maclar) / n, 3) if n else None,
            "yazi_tura": 0.667, "son": maclar[-10:], "bekleyen": [g for g in T if g not in S],
            # piyasa ile aynı maçlarda karşılaştırma (24 Ekim, oranlar.py)
            "piyasa_n": len(pm), "siz_piyasa_maclarinda": round(sum(m["brier"] for m in pm) / len(pm), 3) if pm else None,
            "piyasa": round(sum(m["piyasa_brier"] for m in pm) / len(pm), 3) if pm else None,
            "piyasa_isabet": sum(1 for m in pm if m["piyasa_secim"] == m["sonuc"])}


def mac_sonuc_oto(gun=None):
    """Tahmin yapılmış ve sonucu girilmemiş maçların sonucunu ESPN'den kendiliğinden işler (son 5 gün). Döner: işlenen gün listesi."""
    import oranlar
    L = _oku(MAC, [])
    T = {x["tarih"] for x in L if x.get("tur") == "tahmin"}
    S = {x["tarih"] for x in L if x.get("tur") == "sonuc"}
    out = []
    for g in sorted(T - S):
        if g < (date.today() - timedelta(days=5)).isoformat():
            continue
        try:
            m = oranlar.mac(g)
        except Exception:  # noqa: BLE001
            continue
        if m.get("sonuc"):
            L = _oku(MAC, [])
            L.append({"tarih": g, "tur": "sonuc", "sonuc": m["sonuc"], "skor": m.get("skor", ""), "zaman": time.time(), "kendiliginden": True})
            _yaz(MAC, L[-300:]); out.append(g)
    return out
