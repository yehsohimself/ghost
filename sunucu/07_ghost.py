# sunucu/07_ghost.py — Ghost: X paylaşımları, keşif, defter; Claude, Drive okuma, Chrome uzantısı, kayıt uçları.
# site.py bu dosyayı diğer parçalarla AYNI ad alanında, numara sırasıyla yürütür; tek başına çalıştırılmaz.
# ----------------------------------------------------------------------------- X paylaşım taslakları
paylasim_durum = {}


def _py_yol(temel):
    """Paylaşım taslağı kaynağı: transkript JSON'u ya da Ghost'a doğrudan verilen girdi (ghost__<id> → ghost/<id>.json)."""
    if temel.startswith("ghost__"):
        kid = temel[7:]
        if not re.match(r"^[\w\-]+$", kid) or not (KLASOR / "ghost" / f"{kid}.json").exists():
            abort(404)
        return KLASOR / "ghost" / f"{kid}.json"
    return _temel_dogrula(temel).with_suffix(".json")


@app.get("/api/x-profil")
def x_profil_get():
    import paylasim as paylasim_modulu
    return jsonify(paylasim_modulu.profil())


@app.post("/api/x-profil")
def x_profil_post():
    import paylasim as paylasim_modulu
    v = request.get_json(silent=True) or {}
    ornekler = v.get("ornekler")
    if isinstance(ornekler, str):
        # ayırıcı yalnız tek başına '---' satırı (25 Ekim): boş satır hem gönderi içi paragraf hem ayırıcıydı, çok paragraflı örnekler bölünüyordu.
        # '---' hiç yoksa (eski alışkanlık) boş satırla bölünür.
        ayrac = r"(?m)^\s*---+\s*$" if re.search(r"(?m)^\s*---+\s*$", ornekler) else r"\n\s*\n"
        ornekler = [o.strip() for o in re.split(ayrac, ornekler) if o.strip()]
    return jsonify(paylasim_modulu.profil_kaydet(tarz=v.get("tarz"), ornekler=ornekler, takip_otomatik=v.get("takip_otomatik"),
                                                 her_video=v.get("her_video")))


@app.get("/api/paylasimlar")
def paylasimlar():
    """Ghost: son 30 günün paylaşım önerileri (kaldırılanlar hariç), paylaşılanlar, elenen fikirler, hazırlananlar, özet.
    ?z=1: sayfa gerçekten açıldı (ziyaret; ghost_tempo üretim temposunu buna göre ayarlar)."""
    import ghost_tempo
    if request.args.get("z"):
        ghost_tempo.ziyaret()
    return jsonify({**_paylasim_verisi_onbellekli(), "tempo": ghost_tempo.ozet(7)})


@app.after_request
def _ghost_etkilesim(yanit):
    """Kullanıcının Ghost'ta yaptığı her işlem (taslak kararı, yorum, keşif, defter...) etkileşim sayılır (ghost_tempo)."""
    try:
        y = request.path
        if request.method == "POST" and yanit.status_code < 400 and (y.startswith("/api/paylasim/") or y.startswith("/api/ghost/") or y.startswith("/api/kesif/")):
            import ghost_tempo
            ghost_tempo.etkilesim()
    except Exception:  # noqa: BLE001
        pass
    return yanit


_paylasim_memo = {"t": 0.0, "v": None}


def _paylasim_verisi_onbellekli():
    """Ghost sayfası iş sürerken 6 sn'de bir çekiyor; hesap 5 sn geçerli tutulur (2026-10-25: 367 ms → birkaç ms)."""
    if _paylasim_memo["v"] is not None and time.time() - _paylasim_memo["t"] < 5:
        return _paylasim_memo["v"]
    v = _paylasim_verisi()
    _paylasim_memo.update(t=time.time(), v=v)
    return v


def _paylasim_verisi():
    import difflib
    import kitaplik_onbellek
    out, elenen, kaldirilan = [], [], []
    kal = {"onerilen": 0, "paylasilan": 0, "kaldirilan": 0, "nedenler": {}, "duzeltme": [], "dayanakli_paylasilan": 0, "dayanakli": 0}
    sinir = time.time() - 30 * 86400
    for kayit in kitaplik_onbellek.hepsi(ghost=True):       # mtime önbellekli; segmentler ayrıştırılmaz
        js, veri = kayit["yol"], kayit["veri"]
        if kayit["mtime"] < sinir:
            continue
        p = veri.get("paylasim") or {}
        if (not p.get("taslaklar") and not p.get("elenen")) or (p.get("zaman") or 0) < sinir or veri.get("toplanti"):
            continue
        # önerinin günü = kaydın oluştuğu an (ghost/<YYYYmmddHHMMSS_…>.json ya da veri.olusturma); p.zaman yeniden yazımda güncelleniyor
        olusma = p.get("ilk_zaman") or p.get("zaman") or 0
        if js.parent.name == "ghost":
            try:
                olusma = time.mktime(time.strptime(js.stem[:14], "%Y%m%d%H%M%S"))
            except ValueError:
                pass
        olusma = olusma or p.get("zaman") or 0
        gun_ = time.strftime("%Y-%m-%d", time.localtime(olusma))
        for j, e in enumerate(p.get("elenen") or []):
            if not e.get("yazildi") and not e.get("gizli"):
                elenen.append({"temel": ("ghost__" + js.stem) if js.parent.name == "ghost" else js.stem, "j": j, "konu": e.get("konu"), "gorus": e.get("gorus"),
                               "alan": e.get("alan"), "neden": e.get("neden"), "baslik": veri.get("baslik") or js.stem, "zaman": p.get("zaman")})
        for i, t in enumerate(p.get("taslaklar") or []):
            kal["onerilen"] += 1; kal["dayanakli"] += bool(t.get("dayanak"))
            if t.get("paylasildi"):
                kal["paylasilan"] += 1; kal["dayanakli_paylasilan"] += bool(t.get("dayanak"))
                if t.get("ilk_metin"):
                    kal["duzeltme"].append(1 - difflib.SequenceMatcher(None, t["ilk_metin"], t.get("metin") or "").ratio())
                else:
                    kal["duzeltme"].append(0.0)
            if t.get("gizli"):
                if not t.get("degistirildi"):               # sistemin kendi değiştirdiği taslak kullanıcının reddi sayılmaz (24 Ekim)
                    kal["kaldirilan"] += 1; n = t.get("red_nedeni") or "neden belirtilmedi"; kal["nedenler"][n] = kal["nedenler"].get(n, 0) + 1
                kaldirilan.append({"temel": ("ghost__" + js.stem) if js.parent.name == "ghost" else js.stem, "i": i, "metin": t.get("metin") or "", "alan": t.get("alan") or "",
                                   "neden": t.get("red_nedeni") or "", "platform": t.get("platform") or "x", "paylas_link": t.get("paylas_link") or "",
                                   "gun": gun_})
            if not t.get("gizli"):
                temel = ("ghost__" + js.stem) if js.parent.name == "ghost" else js.stem
                if "paylas_link" not in t and str(veri.get("link") or "").startswith("http"):     # eski taslaklar: kaynak bağlantısı gönderiyle paylaşılır
                    t = {**t, "paylas_link": veri["link"]}
                if veri.get("gundem"):
                    t = {**t, "gundem": veri["gundem"]}
                out.append({**t, "i": i, "temel": temel, "baslik": veri.get("baslik") or js.stem, "link": veri.get("link", ""),
                            "kaynak_tur": veri.get("kaynak_tur") or "video", "kapak": "" if veri.get("ghost") else _kapak_yolu(js.stem, veri.get("kapak")),
                            "zaman": p.get("zaman"), "olusma": olusma, "gun": gun_, "paylasildi": bool(t.get("paylasildi")), "paylasim_zaman": t.get("paylasim_zaman")})
    out.sort(key=lambda x: (-(x["zaman"] or 0), x["i"]))
    import paylasim as paylasim_modulu
    paylasilan = sorted([t for t in out if t["paylasildi"]], key=lambda t: -(t.get("paylasim_zaman") or t.get("zaman") or 0))
    out = [t for t in out if not t["paylasildi"]]
    gece0 = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))

    # 22 Ekim (kullanıcı: "öneriler her gün yenilenmeli; eskilere özellikle tıklayarak ulaşmalıyım"): Bugün'ün planı yalnızca bugün üretilenlerden
    # 24 Ekim: haftanın hikâyesi (7 gün) ve yanıt taslakları plana girmez; Bugün'de ayrı yerlerinde
    def _ozel(t):
        kt = t.get("karisim_tur")
        if kt == "hikaye":
            return "Haftanın hikâyesi" if time.time() - (t.get("olusma") or 0) < 7 * 86400 else "eski"
        if kt == "yanit":
            return "Yanıt" if (t.get("olusma") or 0) >= gece0 else "eski"
        return ""
    ozel = [t for t in out if _ozel(t) and _ozel(t) != "eski"]
    for t in ozel:
        t["plan_gun"], t["plan_dilim"] = "Bugün", _ozel(t)
    ozel_kim = {(t["temel"], t["i"]) for t in ozel}
    planli = paylasim_modulu.plan([t for t in out if (t.get("olusma") or 0) >= gece0 and not _ozel(t)], gun=3)
    for t in planli:
        if t.get("plan_gun") in ("Yarın",) or t.get("plan_gun") in paylasim_modulu.GUN_ADI:
            t["plan_gun"] = "Bugün"; t["plan_dilim"] = ""
    planli_kim = {(t["temel"], t["i"]): (t.get("plan_gun"), t.get("plan_dilim", "")) for t in planli}
    for t in out:
        if (t["temel"], t["i"]) not in ozel_kim:
            t["plan_gun"], t["plan_dilim"] = planli_kim.get((t["temel"], t["i"]), ("", ""))
    out = [t for t in ozel if t["plan_dilim"] == "Haftanın hikâyesi"] + planli + [t for t in ozel if t["plan_dilim"] == "Yanıt"] + \
        [t for t in out if not t["plan_gun"]]
    hazirlanan = []
    for temel, d in list(paylasim_durum.items()):
        if d.get("calisiyor"):
            try:
                hazirlanan.append({"baslik": json.loads(_py_yol(temel).read_text(encoding="utf-8"))["veri"].get("baslik") or temel,
                                   "adim": (d.get("log") or ["Hazırlanıyor"])[-1].strip()})
            except Exception:  # noqa: BLE001
                pass
    with kilit:
        for is_ in list(isler.values()):      # Ghost'tan verilen video linkleri: önce yazıya dökülür
            if is_.get("ghost") and is_.get("durum") in ("sirada", "calisiyor"):
                hazirlanan.append({"baslik": is_.get("baslik") or is_.get("link"), "adim": "Video yazıya dökülüyor" + (f" · %{int(is_.get('ilerleme') or 0)}" if is_.get("ilerleme") else "")})
            elif is_.get("ghost") and is_.get("durum") == "hata" and time.time() - (is_.get("olusturma") or 0) < 3600:
                hazirlanan.append({"baslik": is_.get("baslik") or is_.get("link"), "hata": _hata_metni(is_) if callable(globals().get("_hata_metni")) else "Olmadı"})
    pr = paylasim_modulu.profil()
    hafta = time.time() - 7 * 86400
    ozet = {"hazir": len(out), "hafta": sum(1 for t in paylasilan if (t.get("paylasim_zaman") or t.get("zaman") or 0) > hafta), "paylasilan": len(paylasilan),
            "ornek": len(pr.get("ornekler") or []) + len(pr.get("paylasilan") or []), "kimlik": pr.get("kimlik") or "", "kullanici": pr.get("kullanici") or "",
            "alanlar": [{"kod": a.get("kod"), "ad": a.get("ad"), "not": a.get("not", ""), "n": sum(1 for t in out if t.get("alan") == a.get("ad"))} for a in pr.get("alanlar") or [] if isinstance(a, dict)],
            "reddedilen": len(pr.get("reddedilen") or []), "persona": pr.get("persona") or {}}
    elenen.sort(key=lambda e: -(e.get("zaman") or 0))
    d_ = kal.pop("duzeltme")
    kal["duzeltme_ort"] = round(sum(d_) / len(d_), 2) if d_ else None
    karar = kal["paylasilan"] + kal["kaldirilan"]
    kal["paylasma_orani"] = round(kal["paylasilan"] / karar, 2) if karar else None
    try:                                                 # okurun değer işareti: kaydetme + yeniden paylaşım (görüntülenme değil)
        import performans
        L = [x for x in performans.liste(30) if x.get("goruntulenme", 0) >= 50]
        kal["deger_isareti"] = round(sum(x.get("yerimi", 0) + x.get("repost", 0) for x in L) / max(1, sum(x["goruntulenme"] for x in L)) * 1000, 1) if L else None
        kal["en_degerli"] = [{"id": x["id"], "metin": str(x.get("metin") or "")[:140], "yerimi": x.get("yerimi", 0), "repost": x.get("repost", 0)}
                             for x in sorted(L, key=lambda x: -(x.get("yerimi", 0) + x.get("repost", 0)))[:3] if x.get("yerimi", 0) + x.get("repost", 0) > 0]
    except Exception:  # noqa: BLE001
        pass
    kal["gorus"] = len([g for g in paylasim_modulu.gorusler() if not g.get("yerine")])
    ozet["kalite"] = kal
    ozet["hedef"] = pr.get("hedef") or {}
    bugun0 = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
    ozet["bugun_paylasilan"] = sum(1 for t in paylasilan if (t.get("paylasim_zaman") or 0) >= bugun0)
    # gün gün gezinmek için 30 günün tamamı (eskiden 60/20 ile kesiliyordu; geçmiş günler boş görünürdü)
    return {"taslaklar": out[:300], "paylasilan": paylasilan[:200], "hazirlanan": hazirlanan, "ozet": ozet, "elenen": elenen[:20], "kaldirilanlar": kaldirilan[-400:]}


