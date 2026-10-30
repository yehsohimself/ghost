"""yerimleri.py - X yer imleri: kişinin kendi sistemlerini geliştirmek için Claude'a bıraktığı okuma kutusu (2026-10-24/25).

İlk sürüm yer imlerini "değerli bulduklarım" (ilgi işareti) sayıyordu; kullanıcı düzeltti: "Ben orayı genellikle kendi sistemlerimi geliştirmek için,
senin okuyacağın yer olarak kullanıyorum. Tamamı öyle değil ama farkını anlayabilirsin. Örneğin değerli bir GitHub listesi ya da bir okuma."

Kaynak yalnızca Chrome uzantısının OKUDUKLARI: x.com/i/bookmarks açılınca ekrandaki gönderiler (uzantı `x.js` `yerimleri()`; gönderi metni, bağlantı
kartı, metindeki bağlantılar) → POST /api/x/yerimleri → `kayitlar/x_yerimleri.json` (≤400). Otomatik tarama yok, X'e hiçbir şey yazılmaz.

1) `siniflandir`: yeni gelenler (sonnet, toplu): tur = sistem (araç, GitHub deposu/listesi, yöntem, istem, iş akışı: sistemlerine alınabilecek) |
   okuma (makale, deneme, araştırma: okunup sindirilecek) | ilgi (yalnız beğendiği/eğlendiği içerik) | diger; urun (Studio | Meet | Ghost | Content |
   Couple | genel).
2) `incele`: sistem ve okuma olanların bağlantısı açılır (t.co çözülür; GitHub'da README, diğerlerinde sayfa metni; bağlantı yoksa gönderinin kendisi),
   opus "Video Hub için ne alınabilir" → ozet, fikirler [{urun, ne, neden}], uygunluk 1-5. Uygunluk ≥4 fikirler Ghost → Sesiniz → Gelişim'e öneri olarak
   düşer (kaynak "yer imleriniz"); "Yapılsın" denenler sonraki geliştirme oturumunun iş listesi. Geliştirme oturumunda: `python yerimleri.py liste`.
3) `ilgi_blogu`: yalnız 'ilgi' olanlar keşfin konu seçimine girer (zayıf işaret).
"""
import json
import re
import threading
import time
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
DOSYA = KLASOR / "kayitlar" / "x_yerimleri.json"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15"}
URUNLER = ("Studio", "Meet", "Ghost", "Content", "Couple", "genel")
SISTEMLER = ("Video Hub, kişinin kendi kullandığı yerel araçlar: Studio (video linkinden transkript, özet, altyazı, dublaj, klip, indirme), Meet (toplantı "
             "kaydı, konuşmacı ayırma, Kısaca, kararlar, Asana, danışman notu, Chrome uzantısı), Ghost (X/LinkedIn gönderi taslakları: keşif, kişinin sesi, kalite "
             "kapısı, düzeltmelerden öğrenme, haftalık öz değerlendirme), Content (viral video linki + istek → kişi değiştirme, araya girme, yapay zekâ video "
             "üretimi), Couple (müşteri işleri masası: brief, fikir, sunum metni, creator araştırması). Hepsi Claude (abonelik) ve yerel modellerle çalışıyor; "
             "kişi programcı değil, Claude Code ile geliştiriyor.")


