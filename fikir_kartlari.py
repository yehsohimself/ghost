"""fikir_kartlari.py - Görüş defteri → fikir kartları (2026-10-24; Ghost büyük işi 3).

Her görüş (onaylı ya da gönderisinden çıkarılmış; reddedilen hariç) bir KARTTIR: onu doğal olarak söyletecek haberin tarifini taşır (`bekledigi`)
ve başlıkta geçebilecek tetik sözcükleri (tr + en). Keşfin her turunda günün maddeleri kartlarla eşleşir (sözcük ön elemesi, sonra sonnet
"bu haber bu görüşü gerçekten çağırıyor mu" 1-5); ≥4 olanlar `kayitlar/fikir_eslesme/<gün>.json`. Sonuç: görüş türündeki gönderi artık tetiği
hazır doğar (karisim malzemesinde görüşün `tetik`'i), ayrıca Defter › Görüşler'de "Bugün tetiklendi: <haber> · Şimdi yaz" ve sabah konu toplantısında
bir konu olarak gelir. Kartlar `profil/fikir_kartlari.json` (görüş metninin özetiyle anahtarlı; yeni görüş gelince yalnız o işlenir).
"""
import hashlib
import json
import re
import time
from datetime import date
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
KART = KLASOR / "profil" / "fikir_kartlari.json"
ESLESME = KLASOR / "kayitlar" / "fikir_eslesme"
TR = str.maketrans("çğıöşüâîÇĞİÖŞÜ", "cgiosuaiCGIOSU")


def _oku(yol, vars_):
    try:
        return json.loads(yol.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return vars_


def _yaz(yol, x):
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps(x, ensure_ascii=False, indent=1), encoding="utf-8")


def _anahtar(g):
    return hashlib.sha1(str(g.get("gorus", "")).encode()).hexdigest()[:12]


def _norm(s):
    return " " + re.sub(r"[^a-z0-9 ]+", " ", str(s or "").replace("İ", "I").lower().translate(TR)) + " "


def kartlar(log=print):
    """Etkin görüşlerin kartları (eksik olanlar için tetik sözcükleri tek sonnet çağrısıyla üretilir)."""
    import paylasim
    G = [g for g in paylasim.gorusler() if not g.get("yerine") and paylasim.gorus_durumu(g) != "red" and g.get("gorus")]
    K = _oku(KART, {})
    eksik = [g for g in G if _anahtar(g) not in K]
    for i in range(0, len(eksik), 30):
        parca = eksik[i:i + 30]
        try:
            c = paylasim._claude_json(
                "Aşağıda bir kişinin savunduğu görüşler var. Her biri için: bekledigi = bu görüşü X'te DOĞAL olarak söyletecek haber/olay türü (tek cümle, "
                "somut: 'bir markanın yapay zekâyla ürettiği reklamın tepki çekmesi' gibi); tetikler = o haberin başlığında geçebilecek 6-10 sözcük ya da kısa "
                "söz öbeği, hem Türkçe hem İngilizce, küçük harf (marka/kurum adları, kavramlar; 'yapay zeka', 'ai', 'sponsorluk', 'sponsor' gibi).\n"
                'JSON: {"kartlar": [{"no": 0, "bekledigi": "...", "tetikler": ["...", "..."]}]}\n\n'
                + "\n".join(f"[{j}] ({g.get('konu', '')}) {g['gorus']}" for j, g in enumerate(parca)), model_adi="sonnet", zaman_asimi=240)
        except Exception as e:  # noqa: BLE001
            log(f"Fikir kartları üretilemedi: {e}"); break
        for x in c.get("kartlar") or []:
            try:
                g = parca[int(x.get("no"))]
            except (TypeError, ValueError, IndexError):
                continue
            T = [str(t).strip().lower() for t in (x.get("tetikler") or []) if 2 < len(str(t).strip()) < 40][:12]
            if T:
                K[_anahtar(g)] = {"gorus": g["gorus"], "konu": g.get("konu", ""), "alan": g.get("alan", ""), "bekledigi": str(x.get("bekledigi") or "")[:240],
                                  "tetikler": T, "zaman": time.time()}
    canli = {_anahtar(g) for g in G}
    K = {k: v for k, v in K.items() if k in canli}
    _yaz(KART, K)
    return K