kesif_durum = {"calisiyor": False, "hata": "", "log": []}


def _kesif_calistir(geri_bildirim="", toplanti=""):
    import kesif
    if kesif_durum["calisiyor"]:
        return
    kesif_durum.update({"calisiyor": True, "hata": "", "log": []})
    try:
        kesif.calistir(log=lambda m: (kesif_durum["log"].append(m), print(m, flush=True)), geri_bildirim=geri_bildirim,
                       toplanti=toplanti, hemen=bool(geri_bildirim))
        if toplanti:
            import konu_toplantisi
            t = konu_toplantisi.son()
            if t and t.get("durum") == "bekliyor" and time.time() - t.get("zaman", 0) < 300:
                _bildir(f"Ghost: bugünün {len(t['konular'])} konusu hazır",
                        f"{konu_toplantisi.SURE.get(t['dilim'], 45)} dk içinde bakın; bakmazsanız hepsini yazarım. İlk soru: {(t['konular'][0].get('soru') or '')[:90]}")
    except Exception as e:  # noqa: BLE001
        kesif_durum["hata"] = str(e)[:200]
    finally:
        kesif_durum["calisiyor"] = False


@app.get("/api/kesif")
def kesif_get():
    """Bugünün keşif önerileri (?gun=YYYY-MM-DD ile o günün; 22 Ekim: dünkü yedek kaldırıldı, her gün kendi önerisi); story'ler, X ve LinkedIn."""
    istenen = request.args.get("gun") or ""
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", istenen):
        istenen = datetime.date.today().isoformat()
    f = KAYIT / "kesif" / f"{istenen}.json"
    gun = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    if gun:
        gun["oneriler"] = [o for o in gun.get("oneriler") or [] if o.get("platform") != "story" or o.get("ig_kod")]
    if gun:
        for o in gun.get("oneriler") or []:
            o["hazirlaniyor"] = bool(o.get("temel") and paylasim_durum.get(o["temel"], {}).get("calisiyor"))
    saglik = {}
    try:
        sk = json.loads((KAYIT / "kesif" / "saglik.json").read_text(encoding="utf-8"))
        K = list((sk.get("kaynaklar") or {}).values())
        saglik = {"toplam": len(K), "calisan": sum(1 for x in K if x.get("ok")), "bozuk": [x.get("kaynak") for x in K if not x.get("ok")],
                  "trendler": [t.get("terim") for t in (sk.get("trendler") or [])][:10]}
    except Exception:  # noqa: BLE001
        pass
    return jsonify({"kesif": gun, "calisiyor": kesif_durum["calisiyor"], "hata": kesif_durum["hata"], "adim": (kesif_durum["log"] or [""])[-1], "saglik": saglik})


