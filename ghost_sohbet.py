"""ghost_sohbet.py - Ghost'la konuşma (2026-10-31; kullanıcı: "çok kısıtlı hissediyorum; bir soruya soruyla da karşılık verebilmeliyim, chatbox olmalı;
deneyim insanlaşmalı").

Ghost burada bir arayüz değil, karşınızdaki kişi: iletişim danışmanınız ve yazı ortağınız. Bağlamı bilir (sesiniz, stratejiniz, puan kartı, bu haftanın
planı, bugünün taslakları, fikir ve görüş defteri, yaklaşan gündem, size sorduğu sorular). Soruya soruyla, itirazla, "emin değilim"le cevap verilebilir;
Ghost tartışır, gerekçe verir, gerekirse kendisi tek soru sorar. Yanıt yazıldıkça akar. Sonunda isteğe bağlı olarak hızlı cevap önerileri ve ÖNERİLEN
eylemler gelir (taslak kartı, var olan taslağı düzeltme, Ghost'a tam yazım, görüş/fikir defterine ekleme, yazım tercihi öğrenme, haftanın planını
değiştirme); hiçbir eylem kişi "Uygula" demeden yapılmaz. Geçmiş profil/ghost_sohbet.json (son 120 mesaj).
"""
import datetime as dt
import json
import re
import time
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
DOSYA = KLASOR / "profil" / "ghost_sohbet.json"
AYRAC = "@@@"
EYLEM_TURLERI = ("taslak", "duzenle", "yaz", "gorus", "fikir", "ogren", "plan")


# ---------------------------------------------------------------- geçmiş
def _oku():
    try:
        return json.loads(DOSYA.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"mesajlar": []}


def _yaz(d):
    DOSYA.parent.mkdir(parents=True, exist_ok=True)
    tmp = DOSYA.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(DOSYA)


def mesajlar(n=60):
    return (_oku().get("mesajlar") or [])[-n:]


def ekle(rol, metin, **ek):
    d = _oku()
    L = d.setdefault("mesajlar", [])
    m = {"id": f"m{int(time.time() * 1000)}{len(L) % 10}", "rol": rol, "metin": str(metin or "")[:8000], "zaman": time.time(),
         **{k: v for k, v in ek.items() if v not in (None, "", [], {})}}
    L.append(m)
    d["mesajlar"] = L[-120:]
    _yaz(d)
    return m


def temizle():
    d = _oku()
    if d.get("mesajlar"):
        d.setdefault("arsiv", []).append({"zaman": time.time(), "mesajlar": d["mesajlar"][-60:]})
        d["arsiv"] = d["arsiv"][-10:]
    d["mesajlar"] = []
    _yaz(d)


def eylem_isaretle(mid, i, sonuc):
    d = _oku()
    for m in d.get("mesajlar") or []:
        if m.get("id") == mid and 0 <= i < len(m.get("eylemler") or []):
            m["eylemler"][i]["uygulandi"] = sonuc or True
            _yaz(d)
            return m["eylemler"][i]
    return None


def eylem_bul(mid, i):
    for m in _oku().get("mesajlar") or []:
        if m.get("id") == mid:
            E = m.get("eylemler") or []
            return E[i] if 0 <= i < len(E) else None
    return None


# ---------------------------------------------------------------- bağlam
def _taslaklar(gun=2):
    """Son günlerin görünür, paylaşılmamış taslakları (en yeni önce): {anahtar, metin, alan, platform, okur, neden}."""
    import kitaplik_onbellek
    sinir = time.time() - gun * 86400
    out = []
    for k in kitaplik_onbellek.hepsi(ghost=True):
        v = k["veri"]
        p = v.get("paylasim") or {}
        if v.get("toplanti") or not p.get("taslaklar") or (p.get("ilk_zaman") or p.get("zaman") or k["mtime"]) < sinir:
            continue
        temel = ("ghost__" + k["temel"]) if Path(k["yol"]).parent.name == "ghost" else k["temel"]
        for i, t in enumerate(p["taslaklar"]):
            if t.get("gizli") or t.get("paylasildi"):
                continue
            out.append({"anahtar": f"{temel}#{i}", "metin": str(t.get("metin") or "")[:600], "alan": t.get("alan") or "", "platform": t.get("platform") or "x",
                        "okur": t.get("okur") or {}, "neden": str(t.get("katki") or t.get("neden") or "")[:200], "zaman": p.get("ilk_zaman") or p.get("zaman") or 0})
    return sorted(out, key=lambda x: -x["zaman"])


