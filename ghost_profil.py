"""ghost_profil.py - Ghost profilinin nasıl güncellendiğini görünür kılar (2026-11-02). Bölüm bölüm: nereden öğreniyor, kaç kayıt var, son ne zaman değişti,
son başarılı kayıt ve son hata. Yalnız sayı ve tarih döner; gönderi ya da görüş metni dönmez. Dışarıdan gelen öneriler ayrı satırdadır ve öğrenmeye girmez."""
import json
import time
from pathlib import Path

import ghost_oneri
import paylasim

# kod, ad, nereden, profildeki alanlar
ALANLAR = (("kimlik", "Kimlik ve tarz", "Kurulumda ve Ayarlar’da sizin yazdıklarınız", ("kimlik", "tarz", "persona", "kacin")),
           ("ses", "Ses örnekleri", "Ayarlar’a yazdığınız örnekler ve “paylaştım” dedikleriniz", ("ornekler", "paylasilan")),
           ("begeni", "Beğendikleriniz", "Bir taslağa “Beğendim” demeniz", ("begenilen",)),
           ("ret", "Kaldırdıklarınız", "Kaldırırken söylediğiniz neden", ("reddedilen", "bilgi_hatalari")),
           ("duzeltme", "Düzeltmeleriniz", "Elle düzelttiğiniz metinler", ("duzeltmeler", "duzeltme_dersleri", "silinen_ifadeler")),
           ("performans", "Okur tepkisi", "X’te kendi gönderilerinizin sayıları", ("performans_dersleri",)),
           ("ayar", "Haftalık ayarlar", "Ghost’un haftalık değerlendirmesi; Gelişim’den geri alınabilir", ("alanlar", "hedef")))


def _zaman(t):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t)) if t else None


def _dosya(yol):
    """Ayrı dosyadaki liste: (adet, değişme zamanı)."""
    yol = Path(yol)
    try:
        v = json.loads(yol.read_text(encoding="utf-8"))
        return len(v if isinstance(v, list) else v.get("tercihler") or v.get("gorusler") or v), _zaman(yol.stat().st_mtime)
    except (OSError, ValueError, AttributeError):
        return 0, None


def durum():
    pr = paylasim.profil()
    K = paylasim.profil_kayit_durumu()
    son = {}
    for g in K.get("gecmis") or []:
        for a in g.get("alanlar") or []:
            son[a] = g.get("zaman")
    S = []
    for kod, ad, nereden, alanlar in ALANLAR:
        adet = 0
        for a in alanlar:
            v = pr.get(a)
            adet += len(v) if isinstance(v, (list, dict)) else int(bool(v))
        z = [son[a] for a in alanlar if a in son]
        S.append({"kod": kod, "ad": ad, "nereden": nereden, "adet": adet, "son": max(z) if z else None, "ogrenir": True})
    h, hz = _dosya(paylasim.HAVUZ)
    S.insert(2, {"kod": "havuz", "ad": "Onaylı örnekler", "nereden": "“Evet, paylaştım” dediğiniz gönderiler", "adet": h, "son": hz, "ogrenir": True})
    t, tz = _dosya(paylasim.TERCIH)
    S.append({"kod": "tercih", "ad": "Yazım tercihleri", "nereden": "Düzeltmeleriniz ve açıkça yazdığınız yorumlar", "adet": t, "son": tz, "ogrenir": True})
    g, gz = _dosya(paylasim.GORUS)
    S.append({"kod": "gorus", "ad": "Görüş defteri", "nereden": "Yayımladığınız gönderiler ve onayladığınız görüşler", "adet": g, "son": gz, "ogrenir": True})
    L = ghost_oneri.liste(3650)
    S.append({"kod": "dis_oneri", "ad": "Gelen öneriler", "nereden": "ChatGPT ya da Dot; ayrı saklanır, sizin onayınız sayılmaz", "adet": len(L),
              "son": _zaman(max((d.get("alinma") or 0) for d in L)) if L else None, "ogrenir": False})
    gecmis = [{"zaman": g.get("zaman"), "bolumler": sorted({ad for _k, ad, _n, A in ALANLAR for a in g.get("alanlar") or [] if a in A})} for g in (K.get("gecmis") or [])[-6:]]
    return {"satirlar": S, "son_basarili": K.get("son_basarili"), "son_hata": K.get("son_hata"), "hata_zamani": K.get("hata_zamani"),
            "son_degisiklikler": [g for g in reversed(gecmis) if g["bolumler"]][:5]}