def oku():
    try:
        return json.loads(DOSYA.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []


KILIT = threading.Lock()


def _yaz(L):
    DOSYA.parent.mkdir(parents=True, exist_ok=True)
    DOSYA.write_text(json.dumps(L[-3000:], ensure_ascii=False, indent=1), encoding="utf-8")


def _guncelle(gid, alanlar):
    """Tek kaydı dosyanın GÜNCEL halinde günceller (25 Ekim hatası: uzun Claude çağrısı sürerken bayat listeyi yazmak, bu arada uzantının getirdiği
    yeni yer imlerini siliyordu)."""
    with KILIT:
        L = oku()
        for x in L:
            if x["id"] == gid:
                x.update(alanlar)
        _yaz(L)


def kaydet(gonderiler):
    with KILIT:
        L = oku()
        var = {x["id"] for x in L}
        n = 0
        for g in gonderiler or []:
            gid = "".join(ch for ch in str(g.get("id") or "") if ch.isdigit())[:25]
            if not gid or gid in var:
                continue
            L.append({"id": gid, "kullanici": str(g.get("kullanici") or "")[:40], "ad": str(g.get("ad") or "")[:80], "metin": str(g.get("metin") or "")[:2000],
                      "kart": str(g.get("kart") or "")[:400], "kart_link": str(g.get("kart_link") or "")[:400],
                      "linkler": [str(u)[:400] for u in g.get("linkler") or []][:6], "tarih": str(g.get("tarih") or "")[:40], "zaman": time.time()})
            var.add(gid); n += 1
        if n:
            _yaz(L)
        return n


def tam_metin(gid, metin):
    """Gönderi kendi sayfasında açılınca (uzantı `acilan`) gelen TAM metin: akıştaki/yer imleri listesindeki "Show more" kısaltmasının yerine geçer.
    Önceki inceleme kısa metinle yapıldıysa silinir, yeniden okunur. Döner: güncellendi mi."""
    metin = str(metin or "").strip()
    with KILIT:
        L = oku()
        for x in L:
            if x["id"] == gid and len(metin) > len(x.get("metin") or "") + 15:
                x["metin"] = metin[:6000]; x["metin_tam"] = True
                if x.get("inceleme"):
                    x.pop("inceleme")
                _yaz(L)
                return True
    return False


def _kisaltilmis(x):
    m = str(x.get("metin") or "")
    return not x.get("metin_tam") and (len(m) >= 265 or m.rstrip().endswith("…"))


def siniflandir(log=print):
    """Türü belli olmayanları sınıflar (sonnet, 40'lık gruplar). Döner: sınıflanan sayısı."""
    import paylasim
    L = oku()
    bos = [x for x in L if not x.get("tur")]
    n = 0
    for i in range(0, len(bos), 40):
        G = bos[i:i + 40]
        c = paylasim._claude_json(
            "Bir kişi X'teki yer imlerini çoğunlukla KENDİ SİSTEMLERİNİ GELİŞTİRMEK İÇİN Claude'un okuyacağı bir kutu olarak kullanıyor (değerli bir GitHub listesi, "
            "bir araç, bir yöntem, bir okuma); bir kısmı ise yalnızca beğendiği içerik. Her yer imini sınıfla:\n"
            "tur: sistem (araç, GitHub deposu ya da listesi, istem, iş akışı, teknik: sistemlerine alınabilecek bir şey) | okuma (makale, deneme, araştırma, "
            "uzun düşünce: okunup sindirilecek) | ilgi (eğlendiği, beğendiği, futbol/kültür içeriği; geliştirmeyle ilgisi yok) | diger.\n"
            f"urun: hangi sisteme yarar ({' | '.join(URUNLER)}); ilgi/diger için genel. neden: tek kısa cümle.\nSİSTEMLERİ: {SISTEMLER}\n"
            'JSON: {"yerimleri": [{"no": 0, "tur": "sistem", "urun": "Ghost", "neden": "..."}]}\n\n'
            + "\n".join(f"[{j}] @{x['kullanici']}: {x['metin'][:500]}" + (f" [kart: {x['kart'][:200]}]" if x["kart"] else "") for j, x in enumerate(G)),
            model_adi="sonnet", zaman_asimi=240)
        for y in c.get("yerimleri") or []:
            try:
                x = G[int(y.get("no"))]
            except (TypeError, ValueError, IndexError):
                continue
            _guncelle(x["id"], {"tur": y.get("tur") if y.get("tur") in ("sistem", "okuma", "ilgi", "diger") else "diger",
                                "urun": y.get("urun") if y.get("urun") in URUNLER else "genel", "neden": str(y.get("neden") or "")[:200]})
            n += 1
    if n:
        log(f"Yer imleri: {n} yer imi sınıflandı")
    return n


def _coz(u):
    """t.co ve benzeri kısaltılmış bağlantıyı asıl adrese çevirir."""
    import requests
    try:
        r = requests.get(u, headers=UA, timeout=15, allow_redirects=True)
        m = re.search(r'URL=([^"\'>]+)', r.text[:2000]) if "t.co/" in r.url else None
        return m.group(1) if m else r.url
    except Exception:  # noqa: BLE001
        return u


def _icerik(x):
    """Yer iminin okunacak içeriği: (adres, başlık, metin). GitHub'da README; bağlantı yoksa gönderinin kendisi."""
    import requests
    adaylar = [u for u in (x.get("linkler") or []) + [x.get("kart_link")] if u and u.startswith("http") and "x.com/" not in u and "twitter.com/" not in u]
    for u in adaylar[:3]:
        u = _coz(u)
        if re.search(r"(x|twitter)\.com/", u):
            continue
        g = re.match(r"https?://github\.com/([^/\s]+)/([^/\s#?]+)", u)
        try:
            if g:
                o, r = g.group(1), g.group(2).removesuffix(".git")
                j = requests.get(f"https://api.github.com/repos/{o}/{r}/readme", headers={"Accept": "application/vnd.github.raw"}, timeout=20)
                if j.status_code == 200 and len(j.text) > 200:
                    return u, f"{o}/{r}", j.text[:16000]
            import paylasim
            try:
                b, m = paylasim.sayfa_metni(u)
            except ValueError:                             # <p> kullanmayan eski sayfalar (ör. paulgraham.com): kaba metin
                import html as html_modulu
                h = requests.get(u, headers=UA, timeout=20).text
                b = (re.search(r"<title[^>]*>(.*?)</title>", h, re.I | re.S) or [None, ""])[1]
                m = re.sub(r"\s+", " ", html_modulu.unescape(re.sub(r"(?is)<(script|style)\b.*?</\1>|<[^>]+>", " ", h))).strip()
                if len(m) < 1500:
                    continue
            return u, str(b).strip()[:200], m[:16000]
        except Exception:  # noqa: BLE001
            continue
    # dış bağlantı yoksa içerik gönderinin kendisidir (okunamadı sayılmaz); okunamayan bir bağlantı varsa adres boş döner
    if adaylar:
        return "", f"@{x['kullanici']}", x["metin"] + ("\n" + x["kart"] if x.get("kart") else "")
    return f"https://x.com/{x['kullanici']}/status/{x['id']}", f"@{x['kullanici']}", x["metin"] + ("\n" + x["kart"] if x.get("kart") else "")


TAZE_GUN = 120


def _taze(x, gun=TAZE_GUN):
    """Gönderi tarihi son `gun` gün içinde mi (eski yer imleri kendiliğinden okunmaz; araç dünyası hızlı eskiyor ve Claude kullanımı boşa gitmesin)."""
    try:
        from datetime import datetime
        return datetime.fromisoformat(str(x.get("tarih")).replace("Z", "+00:00")).timestamp() > time.time() - gun * 86400
    except ValueError:
        return True


def incele(en_cok=8, log=print, hepsi=False):
    """Sistem ve okuma yer imlerini okur (yeniden eskiye; kendiliğinden yalnız son 120 gün, `hepsi=True` ile eskiler de), Video Hub için çıkarımlar
    yazar; iyileri Gelişim önerisi olur. Döner: incelenen sayısı."""
    import ghost_gelisim
    import paylasim
    L = sorted(oku(), key=lambda x: x.get("tarih") or "", reverse=True)
    bekleyen = [x for x in L if x.get("tur") in ("sistem", "okuma") and not x.get("inceleme") and (hepsi or _taze(x))][:en_cok]
    for x in bekleyen:
        adres, baslik, metin = _icerik(x)
        okundu = bool(adres)
        adres = adres or f"https://x.com/{x['kullanici']}/status/{x['id']}"
        c = paylasim._claude_json(
            f"Bir kişi bunu X'te yer imlerine, kendi sistemlerini geliştirmek için Claude okusun diye bıraktı. SİSTEMLERİ: {SISTEMLER}\n"
            f"Yer imi türü: {x.get('tur')} ({x.get('neden', '')}). Gönderi (@{x['kullanici']}): {x['metin'][:800]}\n\n"
            "İçeriği oku ve çıkar: ozet (2-3 cümle, sade Türkçe, teknik terimi açıkla), fikirler (en çok 3: bu sistemlerden HANGİSİNE, NE alınabilir, NEDEN; "
            "somut ve bu kişinin işine yarar olsun; 'genel olarak faydalı' deme; zaten var olan bir şeyi önerme), uygunluk (1-5: sistemlere gerçekten katkı), "
            "okuma_notu (okuma türündeyse kişinin aklında kalması gereken tek fikir; değilse boş).\n"
            + ("" if okundu else "DİKKAT: bağlantının içeriği OKUNAMADI, elinde yalnızca gönderi metni var. Kendi bilginden içerik UYDURMA; ozet'te 'içerik "
               "okunamadı' de, yalnızca gönderinin kendisinden çıkanı yaz, uygunluk en çok 2.\n")
            + ("NOT: gönderi metni kısaltılmış olabilir (devamı görünmüyor); yalnızca görüneni kullan, devamını tahmin etme.\n" if _kisaltilmis(x) else "") +
            'JSON: {"ozet": "...", "fikirler": [{"urun": "Ghost", "ne": "...", "neden": "..."}], "uygunluk": 3, "okuma_notu": ""}\n\n'
            f"İÇERİK ({adres}, {baslik}):\n{metin}", model_adi="opus", zaman_asimi=400)
        try:
            u = int(c.get("uygunluk") or 0)
        except (TypeError, ValueError):
            u = 0
        F = [{"urun": f.get("urun") if f.get("urun") in URUNLER else "genel", "ne": str(f.get("ne") or "")[:400], "neden": str(f.get("neden") or "")[:300]}
             for f in c.get("fikirler") or [] if isinstance(f, dict) and f.get("ne")][:3]
        if not okundu:
            u = min(u, 2)
        x["inceleme"] = inc = {"zaman": time.time(), "okundu": okundu, "adres": adres, "baslik": str(baslik)[:200], "ozet": str(c.get("ozet") or "")[:800], "fikirler": F,
                         "uygunluk": u, "okuma_notu": str(c.get("okuma_notu") or "")[:300]}
        if u >= 4 and F:                                   # yalnızca güçlü olanlar Gelişim önerisi olur; diğerleri "okuduklarım"da fikirleriyle durur
            d = ghost_gelisim.oku()
            for f in F:
                if not any(o.get("baslik") == f["ne"][:160] for o in d["oneriler"]):
                    d["oneriler"].append({"id": f"y{int(time.time())}{len(d['oneriler'])}", "baslik": f["ne"][:160], "neden": f["neden"][:400],
                                          "ne_yapilir": f"{f['urun']} · {c.get('ozet', '')[:300]}", "kaynak": f"yer imleriniz · @{x['kullanici']}",
                                          "link": adres, "urun": f["urun"], "durum": "bekliyor", "zaman": time.time()})
            d["oneriler"] = d["oneriler"][-60:]
            ghost_gelisim.yaz(d)
        _guncelle(x["id"], {"inceleme": inc})
        log(f"Yer imi incelendi (uygunluk {u}): {str(baslik)[:70]}")
    return len(bekleyen)


ISLEM = KLASOR / "kayitlar" / ".yerimi_isleniyor"


def isle(log=print, en_cok=8):
    """Yeni gelenleri sınıflar ve inceler (arka planda; uzantı yeni yer imi getirince). Site ile elle çalıştırılan aynı anda çalışmasın diye kilit dosyası."""
    import os
    try:
        pid, t = ISLEM.read_text().split()
        if time.time() - float(t) < 1800:
            os.kill(int(pid), 0)
            log("Yer imleri: başka bir okuma sürüyor"); return 0
    except Exception:  # noqa: BLE001
        pass
    ISLEM.write_text(f"{os.getpid()} {time.time()}")
    try:
        siniflandir(log)
        return incele(en_cok=en_cok, log=log)
    finally:
        ISLEM.unlink(missing_ok=True)


def ilgi_blogu(n=12):
    """Yalnızca 'ilgi' olanlar (beğendiği içerik) keşfin konu seçimine zayıf işaret olarak. Boşsa ''."""
    L = sorted([x for x in oku() if x.get("tur") == "ilgi"], key=lambda x: x.get("tarih") or "", reverse=True)[:n]
    if not L:
        return ""
    return ("KİŞİNİN X'TE KAYDETTİĞİ, BEĞENDİĞİ İÇERİKLER (zayıf ilgi işareti; benzer konulara biraz ağırlık ver, kopyalama ya da anma):\n"
            + "\n".join(f"- @{x['kullanici']}: {(x['metin'] or x['kart'])[:200]}" for x in L) + "\n")


def ozet():
    L = oku()
    say = {t: sum(1 for x in L if x.get("tur") == t) for t in ("sistem", "okuma", "ilgi", "diger")}
    return {"adet": len(L), "son": max((x.get("zaman", 0) for x in L), default=0), "tur": say,
            "incelenen": sum(1 for x in L if x.get("inceleme")),
            "bekleyen": sum(1 for x in L if x.get("tur") in ("sistem", "okuma") and not x.get("inceleme") and _taze(x)),
            "eski_bekleyen": sum(1 for x in L if x.get("tur") in ("sistem", "okuma") and not x.get("inceleme") and not _taze(x)),
            "son_incelemeler": [{"kullanici": x["kullanici"], "tur": x["tur"], "baslik": x["inceleme"]["baslik"], "adres": x["inceleme"]["adres"],
                                 "ozet": x["inceleme"]["ozet"], "uygunluk": x["inceleme"]["uygunluk"], "okuma_notu": x["inceleme"].get("okuma_notu", ""),
                                 "fikir": (x["inceleme"]["fikirler"] or [{}])[0].get("ne", ""), "okundu": x["inceleme"].get("okundu", True)}
                                for x in sorted([y for y in L if y.get("inceleme")], key=lambda y: (-y["inceleme"]["uygunluk"], -y["inceleme"]["zaman"]))[:8]]}


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "isle":
        print(isle(en_cok=int(sys.argv[2]) if len(sys.argv) > 2 else 8))
    elif len(sys.argv) > 1 and sys.argv[1] == "eskiler":      # eski (120 günden önceki) sistem/okuma yer imlerini de oku: python yerimleri.py eskiler 20
        print(incele(en_cok=int(sys.argv[2]) if len(sys.argv) > 2 else 20, hepsi=True))
    elif len(sys.argv) > 1 and sys.argv[1] == "liste":         # geliştirme oturumu için: incelenmiş yer imleri ve fikirleri
        for x in sorted([y for y in oku() if y.get("inceleme")], key=lambda y: -y["inceleme"]["uygunluk"]):
            i = x["inceleme"]
            print(f"[{i['uygunluk']}] {x['tur']} · {x.get('urun')} · {i['baslik']} ({i['adres']})\n    {i['ozet']}")
            for f in i["fikirler"]:
                print(f"    → {f['urun']}: {f['ne']} ({f['neden']})")
    else:
        print(json.dumps(ozet(), ensure_ascii=False, indent=1))
