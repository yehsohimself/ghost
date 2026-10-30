"""performans.py - Ghost'un performans döngüsü (2026-10-21). Chrome uzantısı (x.js) kullanıcı X'te kendi profiline/gönderisine baktığında
ekrandaki sayıları YALNIZCA OKUYUP gönderir; burada saklanır (`profil/x_istatistik.json`), Ghost taslaklarıyla eşlenir ve haftada bir Claude
"ne işliyor" derslerini çıkarır (`profil/x.json` `performans_dersleri`). Dersler konu seçimine ve yazıma girer.
"""
import json
import re
import statistics
import time
from datetime import datetime
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
DOSYA = KLASOR / "profil" / "x_istatistik.json"
GUN_ADI = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


def _oku():
    try:
        return json.loads(DOSYA.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def kaydet(gonderiler):
    d = _oku(); simdi = time.time(); n = 0
    for g in gonderiler or []:
        gid = re.sub(r"\D", "", str(g.get("id") or ""))[:25]
        if not gid:
            continue
        x = d.get(gid) or {"id": gid, "ilk": simdi, "gecmis": []}
        for k in ("tarih", "metin"):
            if g.get(k):
                x[k] = str(g[k])[:4000]
        for k in ("yanit", "repost", "begeni", "yerimi", "goruntulenme"):
            x[k] = max(int(g.get(k) or 0), int(x.get(k) or 0))      # sayılar yalnızca artar (eksik okumada düşmesin)
        x["medya"] = bool(g.get("medya") or x.get("medya"))
        x["guncelleme"] = simdi
        if x.get("goruntulenme") and (not x["gecmis"] or x["gecmis"][-1][1] != x["goruntulenme"]):
            x["gecmis"] = (x["gecmis"] + [[simdi, x["goruntulenme"]]])[-12:]
        d[gid] = x; n += 1
    DOSYA.parent.mkdir(parents=True, exist_ok=True)
    DOSYA.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return n


def _norm(t):
    return re.sub(r"[^a-zçğıöşü0-9]+", " ", str(t or "").replace("İ", "i").replace("I", "ı").lower()).strip()


def _ghost_paylasilanlar():
    """Ghost'tan çıkıp paylaşılmış taslaklar: [(normalize ilk 80 karakter, alan, temel)]."""
    out = []
    import kitaplik_onbellek
    for kayit in kitaplik_onbellek.hepsi(ghost=True):        # 2026-10-25: mtime önbellekli
        js = kayit["yol"]
        p = (kayit["veri"] or {}).get("paylasim") or {}
        for t in p.get("taslaklar") or []:
            if t.get("paylasildi"):
                out.append((_norm(t.get("metin"))[:80], t.get("alan") or "", js.stem))
    return out


def yayin_dogrula(gun=21):
    """'Paylaştım' denen taslak X'te GERÇEKTEN çıktı mı (24 Ekim, kullanıcının editoryal yöntemi: seçildi / yayımlandığı doğrulandı ayrı durumlar)?
    Uzantının yalnızca okuyarak getirdiği kendi gönderileriyle metin benzerliği ≥0,72 ve gönderi tarihi paylaşım işaretinden en çok 1 gün önce →
    taslağa `yayin` {id, url, tarih}. Döner: yeni doğrulanan sayısı."""
    import difflib
    posts = []
    for x in _oku().values():
        try:
            z = datetime.fromisoformat(str(x.get("tarih")).replace("Z", "+00:00")).timestamp()
        except ValueError:
            continue
        if x.get("metin") and z > time.time() - (gun + 2) * 86400:
            posts.append((z, _norm(x["metin"]), x["id"]))
    if not posts:
        return 0
    n = 0
    sinir = time.time() - gun * 86400
    for js in list(KLASOR.glob("transkript_*.json")) + list((KLASOR / "ghost").glob("*.json")):
        if js.stat().st_mtime < sinir:
            continue
        try:
            d = json.loads(js.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        L = ((d.get("veri") or {}).get("paylasim") or {}).get("taslaklar") or []
        degisti = False
        for t in L:
            if not t.get("paylasildi") or t.get("yayin"):
                continue
            m, pz = _norm(t.get("metin")), t.get("paylasim_zaman") or 0
            en, ei = 0.0, None
            for z, pm, pid in posts:
                if pz and z < pz - 86400:
                    continue
                r = difflib.SequenceMatcher(None, m, pm).ratio()
                if r > en:
                    en, ei = r, (z, pid)
            if ei and en >= 0.72:
                t["yayin"] = {"id": ei[1], "url": f"https://x.com/i/status/{ei[1]}", "tarih": time.strftime("%Y-%m-%d %H:%M", time.localtime(ei[0])),
                              "benzerlik": round(en, 2)}
                degisti = True; n += 1
        if degisti:
            js.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return n


def oto_tani(gun=10, esik=0.6, yaz=True):
    """'Ne oldu?'ya basılmadan X'te paylaşılan Ghost taslaklarını kendiliğinden tanır (24 Ekim; 63 öneriden yalnızca 1'i işaretlenmişti, öğrenme
    yürümüyordu). Uzantının okuduğu kendi gönderileri ile işaretlenmemiş taslaklar karşılaştırılır: gönderi taslaktan SONRA atılmış ve benzerlik
    ≥esik ise taslak 'paylaşıldı' sayılır; kullanıcı metni değiştirdiyse paylaşılan metin taslağa yazılır, eskisi `ilk_metin` olur (öğrenme bunu
    düzeltme çifti olarak kullanır). Bir gönderi tek taslağa eşlenir. Döner: [{yol, i, once, sonra, taslak}] (öğrenme kilitsiz, sonra yapılır)."""
    import difflib
    posts, kullanilan = [], set()
    for x in _oku().values():
        try:
            z = datetime.fromisoformat(str(x.get("tarih")).replace("Z", "+00:00")).timestamp()
        except ValueError:
            continue
        if x.get("metin") and len(_norm(x["metin"])) >= 25 and z > time.time() - (gun + 2) * 86400:
            posts.append((z, _norm(x["metin"]), x["id"], x["metin"]))
    if not posts:
        return []
    dosyalar = [js for js in list(KLASOR.glob("transkript_*.json")) + list((KLASOR / "ghost").glob("*.json")) if js.stat().st_mtime > time.time() - gun * 86400]
    veriler = {}
    for js in dosyalar:
        try:
            veriler[js] = json.loads(js.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        for t in ((veriler[js].get("veri") or {}).get("paylasim") or {}).get("taslaklar") or []:
            if t.get("yayin"):
                kullanilan.add(t["yayin"].get("id"))
    adaylar = []                                         # (benzerlik, yol, i, gönderi)
    for js, d in veriler.items():
        p = (d.get("veri") or {}).get("paylasim") or {}
        bas = p.get("ilk_zaman") or p.get("zaman") or js.stat().st_mtime - 86400
        for i, t in enumerate(p.get("taslaklar") or []):
            if t.get("paylasildi") or t.get("yayin") or (t.get("platform") or "x") != "x":
                continue
            m = _norm(t.get("metin"))
            if len(m) < 25:
                continue
            for z, pm, pid, ham in posts:
                if pid in kullanilan or z < bas - 3600:
                    continue
                r = difflib.SequenceMatcher(None, m, pm).ratio()
                if r >= esik:
                    adaylar.append((r, js, i, (z, pid, ham)))
    out, dolu = [], set()
    for r, js, i, (z, pid, ham) in sorted(adaylar, key=lambda a: -a[0]):
        if pid in kullanilan or (js, i) in dolu:
            continue
        kullanilan.add(pid); dolu.add((js, i))
        t = veriler[js]["veri"]["paylasim"]["taslaklar"][i]
        once = t.get("metin") or ""
        t.update({"paylasildi": True, "paylasim_zaman": z, "oto_tanindi": True,
                  "yayin": {"id": pid, "url": f"https://x.com/i/status/{pid}", "tarih": time.strftime("%Y-%m-%d %H:%M", time.localtime(z)), "benzerlik": round(r, 2)}})
        if r < 0.97 and ham.strip() != once.strip():
            t.setdefault("ilk_metin", once); t["duzenlendi"] = True; t["metin"] = ham.strip()[:4000]; t["karakter"] = len(t["metin"])
        out.append({"yol": js, "i": i, "once": t.get("ogrenilen_metin") or t.get("ilk_metin") or once, "sonra": t["metin"], "taslak": dict(t)})
    for js in ({o["yol"] for o in out} if yaz else ()):
        js.write_text(json.dumps(veriler[js], ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def liste(gun=30):
    sinir = time.time() - gun * 86400
    G = _ghost_paylasilanlar()
    out = []
    for x in _oku().values():
        try:
            z = datetime.fromisoformat(str(x.get("tarih")).replace("Z", "+00:00")).timestamp()
        except Exception:  # noqa: BLE001
            continue
        if z < sinir or not x.get("goruntulenme"):
            continue
        n = _norm(x.get("metin"))
        eş = next((g for g in G if len(g[0]) >= 20 and len(n) >= 20 and (n.startswith(g[0][:50]) or g[0].startswith(n[:50]))), None)   # emoji-only gönderi her şeyle eşleşmesin
        etk = (x.get("begeni", 0) + x.get("yanit", 0) + x.get("repost", 0) + x.get("yerimi", 0)) / max(1, x["goruntulenme"])
        lt = datetime.fromtimestamp(z)
        out.append({**{k: x.get(k) for k in ("id", "metin", "yanit", "repost", "begeni", "yerimi", "goruntulenme", "medya")}, "zaman": z,
                    "uzunluk": len(x.get("metin") or ""), "etkilesim": round(etk * 100, 2), "ghost": bool(eş), "alan": eş[1] if eş else "",
                    "gun": GUN_ADI[lt.weekday()], "saat": lt.hour})
    return sorted(out, key=lambda x: -x["zaman"])


def ozet(gun=30):
    L = liste(gun)
    if not L:
        return {"adet": 0}
    med = lambda xs: int(statistics.median(xs)) if xs else 0   # noqa: E731
    gor = [x["goruntulenme"] for x in L]
    kisa = [x["goruntulenme"] for x in L if x["uzunluk"] <= 280]; uzun = [x["goruntulenme"] for x in L if x["uzunluk"] > 280]
    gh = [x["goruntulenme"] for x in L if x["ghost"]]
    en = sorted(L, key=lambda x: -x["goruntulenme"])[:3]
    pr = {}
    try:
        pr = json.loads((KLASOR / "profil" / "x.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass
    return {"adet": len(L), "medyan": med(gor), "toplam": sum(gor), "kisa_medyan": med(kisa), "uzun_medyan": med(uzun), "kisa_adet": len(kisa),
            "uzun_adet": len(uzun), "ghost_adet": len(gh), "ghost_medyan": med(gh), "en_iyi": en,
            "son_guncelleme": max(x.get("guncelleme", 0) for x in _oku().values()) if _oku() else 0,
            "dersler": pr.get("performans_dersleri") or [], "dersler_zaman": pr.get("performans_zaman") or 0}


def dersler(zorla=False, log=print):
    """≥10 ölçülmüş gönderi varsa ve son dersten 6 gün geçtiyse (ya da zorla): Claude 'ne işliyor' çıkarır → x.json performans_dersleri."""
    import paylasim
    pr = paylasim.profil()
    L = liste(90)
    if len(L) < 10 or (not zorla and time.time() - (pr.get("performans_zaman") or 0) < 6 * 86400):
        return None
    satir = "\n".join(f"- [{x['goruntulenme']} görüntülenme · {x['begeni']} beğeni · {x['yanit']} yanıt · {x['yerimi']} yer imi · {x['uzunluk']} karakter · "
                      f"{x['gun']} {x['saat']:02d}.00{' · görselli' if x['medya'] else ''}] {str(x['metin'])[:300]}" for x in L[:60])
    c = paylasim._claude_json(
        f"Aşağıda {pr.get('kimlik') or 'bir kişinin'} X'teki son gönderileri ve gerçek sayıları var. Hangi gönderilerin neden daha çok okunduğunu "
        "ve etkileşim aldığını çıkar. Somut ol: konu/alan, açılış türü (yeniden çerçeveleme, kişisel üretim, gözlem, tek cümle), uzunluk, görsel, "
        "gün/saat. Sayıların az olduğu yerde kesin konuşma ('az örnek' de). Tek seferlik viral bir gönderiyi kural yapma.\n"
        "25 Ekim: dersler GÖZLEM olarak yazılır, yazım REÇETESİ olarak değil: 'ilk cümlede köprü kur', 'sonuna bir bu yüzden cümlesi ekle', 'X ile başla' gibi "
        "açılış/kapanış formülü ve kelime önerisi YOK (iki örnekten kural olmaz; kişinin yazı ilkesi 'düşünce bittiğinde dur'). Neyin okunduğunu konu ve "
        "düşünce düzeyinde söyle (ör. 'kendi gözleminden iki alanı bağlayan gönderiler daha çok kaydedildi').\n"
        "dersler: en çok 6 madde, her biri tek cümle, konu ve düşünce düzeyinde gözlem (ör. 'Kendi yaptığın araçtan çıkan gözlemler medyanın 3 katı "
        "okunuyor').\ndeneyin: en çok 2 madde (henüz denenmemiş ama verinin işaret ettiği şey).\n"
        'JSON: {"dersler": ["..."], "deneyin": ["..."]}\n\nGÖNDERİLER:\n' + satir, model_adi="sonnet")
    d = [str(x).strip() for x in c.get("dersler") or [] if str(x).strip()][:6]
    if d:
        paylasim.profil_kaydet(performans_dersleri=d, performans_deneyin=[str(x).strip() for x in c.get("deneyin") or [] if str(x).strip()][:2],
                               performans_zaman=time.time())
        log(f"Performans dersleri güncellendi ({len(L)} gönderi)")
    return d


if __name__ == "__main__":
    print(json.dumps(ozet(), ensure_ascii=False, indent=1)[:3000])
