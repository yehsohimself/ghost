"""konu_toplantisi.py - Sabah konu toplantısı + önce sor, sonra yaz (2026-10-24; Ghost büyük işleri 1 ve 2).

Eskiden keşif turu açıları seçip hemen yazıyordu; kişi yalnızca bitmiş taslakları görüyordu ve konuya kendi bakışını katamıyordu (dayanaksız taslak).
Şimdi zamanlanmış turda (07.30 / 14.00) açı elemesinden sonra yazım BEKLER:
  1) Toplantı: günün konuları (açı elemesinden geçen haberler + bugün tetiklenen görüşler (fikir_kartlari)) tek ekranda: konu, Ghost'un açısı, kaynak,
     kreatif konularda reklam arşivinden emsal. Kişi her birine "Yaz" ya da "Geç" der (Geç = konu reddi, öğrenilir).
  2) Önce sor: her konunun altında Ghost'un TEK sorusu ("Bu kampanyada sizi rahatsız eden ne?"). Cevap verilirse gönderinin çekirdeği o olur
     (`kendi_yorum`, dayanak 'kendi'); sesli de cevaplanabilir.
  Kişi "Yazmaya başla" der ya da süre dolar (sabah 60, öğle 45 dk) → `bitir`: geçilenler çıkar, cevaplar eklenir, karışım + LinkedIn yazımı çalışır.
  Hiç dokunulmazsa eskisi gibi her şey yazılır (kişi yoksa günü kaçırmasın).
Kayıt: `kayitlar/ghost_toplanti/<gün>_<dilim>.json` (+ `_maddeler.json`, karışım malzemesi için günün maddeleri).
"""
import json
import time
from datetime import date
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
KLASOR_T = KLASOR / "kayitlar" / "ghost_toplanti"
SURE = {"sabah": 60, "ogle": 45, "elle": 20}


def _oku(yol, v):
    try:
        return json.loads(yol.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return v


def _yaz(yol, x):
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps(x, ensure_ascii=False, indent=1), encoding="utf-8")


