# sunucu/19_ghost_gelisim.py — Ghost'un kendini besleyen yapısı (2026-10-24): haftanın hikâyesi, yanıt taslakları,
# haftalık öz değerlendirme + gelişme takibi (ghost_gelisim.py) ve telefonda tek kart sayfası (/tek). Tek döngü dakikada bir uyanır.

ghost_gelisim_durum = {}     # ad → {calisiyor, son, hata, sonuc}


def _gg_is(ad, fn, *arg, **kw):
    """Uzun Ghost işini arka planda, tek kopya olarak çalıştırır."""
    d = ghost_gelisim_durum.setdefault(ad, {})
    if d.get("calisiyor"):
        return False
    d.update({"calisiyor": True, "hata": "", "baslangic": time.time()})

    def _calis():
        try:
            d["sonuc"] = fn(*arg, **kw)
        except Exception as e:  # noqa: BLE001
            d["hata"] = str(e)[:200]; print(f"Ghost {ad} yapılamadı: {e}", flush=True)
        finally:
            d["calisiyor"] = False; d["son"] = time.time()
    threading.Thread(target=_calis, daemon=True).start()
    return True


def _gg_isaret(ad, anahtar):
    """Günde/haftada bir işler için işaret dosyası: anahtar değiştiyse True ve yazar."""
    f = KAYIT / f".gg_{ad}"
    if f.exists() and f.read_text(encoding="utf-8") == anahtar:
        return False
    f.write_text(anahtar, encoding="utf-8")
    return True


def _gg_log(m):
    print(m, flush=True)


def _ghost_gelisim_dongu():
    time.sleep(90)
    while True:
        if not _ghost_kurulu():
            time.sleep(60)
            continue
        try:
            A = ayarlar_oku()
            zt = time.localtime()
            import claude_yaz
            uygun = claude_yaz.arka_plan_uygun()
            if uygun and zt.tm_hour >= 13 and A.get("ghost_yanit", True) and _gg_isaret("yanit", time.strftime("%Y-%m-%d")):
                import ghost_tempo
                if ghost_tempo.yan_isler_uygun():
                    import ghost_yanit
                    _gg_is("yanıt taslakları", ghost_yanit.uret, log=_gg_log)
                else:
                    ghost_tempo.atlandi("yanıt taslakları", "iki gündür bakılmadı")
            if uygun and zt.tm_wday == 3 and zt.tm_hour >= 15 and A.get("ghost_hikaye", True) and _gg_isaret("hikaye", time.strftime("%G-%V")):
                import ghost_hikaye

                def _hk():
                    t = ghost_hikaye.uret(log=_gg_log)
                    if t:
                        _bildir("Ghost: haftanın hikâyesi hazır", "Bugün sekmesinin başında; kaynaklı bir zincir")
                    return t
                _gg_is("haftanın hikâyesi", _hk)
            if _gg_isaret("yerimi", time.strftime("%Y-%m-%d %H")):    # okunmamış yer imi kaldıysa saatte bir devam (her turda en çok 8)
                import yerimleri
                if ayarlar_oku().get("yerimleri_incele", True) and (yerimleri.ozet()["bekleyen"] or any(not x.get("tur") for x in yerimleri.oku())):
                    _gg_is("yer imleri okunuyor", yerimleri.isle, log=_gg_log)
            if zt.tm_hour >= 6 and _gg_isaret("ihmal", time.strftime("%Y-%m-%d")):   # az beslenen alanlar her gün (ucuz, Claude yok)
                import ghost_gelisim
                d = ghost_gelisim.oku(); d["aktif"]["ihmal"] = ghost_gelisim.ihmal_edilenler(); ghost_gelisim.yaz(d)
            if uygun and zt.tm_wday == 0 and zt.tm_hour >= 8 and A.get("ghost_gelisim", True) and _gg_isaret("gelisim", time.strftime("%G-%V")):
                import ghost_gelisim

                def _gl():
                    r = ghost_gelisim.ozdegerlendirme(log=_gg_log)
                    ghost_gelisim.takip(log=_gg_log)
                    if r:
                        _bildir("Ghost bu haftayı değerlendirdi", (r.get("ozet") or "")[:150])
                    return bool(r)
                _gg_is("haftalık değerlendirme", _gl)
        except Exception as e:  # noqa: BLE001
            print(f"Ghost gelişim döngüsü: {e}", flush=True)
        time.sleep(60)