def taslak(anahtar):
    """'temel#i' → (yol, i, taslak) ya da None."""
    try:
        temel, i = str(anahtar).rsplit("#", 1); i = int(i)
    except ValueError:
        return None
    if not re.fullmatch(r"[\w.\-]+", temel):
        return None
    yol = KLASOR / "ghost" / f"{temel[7:]}.json" if temel.startswith("ghost__") else KLASOR / f"{temel}.json"
    try:
        L = json.loads(yol.read_text(encoding="utf-8"))["veri"]["paylasim"]["taslaklar"]
        return yol, i, L[i]
    except Exception:  # noqa: BLE001
        return None


def _okur_ozeti(o):
    adlar = {"anlasilir": "anlaşılır", "tamlik": "tam", "deger": "değer", "kanca": "kanca", "ses": "ses", "tazelik": "tazelik", "paylasilir": "paylaşılır"}
    p = [f"{adlar[k]} {o[k]}" for k in adlar if isinstance(o.get(k), (int, float))]
    return ", ".join(p) + (f"; okurun notu: {o.get('not')}" if o.get("not") else "")


def baglam(odak=None):
    import ghost_danisman
    import paylasim
    pr = paylasim.profil()
    ps = pr.get("persona") or {}
    b = [f"KİŞİ: {pr.get('kimlik') or '-'}", f"OLMAK İSTEDİĞİ SES: {ps.get('karakter', '')} · merkez: {ps.get('merkez', '')}"]
    if ps.get("ilkeler"):
        b.append("YAZI İLKELERİ: " + " | ".join(str(x) for x in ps["ilkeler"][:8]))
    if pr.get("tarz"):
        b.append("TARZI (geçmiş gönderilerinden): " + str(pr["tarz"])[:700])
    ornek = [str(o)[:280] for o in (pr.get("ornekler") or [])[:6]]
    if ornek:
        b.append("GERÇEK GÖNDERİLERİNDEN ÖRNEKLER:\n" + "\n".join(f"- {o}" for o in ornek))
    alanlar = [f"{a.get('ad')} (ağırlık {a.get('agirlik')})" for a in pr.get("alanlar") or [] if isinstance(a, dict) and (a.get("agirlik") or 0) > 0]
    if alanlar:
        b.append("ALANLARI: " + ", ".join(alanlar))
    if pr.get("kacin"):
        b.append("KAÇINDIKLARI: " + ", ".join(str(x) for x in pr["kacin"][:8]))
    b.append(ghost_danisman.strateji_blogu().strip() or "STRATEJİ: danışman görüşmesi yapılmadı.")
    try:
        P = ghost_danisman.puan()
        if P.get("genel") is not None:
            b.append(f"PUAN KARTI (son 28 gün, 10 üzerinden, KODLA ölçüldü): genel {P['genel']}; "
                     + "; ".join(f"{x['ad']} {x['puan'] if x['puan'] is not None else 'veri yok'}" + (f" ({x['eksik']})" if x.get("eksik") else "")
                                 for x in P.get("boyutlar") or []))
    except Exception:  # noqa: BLE001
        pass
    d = ghost_danisman._oku()
    r = d.get("rapor") or {}
    if r.get("not"):
        b.append("BU HAFTAKİ DANIŞMAN NOTUN: " + str(r["not"])[:600])
    try:
        pl = ghost_danisman.plan()
        if pl["maddeler"]:
            b.append("BU HAFTANIN PLANI (i numarasıyla; durum kodla izlenir):\n" + "\n".join(
                f"- i={x['i']} {x['gun']} {x['tarih']}: {x['ne']} [{x['mecra']}] durum: {x['durum']}" + (f", taslak: {x['taslak']}" if x.get("taslak") else "")
                for x in pl["maddeler"]))
        rt = ghost_danisman.ritim()
        b.append(f"RİTİM: bu hafta {rt.get('bu_hafta')} gönderi, haftalık hedef {rt.get('hedef')}, üst üste hedefi tutan hafta {rt.get('seri')}.")
    except Exception:  # noqa: BLE001
        pass
    T = _taslaklar()
    if T:
        b.append("BUGÜN VE DÜN ÖNERDİĞİN TASLAKLAR (anahtar ile):\n" + "\n".join(
            f"- {t['anahtar']} [{t['alan']}, {t['platform']}]: {t['metin'][:260]}" + (f" (okur: {_okur_ozeti(t['okur'])})" if t["okur"] else "") for t in T[:8]))
    try:
        import ghost_defter
        N = ghost_defter.notlar(6)
        if N:
            b.append("FİKİR DEFTERİNDEN SON NOTLAR: " + " | ".join(str(n.get("metin"))[:160] for n in N))
        S = (ghost_defter._oku(ghost_defter.SORU / f"{dt.date.today().isoformat()}.json", {}) or {}).get("sorular") or []   # yalnız okur; üretmez
        acik = [q["soru"] for q in S if not q.get("cevap")]
        if acik:
            b.append("BUGÜN ONA SORDUĞUN, CEVAPLANMAMIŞ SORULAR: " + " | ".join(acik))
    except Exception:  # noqa: BLE001
        pass
    G = [g for g in paylasim.gorusler() if not g.get("yerine") and paylasim.gorus_durumu(g) != "red"]
    if G:
        b.append("GÖRÜŞ DEFTERİ (kendi sözlerinden): " + " | ".join(str(g.get("gorus"))[:140] for g in G[-10:]))
    Y = ghost_danisman.yaklasan(7)
    if Y:
        b.append("YAKLAŞAN GÜNDEM: " + " | ".join(f"{m.get('tarih')} {m.get('ad')}" for m in Y[:6]))
    b.append(_odak_metni(odak))
    return "\n\n".join(x for x in b if x)


