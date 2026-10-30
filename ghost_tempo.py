"""ghost_tempo.py - Ghost'un üretim temposu kullanıcının ilgisine göre (2026-10-27, Ghost geliştirme günü).

Ölçüm (20-27 Ekim): 152 öneri yazıldı, 1'i paylaşıldı; 81'i toplu retle, 36'sı hiç dokunulmadan gitti. Ghost bu hafta bütün Claude çağrılarının
%70'ini (1.622 çağrı, ~12 saat) kullandı. Kullanıcının günde 10-15 öneri kararı korunur; yalnız o bakmadığı günlerde Ghost boşa yazmaz:
- öğle turu, sabahın önerilerine hiç bakılmadıysa atlanır (aynı paketin üstüne yenisi yazılmaz);
- iki gündür bakılmadıysa günlük hedef 5, bakılıp hiçbir şeye dokunulmadıysa 8; dokunduğu an hedef yeniden profildeki değer olur;
- uzaktayken yan işler (yanıt taslakları, LinkedIn) beklenir.
Ziyaret: Ghost sayfası ya da telefondaki tek kart açılınca (GET /api/paylasimlar?z=1). Etkileşim: kullanıcının Ghost'ta yaptığı her POST.
Ayar `ghost_tempo` (varsayılan açık) kapatılırsa hep profildeki hedef.
"""
import json
import threading
import time
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
DOSYA = KLASOR / "kayitlar" / ".ghost_ziyaret.json"
_KILIT = threading.Lock()
GUN = 86400


def _oku():
    try:
        d = json.loads(DOSYA.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _yaz(d):
    try:
        DOSYA.parent.mkdir(parents=True, exist_ok=True)
        t = DOSYA.with_suffix(".tmp")
        t.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        t.replace(DOSYA)
    except Exception:  # noqa: BLE001
        pass


def _ekle(tur, ek=None):
    """Zaman damgasını listeye ekler (dakikada en çok bir; son 300)."""
    now = time.time()
    with _KILIT:
        d = _oku()
        L = [t for t in d.get(tur) or [] if isinstance(t, (int, float))]
        if not L or now - L[-1] > 60:
            L.append(now)
            d[tur] = L[-300:]
        if ek:
            d.setdefault("olay", []).append({"t": now, **ek})
            d["olay"] = d["olay"][-200:]
        _yaz(d)


def ziyaret():
    _ekle("ziyaret")


def etkilesim():
    _ekle("etkilesim")


def atlandi(ne, neden):
    """Atlanan üretimi kaydet (ölçüm ve arayüz notu için)."""
    _ekle("atlanan", {"ne": ne, "neden": neden})


def _son(tur):
    L = _oku().get(tur) or []
    return max(L) if L else 0


def acik():
    try:
        import ortak
        return bool(ortak.ayar().get("ghost_tempo", True))
    except Exception:  # noqa: BLE001
        return True


def durum(simdi=None):
    """{mod: aktif|sakin|uzakta, son_ziyaret, son_etkilesim}. Hiç kayıt yoksa (ilk kurulum) aktif sayılır."""
    simdi = simdi or time.time()
    z, e = _son("ziyaret"), _son("etkilesim")
    if not z and not e:
        mod = "aktif"
    elif e and simdi - e < 2 * GUN:
        mod = "aktif"
    elif z and simdi - z < 2 * GUN:
        mod = "sakin"
    else:
        mod = "uzakta"
    return {"mod": mod, "son_ziyaret": z, "son_etkilesim": e}


def gunluk_hedef(profil_hedefi):
    """Profildeki x_gunluk'u kullanıcının ilgisine göre ayarlar."""
    g = int(profil_hedefi or 12)
    if not acik():
        return g
    m = durum()["mod"]
    return g if m == "aktif" else min(g, 8) if m == "sakin" else min(g, 5)


def ogle_turu_gerekli(sabah_turu=None):
    """Öğle turu ancak kullanıcı sabah turundan sonra Ghost'a baktıysa (ya da sabah turu hiç olmadıysa) gerekir."""
    if not acik():
        return True
    if sabah_turu is None:
        g = time.localtime()
        sabah_turu = time.mktime((g.tm_year, g.tm_mon, g.tm_mday, 7, 30, 0, 0, 0, -1))
    return _son("ziyaret") >= sabah_turu or _son("etkilesim") >= sabah_turu


def yan_isler_uygun():
    """Yanıt taslakları ve LinkedIn gibi ek üretim: kullanıcı iki gündür hiç bakmadıysa bekler."""
    return not acik() or durum()["mod"] != "uzakta"


def ozet(gun=7):
    """Ölçüm ve arayüz için: son N günün ziyaret/etkileşim günleri ve atlanan üretimler."""
    d, sinir = _oku(), time.time() - gun * GUN
    gunler = lambda L: len({time.strftime("%Y-%m-%d", time.localtime(t)) for t in L if t >= sinir})   # noqa: E731
    atl = [o for o in d.get("olay") or [] if o.get("t", 0) >= sinir and o.get("ne")]
    return {**durum(), "ziyaret_gunu": gunler(d.get("ziyaret") or []), "etkilesim_gunu": gunler(d.get("etkilesim") or []),
            "atlanan": len(atl), "atlanan_son": atl[-5:]}