def hazirla(maddeler, haberler, birlesik, dilim="sabah", log=print):
    """Toplantıyı kurar (sorular + arşiv emsalleri), yazımı bekletir. Döner: toplantı kaydı."""
    import paylasim
    gun = date.today().isoformat()
    tid = f"{gun}_{dilim}"
    konular = []
    for i, o in enumerate(haberler):
        konular.append({"id": f"h{i}", "tur": "haber", "baslik": o.get("baslik", ""), "link": o.get("link", ""), "kaynak": o.get("kaynak", ""),
                        "alan": o.get("alan", ""), "alan_ad": o.get("alan_ad", ""), "aci": o.get("aci", ""), "ayrinti": o.get("ayrinti", ""),
                        "kesif": o.get("kesif_bulten") or o.get("kesif_yayin") or o.get("kesif_kantan") or (("@" + o["x_hesap"]) if o.get("x_hesap") else ""), "oid": o.get("id", "")})
    try:
        import fikir_kartlari
        for e in fikir_kartlari.bugun(gun):
            konular.append({"id": "o" + e["anahtar"], "tur": "gorus", "baslik": e["madde"].get("baslik", ""), "link": e["madde"].get("link", ""),
                            "kaynak": e["madde"].get("kaynak", ""), "alan": e.get("alan", ""), "aci": e["gorus"], "neden": e["neden"], "anahtar": e["anahtar"]})
    except Exception as e:  # noqa: BLE001
        log(f"Fikir kartları toplantıya alınamadı: {e}")
    if not konular:
        return None
    try:                                                   # kreatif konulara reklam arşivinden emsal (reklam_arsivi.py)
        import reklam_arsivi
        kr = [k for k in konular if k["alan"] in ("kreatif", "reklamcilik", "populer_kultur") or "reklam" in (k.get("alan_ad") or "").lower()]
        if kr:
            B = reklam_arsivi.benzerleri_sec([{"id": k["id"], "metin": f"{k['baslik']}. {k.get('ayrinti', '')} {k['aci']}"} for k in kr], log)
            for k in kr:
                k["arsiv"] = [{"kunye": reklam_arsivi.kisa(b["is"])[:220], "neden": b["neden"], "link": b["is"].get("link", ""), "id": b["is"]["id"]}
                              for b in B.get(k["id"], [])]
    except Exception as e:  # noqa: BLE001
        log(f"Arşiv emsali bulunamadı: {e}")
    pr = paylasim.profil()
    try:
        c = paylasim._claude_json(
            f"KİŞİ: {pr.get('kimlik', '')}\n{paylasim._persona_blogu(pr, kisa=True)}\n{__import__('ghost_rehber').oneri_blogu()}\n"
            "Aşağıdaki konuların her biri için bu kişiye TEK bir soru sor; cevabı gönderinin çekirdeği olacak. Soru onun KENDİ bakışını, deneyimini ya da "
            "hükmünü çıkarsın (bilgi sorma, yönlendirme yapma, 'sizce önemli mi' gibi boş soru yok). Bir cümlede cevaplanabilsin; en çok 140 karakter; 'siz' "
            "diliyle. Ör: 'Bu kampanyada markanın yerinde olsanız hangi kararı geri alırdınız?', 'Bu transferde kulübün asıl hesabı ne sizce?'\n"
            'JSON: {"sorular": [{"id": "h0", "soru": "..."}]}\n\n'
            + "\n".join(f"[{k['id']}] {k['baslik']} | Ghost'un açısı: {k['aci'][:200]}" for k in konular), model_adi="sonnet", zaman_asimi=180)
        S = {str(x.get("id")): str(x.get("soru") or "")[:200] for x in c.get("sorular") or []}
    except Exception as e:  # noqa: BLE001
        S = {}; log(f"Toplantı soruları yazılamadı: {e}")
    for k in konular:
        k["soru"] = S.get(k["id"], "")
        k["karar"] = None; k["cevap"] = ""
    simdi = time.time()
    t = {"id": tid, "gun": gun, "dilim": dilim, "durum": "bekliyor", "zaman": simdi, "son": simdi + SURE.get(dilim, 45) * 60, "konular": konular}
    _yaz(KLASOR_T / f"{tid}.json", t)
    _yaz(KLASOR_T / f"{tid}_ek.json", {"maddeler": maddeler, "haberler": haberler, "birlesik": birlesik})
    log(f"Konu toplantısı hazır: {len(konular)} konu; {SURE.get(dilim, 45)} dk içinde karar verilmezse hepsi yazılır")
    return t


def kullaniliyor(son_n=6, en_az=4):
    """Son toplantılara hiç dokunulmadıysa (Yaz/Geç/cevap yok) False (2026-10-27: 5 toplantıda 19 konu, sıfır karar; toplantı yalnız yazımı
    bir saat geciktiriyordu). Kişi bir karar verdiği an yeniden açılır; elle tetiklenen tur her zaman toplantılıdır."""
    bugun = date.today().isoformat()
    L = sorted([p for p in KLASOR_T.glob("*.json") if not p.stem.endswith("_ek") and not p.stem.startswith(bugun)], key=lambda p: p.stem)[-son_n:]
    if len(L) < en_az:
        return True
    for p in L:
        t = _oku(p, None) or {}
        if any(k.get("karar") or k.get("cevap") for k in t.get("konular") or []):
            return True
    return False


def son(gun=None):
    """Bugünün en son toplantısı (ek dosyası olmadan)."""
    gun = gun or date.today().isoformat()
    L = sorted(KLASOR_T.glob(f"{gun}_*.json"), key=lambda p: p.stat().st_mtime)
    L = [p for p in L if not p.stem.endswith("_ek")]
    return _oku(L[-1], None) if L else None


