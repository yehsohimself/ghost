"""hesaplar.py - Ghost'un izlediği X ve Instagram hesapları (2026-10-24; kullanıcı: "50 X, 30 Instagram hesabı belirlesek, mecra içi alıntılama
anlamında da çok iyi olur"; "dışarıdan da öner").

Liste `profil/hesaplar.json`: x (takip ettikleri, alana göre), x_oneri (takip etmedikleri, doğrulanmış 50 hesap), instagram (takip ettikleri).
X'te ve Instagram'da OTOMATİK TARAMA YOK (hesap riski): kullanıcı bu hesapları X'te bir listede, Instagram'da Favoriler'de toplar; listeyi/favorileri
açtığında Chrome uzantısı (3.3 `x.js`, `ig.js`) ekrandakileri YALNIZCA OKUR → `POST /api/x/akis` → `kayitlar/x_akis.json` (4 gün).
Kullanım: keşifte aday (`kesif_maddeleri`), alıntı önerisinde öncelik (bağlantılı gönderiler `x_kartli.json`'a da yazılır), karışımda 'akış'
malzemesi (`akis_malzemesi`), tetik aramasında aday.
"""
import json
import re
import time
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
DOSYA = KLASOR / "profil" / "hesaplar.json"
AKIS = KLASOR / "kayitlar" / "x_akis.json"
X_KARTLI = KLASOR / "kayitlar" / "x_kartli.json"
# hesap listesindeki alanlar → keşif alanları
ALAN = {"futbol": "futbol", "futbol_teknoloji": "futbol_teknoloji", "kreatif": "kreatif", "teknoloji_ai": "teknoloji_ai", "kendi_arac": "teknoloji_ai",
        "toplum_kultur": "toplum", "kultur": "populer_kultur", "turkiye": "toplum", "kultur_berlin": "populer_kultur", "teknoloji": "teknoloji_ai"}


def yukle():
    try:
        return json.loads(DOSYA.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def x_hesaplari():
    """{handle_kucuk: {hesap, alan, neden, kaynak: takip|oneri}}"""
    d, out = yukle(), {}
    for kaynak, anahtar in (("takip", "x"), ("oneri", "x_oneri")):
        for alan, L in (d.get(anahtar) or {}).items():
            for x in L:
                out[x["hesap"].lower()] = {"hesap": x["hesap"], "alan": ALAN.get(alan, "toplum"), "neden": x.get("neden", ""), "kaynak": kaynak}
    return out


def ig_hesaplari():
    d, out = yukle(), {}
    for alan, L in (d.get("instagram") or {}).items():
        for x in L:
            out[x["hesap"].lower()] = {"hesap": x["hesap"], "alan": ALAN.get(alan, "populer_kultur"), "neden": x.get("neden", "")}
    return out


def _oku(yol):
    try:
        L = json.loads(yol.read_text(encoding="utf-8"))
        return L if isinstance(L, list) else []
    except Exception:  # noqa: BLE001
        return []


def akis_kaydet(gonderiler, liste=False):
    """Uzantının X listesi sayfasından (ya da ana akıştan, yalnız izlenen hesaplar) okuduğu gönderiler. Bağlantı kartlı olanlar alıntı eşleştirmesi için
    `x_kartli.json`'a da eklenir. Döner: yeni kayıt sayısı."""
    H = x_hesaplari()
    L = _oku(AKIS)
    var = {x.get("id") for x in L}
    K = _oku(X_KARTLI)
    kvar = {x.get("id") for x in K}
    n = 0
    for g in (gonderiler or [])[:120]:
        gid = re.sub(r"\D", "", str(g.get("id") or ""))[:25]
        k = re.sub(r"[^\w]", "", str(g.get("kullanici") or ""))[:30]
        if not gid or gid in var or not (g.get("metin") or g.get("kart")):
            continue
        if not liste and k.lower() not in H:
            continue                                   # ana akışta yalnız izlenen hesaplar
        x = {"id": gid, "kullanici": k, "ad": str(g.get("ad") or "")[:80], "metin": str(g.get("metin") or "")[:1500],
             "kart": str(g.get("kart") or "")[:600], "kart_link": str(g.get("kart_link") or "")[:500], "tarih": str(g.get("tarih") or "")[:40],
             "liste": bool(liste), "izlenen": k.lower() in H, "zaman": time.time()}
        L.append(x); var.add(gid); n += 1
        if x["kart"] and gid not in kvar:
            K.append({k_: x[k_] for k_ in ("id", "kullanici", "ad", "metin", "kart", "tarih", "zaman")} | {"arama": "", "izlenen": x["izlenen"]}); kvar.add(gid)
    sinir = time.time() - 4 * 86400
    AKIS.write_text(json.dumps([x for x in L if x.get("zaman", 0) > sinir][-1500:], ensure_ascii=False), encoding="utf-8")
    X_KARTLI.write_text(json.dumps([x for x in K if x.get("zaman", 0) > time.time() - 3 * 86400][-600:], ensure_ascii=False), encoding="utf-8")
    return n


def akis(saat=36):
    """Son N saatte okunan, izlenen hesaplara ait gönderiler (yeniden eskiye)."""
    s = time.time() - saat * 3600
    return sorted([x for x in _oku(AKIS) if x.get("zaman", 0) > s and (x.get("izlenen") or x.get("liste"))], key=lambda x: -x.get("zaman", 0))   # listeye kendi eklediği hesaplar da


def son_liste_bakisi():
    L = [x.get("zaman", 0) for x in _oku(AKIS) if x.get("liste")]
    return max(L) if L else 0


def kesif_maddeleri(saat=36):
    """Keşif adayları: izlenen hesapların bağlantı verdiği haberler (bağlantı = asıl içerik; gönderi = alıntılanacak tetik) ve bağlantısız ama
    konuşulmaya değer gönderiler. Madde biçimi kesif._akis ile aynı + `x_gonderi`."""
    H = x_hesaplari()
    out = []
    for x in akis(saat)[:80]:
        h = H.get(x["kullanici"].lower()) or {}
        try:
            z = time.mktime(time.strptime(x["tarih"][:19], "%Y-%m-%dT%H:%M:%S")) if x.get("tarih") else x["zaman"]
        except ValueError:
            z = x["zaman"]
        url = f"https://x.com/{x['kullanici']}/status/{x['id']}"
        baslik = (x.get("kart") or x.get("metin") or "")[:140].replace("\n", " ")
        out.append({"alan": h.get("alan", "toplum"), "kaynak": f"X: @{x['kullanici']}", "baslik": baslik, "ozet": x.get("metin", "")[:400],
                    "link": x.get("kart_link") or url, "zaman": z, "resim": "", "x_hesap": x["kullanici"],
                    "x_gonderi": {"id": x["id"], "kullanici": x["kullanici"], "ad": x.get("ad", ""), "metin": x.get("metin", "")[:600], "url": url}})
    return out


def akis_malzemesi(saat=30, n=10):
    """Karışımın 'akış' türü için: izlenen hesapların bağlantısız gönderileri (alıntıyla tepki)."""
    return [x for x in akis(saat) if not x.get("kart")][:n]