def _odak_metni(odak):
    if not isinstance(odak, dict) or not odak.get("tur"):
        return ""
    t = odak["tur"]
    if t == "taslak":
        x = taslak(odak.get("anahtar"))
        if x:
            ts = x[2]
            return (f"KONUŞMANIN ODAĞI: şu taslak (anahtar {odak['anahtar']}):\n{ts.get('metin')}\nNeden önerdin: {ts.get('katki') or ts.get('neden') or '-'}\n"
                    f"Kaynak: {(ts.get('kaynak') or {}).get('baslik', '') if isinstance(ts.get('kaynak'), dict) else ''}\n"
                    + (f"Okur puanları: {_okur_ozeti(ts.get('okur') or {})}" if ts.get("okur") else ""))
    if t == "soru":
        return f"KONUŞMANIN ODAĞI: ona şu soruyu sordun: “{str(odak.get('soru'))[:400]}”. Cevabı yeterince somutsa 'yaz' eylemini öner (girdi: onun sözleri)."
    if t == "plan":
        return f"KONUŞMANIN ODAĞI: haftanın planındaki şu madde (i={odak.get('i')}): {str(odak.get('ne'))[:300]}"
    if t == "gundem":
        return f"KONUŞMANIN ODAĞI: yaklaşan gündem: {str(odak.get('baslik'))[:300]} ({odak.get('tarih', '')})"
    if t == "puan":
        return f"KONUŞMANIN ODAĞI: puan kartındaki '{odak.get('ad')}' boyutu."
    return ""


ISTEM = """Sen Ghost'sun: {ad}'in iletişim danışmanı ve yazı ortağısın. Onu uzun süredir tanıyan, işini bilen, sıcak ama dalkavuk olmayan biri gibi konuş.

NASIL KONUŞURSUN
- Türkçe, "sen" diliyle, doğal ve kısa (çoğu zaman 2-5 cümle). Liste yalnız gerçekten gerekiyorsa. Başlık, madde işareti yığını, emoji yok.
- "Harika soru", "Elbette!", "Umarım yardımcı olur" gibi kalıplar yok. Ne düşündüğünü doğrudan söyle; katılmıyorsan nedenini söyle.
- O sana soruyla, itirazla ya da "emin değilim"le cevap verebilir: buna gerçekten cevap ver, gerekçeni aşağıdaki verilere dayandır (puan kartı, plan,
  taslakların okur puanları, gerçek gönderileri). Gerekirse sen de TEK bir soru sor; sorgu yağmuru yok.
- Bilmediğin şeyi uydurma: "bunu bilmiyorum" ya da "verim yok" de. Sayılar yalnız aşağıdaki verilerden.
- Gönderi metni yazarsan ONUN sesiyle yaz (örnekler ve ilkeler aşağıda), yorumcu cümlesi ve vecize kapanış yok; olgu uydurma; metni yanıtın içine değil
  eylem olarak 'taslak' kartına koy, yanıtta kısaca ne yaptığını söyle.
- Siyaset, din, kimlik kavgası, yatırım tavsiyesi önermezsin (kaçındıkları).

VERİLER
{baglam}

BUGÜN: {bugun}

KONUŞMA (en eskiden yeniye):
{gecmis}

{ad}: {mesaj}

Önce yanıtını düz metin olarak yaz. Sonra, gerekiyorsa, tek başına bir satırda @@@ yaz ve ardından JSON ver:
{{"secenekler": ["onun verebileceği 2-4 kısa cevap; içlerinden biri soru olabilir"],
  "eylemler": [{{"tur": "taslak|duzenle|yaz|gorus|fikir|ogren|plan", "baslik": "düğmede görünecek 2-5 kelime",
     "metin": "taslak/duzenle: gönderinin tam metni · gorus/fikir: onun sözü (büyütmeden) · ogren: kalıcı yazım tercihi, emir kipi tek cümle",
     "platform": "x|linkedin", "anahtar": "duzenle için taslak anahtarı", "girdi": "yaz için: Ghost'un tam yazım hattına verilecek fikir (onun sözleriyle)",
     "i": "plan için madde numarası", "ne": "plan için yeni madde metni", "neden": "plan için tek cümle"}}]}}
Eylem yalnız konuşma gerçekten ona varıyorsa (en çok 2). Öneri yoksa @@@ satırını hiç yazma."""