def karar(tid, kid, karar_=None, cevap=None):
    yol = KLASOR_T / f"{tid}.json"
    t = _oku(yol, None)
    if not t:
        raise ValueError("Toplantı bulunamadı")
    if t["durum"] != "bekliyor":
        raise ValueError("Bu toplantının yazımı başladı")
    k = next((k for k in t["konular"] if k["id"] == kid), None)
    if not k:
        raise ValueError("Konu bulunamadı")
    if karar_ in ("yaz", "gec", None):
        k["karar"] = karar_
    if cevap is not None:
        k["cevap"] = str(cevap).strip()[:1500]
        if k["cevap"] and k["karar"] != "gec":
            k["karar"] = "yaz"
    t["son"] = max(t["son"], time.time() + 10 * 60)        # karar verilirken süre dolup yazım başlamasın
    _yaz(yol, t)
    return t


def bekleyen():
    """Süresi dolmuş, hâlâ bekleyen toplantılar (site döngüsü bitirir)."""
    out = []
    for p in KLASOR_T.glob("*.json"):
        if p.stem.endswith("_ek"):
            continue
        t = _oku(p, None)
        if t and t.get("durum") == "bekliyor" and time.time() >= t.get("son", 0):
            out.append(t["id"])
    return out


def bitir(tid, log=print):
    """Kararları uygular ve yazar (karışım + budama + LinkedIn)."""
    import kesif
    import paylasim
    yol = KLASOR_T / f"{tid}.json"
    t = _oku(yol, None)
    if not t or t["durum"] != "bekliyor":
        return
    t["durum"] = "yaziliyor"; t["basla"] = time.time(); _yaz(yol, t)
    ek = _oku(KLASOR_T / f"{tid}_ek.json", {})
    K = {k["id"]: k for k in t["konular"]}
    haberler = []
    for i, o in enumerate(ek.get("haberler") or []):
        k = K.get(f"h{i}") or {}
        if k.get("karar") == "gec":
            paylasim.red_kaydet({"konu": o.get("baslik", ""), "metin": o.get("aci", "")}, "konu uymuyor")
            continue
        if k.get("cevap"):
            o["kendi_yorum"] = k["cevap"]
        if k.get("arsiv"):
            o["arsiv_emsal"] = k["arsiv"]
        if k.get("karar") == "yaz":
            o["secildi"] = True
        haberler.append(o)
    haberler.sort(key=lambda o: 0 if o.get("kendi_yorum") else (1 if o.get("secildi") else 2))
    gorus_yaz = [k for k in t["konular"] if k["tur"] == "gorus" and k.get("karar") != "gec"]
    gecilen_gorus = {k.get("anahtar") for k in t["konular"] if k["tur"] == "gorus" and k.get("karar") == "gec"}
    if gecilen_gorus:                                      # geçilen görüş eşleşmesi bugün malzemeye girmesin
        try:
            import fikir_kartlari
            g = t["gun"]
            fikir_kartlari._yaz(fikir_kartlari.ESLESME / f"{g}.json", [e for e in fikir_kartlari.bugun(g) if e["anahtar"] not in gecilen_gorus])
        except Exception:  # noqa: BLE001
            pass
    log(f"Konu toplantısı bitti: {sum(1 for k in t['konular'] if k.get('karar') == 'yaz')} seçildi, "
        f"{sum(1 for k in t['konular'] if k.get('karar') == 'gec')} geçildi, {sum(1 for k in t['konular'] if k.get('cevap'))} cevap")
    try:
        kesif.yazim_turu(ek.get("maddeler") or [], haberler, ek.get("birlesik") or [], log=log,
                         gorus_cevaplari={k["aci"]: k["cevap"] for k in gorus_yaz if k.get("cevap")})
    finally:
        t = _oku(yol, t); t["durum"] = "bitti"; t["bitis"] = time.time(); _yaz(yol, t)
        (KLASOR_T / f"{tid}_ek.json").unlink(missing_ok=True)
