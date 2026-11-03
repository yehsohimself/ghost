"""ghost_arsiv.py - gündemi geçmiş önerileri arşive alır (2026-11-01; kullanıcı: "paylaşmadıkça öneriler birikiyor, yığın oluyor; günde bir güncellensin,
gündemi kaçmış konular arşive alınsın; bu kadar öneri verimsiz, boşa token harcıyor").

Arşiv bir RET değildir: öğrenmeye girmez, kalite sayacında kaldırılan sayılmaz, Taslaklar listesinden çıkar ama gün arşivinde ve "Arşiv" bölümünde
durur, tek dokunuşla geri gelir. Paylaşılan ya da kişinin kaldırdığı taslağa dokunulmaz.

Ömür (oluşmadan itibaren; kişi dokunduysa +5 gün):
  yanıt önerisi 1 gün · gündeme bağlı (haber, taraftar, ironi, akış, keşif, hikâye dışı bağlantılı) 2 gün · haftanın hikâyesi ve LinkedIn 7 gün ·
  zamansız (görüş, kendi işi, kişinin fikri/taslağı, gelen öneri, seçki, sohbet, dayanağı kendisi olan) 7 gün.
Haftanın planına bağlı taslak plan günü geçmeden arşive gitmez.
"""
import json
import time
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
GUN = 86400
ZAMANSIZ_TUR = {"gorus", "kendi"}
ZAMANSIZ_KAYNAK = {"fikir", "taslak", "dis_oneri", "secki", "sohbet", "yazi"}


def omur(t, veri):
    """Taslağın arşivden önce kalabileceği süre (saniye) ve gerekçe."""
    kt, kaynak = t.get("karisim_tur") or "", veri.get("kaynak_tur") or ""
    if kt == "yanit" or t.get("yanit_to"):
        o, neden = 1 * GUN, "yanıt önerisi; yanıtlanan gönderinin günü geçti"
    elif kt == "hikaye" or (t.get("platform") or "x") == "linkedin":
        o, neden = 7 * GUN, "haftalık öneri; haftası geçti"
    elif kt in ZAMANSIZ_TUR or kaynak in ZAMANSIZ_KAYNAK or t.get("dayanak") in ("kendi", "gorus"):
        o, neden = 7 * GUN, "bir hafta paylaşılmadı"
    else:
        o, neden = 2 * GUN, "gündemi geçti"
    if any(t.get(a) for a in ("duzenlendi", "yorumlar", "begendi", "kopyalandi")):
        o += 5 * GUN
    return o, neden


def _plan_temelleri():
    """Haftanın planına bağlı, plan günü bugün ya da sonra olan taslak kayıtları (arşive gitmez)."""
    try:
        import ghost_danisman
        bugun = time.strftime("%Y-%m-%d")
        return {x.get("hazirlandi") for x in ghost_danisman.plan()["maddeler"] if x.get("hazirlandi") and x["tarih"] >= bugun}
    except Exception:  # noqa: BLE001
        return set()


def arsivle(simdi=None, kuru=False, log=print):
    """Ghost kayıtlarındaki gündemi geçmiş taslakları arşivler. Döner {sayi, ornek}."""
    import kayit_json
    import kitaplik_onbellek
    simdi = simdi or time.time()
    korunan = _plan_temelleri()
    sayi, ornek = 0, []
    for k in kitaplik_onbellek.hepsi(ghost=True):
        v = k["veri"]
        p = v.get("paylasim") or {}
        if v.get("toplanti") or not p.get("taslaklar"):
            continue
        temel = ("ghost__" + k["temel"]) if Path(k["yol"]).parent.name == "ghost" else k["temel"]
        if temel in korunan:
            continue
        olusma = p.get("ilk_zaman") or p.get("zaman") or k["mtime"]
        hedef = []
        for i, t in enumerate(p["taslaklar"]):
            if t.get("paylasildi") or t.get("gizli") or t.get("arsiv"):
                continue
            o, neden = omur(t, v)
            if t.get("arsiv_geri") and simdi - t["arsiv_geri"] < 3 * GUN:      # kişi geri getirdi: üç gün dokunulmaz
                continue
            if simdi - olusma >= o:
                hedef.append((i, neden))
        if not hedef:
            continue
        sayi += len(hedef)
        ornek += [(p["taslaklar"][i].get("metin") or "")[:60] for i, _ in hedef[:2]]
        if kuru:
            continue

        def fn(d, hedef=hedef):
            L = (d["veri"].get("paylasim") or {}).get("taslaklar") or []
            for i, neden in hedef:
                if i < len(L) and not (L[i].get("paylasildi") or L[i].get("gizli")):
                    L[i].update(arsiv=True, arsiv_zaman=simdi, arsiv_neden=neden)
        try:
            kayit_json.guncelle(k["yol"], fn)
        except Exception as e:  # noqa: BLE001
            log(f"Arşivleme yazılamadı ({k['temel']}): {str(e)[:120]}")
    if sayi and not kuru:
        log(f"Ghost: {sayi} gündemi geçmiş öneri arşive alındı")
    return {"sayi": sayi, "ornek": ornek[:6]}


if __name__ == "__main__":
    import sys
    print(json.dumps(arsivle(kuru="--kuru" in sys.argv), ensure_ascii=False, indent=1))