def _gecmis_metni(ad, n=14):
    L = mesajlar(n)
    return "\n".join(f"{'Ghost' if m['rol'] == 'ghost' else ad}: {m['metin'][:1200]}" for m in L) or "(yeni konuşma)"


def istem(mesaj, odak=None):
    import ortak
    ad = ortak.kimlik()["ilk_ad"]
    return ISTEM.format(ad=ad, baglam=baglam(odak), bugun=dt.date.today().strftime("%Y-%m-%d %A"), gecmis=_gecmis_metni(ad), mesaj=str(mesaj)[:4000])


def ayir(tam):
    """Model çıktısı → (yanıt metni, {secenekler, eylemler}). JSON bozuksa yalnız metin."""
    if AYRAC not in tam:
        return tam.strip(), {}
    metin, _, j = tam.partition(AYRAC)
    j = j.strip()
    j = re.sub(r"^```(?:json)?|```$", "", j, flags=re.M).strip()
    try:
        ek = json.loads(j[j.find("{"): j.rfind("}") + 1])
    except Exception:  # noqa: BLE001
        ek = {}
    sec = [str(s).strip()[:120] for s in ek.get("secenekler") or [] if str(s).strip()][:4]
    E = []
    for e in ek.get("eylemler") or []:
        if not isinstance(e, dict) or e.get("tur") not in EYLEM_TURLERI:
            continue
        e = {k: v for k, v in e.items() if k in ("tur", "baslik", "metin", "platform", "anahtar", "girdi", "i", "ne", "neden") and v not in (None, "")}
        if e["tur"] in ("taslak", "duzenle", "gorus", "fikir", "ogren") and not str(e.get("metin") or "").strip():
            continue
        if e["tur"] == "duzenle" and not taslak(e.get("anahtar")):
            continue
        if e["tur"] == "yaz" and not str(e.get("girdi") or "").strip():
            continue
        if e["tur"] == "taslak":
            import paylasim
            e["metin"] = paylasim._temiz(str(e["metin"]))
        E.append(e)
    return metin.strip(), {"secenekler": sec, "eylemler": E[:2]}


def akis(mesaj, odak=None):
    """Kullanıcı mesajını kaydeder, yanıtı yazıldıkça verir (görünen metin parçaları), sonunda ('SON', mesaj kaydı) verir."""
    import claude_yaz
    ekle("ben", mesaj, odak=odak if isinstance(odak, dict) else None)
    tam, verilen = "", 0
    for parca in claude_yaz.sor_akis(istem(mesaj, odak), model_adi="sonnet"):
        tam += parca
        g = tam.split(AYRAC)[0]
        guvenli = len(g) if AYRAC in tam else max(verilen, len(g) - (len(AYRAC) - 1))
        if guvenli > verilen:
            yield g[verilen:guvenli]
            verilen = guvenli
    metin, ek = ayir(tam)
    if len(metin) > verilen:
        yield metin[verilen:]
    yield ("SON", ekle("ghost", metin, **ek))