def eslestir(maddeler, log=print, gun=None):
    """Günün maddeleri ↔ kartlar. Döner ve kaydeder: [{anahtar, gorus, konu, alan, madde{baslik, link, kaynak, zaman, ozet}, uyum, neden}]."""
    import paylasim
    gun = gun or date.today().isoformat()
    K = kartlar(log)
    if not K or not maddeler:
        return []
    M = [(m, _norm(m.get("baslik", "") + " " + (m.get("ozet") or "")[:300])) for m in maddeler if m.get("baslik")]
    aday = []
    for k, kart in K.items():
        T = [_norm(t).strip() for t in kart["tetikler"]]
        puanli = []
        for m, metin in M:
            p = sum((2 if " " in t else 1) for t in T if t and f" {t} " in metin)
            if p >= 2:
                puanli.append((p, m))
        puanli.sort(key=lambda t: -t[0])
        aday += [(k, m) for _, m in puanli[:2]]
    aday = aday[:24]
    if not aday:
        _yaz(ESLESME / f"{gun}.json", [])
        return []
    try:
        c = paylasim._claude_json(
            "Aşağıda bir kişinin görüşleri ile bugünkü haberlerden eşleşme adayları var. Her çift için: bu haber, bu görüşü X'te söylemek için DOĞAL bir tetik "
            "mi? (Okur haberi görünce kişinin bu görüşü söylemesini anlar mı; konu benzerliği yetmez, haber görüşün tam üstüne basmalı. Görüş belli bir maça, "
            "takıma, kişiye ya da olaya aitse haber de AYNI özneden olmalı: milli takım görüşü kulüp haberine, bir oyuncu görüşü başka oyuncuya bağlanmaz.) "
            "25 Ekim: haber görüşü İLGİLENDİREN YENİ BİR OLGU taşımalı; aynı kelime ya da konu ('orta saha', 'AI şirketi') yetmez. iliski: destekler (haberdeki "
            "olgu görüşü gerçekten doğruluyor) | sinar (görüşü zorluyor ya da değiştirebilir; kişi görüşünü yeniden düşünmeli) | ilgisiz. Olguyu görüşün tezine "
            "zorla uydurma: bir laboratuvara destek vermek tek başına önceki bir güvenlik çağrısıyla çelişmez. uyum 1-5; neden: haberdeki HANGİ olgu görüşün "
            "HANGİ kısmına değiyor, adıyla (tek cümle).\n"
            'JSON: {"ciftler": [{"no": 0, "iliski": "destekler", "uyum": 1, "neden": "..."}]}\n\n'
            + "\n".join(f"[{i}] GÖRÜŞ: {K[k]['gorus'][:300]}\n    HABER: {m['baslik']} ({m.get('kaynak', '')}) {(m.get('ozet') or '')[:200]}" for i, (k, m) in enumerate(aday)),
            model_adi="sonnet", zaman_asimi=240)
    except Exception as e:  # noqa: BLE001
        log(f"Fikir kartı eşleştirmesi yapılamadı: {e}"); return []
    out, gor, haber_gor, metin_gor = [], set(), {}, set()
    sirali = []
    for x in c.get("ciftler") or []:
        try:
            k, m = aday[int(x.get("no"))]; u = int(x.get("uyum") or 0)
        except (TypeError, ValueError, IndexError):
            continue
        sirali.append((u, k, m, x))
    sirali.sort(key=lambda t: -t[0])
    for u, k, m, x in sirali:
        oz = re.sub(r"\W+", "", K[k]["gorus"].lower())[:40]             # neredeyse aynı iki görüş tek kart sayılır
        if u < 4 or x.get("iliski") not in ("destekler", "sinar") or k in gor or m["baslik"] in haber_gor or oz in metin_gor:
            continue                                       # bir haber tek görüşe (en uyumlusuna) bağlanır
        gor.add(k); haber_gor[m["baslik"]] = k; metin_gor.add(oz)
        out.append({"anahtar": k, "gorus": K[k]["gorus"], "konu": K[k]["konu"], "alan": K[k].get("alan", ""), "uyum": u, "iliski": x.get("iliski"), "neden": str(x.get("neden") or "")[:240],
                    "madde": {a: m.get(a) for a in ("baslik", "link", "kaynak", "zaman", "ozet", "alan") if m.get(a)}})
    eski = [e for e in _oku(ESLESME / f"{gun}.json", []) if e.get("anahtar") not in gor]
    _yaz(ESLESME / f"{gun}.json", eski + out)
    if out:
        log(f"Fikir kartları: {len(out)} görüş bugün tetiklendi")
    return eski + out


def bugun(gun=None):
    return _oku(ESLESME / f"{gun or date.today().isoformat()}.json", [])


def yaz(anahtar, gun=None):
    """Tetiklenen görüşten taslak: görüş + haber → tepki dilinde (tetik.tepki_olarak_yaz). Döner: ghost temel."""
    _bas = __import__('time').time()
    import paylasim
    import tetik
    e = next((x for x in bugun(gun) if x["anahtar"] == anahtar), None)
    if not e:
        raise ValueError("Bu görüşün bugün tetiği yok")
    m = e["madde"]
    aday = {"tur": "haber", "baslik": m.get("baslik", ""), "link": m.get("link", ""), "kaynak": m.get("kaynak", ""), "neden": e["neden"],
            "tarih": time.strftime("%Y-%m-%d", time.localtime(m.get("zaman") or time.time())), "metin": m.get("ozet", "")}
    y = tetik.tepki_olarak_yaz({"metin": e["gorus"], "konu": e["konu"]}, aday)
    temel = paylasim.ghost_kaydi(e["gorus"], "fikir", e["konu"] or m.get("baslik", ""), y.get("paylas_link", ""), e["gorus"], deneyim="",
                                 ek={"fikir_karti": anahtar})
    t = {"platform": "x", "alan": e.get("alan", ""), "metin": y["metin"], "karakter": len(y["metin"]), "konu": e["konu"], "kancalar": y.get("kancalar") or [],
         "zincir": [], "uzunluk": "kisa", "ilk_yanit": "", "paylas_link": y.get("paylas_link", ""), "link_oner": True, "okur": {}, "kod_notlari": [],
         "itirazlar": [], "iddialar": [], "panel": [], "dayanak": "gorus", "kaynak": y.get("kaynak"), "tetik": y.get("tetik"), "alinti": y.get("alinti"),
         "katki": "Defterdeki görüşünüz: " + e["gorus"][:160]}
    yol = paylasim.GHOST / f"{temel[7:]}.json"
    d = json.loads(yol.read_text(encoding="utf-8"))
    d["veri"]["paylasim"] = {"taslaklar": [t], "zaman": time.time(), "ilk_zaman": time.time(), "model": __import__("paylasim")._yazan(_bas)}
    yol.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return temel