@app.post("/api/kesif/yenile")
def kesif_yenile():
    """{begenmedim: true, neden}: bu turun keşiften gelen, paylaşılmamış ve dokunulmamış önerileri kaldırılır (nedeni öğrenilir), keşif bu geri
    bildirimle yeniden çalışır; aynı başlıklar bir daha önerilmez (kesif._onceki_basliklar). Boş gövde: yalnızca yeni öneri ekler."""
    v = request.get_json(silent=True) or {}
    geri = ""
    if v.get("begenmedim"):
        import paylasim as paylasim_modulu
        neden = str(v.get("neden") or "").strip()[:400]
        neden_tur = str(v.get("neden_tur") or "")              # 24 Ekim: tek dokunuşluk hazır neden (konu | ses | tur); toplu ret de öğretsin
        basliklar, kaldirilan, giden = [], 0, []
        for js in sorted(list((KLASOR / "ghost").glob("*.json")) + list(KLASOR.glob("transkript_*.json")), key=lambda p: -p.stat().st_mtime)[:120]:
            try:
                with kilit:
                    d = json.loads(js.read_text(encoding="utf-8")); veri = d["veri"]
                    if veri.get("kaynak_tur") in ("fikir", "secki") or veri.get("toplanti") or time.time() - js.stat().st_mtime > 3 * 86400:
                        continue
                    degisti = False
                    for t in (veri.get("paylasim") or {}).get("taslaklar") or []:
                        if not t.get("paylasildi") and not t.get("gizli") and not t.get("duzenlendi") and not t.get("yorumlar") and t.get("dayanak") != "kendi":
                            t["gizli"] = True; t["red_nedeni"] = "tur beğenilmedi" + (f": {neden}" if neden else ""); degisti = True; kaldirilan += 1
                            giden.append(dict(t))
                    if degisti:
                        basliklar.append(str(veri.get("baslik") or "")[:90])
                        js.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            except Exception:  # noqa: BLE001
                continue
        try:                                             # story önerileri de
            import kesif
            f = kesif.KESIF / f"{datetime.date.today().isoformat()}.json"
            if f.exists():
                k = json.loads(f.read_text(encoding="utf-8"))
                for o in k.get("oneriler") or []:
                    if o.get("platform") == "story" and not o.get("paylasildi"):
                        o["gizli"] = True
                f.write_text(json.dumps(k, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
        turler = collections.Counter(t.get("karisim_tur") or t.get("bicim") or "" for t in giden if t.get("karisim_tur") or t.get("bicim"))
        if neden_tur == "tur" and turler:
            neden = (neden + " · " if neden else "") + "hepsi aynı türdendi (" + ", ".join(f"{k} {n}" for k, n in turler.most_common(3)) + "); bu sefer türleri karıştır"
        elif neden_tur == "ses":
            neden = (neden + " · " if neden else "") + "yazım sesi bana benzemiyordu"
            for t in giden[:6]:                                   # 'bu ben değilim' örnekleri: yazıcı bunlara benzememeye çalışır
                paylasim_modulu.red_kaydet(t, "ben değilim")
        elif neden_tur == "konu":
            neden = (neden + " · " if neden else "") + "konular sıkıcıydı"
        elif neden_tur == "aci":                           # konu iyi, söylenen bariz/zayıf: açı elemesine örnek olur (konu reddi DEĞİL)
            neden = (neden + " · " if neden else "") + "konular iyiydi ama söylenenler barizdi"
            for t in giden[:6]:
                paylasim_modulu.red_kaydet(t, "açı zayıf")
        pr = paylasim_modulu.profil()
        paylasim_modulu.profil_kaydet(kesif_red=([r for r in pr.get("kesif_red") or [] if isinstance(r, dict)]
                                                 + [{"zaman": time.time(), "neden": neden, "tur": neden_tur, "basliklar": basliklar[:12],
                                                     "turler": dict(turler)}])[-30:])
        geri = (neden or "neden belirtmedi") + (" · beğenilmeyen başlıklar: " + "; ".join(basliklar[:10]) if basliklar else "")
        kalite_kaydet = {"kaldirilan": kaldirilan}
    threading.Thread(target=_kesif_calistir, args=(geri, "" if geri else "elle"), daemon=True).start()
    return jsonify({"tamam": True, **({"kaldirilan": kalite_kaydet["kaldirilan"]} if v.get("begenmedim") else {})})


toplanti_bitiyor = set()


def _konu_toplantisi_bitir(tid):   # 2026-10-25: eski adı _toplanti_bitir, Meet'in _toplanti_bitir(is_)'ını EZİYORDU (23_misafir_meet yanlışını sarmaladı; dakikada bir çöken iş parçacığı)
    import konu_toplantisi
    if tid in toplanti_bitiyor:
        return
    toplanti_bitiyor.add(tid)
    kesif_durum.update({"calisiyor": True, "hata": "", "log": []})
    try:
        konu_toplantisi.bitir(tid, log=lambda m: (kesif_durum["log"].append(m), print(m, flush=True)))
    except Exception as e:  # noqa: BLE001
        kesif_durum["hata"] = str(e)[:200]; print(f"Konu toplantısı yazımı hatası: {e}", flush=True)
    finally:
        kesif_durum["calisiyor"] = False
        toplanti_bitiyor.discard(tid)


def _fikir_eslesme():
    try:
        import fikir_kartlari
        return fikir_kartlari.bugun()
    except Exception:  # noqa: BLE001
        return []


def _arsiv_toplam():
    try:
        import reklam_arsivi
        return len(reklam_arsivi.isler())
    except Exception:  # noqa: BLE001
        return 0


@app.post("/api/ghost/fikir-karti/yaz")
def ghost_fikir_karti_yaz():
    """{anahtar}: bugün tetiklenen görüşten taslak (arka planda; tetik.tepki_olarak_yaz)."""
    import fikir_kartlari
    a = str((request.get_json(silent=True) or {}).get("anahtar") or "")
    if not any(e["anahtar"] == a for e in fikir_kartlari.bugun()):
        return jsonify({"hata": "Bu görüşün bugün tetiği yok."}), 404

    def _is():
        try:
            fikir_kartlari.yaz(a)
        except Exception as e:  # noqa: BLE001
            print(f"Fikir kartı yazılamadı: {e}", flush=True)
    threading.Thread(target=_is, daemon=True).start()
    return jsonify({"tamam": True})


@app.get("/api/reklam-arsivi")
def reklam_arsivi_ara():
    """?q= arama (marka, proje, fikir, içgörü...); q yoksa özet sayılar."""
    import reklam_arsivi
    q = str(request.args.get("q") or "").strip()
    L = reklam_arsivi.isler()
    if not q:
        say = {}
        for x in L:
            say[f"{x['kaynak']} {x['yil']}"] = say.get(f"{x['kaynak']} {x['yil']}", 0) + 1
        return jsonify({"toplam": len(L), "kaynaklar": say})
    alan = ("kaynak", "yil", "odul", "kategori", "ajans", "marka", "proje", "ulke", "link", "problem", "icgoru", "fikir", "sicrama", "cumle", "sonuc", "ogrenme", "aciklama")
    return jsonify({"toplam": len(L), "sonuclar": [{k: x.get(k) for k in alan if x.get(k)} for x in reklam_arsivi.ara(q, 30)]})


@app.get("/api/ghost/toplanti")
def ghost_toplanti_get():
    import konu_toplantisi
    t = konu_toplantisi.son()
    return jsonify({"toplanti": t, "yaziliyor": bool(toplanti_bitiyor)})


@app.post("/api/ghost/toplanti/<tid>")
def ghost_toplanti_karar(tid):
    """{konu, karar: yaz|gec|null, cevap} ya da {bitir: true} (yazmaya başla)."""
    import konu_toplantisi
    v = request.get_json(silent=True) or {}
    if v.get("bitir"):
        threading.Thread(target=_konu_toplantisi_bitir, args=(tid,), daemon=True).start()
        return jsonify({"tamam": True})
    try:
        t = konu_toplantisi.karar(tid, str(v.get("konu") or ""), v.get("karar") if "karar" in v else "__", v.get("cevap"))
    except ValueError as e:
        return jsonify({"hata": str(e)}), 400
    return jsonify({"toplanti": t})


blog_durum = {"calisiyor": False, "hata": ""}       # 26 Ekim: blog konusu önerileri (ghost_blog.py)


def _blog_oner(yon=""):
    import ghost_blog
    blog_durum.update({"calisiyor": True, "hata": ""})
    try:
        ghost_blog.oner(yon, log=lambda *_: None)
    except Exception as e:  # noqa: BLE001
        blog_durum["hata"] = str(e)[:200]
    finally:
        blog_durum["calisiyor"] = False


@app.get("/api/ghost/blog")
def ghost_blog_get():
    import ghost_blog
    return jsonify({"oneriler": ghost_blog.liste()[:40], **blog_durum})


@app.post("/api/ghost/blog")
def ghost_blog_post():
    """{yon} → yeni öneriler (arka planda) | {id, durum: begendim|gec|yazildi|null, neden} → karar."""
    import ghost_blog
    v = request.get_json(silent=True) or {}
    if v.get("id"):
        try:
            return jsonify({"oneri": ghost_blog.isaretle(str(v["id"]), v.get("durum"), v.get("neden") or "")})
        except ValueError as e:
            return jsonify({"hata": str(e)}), 404
    if blog_durum["calisiyor"]:
        return jsonify({"hata": "Öneriler zaten hazırlanıyor"}), 409
    threading.Thread(target=_blog_oner, args=(str(v.get("yon") or "").strip()[:300],), daemon=True).start()
    return jsonify({"tamam": True})


@app.post("/api/kesif/yaz")
def kesif_yaz():
    """{tarih, id, yorum} → öneriden taslak (kullanıcının yorumu merkezde); arka planda."""
    import kesif
    v = request.get_json(silent=True) or {}
    tarih = re.sub(r"[^0-9-]", "", str(v.get("tarih") or ""))[:10]; oid = str(v.get("id") or "")[:80]

    def _calis():
        try:
            temel = None
            yol, k, o = kesif._bul(tarih, oid)
            kesif.taslak_yaz(tarih, oid, str(v.get("yorum") or "")[:2000], log=lambda m: print(m, flush=True))
        except Exception as e:  # noqa: BLE001
            print(f"Keşif taslağı hatası: {e}", flush=True)
    threading.Thread(target=_calis, daemon=True).start()
    return jsonify({"tamam": True})


@app.post("/api/kesif/story")
def kesif_story():
    import kesif
    v = request.get_json(silent=True) or {}
    kesif.story_isaretle(re.sub(r"[^0-9-]", "", str(v.get("tarih") or ""))[:10], str(v.get("id") or "")[:80], bool(v.get("paylasildi")), bool(v.get("gizli")),
                         str(v.get("neden") or "")[:120])
    return jsonify({"tamam": True})


X_GORULEN = KAYIT / "x_gorulen.json"


def _ghost_fikirden_yaz(girdi, deneyim="", ek=None):
    """Kişinin kendi notundan/cevabından Ghost taslağı (arka planda). Döner: temel."""
    import paylasim as paylasim_modulu
    temel = paylasim_modulu.ghost_kaydi(girdi, "fikir", "", "", girdi, deneyim=deneyim or girdi, ek=ek)
    threading.Thread(target=_paylasim_arka, args=(temel,), daemon=True).start()
    return temel


@app.post("/api/ghost/not")
def ghost_not():
    """Fikir defterindeki bir not: {id, yaz: true} gönderiye çevirir; {id, sil: true} defterden siler."""
    import ghost_defter
    v = request.get_json(silent=True) or {}
    x = next((n for n in ghost_defter.notlar(1000) if n.get("id") == str(v.get("id"))), None)
    if not x:
        return jsonify({"hata": "Not bulunamadı."}), 404
    if v.get("sil"):
        ghost_defter.not_sil(x["id"])
        return jsonify({"tamam": True})
    temel = _ghost_fikirden_yaz(x["metin"])
    ghost_defter.not_kullanildi(x["id"], temel)
    return jsonify({"tamam": True, "temel": temel})


SESNOT = KAYIT / "sesli_notlar"


@app.post("/api/ghost/sesli-not")
def ghost_sesli_not():
    """Kişinin KENDİ sesli notu (tarayıcı mikrofonu ya da iPhone Kısayolu): yazıya döker. ?tur=yazi yalnız metni döner; tur=fikir deftere ekler ve
    gönderiye çevirir (varsayılan; telefon kısayolu); tur=mac_once|mac_sonra maç defterine. Sürekli kayıt yok (Almanya §201)."""
    import ghost_defter
    tur = request.args.get("tur") or request.form.get("tur") or "fikir"
    f = request.files.get("dosya")
    SESNOT.mkdir(parents=True, exist_ok=True)
    yol = SESNOT / f"{time.strftime('%Y%m%d_%H%M%S')}{Path(f.filename).suffix if f and f.filename else '.m4a'}"
    if f:
        f.save(str(yol))
    else:
        yol.write_bytes(request.get_data()[:60_000_000])
    if yol.stat().st_size < 2000:
        return jsonify({"hata": "Ses çok kısa."}), 400
    p = subprocess.run([str(KLASOR / ".venv" / "bin" / "python"), str(KLASOR / "sesnot.py"), str(yol), "tr"], capture_output=True, text=True, timeout=300)
    try:
        sonuc = json.loads(p.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        return jsonify({"hata": "Yazıya dökülemedi."}), 500
    metin = sonuc.get("metin", "").strip()
    if not metin:
        return jsonify({"hata": "Seste konuşma bulunamadı."}), 400
    if tur == "yazi":
        return jsonify({"metin": metin, "sure": sonuc.get("sure")})
    if tur in ("mac_once", "mac_sonra"):
        ghost_defter.mac_not("once" if tur == "mac_once" else "sonra", metin)
        return jsonify({"metin": metin, "tur": tur})
    x = ghost_defter.not_ekle(metin, "sesli", ek={"ses": yol.name})
    temel = _ghost_fikirden_yaz(metin)
    if x:
        ghost_defter.not_kullanildi(x["id"], temel)
    _bildir("Sesli not alındı", metin[:120])
    return jsonify({"metin": metin, "temel": temel})


ghost_defter_durum = {"calisiyor": ""}


def _ghost_defter_is(ad, fn, *arg):
    if ghost_defter_durum["calisiyor"]:
        return
    ghost_defter_durum["calisiyor"] = ad
    try:
        fn(*arg)
    except Exception as e:  # noqa: BLE001
        print(f"Ghost defter ({ad}) hatası: {e}", flush=True)
    finally:
        ghost_defter_durum["calisiyor"] = ""


@app.get("/api/ghost/defter")
def ghost_defter_get():
    import ghost_defter
    gun = datetime.date.today().isoformat()
    sor = ghost_defter._oku(ghost_defter.SORU / f"{gun}.json", {})
    mac = ghost_defter._oku(KAYIT / "mac" / f"{gun}.json", {"var": False})
    import paylasim as paylasim_modulu
    return jsonify({"sorular": sor, "notlar": ghost_defter.notlar(30), "adaylar": ghost_defter.adaylar()[:12], "mac": mac,
                    "mac_gecmis": [x for x in ghost_defter._oku(ghost_defter.MAC, []) if x.get("tur") in ("once", "sonra")][-12:][::-1],
                    "karne": ghost_defter.karne(),
                    "fikir_eslesme": _fikir_eslesme(), "arsiv_toplam": _arsiv_toplam(),
                    # 29 Ekim: kişisel entegrasyonlar yalnız kuruluysa görünür (ChatGPT seçkisi Drive'da, maç defteri tuttuğu takım, toplantılar Meet)
                    "acik": {"secki": bool(ayarlar_oku().get("secki_klasor_id")), "mac": bool(__import__("ortak").kimlik().get("takim")),
                             "toplanti": "note" in URUNLER_KURULU},
                    "mac_piyasa": ghost_defter._oku(KAYIT / "mac" / f"piyasa_{gun}.json", {}).get("piyasa"),
                    "mac_tahmin": next((x for x in ghost_defter._oku(ghost_defter.MAC, []) if x.get("tarih") == gun and x.get("tur") == "tahmin"), None),
                    "mac_sonuc": next((x["sonuc"] for x in ghost_defter._oku(ghost_defter.MAC, []) if x.get("tarih") == gun and x.get("tur") == "sonuc"), None),
                    "gorusler": [{**g, "durum": paylasim_modulu.gorus_durumu(g)} for g in paylasim_modulu.gorusler() if not g.get("yerine")][::-1][:60],
                    "mac_notlari": ghost_defter.mac_notlari(), "birlestirme": ghost_defter._oku(ghost_defter.BIRLES, {}), "calisiyor": ghost_defter_durum["calisiyor"]})


@app.post("/api/ghost/sorular/yenile")
def ghost_sorular_yenile():
    import ghost_defter
    threading.Thread(target=_ghost_defter_is, args=("sorular", ghost_defter.sorular, None, True), daemon=True).start()
    return jsonify({"tamam": True})


@app.post("/api/ghost/soru/cevap")
def ghost_soru_cevap():
    """{tarih, i, cevap}: günün sorusuna cevap → deftere + gönderiye çevir."""
    import ghost_defter
    v = request.get_json(silent=True) or {}
    cevap = str(v.get("cevap") or "").strip()[:2000]
    if len(cevap) < 4:
        return jsonify({"hata": "Bir iki cümle yazın."}), 400
    gun = re.sub(r"[^0-9-]", "", str(v.get("tarih") or ""))[:10]
    k = ghost_defter._oku(ghost_defter.SORU / f"{gun}.json", {})
    i = int(v.get("i", -1))
    if not 0 <= i < len(k.get("sorular") or []):
        return jsonify({"hata": "Soru bulunamadı."}), 404
    s_ = k["sorular"][i]
    temel = _ghost_fikirden_yaz(f"SORU (kendine sorulan): {s_['soru']}\nKENDİ CEVABI: {cevap}", cevap, ek={"alan_ad": ""})
    ghost_defter.soru_cevapla(gun, i, cevap, temel)
    return jsonify({"tamam": True, "temel": temel})


@app.post("/api/ghost/gorus-adaylari/tara")
def ghost_gorus_tara():
    import ghost_defter
    threading.Thread(target=_ghost_defter_is, args=("gorus", ghost_defter.gorus_adaylari_tara), daemon=True).start()
    return jsonify({"tamam": True})


@app.post("/api/ghost/gorus")
def ghost_gorus_isaretle():
    """Görüş defterinde: {gorus (metin), islem: onayla | red | duzelt, metin}."""
    import paylasim as paylasim_modulu
    v = request.get_json(silent=True) or {}
    if v.get("islem") not in ("onayla", "red", "duzelt") or not v.get("gorus"):
        return jsonify({"hata": "geçersiz"}), 400
    paylasim_modulu.gorus_isaretle(str(v["gorus"]), v["islem"], str(v.get("metin") or ""))
    return jsonify({"tamam": True})


@app.post("/api/ghost/gorus-aday")
def ghost_gorus_aday():
    import ghost_defter
    v = request.get_json(silent=True) or {}
    ghost_defter.aday_karar(int(v.get("i", -1)), bool(v.get("kabul")))
    return jsonify({"tamam": True})


@app.post("/api/ghost/mac")
def ghost_mac():
    """{tur: once|sonra, metin} maç defterine; {gonderi: once|sonra} o nottan taslak."""
    import ghost_defter
    v = request.get_json(silent=True) or {}
    if v.get("gonderi") in ("once", "sonra"):
        g = ghost_defter.mac_girdisi(v["gonderi"])
        if not g:
            return jsonify({"hata": "Önce not yazın."}), 400
        return jsonify({"tamam": True, "temel": _ghost_fikirden_yaz(g, g, ek={"alan_ad": "Futbol"})})
    if v.get("tahmin") in ghost_defter.SONUC_AD:            # {tahmin: G|B|M, guven: 40-95}
        return jsonify(ghost_defter.mac_tahmin(v["tahmin"], float(v.get("guven") or 60)))
    if v.get("sonuc") in ghost_defter.SONUC_AD:             # {sonuc: G|B|M}
        return jsonify(ghost_defter.mac_sonuc(v["sonuc"]))
    if v.get("tur") in ("once", "sonra") and len(str(v.get("metin") or "").strip()) >= 3:
        return jsonify(ghost_defter.mac_not(v["tur"], str(v["metin"])))
    return jsonify({"hata": "Not boş."}), 400


@app.get("/api/ghost/karne")
def ghost_karne():
    import ghost_defter
    return jsonify(ghost_defter.karne())


@app.post("/api/ghost/birlestirme/yenile")
def ghost_birlestirme_yenile():
    import ghost_defter
    threading.Thread(target=_ghost_defter_is, args=("birlestirme", ghost_defter.birlestirme_onerileri, True), daemon=True).start()
    return jsonify({"tamam": True})


@app.post("/api/ghost/birlestir")
def ghost_birlestir():
    import ghost_defter
    k = ghost_defter._oku(ghost_defter.BIRLES, {}); i = int((request.get_json(silent=True) or {}).get("i", -1))
    O = k.get("oneriler") or []
    if not 0 <= i < len(O):
        return jsonify({"hata": "Öneri bulunamadı."}), 404
    o = O[i]
    g = f"İKİ KENDİ PARÇASI BİRLİKTE (aralarındaki bağı kur):\n1) {o['a']}\n2) {o['b']}\nTEZ: {o['fikir']}"
    return jsonify({"tamam": True, "temel": _ghost_fikirden_yaz(g, o["a"] + " / " + o["b"])})


@app.get("/api/ghost/tercihler")
def ghost_tercihler():
    import paylasim as paylasim_modulu
    pr = paylasim_modulu.profil()
    return jsonify({"tercihler": [{**t, "i": i} for i, t in enumerate(paylasim_modulu.tercihler())][::-1][:40],
                    "silinen": pr.get("silinen_ifadeler") or [], "dersler": pr.get("duzeltme_dersleri") or []})


@app.post("/api/ghost/tercih")
def ghost_tercih():
    """{i, aktif}: düzeltmeden öğrenilen tercihi kapatır/açar (geri alınabilir); {silinen, kaldir}: sık silinen ifadeyi listeden çıkarır."""
    import paylasim as paylasim_modulu
    v = request.get_json(silent=True) or {}
    if "silinen" in v:
        pr = paylasim_modulu.profil(); L = [x for x in pr.get("silinen_ifadeler") or [] if x != v["silinen"]]
        paylasim_modulu.profil_kaydet(silinen_ifadeler=L); return jsonify({"tamam": True})
    T = paylasim_modulu.tercihler(); i = int(v.get("i", -1))
    if 0 <= i < len(T):
        T[i]["aktif"] = bool(v.get("aktif")); paylasim_modulu.TERCIH.write_text(json.dumps(T, ensure_ascii=False, indent=1), encoding="utf-8")
    return jsonify({"tamam": True})


@app.post("/api/x/gorulen")
def x_gorulen_ekle():
    """Uzantı: kullanıcının X'te açtığı gönderi (yalnız okunur) → alıntılayarak yazmak için son açılanlar listesi."""
    g = (request.get_json(silent=True) or {}).get("gonderi") or {}
    gid = re.sub(r"\D", "", str(g.get("id") or ""))[:25]
    if not gid or not g.get("metin"):
        return jsonify({"tamam": False})
    try:
        L = json.loads(X_GORULEN.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        L = []
    L = [x for x in L if x.get("id") != gid] + [{"id": gid, "kullanici": re.sub(r"[^\w]", "", str(g.get("kullanici") or ""))[:30], "ad": str(g.get("ad") or "")[:80],
                                                  "metin": str(g.get("metin"))[:2000], "tarih": str(g.get("tarih") or "")[:40], "zaman": time.time()}]
    X_GORULEN.write_text(json.dumps(L[-40:], ensure_ascii=False, indent=1), encoding="utf-8")
    try:                                                   # açılan gönderi bir yer imiyse tam metin oraya da (25 Ekim: akışta "Show more" ile kısaltılmış geliyordu)
        import yerimleri
        yerimleri.tam_metin(gid, str(g.get("metin")))
    except Exception:  # noqa: BLE001
        pass
    return jsonify({"tamam": True})


X_KARTLI = KAYIT / "x_kartli.json"


IG_DURUM = {"calisiyor": False, "son": 0, "yeni": 0}


@app.post("/api/ig/gorulen")
def ig_gorulen():
    """Uzantı (yalnızca okuma): Instagram'da görülen gönderiler → story önerileri. Yeni gönderi biriktikçe (≥5, en çok 2 saatte bir) story'ler tazelenir."""
    import kesif
    yeni = kesif.ig_kaydet((request.get_json(silent=True) or {}).get("gonderiler") or [])
    IG_DURUM["yeni"] += yeni
    # story listesi hedefin altındaysa 20 dakikada bir, doluysa 2 saatte bir tazelenir (ilk sürümde 2 saat bekliyordu; sonra gelen gönderiler bakılmadan kalıyordu)
    try:
        mevcut = sum(1 for o in json.loads((KAYIT / "kesif" / f"{datetime.date.today().isoformat()}.json").read_text(encoding="utf-8")).get("oneriler") or []
                     if o.get("platform") == "story" and o.get("ig_kod") and not o.get("gizli"))
    except Exception:  # noqa: BLE001
        mevcut = 0
    import paylasim as paylasim_modulu
    aralik = 20 * 60 if mevcut < int((paylasim_modulu.profil().get("hedef") or {}).get("story_gunluk") or 4) else 2 * 3600
    if IG_DURUM["yeni"] >= 5 and not IG_DURUM["calisiyor"] and time.time() - IG_DURUM["son"] > aralik and ayarlar_oku().get("ghost_kesif", True):
        import claude_yaz
        if claude_yaz.hazir():
            IG_DURUM.update({"calisiyor": True, "son": time.time(), "yeni": 0})

            def _calis():
                try:
                    kesif.story_guncelle(log=lambda m: print(m, flush=True))
                except Exception as e:  # noqa: BLE001
                    print(f"Story güncellenemedi: {e}", flush=True)
                finally:
                    IG_DURUM["calisiyor"] = False
            threading.Thread(target=_calis, daemon=True).start()
    return jsonify({"tamam": True, "yeni": yeni})


@app.get("/ig-gorsel/<kod>.jpg")
def ig_gorsel(kod):
    f = KLASOR / "kayitlar" / "ig" / f"{re.sub(r'[^\w-]', '', kod)}.jpg"
    if not f.exists():
        abort(404)
    return send_from_directory(f.parent, f.name, max_age=86400)


@app.get("/api/x/hesaplar")
def x_hesaplar_liste():
    """Uzantı 3.3: izlenen X ve Instagram hesapları (ana akışta yalnız bunların gönderileri okunur) + X liste adresi."""
    import hesaplar
    import paylasim as paylasim_modulu
    return jsonify({"x": sorted(hesaplar.x_hesaplari()), "ig": sorted(hesaplar.ig_hesaplari()),
                    "liste_url": paylasim_modulu.profil().get("x_liste_url") or "", "son_liste": hesaplar.son_liste_bakisi()})


@app.get("/api/ghost/hesaplar")
def ghost_hesaplar():
    """Sesiniz → İzlediğiniz hesaplar: gruplu liste, liste adresi, son okuma ve son 36 saatte okunan gönderi sayısı."""
    import hesaplar
    import paylasim as paylasim_modulu
    return jsonify({**hesaplar.yukle(), "liste_url": paylasim_modulu.profil().get("x_liste_url") or "", "son_liste": hesaplar.son_liste_bakisi(),
                    "son_36": len(hesaplar.akis(36))})


@app.post("/api/ghost/hesaplar")
def ghost_hesaplar_kaydet():
    """{liste_url}: X listesinin adresi (x.com/i/lists/<sayı>)."""
    import paylasim as paylasim_modulu
    u = str((request.get_json(silent=True) or {}).get("liste_url") or "").strip()
    if u and not re.match(r"^https://(x|twitter)\.com/i/lists/\d+", u):
        return jsonify({"hata": "Liste adresi x.com/i/lists/… biçiminde olmalı"}), 400
    paylasim_modulu.profil_kaydet(x_liste_url=u.replace("twitter.com", "x.com"))
    return jsonify({"tamam": True})


@app.post("/api/x/akis")
def x_akis_ekle():
    """Uzantı 3.3: X listesi sayfasında (liste: true) ya da ana akışta izlenen hesapların ekranda görünen gönderileri (YALNIZ okunur)."""
    import hesaplar
    v = request.get_json(silent=True) or {}
    return jsonify({"tamam": True, "yeni": hesaplar.akis_kaydet(v.get("gonderiler") or [], liste=bool(v.get("liste")))})


@app.post("/api/x/kartli")
def x_kartli_ekle():
    """Uzantı 2.5: X'te ekranda görünen, habere bağlantı veren gönderiler ve arama sonuçları (yalnız okunur). Son 3 gün, en çok 600."""
    G = (request.get_json(silent=True) or {}).get("gonderiler") or []
    try:
        L = json.loads(X_KARTLI.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        L = []
    var = {x.get("id") for x in L}
    for g in G[:80]:
        gid = re.sub(r"\D", "", str(g.get("id") or ""))[:25]
        if gid and gid not in var and (g.get("metin") or g.get("kart")):
            L.append({"id": gid, "kullanici": re.sub(r"[^\w]", "", str(g.get("kullanici") or ""))[:30], "ad": str(g.get("ad") or "")[:80],
                      "metin": str(g.get("metin") or "")[:1500], "kart": str(g.get("kart") or "")[:600], "tarih": str(g.get("tarih") or "")[:40],
                      "arama": str(g.get("arama") or "")[:200], "zaman": time.time()})
            var.add(gid)
    sinir = time.time() - 3 * 86400
    X_KARTLI.write_text(json.dumps([x for x in L if x.get("zaman", 0) > sinir][-600:], ensure_ascii=False), encoding="utf-8")
    return jsonify({"tamam": True})


def _x_eslesen(link, baslik, hesap="", n=3):
    """Taslağın haberine en uygun X gönderileri (uzantının okuduklarından): aynı site kartı/bağlantısı +4, yayıncı hesabı +3, başlık kökü örtüşmesi
    (en çok +4). ≥5 puan alanlar, puan sırasıyla."""
    import paylasim as paylasim_modulu
    try:
        L = json.loads(X_KARTLI.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    alan = re.sub(r"^www\.", "", urllib.parse.urlparse(link or "").netloc.lower())
    kok = paylasim_modulu._kokler(baslik)
    out = []
    for x in L:
        govde = (x.get("kart", "") + " " + x.get("metin", "")).lower()
        p = (4 if alan and alan in govde else 0) + (3 if hesap and x.get("kullanici", "").lower() == hesap.lower() else 0) \
            + min(4, len(kok & paylasim_modulu._kokler(govde))) + (2 if x.get("izlenen") else 0)   # izlenen hesaplar (hesaplar.py) önce
        if p >= 5:
            out.append({**{k: x.get(k) for k in ("id", "kullanici", "ad", "metin", "tarih")}, "url": f"https://x.com/{x.get('kullanici')}/status/{x.get('id')}", "puan": p})
    return sorted(out, key=lambda x: -x["puan"])[:n]


@app.get("/api/x/gorulen")
def x_gorulen_liste():
    try:
        L = json.loads(X_GORULEN.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        L = []
    return jsonify(sorted(L, key=lambda x: -x.get("zaman", 0))[:12])


@app.post("/api/paylasim/<temel>/<int:i>/alinti")
def paylasim_alinti(temel, i):
    """{id}: taslağı son açılan X gönderisini alıntılayan bir tepkiye çevirir; {kaldir: true} bağlantı/alıntıyı kaldırır."""
    import paylasim as paylasim_modulu
    yol = _py_yol(temel); v = request.get_json(force=True) or {}
    if v.get("kaldir") or v.get("link"):         # {link}: kullanıcının kendi eklediği bağlantı (haber, video, gönderi adresi)
        link = str(v.get("link") or "").strip()
        if link and not re.match(r"^https?://\S+$", link):
            return jsonify({"hata": "Geçerli bir bağlantı yapıştırın (https:// ile başlayan)."}), 400
        with kilit:
            d = json.loads(yol.read_text(encoding="utf-8")); t = d["veri"]["paylasim"]["taslaklar"][i]
            t["paylas_link"] = link; t.pop("alinti", None)
            yol.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        return jsonify({"tamam": True})
    L = (json.loads(yol.read_text(encoding="utf-8"))["veri"].get("paylasim") or {}).get("taslaklar") or []
    tw = None                      # sıra: uzantının okuduğu gönderiler → taslağın kaynağındaki X gönderileri → yapıştırılan gönderi adresi (herkese açık gömme)
    try:
        tw = next((x for x in json.loads(X_GORULEN.read_text(encoding="utf-8")) if x.get("id") == str(v.get("id"))), None)
    except Exception:  # noqa: BLE001
        pass
    if not tw and 0 <= i < len(L):
        tw = next((x for x in (L[i].get("x_kaynak") or {}).get("gonderiler") or [] if x.get("id") == str(v.get("id"))), None)
    if not tw:
        try:
            tw = next((x for x in json.loads(X_KARTLI.read_text(encoding="utf-8")) if x.get("id") == str(v.get("id"))), None)
        except Exception:  # noqa: BLE001
            pass
    if not tw and v.get("url"):
        import kesif
        tw = kesif.x_gonderisi(str(v["url"]))
    if not tw:
        return jsonify({"hata": "Gönderi okunamadı. X'te gönderiyi açın ya da gönderinin bağlantısını yapıştırın."}), 404
    if not 0 <= i < len(L):
        abort(404)
    try:
        yeni = paylasim_modulu.alintiyla_yaz(L[i], tw)
    except Exception as e:  # noqa: BLE001
        return jsonify({"hata": f"Yazılamadı: {str(e)[:120]}"}), 500
    with kilit:
        d = json.loads(yol.read_text(encoding="utf-8")); L = d["veri"]["paylasim"]["taslaklar"]; L[i].update(yeni); L[i].pop("ilk_metin", None)
        yol.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return jsonify(L[i])


@app.get("/api/paylasim/<temel>/<int:i>/x-kaynak")
def paylasim_x_kaynak(temel, i):
    """Taslağın dış bağlantısının X'teki karşılığı (gömülü gönderiler + yayıncı hesabında arama); ilk istekte bulunur, taslağa yazılır."""
    import kesif
    yol = _py_yol(temel)
    L = (json.loads(yol.read_text(encoding="utf-8"))["veri"].get("paylasim") or {}).get("taslaklar") or []
    if not 0 <= i < len(L):
        abort(404)
    veri = json.loads(yol.read_text(encoding="utf-8"))["veri"]
    link = L[i].get("paylas_link") or veri.get("link") or ""
    oneri = L[i].get("x_alinti_onerisi")                      # haberi izlenen bir hesabın gönderisinden bulduysa (hesaplar.py) o gönderi en üstte
    def _eslesen(xk):
        E = _x_eslesen(link, veri.get("baslik") or "", xk.get("hesap", ""))
        return ([{**oneri, "puan": 99}] if oneri else []) + [e for e in E if not oneri or e.get("id") != oneri.get("id")]
    if L[i].get("x_kaynak") and not request.args.get("yenile"):
        xk = L[i]["x_kaynak"]
        return jsonify({**xk, "eslesen": _eslesen(xk)})
    xk = kesif.x_kaynak(link, veri.get("baslik") or "")
    with kilit:
        d = json.loads(yol.read_text(encoding="utf-8")); d["veri"]["paylasim"]["taslaklar"][i]["x_kaynak"] = xk
        yol.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return jsonify({**xk, "eslesen": _eslesen(xk)})


@app.post("/api/paylasim/<temel>/<int:i>/tetik")
def paylasim_tetik(temel, i):
    """Tetik (2026-10-23; kullanıcı: "kimse durup dururken paylaşmaz, uygun bir link veya tweet bul"): {} → uygun haber/gönderi adayları (taslakta
    `tetik_adaylari`); {sec: n} → taslak o içeriğe TEPKİ dilinde yeniden yazılır, bağlantı ya da alıntı eklenir."""
    import tetik
    yol = _py_yol(temel); v = request.get_json(silent=True) or {}
    L = (json.loads(yol.read_text(encoding="utf-8"))["veri"].get("paylasim") or {}).get("taslaklar") or []
    if not 0 <= i < len(L):
        abort(404)
    taslak = dict(L[i])
    if "sec" not in v:
        try:
            A = tetik.adaylar(taslak.get("konu") or "", taslak.get("metin") or "", en_cok=4, log=lambda m: print(m, flush=True))
        except Exception as e:  # noqa: BLE001
            return jsonify({"hata": f"Aranamadı: {str(e)[:120]}"}), 500
        with kilit:
            d = json.loads(yol.read_text(encoding="utf-8")); d["veri"]["paylasim"]["taslaklar"][i]["tetik_adaylari"] = A
            yol.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        return jsonify({"adaylar": A})
    try:
        a = (taslak.get("tetik_adaylari") or [])[int(v["sec"])]
        yeni = tetik.tepki_olarak_yaz({**taslak, "metin": taslak.get("tetik_oncesi") or taslak.get("metin")}, a)   # başka tetik denenirse ilk görüşten yazılır
    except (IndexError, ValueError, TypeError):
        return jsonify({"hata": "Aday bulunamadı; yeniden arayın."}), 404
    except Exception as e:  # noqa: BLE001
        return jsonify({"hata": f"Yazılamadı: {str(e)[:120]}"}), 500
    with kilit:
        d = json.loads(yol.read_text(encoding="utf-8")); T = d["veri"]["paylasim"]["taslaklar"][i]
        T.setdefault("ilk_metin", T.get("metin")); T.setdefault("tetik_oncesi", T.get("metin"))
        T.update({k: x for k, x in yeni.items() if k != "onceki" and x is not None}); T["ogrenilen_metin"] = T["metin"]
        if yeni.get("alinti") is None and "alinti" in T and a.get("tur") != "tweet":
            T.pop("alinti", None)
        yol.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return jsonify({"tamam": True, "metin": T["metin"]})


@app.post("/api/paylasim/<temel>/<int:i>/yorum")
def paylasim_yorum(temel, i):
    """{yorum}: kullanıcının taslağa yorumu. Taslak yoruma göre yeniden yazılır (opus) ve yorumdan kalıcı tercih öğrenilir (sonnet, aynı anda)."""
    import paylasim as paylasim_modulu
    yol = _py_yol(temel); yorum = str((request.get_json(silent=True) or {}).get("yorum") or "").strip()[:1500]
    if len(yorum) < 3:
        return jsonify({"hata": "Bir iki kelime yazın."}), 400
    L = (json.loads(yol.read_text(encoding="utf-8"))["veri"].get("paylasim") or {}).get("taslaklar") or []
    if not 0 <= i < len(L):
        abort(404)
    taslak = dict(L[i]); ogrenilen = {}
    t = threading.Thread(target=lambda: ogrenilen.update(tercih=paylasim_modulu.yorum_ogren(taslak, yorum)), daemon=True); t.start()
    try:
        yeni = paylasim_modulu.yeniden_yaz(taslak, yorum)
    except Exception as e:  # noqa: BLE001
        return jsonify({"hata": f"Yeniden yazılamadı: {str(e)[:120]}"}), 500
    t.join(timeout=90)
    with kilit:
        d = json.loads(yol.read_text(encoding="utf-8")); T = d["veri"]["paylasim"]["taslaklar"][i]
        T.setdefault("ilk_metin", T.get("metin")); T.setdefault("yorumlar", []).append({"yorum": yorum, "zaman": time.time(), "onceki": T.get("metin")})
        T.update({k: v for k, v in yeni.items() if k != "onceki"}); T["ogrenilen_metin"] = T["metin"]
        yol.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        import kalite
        kalite.kaydet("paylasim_yorum", yorum=yorum[:200], tercih=ogrenilen.get("tercih", ""))
    except Exception:  # noqa: BLE001
        pass
    return jsonify({"tamam": True, "metin": T["metin"], "tercih": ogrenilen.get("tercih", "")})


_duzeltme_zaman = {}


def _duzeltmeden_ogren_sonra(yol, i, anahtar, bekle=90):
    """Elle düzenlemeden öğrenme (paylaşmayı beklemeden): son düzenlemeden 90 sn sonra (kullanıcı yazmayı bitirince) bir kez; aynı metin iki kez öğrenilmez."""
    import paylasim as paylasim_modulu
    time.sleep(bekle)
    if time.time() - _duzeltme_zaman.get(anahtar, 0) < bekle - 1:
        return                                  # bu arada yeni düzenleme geldi; onun zamanlayıcısı öğrenecek
    try:
        with kilit:
            d = json.loads(yol.read_text(encoding="utf-8")); T = d["veri"]["paylasim"]["taslaklar"][i]
            once, sonra = T.get("ogrenilen_metin") or T.get("ilk_metin") or "", T.get("metin") or ""
            if not once or once.strip() == sonra.strip():
                return
            T["ogrenilen_metin"] = sonra
            yol.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        paylasim_modulu.duzeltme_ogren(once, sonra, paylasim_modulu.taslak_is_turu(T), "duzenledi")
    except Exception:  # noqa: BLE001
        pass


@app.post("/api/x/istatistik")
def x_istatistik():
    """Chrome uzantısının X'ten YALNIZCA OKUYARAK getirdiği kendi gönderi sayıları. Yeterli veri birikince haftada bir dersler çıkarılır."""
    import performans
    n = performans.kaydet((request.get_json(silent=True) or {}).get("gonderiler") or [])
    def _dogrula():                                           # 'paylaştım' denen taslak X'te gerçekten çıktı mı (24 Ekim)
        tanindi = []
        with kilit:
            try:
                performans.yayin_dogrula()
                tanindi = performans.oto_tani()               # işaretlenmeden paylaşılanlar da (24 Ekim)
            except Exception as e:  # noqa: BLE001
                print(f"Yayın doğrulaması yapılamadı: {e}", flush=True)
        _oto_tanindi_ogren(tanindi)
    threading.Thread(target=_dogrula, daemon=True).start()
    try:
        import claude_yaz
        if claude_yaz.arka_plan_uygun():
            threading.Thread(target=performans.dersler, daemon=True).start()
    except Exception:  # noqa: BLE001
        pass
    return jsonify({"tamam": True, "n": n})


def _oto_tanindi_ogren(tanindi):
    """X'te kendiliğinden tanınan paylaşımlar 'Evet, paylaştım' ile aynı yoldan öğretir: ses örneği, onaylı havuz, görüş, düzeltme çifti."""
    import paylasim as pm
    for o in tanindi or []:
        try:
            t = o["taslak"]
            pm.ogren("paylasilan", t["metin"]); pm.havuza_ekle(t); pm.gorus_ekle_paylasimdan(t["metin"])
            if o["once"] and o["once"].strip() != t["metin"].strip():
                pm.duzeltme_ogren(o["once"], t["metin"], pm.taslak_is_turu(t), "dogrulandi")
            import kalite
            kalite.kaydet("paylasim_karar", karar="paylasildi", neden="X'te kendiliğinden tanındı", duzenlendi=bool(t.get("duzenlendi")), alan=t.get("alan", ""))
            print(f"Ghost: X'te paylaşılan taslak tanındı ({t.get('yayin', {}).get('benzerlik')}): {t['metin'][:70]}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"Tanınan paylaşımdan öğrenilemedi: {e}", flush=True)


@app.get("/api/x/performans")
def x_performans():
    import performans
    if request.args.get("dersler") == "1":
        performans.dersler(zorla=True)
    return jsonify(performans.ozet(int(request.args.get("gun", 30))))


@app.post("/api/paylasim/<temel>/elenen/<int:j>")
def paylasim_elenen_yaz(temel, j):
    """Elenen fikir için 'Yine de yaz' (okur eşiği olmadan; arka planda)."""
    yol = _py_yol(temel)
    if paylasim_durum.get(temel, {}).get("calisiyor"):
        return jsonify({"hata": "Bu kaynak için zaten yazılıyor."}), 409

    def _calis():
        import paylasim as paylasim_modulu
        paylasim_durum[temel] = {"calisiyor": True, "log": ["Elenen fikir yazılıyor"], "hata": ""}
        try:
            paylasim_modulu.elenen_yaz(yol, j)
        except Exception as e:  # noqa: BLE001
            paylasim_durum[temel]["hata"] = str(e)[:200]
        paylasim_durum[temel]["calisiyor"] = False
    threading.Thread(target=_calis, daemon=True).start()
    return jsonify({"tamam": True})


@app.post("/api/ghost/yaz")
def ghost_yaz():
    """Ghost'a doğrudan girdi: video linki → yazıya dökülür, sonra taslak; makale linki / yapıştırılan yazı / fikir → hemen taslak (arka planda)."""
    import paylasim as paylasim_modulu
    girdi = str((request.get_json(silent=True) or {}).get("girdi") or "").strip()[:40000]
    if len(girdi) < 12:
        return jsonify({"hata": "Bir link, yazı ya da birkaç cümlelik bir fikir yazın."}), 400
    tur = paylasim_modulu.girdi_turu(girdi)
    if tur in ("x", "yazi_link"):
        # 23 Ekim: bağlantı → Ghost karar verir (alıntıla ve şunu de / fikri kendi gönderine çevir / geç) ve son metni verir
        import kesif
        if tur == "x":
            tw = kesif.x_gonderisi(girdi)
            if not tw:
                return jsonify({"hata": "Bu X gönderisi okunamadı (gizli hesap ya da silinmiş olabilir). Metnini kopyalayıp yapıştırın."}), 400
            temel = paylasim_modulu.ghost_kaydi(girdi, "x", f"@{tw['kullanici']}: {tw['metin'][:70]}", tw["url"], tw["metin"], ek={"x_gonderi": tw})
        else:
            try:
                baslik, metin = paylasim_modulu.sayfa_metni(girdi)
            except Exception as e:  # noqa: BLE001
                return jsonify({"hata": str(e)[:200]}), 400
            temel = paylasim_modulu.ghost_kaydi(girdi, "yazi", baslik, girdi, metin)

        def _karar(t=temel):
            paylasim_durum[t] = {"calisiyor": True, "log": [], "hata": ""}
            try:
                paylasim_modulu.link_karari(_py_yol(t), log=lambda m: paylasim_durum[t]["log"].append(m))
            except Exception as e:  # noqa: BLE001
                paylasim_durum[t]["hata"] = str(e)
            paylasim_durum[t]["calisiyor"] = False
        threading.Thread(target=_karar, daemon=True).start()
        return jsonify({"tamam": True, "tur": tur, "temel": temel})
    if tur == "video":
        for t, is_ in list(isler.items()):
            if is_.get("link") == girdi and is_.get("durum") in ("sirada", "calisiyor"):
                is_["ghost"] = True
                return jsonify({"tamam": True, "tur": "video"})
        mevcut = next((js for js in KLASOR.glob("transkript_*.json") if (lambda v: v.get("link") == girdi)(_oku_veri(js))), None)
        if mevcut:      # bu video zaten yazıya dökülmüş: doğrudan taslak
            temel = mevcut.stem
        else:
            r = _baslat({"link": girdi, "islem": "transkript", "konusmaci": False, "ozet": True, "ghost": True})
            j = r[0].get_json() if isinstance(r, tuple) else r.get_json()
            if (j or {}).get("hata"):
                return jsonify({"hata": j["hata"]}), 400
            return jsonify({"tamam": True, "tur": "video"})
    else:
        baslik, metin, link = "", girdi, ""
        if tur == "yazi_link":
            try:
                baslik, metin = paylasim_modulu.sayfa_metni(girdi)
            except Exception as e:  # noqa: BLE001
                return jsonify({"hata": str(e)[:200]}), 400
            link = girdi
        ayr = paylasim_modulu.taslak_ayir(girdi) if tur in ("fikir", "yazi") else None
        if ayr:                                   # 25 Ekim: kendi taslağınız + "şunu ekle/düzenle" → sınırlı düzenleme (fikir defterine girmez)
            tur, metin = "taslak", ayr[0]
            temel = paylasim_modulu.ghost_kaydi(girdi, "taslak", "", "", metin, ek={"istek": ayr[1][:1000]})
        else:
            temel = paylasim_modulu.ghost_kaydi(girdi, "yazi" if tur == "yazi_link" else tur, baslik, link, metin)
        if tur == "fikir":
            import ghost_defter
            x = ghost_defter.not_ekle(girdi, "yazi")
            if x:
                ghost_defter.not_kullanildi(x["id"], temel)
    if paylasim_durum.get(temel, {}).get("calisiyor"):
        return jsonify({"tamam": True, "tur": tur})
    threading.Thread(target=_paylasim_arka, args=(temel,), daemon=True).start()
    return jsonify({"tamam": True, "tur": tur, "temel": temel})


def _oku_veri(js):
    try:
        return json.loads(js.read_text(encoding="utf-8")).get("veri") or {}
    except Exception:  # noqa: BLE001
        return {}


@app.post("/api/paylasim/<temel>/<int:i>")
def paylasim_isaretle(temel, i):
    """{gizli: true, neden} öneriyi kaldırır (neden öğrenilir); {paylasildi: true, metin} paylaşıldı (son metin ses örneği olur);
    {metin} kullanıcının düzenlemesini kaydeder."""
    import paylasim as paylasim_modulu
    yol = _py_yol(temel)
    v = request.get_json(force=True) or {}
    with kilit:
        d = json.loads(yol.read_text(encoding="utf-8"))
        L = (d["veri"].get("paylasim") or {}).get("taslaklar") or []
        if not 0 <= i < len(L):
            abort(404)
        if isinstance(v.get("eski"), str) and v["eski"].strip() != (L[i].get("metin") or "").strip():
            # istemci başka bir taslağın metnini sanıyor (eski sekme, bayat kart): yazma. 21 Ekim'de 6 taslağın metni böyle ezilmişti.
            return jsonify({"hata": "Bu taslak bu arada değişmiş; sayfayı yenileyip yeniden deneyin."}), 409
        if isinstance(v.get("metin"), str) and v["metin"].strip():
            if v["metin"].strip() != L[i].get("metin"):
                L[i]["duzenlendi"] = True
                L[i].setdefault("ilk_metin", L[i].get("metin"))
            L[i]["metin"] = v["metin"].strip()[:4000]; L[i]["karakter"] = len(L[i]["metin"])
            if v.get("ilk_daha_iyi"):                 # 25 Ekim: editörlerden geçen hal yerine ilk taslağı seçti (editörlerin aşırı müdahalesi ölçülür)
                L[i]["ilk_daha_iyi"] = True
                try:
                    import kalite
                    kalite.kaydet("ilk_taslak_tercih", tur=L[i].get("karisim_tur") or L[i].get("bicim") or "", alan=L[i].get("alan_kod") or "")
                except Exception:  # noqa: BLE001
                    pass
            if L[i].get("duzenlendi") and not v.get("paylasildi"):
                an = f"{temel}#{i}"; _duzeltme_zaman[an] = time.time()
                threading.Thread(target=_duzeltmeden_ogren_sonra, args=(yol, i, an), daemon=True).start()
        for an in ("gizli", "paylasildi"):
            if an in v:
                L[i][an] = bool(v[an])
        if "gizli" in v and not v["gizli"]:
            L[i]["geri_getirildi"] = True; L[i].pop("degistirildi", None)    # kullanıcı geri getirdi: budama bir daha dokunmaz
        if v.get("gizli"):
            L[i].pop("degistirildi", None)                                    # kullanıcının kendi kaldırması (öğrenme ve sayaç bunu sayar)
        if v.get("paylasildi"):
            L[i]["paylasim_zaman"] = time.time()
        if v.get("neden"):
            L[i]["red_nedeni"] = str(v["neden"])[:200]
        if v.get("neden_metin"):                      # "Paylaşmadım, çünkü…" (kendi cümlesi)
            L[i]["red_nedeni"] = str(v["neden_metin"])[:300]
        if v.get("neden_iyi"):
            L[i]["neden_iyi"] = str(v["neden_iyi"])[:120]
        if v.get("kopyalandi"):                       # yalnız durum; beğeni ya da yayın sayılmaz (kopyalayıp vazgeçmiş olabilir)
            L[i]["kopyalandi"] = time.time()
        if "begendi" in v:                            # 27 Ekim: elden geçirirken "Kalsın" (zayıf olumlu sinyal; plan öne alır, ses bloğuna girer)
            if v["begendi"]:
                L[i]["begendi"] = time.time()
            else:
                L[i].pop("begendi", None)
        taslak = dict(L[i])
        yol.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        import kalite
        if v.get("paylasildi") or v.get("gizli"):
            kalite.kaydet("paylasim_karar", karar="paylasildi" if v.get("paylasildi") else "kaldirildi", neden=str(v.get("neden") or ""),
                          duzenlendi=bool(taslak.get("duzenlendi")), alan=taslak.get("alan", ""))
        if v.get("neden_iyi"):
            paylasim_modulu.havuz_neden(taslak["metin"], v["neden_iyi"])
        if "begendi" in v:
            paylasim_modulu.begeni(taslak, bool(v["begendi"]))
            if v["begendi"]:
                kalite.kaydet("paylasim_karar", karar="begendi", alan=taslak.get("alan", ""), tur=taslak.get("karisim_tur") or taslak.get("bicim") or "")
        if v.get("paylasildi"):
            paylasim_modulu.ogren("paylasilan", taslak["metin"])
            paylasim_modulu.havuza_ekle(taslak)
            threading.Thread(target=paylasim_modulu.gorus_ekle_paylasimdan, args=(taslak["metin"],), daemon=True).start()
            once = taslak.get("ogrenilen_metin") or taslak.get("ilk_metin")
            if once and once.strip() != taslak["metin"].strip():
                threading.Thread(target=paylasim_modulu.duzeltme_ogren, args=(once, taslak["metin"]), daemon=True).start()
        if v.get("gizli") and v.get("neden_metin"):
            ogrenilen = paylasim_modulu.yorum_ogren(taslak, "Bunu paylaşmadım, çünkü: " + str(v["neden_metin"])[:600])   # türünü ayırır: konu/üslup/bilgi/deneyim/tek
            return jsonify({"tamam": True, "ogrenilen": ogrenilen or "Kaydedildi; bu bir kerelik bir neden olarak not edildi"})
        if v.get("gizli"):
            paylasim_modulu.red_kaydet(taslak, v.get("neden") or "")
        elif "gizli" in v and not v["gizli"]:
            paylasim_modulu.red_geri_al(taslak)
    except Exception:  # noqa: BLE001
        pass
    return jsonify({"tamam": True})


@app.post("/api/paylasim/<temel>/<int:i>/parlat")
def paylasim_parlat(temel, i):
    """Son cümle için 3 seçenek (opus, ~20 sn); yazmaz: kullanıcı seçince metin güncellemesi ({metin, eski}) ile kaydedilir."""
    import paylasim as paylasim_modulu
    yol = _py_yol(temel)
    L = (json.loads(yol.read_text(encoding="utf-8"))["veri"].get("paylasim") or {}).get("taslaklar") or []
    if not 0 <= i < len(L):
        abort(404)
    try:
        return jsonify({"secenekler": paylasim_modulu.son_cumle_alternatifleri(L[i])})
    except Exception as e:  # noqa: BLE001
        return jsonify({"hata": f"Seçenek çıkmadı: {str(e)[:120]}"}), 500


@app.post("/api/paylasim/<temel>/<int:i>/yeniden")
def paylasim_yeniden(temel, i):
    """{talimat: kisa|keskin|zincir|tek|<serbest>} tek taslağı yeniden yazar (opus, ~20-40 sn)."""
    import paylasim as paylasim_modulu
    yol = _py_yol(temel)
    talimat = str((request.get_json(force=True) or {}).get("talimat") or "").strip()[:400]
    if not talimat:
        return jsonify({"hata": "Talimat yok."}), 400
    L = (json.loads(yol.read_text(encoding="utf-8"))["veri"].get("paylasim") or {}).get("taslaklar") or []
    if not 0 <= i < len(L):
        abort(404)
    try:
        yeni = paylasim_modulu.yeniden_yaz(L[i], talimat)
    except Exception as e:  # noqa: BLE001
        return jsonify({"hata": f"Yeniden yazılamadı: {str(e)[:120]}"}), 500
    with kilit:
        d = json.loads(yol.read_text(encoding="utf-8"))
        L = d["veri"]["paylasim"]["taslaklar"]; L[i].update(yeni)
        yol.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return jsonify(L[i])


@app.post("/api/paylasim/<temel>/<int:i>/dayanak")
def paylasim_dayanak(temel, i):
    """{yorum}: kişinin kendi karşılığıyla taslağı yeniden kurar (opus, ~30 sn); taslak 'dayanaklı' olur."""
    import paylasim as paylasim_modulu
    yol = _py_yol(temel)
    yorum = str((request.get_json(force=True) or {}).get("yorum") or "").strip()[:1500]
    if len(yorum) < 8:
        return jsonify({"hata": "Bir iki cümle yazın."}), 400
    L = (json.loads(yol.read_text(encoding="utf-8"))["veri"].get("paylasim") or {}).get("taslaklar") or []
    if not 0 <= i < len(L):
        abort(404)
    try:
        yeni = paylasim_modulu.dayanakla_yaz(L[i], yorum)
    except Exception as e:  # noqa: BLE001
        return jsonify({"hata": f"Yazılamadı: {str(e)[:120]}"}), 500
    with kilit:
        d = json.loads(yol.read_text(encoding="utf-8"))
        L = d["veri"]["paylasim"]["taslaklar"]; L[i].update(yeni); L[i].pop("ilk_metin", None); L[i]["duzenlendi"] = False
        yol.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    if (request.get_json(silent=True) or {}).get("gorus"):   # "Bununla ilgili şöyle düşünüyorum": kendi sözü → görüş defterine ONAYLI, fikir defterine
        try:
            paylasim_modulu._gorus_yaz([{"konu": str(L[i].get("konu") or "")[:60], "gorus": yorum[:400], "alan": L[i].get("alan_kod") or "", "kanit": yorum[:120],
                                         "tarih": time.strftime("%Y-%m-%d"), "kaynak": "kendi sözü (onaylı)", "durum": "onayli"}])
            import ghost_defter
            ghost_defter.not_ekle(yorum, "dusunce", ek={"taslak": str(L[i].get("metin") or "")[:300]})
        except Exception:  # noqa: BLE001
            pass
    return jsonify(L[i])


def _paylasim_arka(temel):
    import paylasim as paylasim_modulu
    paylasim_durum[temel] = {"calisiyor": True, "log": [], "hata": ""}
    try:
        paylasim_modulu.uret(_py_yol(temel), log=lambda m: paylasim_durum[temel]["log"].append(m))
    except SystemExit as e:
        paylasim_durum[temel]["hata"] = str(e)
    except Exception as e:  # noqa: BLE001
        paylasim_durum[temel]["hata"] = str(e)
    paylasim_durum[temel]["calisiyor"] = False


@app.post("/api/paylasim/<temel>")
def paylasim_uret(temel):
    _temel_dogrula(temel)
    if paylasim_durum.get(temel, {}).get("calisiyor"):
        return jsonify({"hata": "Zaten hazırlanıyor."}), 409
    threading.Thread(target=_paylasim_arka, args=(temel,), daemon=True).start()
    return jsonify({"tamam": True})


@app.get("/api/paylasim-durum/<temel>")
def paylasim_durum_get(temel):
    tj = _py_yol(temel)
    d = paylasim_durum.get(temel) or {"calisiyor": False, "log": [], "hata": ""}
    veri = json.loads(tj.read_text(encoding="utf-8"))["veri"]
    return jsonify({**d, "paylasim": veri.get("paylasim")})


drive_oku_durum = {"calisiyor": False, "hata": ""}
secki_durum = {"calisiyor": False, "son": 0, "hata": ""}
SECKI_YAZILAN = KAYIT / "secki" / "yazilan.json"


@app.get("/api/drive-oku")
def drive_oku_get():
    import seckiler
    return jsonify({"bagli": seckiler.bagli(), **drive_oku_durum})


@app.post("/api/drive-oku/baglan")
def drive_oku_baglan():
    """Drive'a YALNIZCA OKUMA izni (ChatGPT'nin günlük seçkisi ve Öneri Havuzu için). Tarayıcıda Google onay sayfası açılır; onayı kullanıcı verir."""
    if not RCLONE.exists():
        return jsonify({"hata": "Drive aracı kurulu değil."}), 503
    if not drive_oku_durum["calisiyor"]:
        threading.Thread(target=_rclone_yetki, args=("gdrive_oku", "drive.readonly", drive_oku_durum), daemon=True).start()
        drive_oku_durum["calisiyor"] = True
    return jsonify({"tamam": True})


@app.delete("/api/drive-oku")
def drive_oku_kopar():
    subprocess.run([str(RCLONE), "config", "delete", "gdrive_oku"], capture_output=True, timeout=20)
    return jsonify({"tamam": True})


def _secki_tazele(zorla=False):
    import seckiler
    if secki_durum["calisiyor"]:
        return
    secki_durum.update({"calisiyor": True, "hata": ""})
    try:
        seckiler.getir(zorla=zorla)
        seckiler.havuz(zorla=zorla)
    except Exception as e:  # noqa: BLE001
        secki_durum["hata"] = str(e)[:200]
    finally:
        secki_durum.update({"calisiyor": False, "son": time.time()})


def _secki_yazilan():
    try:
        return json.loads(SECKI_YAZILAN.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


@app.get("/api/secki")
def secki_get():
    """ChatGPT'nin son günlük seçkisi + Öneri Havuzu'ndaki paylaşım fikirleri (önbellekten; eskiyse arka planda tazelenir)."""
    import seckiler
    bagli = seckiler.bagli()
    if bagli and time.time() - secki_durum["son"] > 1800 and not secki_durum["calisiyor"]:
        threading.Thread(target=_secki_tazele, args=(request.args.get("zorla") == "1",), daemon=True).start()
    s = None
    for n in range(3):
        f = KAYIT / "secki" / f"{(datetime.date.today() - datetime.timedelta(days=n)).isoformat()}.json"
        if f.exists():
            s = json.loads(f.read_text(encoding="utf-8")); break
    hv = []
    try:
        hv = json.loads((KAYIT / "secki" / "havuz.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass
    return jsonify({"bagli": bagli, "secki": s, "havuz": hv, "yazilan": _secki_yazilan(), "calisiyor": secki_durum["calisiyor"], "hata": secki_durum["hata"]})


@app.post("/api/secki/yaz")
def secki_yaz():
    """{tur: konu|havuz, tarih, no | id, deneyim} → Ghost taslağı (kişinin kendi karşılığı merkezde); arka planda."""
    import paylasim as paylasim_modulu
    import seckiler
    v = request.get_json(silent=True) or {}
    deneyim = str(v.get("deneyim") or "").strip()[:2000]
    if v.get("tur") == "havuz":
        konu = next((x for x in json.loads((KAYIT / "secki" / "havuz.json").read_text(encoding="utf-8")) if x["id"] == v.get("id")), None)
        if not konu:
            return jsonify({"hata": "Fikir bulunamadı."}), 404
        anahtar, baslik, link, secki = f"havuz:{konu['id']}", konu["oneri"], konu.get("kaynak") or "", None
    else:
        tarih = re.sub(r"[^0-9-]", "", str(v.get("tarih") or ""))[:10]
        f = KAYIT / "secki" / f"{tarih}.json"
        if not f.exists():
            return jsonify({"hata": "Seçki bulunamadı."}), 404
        secki = json.loads(f.read_text(encoding="utf-8"))
        konu = next((x for x in secki.get("konular") or [] if x["no"] == int(v.get("no") or 0)), None)
        if not konu:
            return jsonify({"hata": "Konu bulunamadı."}), 404
        anahtar, baslik, link = f"{tarih}:{konu['no']}", konu["baslik"], (konu.get("kaynaklar") or [""])[0]
    girdi = seckiler.ghost_girdisi(konu, deneyim, secki)
    temel = paylasim_modulu.ghost_kaydi(girdi, "secki", baslik, link, girdi, deneyim=deneyim, ek={"secki": anahtar})
    with kilit:
        y = _secki_yazilan(); y[anahtar] = {"temel": temel, "zaman": time.time(), "deneyim": bool(deneyim)}
        SECKI_YAZILAN.parent.mkdir(parents=True, exist_ok=True); SECKI_YAZILAN.write_text(json.dumps(y, ensure_ascii=False, indent=1), encoding="utf-8")
    threading.Thread(target=_paylasim_arka, args=(temel,), daemon=True).start()
    return jsonify({"tamam": True, "temel": temel})


# ----------------------------------------------------------------------------- Ghost zamanlı işleri (2026-10-29: Meet'in hazırlık notu döngüsünden ayrıldı;
# ürünler ayrı depo olabilsin diye). Keşif turları, konu toplantısı, defter, maç karnesi, sabah ve liste hatırlatmaları; dakikada bir.
def _ghost_kurulu():
    try:
        import ghost_kurulum
        return ghost_kurulum.kurulu_mu()
    except Exception:  # noqa: BLE001
        return False


def _ghost_zaman_dongu():
    while True:
        time.sleep(60)
        if not _ghost_kurulu():                            # ilk açılış kurulumu yapılmadan keşif ve hatırlatma yok (2026-10-29)
            continue
        try:                                               # Ghost keşfi: 07.30 ve 14.00'ten sonra birer kez (kaynak tarama + taslaklar)
            zt = time.localtime(); dilim = "ogle" if zt.tm_hour >= 14 else ("sabah" if (zt.tm_hour, zt.tm_min) >= (7, 30) else "")
            isaret = KAYIT / ".kesif_son"; anahtar = time.strftime("%Y-%m-%d") + ":" + dilim
            if dilim and ayarlar_oku().get("ghost_kesif", True) and (not isaret.exists() or isaret.read_text(encoding="utf-8") != anahtar):
                import claude_yaz
                import ghost_tempo
                if dilim == "ogle" and not ghost_tempo.ogle_turu_gerekli():
                    # 27 Ekim: sabahın önerilerine bakılmadıysa öğle turu yazılmaz (aynı paketin üstüne yenisi; haftada ~70 boşa Claude çağrısı)
                    isaret.write_text(anahtar, encoding="utf-8")
                    ghost_tempo.atlandi("öğle turu", "sabahın önerilerine bakılmadı")
                    print("Ghost: öğle turu atlandı (sabahın önerilerine bakılmadı)", flush=True)
                elif claude_yaz.hazir():
                    isaret.write_text(anahtar, encoding="utf-8")
                    threading.Thread(target=_kesif_calistir, args=("", dilim), daemon=True).start()
        except Exception as e:  # noqa: BLE001
            print(f"Keşif döngüsü hatası: {e}", flush=True)
        try:                                               # konu toplantısı: süresi dolan toplantının yazımı (konu_toplantisi.py)
            import konu_toplantisi
            for tid in konu_toplantisi.bekleyen():
                threading.Thread(target=_konu_toplantisi_bitir, args=(tid,), daemon=True).start()
        except Exception as e:  # noqa: BLE001
            print(f"Keşif döngüsü hatası: {e}", flush=True)
        try:                                               # Ghost defteri: 10.00 günün soruları (bildirim), 21.00 görüş adayları + birleştirme önerileri
            import ghost_defter
            zt = time.localtime(); gun = time.strftime("%Y-%m-%d")
            if zt.tm_hour >= 10 and not (ghost_defter.SORU / f"{gun}.json").exists() and ayarlar_oku().get("ghost_sorular", True):
                import claude_yaz
                if claude_yaz.hazir():
                    def _s():
                        k = ghost_defter.sorular()
                        if k.get("sorular"):
                            _bildir(f"Ghost: bugün size {len(k['sorular'])} sorum var", k["sorular"][0]["soru"][:150])
                    threading.Thread(target=_ghost_defter_is, args=("sorular", _s), daemon=True).start()
            isaret = KAYIT / ".ghost_aksam"
            if zt.tm_hour >= 21 and (not isaret.exists() or isaret.read_text(encoding="utf-8") != gun):
                isaret.write_text(gun, encoding="utf-8")
                def _a():
                    ghost_defter.gorus_adaylari_tara(); ghost_defter.birlestirme_onerileri()
                threading.Thread(target=_ghost_defter_is, args=("aksam", _a), daemon=True).start()
        except Exception as e:  # noqa: BLE001
            print(f"Ghost defter döngüsü hatası: {e}", flush=True)
        try:                                               # maç (oranlar.py): saatte bir, tahmini yapılmış biten maçın sonucu karneye; maç günü piyasa oranı kaydı
            isaret = KAYIT / ".mac_oto"
            if not isaret.exists() or time.time() - isaret.stat().st_mtime > 3600:
                isaret.write_text(time.strftime("%Y-%m-%d %H:%M"), encoding="utf-8")
                def _m():
                    import ghost_defter
                    import oranlar
                    for g in ghost_defter.mac_sonuc_oto():
                        _bildir("Maç karnesi güncellendi", f"{g} maçının sonucu işlendi")
                    if ghost_defter.mac_gunu().get("var"):
                        oranlar.piyasa_kaydet()
                threading.Thread(target=_m, daemon=True).start()
        except Exception as e:  # noqa: BLE001
            print(f"Maç sonucu döngüsü hatası: {e}", flush=True)
        try:                                               # Ghost: sabah 09.30'dan sonra bir kez "bugünün gönderisi hazır"
            gun = time.strftime("%Y-%m-%d"); isaret = KAYIT / ".ghost_hatirlatma"; zt = time.localtime()
            if (zt.tm_hour, zt.tm_min) >= (9, 30) and (not isaret.exists() or isaret.read_text(encoding="utf-8") != gun) and ayarlar_oku().get("ghost_bildirim", True):
                isaret.write_text(gun, encoding="utf-8")
                b = next((t for t in _paylasim_verisi()["taslaklar"] if t.get("plan_gun") == "Bugün"), None)
                if b:
                    ilk = re.split(r"(?<=[.!?…])\s", b["metin"].strip())[0]
                    _bildir("Bugünün gönderisi hazır", ilk[:150])
        except Exception as e:  # noqa: BLE001
            print(f"Ghost hatırlatma hatası: {e}", flush=True)
        try:                                               # izlenen hesaplar (24 Ekim): 20 saattir X listesine bakılmadıysa 09.00'dan sonra bir kez hatırlat
            import hesaplar
            gun = time.strftime("%Y-%m-%d"); isaret = KAYIT / ".liste_hatirlatma"; zt = time.localtime()
            if (zt.tm_hour >= 9 and (not isaret.exists() or isaret.read_text(encoding="utf-8") != gun) and ayarlar_oku().get("ghost_bildirim", True)
                    and hesaplar.x_hesaplari() and time.time() - hesaplar.son_liste_bakisi() > 20 * 3600):
                isaret.write_text(gun, encoding="utf-8")
                _bildir("X listenize bir göz atın", "Ghost öğleden sonraki önerileri listenizdeki ve Instagram favorilerinizdeki paylaşımlardan da seçer")
        except Exception as e:  # noqa: BLE001
            print(f"Liste hatırlatma hatası: {e}", flush=True)


threading.Thread(target=_ghost_zaman_dongu, daemon=True).start()