# ---------------------------------------------------------------- karşılama (model yok; hemen)
def karsilama(saat=None, odak=None):
    """Panel açılınca Ghost'un ilk sözü: günün saatine ve duruma göre, verilerden. Döner {metin, secenekler}."""
    import ghost_danisman
    import ortak
    ad = ortak.kimlik()["ilk_ad"]
    saat = dt.datetime.now().hour if saat is None else saat
    sel = "Günaydın" if 5 <= saat < 12 else "Merhaba" if saat < 17 else "İyi akşamlar" if saat < 23 else "Geç oldu"
    if isinstance(odak, dict) and odak.get("tur") == "taslak":
        x = taslak(odak.get("anahtar"))
        if x:
            o = x[2].get("okur") or {}
            zayif = min((k for k in ("anlasilir", "tamlik", "deger", "kanca", "ses", "tazelik") if isinstance(o.get(k), (int, float))), key=lambda k: o[k], default="")
            ad_z = {"anlasilir": "anlaşılırlık", "tamlik": "tamlık", "deger": "değer", "kanca": "ilk cümle", "ses": "ses", "tazelik": "tazelik"}.get(zayif, "")
            neden = str(x[2].get("katki") or x[2].get("neden") or "").strip()
            m = (f"Bunu şunun için önerdim: {neden[:180]}" if neden else "Bu taslak hakkında konuşalım.") + (
                f" Okur en çok {ad_z} tarafını zayıf buldu." if ad_z else "") + " Sen ne düşünüyorsun, paylaşır mıydın?"
            return {"metin": m, "secenekler": ["Neden bu konu?", "Daha kısa olsun", "Bunu ben söylemezdim", "Başka bir açı bul"]}
    if isinstance(odak, dict) and odak.get("tur") == "soru":
        return {"metin": str(odak.get("soru") or ""), "secenekler": ["Bunu neden soruyorsun?", "Emin değilim", "Başka bir soru sor"]}
    if isinstance(odak, dict) and odak.get("tur") == "plan":
        return {"metin": f"Planda şu var: {odak.get('ne')}. Bunu yapmak istiyor musun, yoksa değiştirelim mi?",
                "secenekler": ["Neden bu?", "Birlikte yazalım", "Başka bir şey koy", "Bu hafta yapamam"]}
    if isinstance(odak, dict) and odak.get("tur") == "puan":
        return {"metin": f"{odak.get('ad')} tarafına bakalım. Ne merak ediyorsun?", "secenekler": ["Bu neden düşük?", "Nasıl yükseltirim?", "Bu ölçü bana uymuyor"]}
    parca, sec = [], []
    try:
        pl = ghost_danisman.plan()
        bugun = next((x for x in pl["maddeler"] if x["durum"] == "bugun"), None)
        if bugun:
            ne = str(bugun["ne"]).rstrip(".")
            if bugun.get("taslak") == "hazir":
                parca.append(f"bugünün planı için taslak hazır: {ne}. Bakmak ister misin?")
            elif bugun.get("taslak") == "elendi":
                parca.append(f"bugünün planını ({ne}) yazdım ama içime sinmedi, okur kapısından geçmedi. Birlikte yazalım mı?")
            else:
                parca.append(f"bugün planda şu var: {ne}.")
            sec.append("Bugünkü planı birlikte yazalım")
        rt = ghost_danisman.ritim()
        if rt.get("hedef"):
            kalan = max(0, rt["hedef"] - (rt.get("bu_hafta") or 0))
            if kalan:
                parca.append(f"Bu hafta {rt.get('bu_hafta') or 0} gönderin var, hedefe {kalan} kaldı.")
            else:
                parca.append("Bu haftanın hedefini tutturdun.")
    except Exception:  # noqa: BLE001
        pass
    try:
        Y = ghost_danisman.yaklasan(2)
        if Y:
            parca.append(f"Yaklaşan bir gündem var: {Y[0].get('ad')}.")
            sec.append("Yaklaşan gündem için ne yazayım?")
    except Exception:  # noqa: BLE001
        pass
    if not parca:
        parca.append("aklında bir şey varsa anlat, birlikte gönderiye çevirelim. Ya da bana bir şey sor.")
    sec += ["Bugün ne paylaşayım?", "Neden geride kalıyorum?", "Bana bir soru sor"]
    ilk = parca[0]
    return {"metin": f"{sel} {ad}, {ilk}" + ("" if len(parca) == 1 else " " + " ".join(parca[1:])), "secenekler": sec[:4]}


# ---------------------------------------------------------------- eylemler
def plan_degistir(i, ne, neden=""):
    import ghost_danisman
    d = ghost_danisman._oku()
    H = (d.get("rapor") or {}).get("hafta") or []
    i = int(i)
    if not 0 <= i < len(H) or not str(ne).strip():
        return None
    H[i]["ne_eski"] = H[i].get("ne_eski") or H[i].get("ne")
    H[i]["ne"] = str(ne).strip()[:300]
    if neden:
        H[i]["neden"] = str(neden).strip()[:300]
    for k in ("hazirlandi", "deneme"):
        H[i].pop(k, None)
    d["rapor"]["hafta"] = H
    ghost_danisman._yaz(d)
    return H[i]