threading.Thread(target=_ghost_gelisim_dongu, daemon=True).start()


@app.get("/api/ghost/gelisim")
def ghost_gelisim_get():
    import ghost_gelisim
    return jsonify({**ghost_gelisim.durum(), "isler": {k: {a: v.get(a) for a in ("calisiyor", "son", "hata")} for k, v in ghost_gelisim_durum.items()}})


@app.post("/api/ghost/gelisim")
def ghost_gelisim_post():
    """{islem: degerlendir | takip | geri_al {zaman} | oneri {id, kabul} | not_sil {i} | asama {ad, acik}}."""
    import ghost_gelisim
    v = request.get_json(silent=True) or {}
    i = v.get("islem")
    if i == "degerlendir":
        return jsonify({"tamam": _gg_is("haftalık değerlendirme", lambda: ghost_gelisim.ozdegerlendirme(zorla=True, log=_gg_log))})
    if i == "takip":
        return jsonify({"tamam": _gg_is("gelişme takibi", lambda: ghost_gelisim.takip(zorla=True, log=_gg_log))})
    if i == "geri_al":
        return jsonify({"tamam": ghost_gelisim.geri_al(v.get("zaman") or 0)})
    if i == "oneri":
        return jsonify({"tamam": bool(ghost_gelisim.oneri_karar(str(v.get("id") or ""), bool(v.get("kabul")),
                                                            v.get("durum") if v.get("durum") in ("kabul", "red", "sonra") else None))})
    if i == "not_sil":
        return jsonify({"tamam": ghost_gelisim.not_sil(int(v.get("i", -1)))})
    if i == "asama":
        return jsonify({"tamam": ghost_gelisim.asama_ayarla(str(v.get("ad") or ""), bool(v.get("acik")))})
    return jsonify({"hata": "Bilinmeyen işlem"}), 400


@app.post("/api/x/yerimleri")
def x_yerimleri_ekle():
    """Uzantının x.com/i/bookmarks sayfasından YALNIZCA OKUDUĞU yer imleri (yerimleri.py)."""
    import yerimleri
    n = yerimleri.kaydet((request.get_json(silent=True) or {}).get("gonderiler") or [])
    if n and ayarlar_oku().get("yerimleri_incele", True):  # kişinin doğrudan bıraktığı okuma (kendi araçları için; yeni kurulumlarda kapalı)
        _gg_is("yer imleri okunuyor", yerimleri.isle, log=_gg_log)
    return jsonify({"tamam": True, "yeni": n})


@app.post("/api/ghost/hikaye")
def ghost_hikaye_post():
    import ghost_hikaye
    return jsonify({"tamam": _gg_is("haftanın hikâyesi", lambda: ghost_hikaye.uret(zorla=True, log=_gg_log))})


@app.post("/api/ghost/yanit")
def ghost_yanit_post():
    import ghost_yanit
    return jsonify({"tamam": _gg_is("yanıt taslakları", lambda: ghost_yanit.uret(zorla=True, log=_gg_log))})


@app.get("/tek")
def ghost_tek():
    """Telefonda tek kart: günün sıradaki gönderisi, Kopyala ve X'te paylaş (ana ekrana eklenir; ağ paylaşımı açıkken telefondan da)."""
    r = make_response((Path(app.static_folder) / "ghost_tek.html").read_text(encoding="utf-8"))
    r.headers["Cache-Control"] = "no-cache"
    return r
