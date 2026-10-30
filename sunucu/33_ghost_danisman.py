# sunucu/33_ghost_danisman.py — Ghost'un iletişim danışmanı (2026-10-30; ghost_danisman.py): uzman görüşmesi, puan kartı, haftalık not,
# yaklaşan gündem ve hatırlatmalar. site.py bu dosyayı diğer parçalarla AYNI ad alanında yürütür.
ghost_danisman_durum = {"calisiyor": False, "hata": "", "son": 0}


def _ghost_danisman_is(fn):
    if ghost_danisman_durum["calisiyor"]:
        return False
    ghost_danisman_durum.update({"calisiyor": True, "hata": ""})

    def _calis():
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            ghost_danisman_durum["hata"] = str(e)[:200]; print(f"Ghost danışmanı: {e}", flush=True)
        finally:
            ghost_danisman_durum.update({"calisiyor": False, "son": time.time()})
    threading.Thread(target=_calis, daemon=True).start()
    return True


@app.get("/api/ghost/danisman")
def ghost_danisman_get():
    import ghost_danisman
    return jsonify({**ghost_danisman.durum(), "calisiyor": ghost_danisman_durum["calisiyor"], "hata": ghost_danisman_durum["hata"]})


@app.post("/api/ghost/danisman/gorusme")
def ghost_danisman_gorusme():
    import ghost_danisman
    v = request.get_json(silent=True) or {}
    try:
        s = ghost_danisman.gorusme_kaydet(v.get("cevaplar") or {}, str(v.get("konum") or ""), str(v.get("notlar") or ""))
    except ValueError as e:
        return jsonify({"hata": str(e)}), 400

    def _sonra():                                            # yeni stratejiyle not ve gündem hemen
        import claude_yaz
        if claude_yaz.hazir():
            ghost_danisman.gundem(log=print)
            ghost_danisman.rapor(zorla=True, log=print)
    _ghost_danisman_is(_sonra)
    return jsonify({"tamam": True, "strateji": s})


@app.post("/api/ghost/danisman/yenile")
def ghost_danisman_yenile():
    import ghost_danisman

    def _y():
        ghost_danisman.gundem(zorla=True, log=print)
        ghost_danisman.rapor(zorla=True, log=print)
    if not _ghost_danisman_is(_y):
        return jsonify({"hata": "Danışman zaten çalışıyor"}), 409
    return jsonify({"tamam": True})


@app.post("/api/ghost/danisman/gundem/<mid>")
def ghost_danisman_gundem(mid):
    """{gizli: true} gizler; {hazirlan: true} 'Hazırlan': Ghost'un yazma kutusuna fikir olarak verir (ghost_yaz ile aynı yol)."""
    import ghost_danisman
    v = request.get_json(silent=True) or {}
    m = next((x for x in ghost_danisman._gundem_oku().get("maddeler") or [] if x.get("id") == mid), None)
    if not m:
        return jsonify({"hata": "Madde bulunamadı"}), 404
    if v.get("gizli") is not None:
        ghost_danisman.gundem_isaretle(mid, gizli=bool(v["gizli"]))
        return jsonify({"tamam": True})
    if v.get("hazirlan"):
        temel = _ghost_fikirden_yaz(ghost_danisman.hazirlik_girdisi(m), ek={"gundem": mid, "kaynak_link": m.get("kaynak") or ""})
        ghost_danisman.gundem_isaretle(mid, hazirlandi=temel)
        return jsonify({"tamam": True, "temel": temel})
    return jsonify({"hata": "Ne yapılacağı belirsiz"}), 400


def _ghost_danisman_dongu():
    """Pazartesi 08.30'dan sonra haftalık not + gündem (haftada bir); gündem 3 günde bir tazelenir; 09.00'dan sonra bugün/yarın olan gündem
    maddesi için bir bildirim (günde bir)."""
    time.sleep(120)
    while True:
        try:
            if _ghost_kurulu():
                import claude_yaz
                import ghost_danisman
                zt = time.localtime(); gun = time.strftime("%Y-%m-%d")
                if claude_yaz.hazir() and claude_yaz.arka_plan_uygun():
                    hafta = KAYIT / ".gh_danisman_hafta"
                    if zt.tm_wday == 0 and (zt.tm_hour, zt.tm_min) >= (8, 30) and (not hafta.exists() or hafta.read_text(encoding="utf-8") != time.strftime("%G-%V")):
                        hafta.write_text(time.strftime("%G-%V"), encoding="utf-8")
                        _ghost_danisman_is(lambda: (ghost_danisman.gundem(log=print), ghost_danisman.rapor(zorla=True, log=print)))
                    elif time.time() - (ghost_danisman._gundem_oku().get("zaman") or 0) > 3 * 86400 and zt.tm_hour >= 7:
                        _ghost_danisman_is(lambda: ghost_danisman.gundem(log=print))
                isaret = KAYIT / ".gh_danisman_hatirlatma"
                if zt.tm_hour >= 9 and (not isaret.exists() or isaret.read_text(encoding="utf-8") != gun) and ayarlar_oku().get("ghost_bildirim", True):
                    isaret.write_text(gun, encoding="utf-8")
                    Y = [m for m in ghost_danisman.yaklasan(1) if not m.get("hazirlandi")]
                    if Y:
                        m = Y[0]; ne = "Bugün" if m["tarih"] == gun else "Yarın"
                        _bildir(f"{ne}: {m['ad']}", (m.get("hazirlik") or m.get("neden") or "")[:150])
        except Exception as e:  # noqa: BLE001
            print(f"Ghost danışman döngüsü hatası: {e}", flush=True)
        time.sleep(60)


threading.Thread(target=_ghost_danisman_dongu, daemon=True).start()
