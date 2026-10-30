# sunucu/32_ghost_kurulum.py — Ghost'un ilk açılışı (kendi sesinizi, konularınızı, kaynaklarınızı kurun), kaynak/konu düzenleme ve yazı dili
# (2026-10-29, Ghost herkese açık depo olarak çıkarken; ghost_kurulum.py). site.py bu dosyayı diğer parçalarla AYNI ad alanında yürütür.
ghost_kurulum_durum = {"calisiyor": False, "hata": "", "log": [], "sonuc": None}


def _ghost_yazi_dili():
    """Gönderilerin dili profilden (profil/x.json `dil`). Türkçede ek talimat yok; başka dilde alt süreçler ve bütün Claude çağrıları o dilde yazar.
    Toplantılar (31_yazi_dili) kendi bağlamlarında kendi dillerini kurar (contextvar ortam değişkeninden önce gelir)."""
    try:
        import paylasim
        d = str(paylasim.profil().get("dil") or "tr")[:2]
    except Exception:  # noqa: BLE001
        d = "tr"
    if d != "tr":
        os.environ["VH_YAZI_DILI"] = d
    elif os.environ.get("VH_YAZI_DILI_GHOST"):
        os.environ.pop("VH_YAZI_DILI", None)
    os.environ["VH_YAZI_DILI_GHOST"] = d


_ghost_yazi_dili()


@app.get("/api/ghost/kurulum")
def ghost_kurulum_get():
    import ghost_kurulum
    return jsonify({**ghost_kurulum.durum(), **{k: v for k, v in ghost_kurulum_durum.items() if k != "log"}, "log": ghost_kurulum_durum["log"][-6:]})


@app.post("/api/ghost/kurulum")
def ghost_kurulum_post():
    import ghost_kurulum
    if ghost_kurulum_durum["calisiyor"]:
        return jsonify({"hata": "Kurulum sürüyor"}), 409
    v = request.get_json(silent=True) or {}
    if not v.get("konular"):
        return jsonify({"hata": "En az bir konu seçin"}), 400
    ghost_kurulum_durum.update({"calisiyor": True, "hata": "", "log": [], "sonuc": None})

    def _log(m):
        ghost_kurulum_durum["log"].append(str(m)); print("Ghost kurulumu:", m, flush=True)

    def _calis():
        try:
            ghost_kurulum_durum["sonuc"] = ghost_kurulum.kur(v, log=_log)
            _ghost_yazi_dili()
            try:                                             # ilk öneriler hemen (zamanlı turu beklemeden)
                threading.Thread(target=_kesif_calistir, args=("", ""), daemon=True).start()   # ilk tur soru beklemeden yazar
            except NameError:
                pass
        except Exception as e:  # noqa: BLE001
            ghost_kurulum_durum["hata"] = str(e)[:300]
        finally:
            ghost_kurulum_durum["calisiyor"] = False
    threading.Thread(target=_calis, daemon=True).start()
    return jsonify({"tamam": True})


@app.get("/api/ghost/kaynaklar")
def ghost_kaynaklar_get():
    import ghost_kurulum
    return jsonify({**ghost_kurulum.kaynaklar(), "konu": {k: v for k, v in ghost_konu_durum.items()}})


@app.post("/api/ghost/kaynak")
def ghost_kaynak_post():
    import ghost_kurulum
    v = request.get_json(silent=True) or {}
    alan = str(v.get("alan") or "").strip()
    if not alan:
        return jsonify({"hata": "Konu seçin"}), 400
    try:
        if v.get("sil"):
            ghost_kurulum.kaynak_sil(alan, str(v.get("ad") or ""))
            return jsonify({"tamam": True})
        k = ghost_kurulum.kaynak_ekle(alan, str(v.get("ad") or "").strip(), str(v.get("url") or "").strip(), str(v.get("sorgu") or "").strip(),
                                      str(v.get("dil") or "en"))
        return jsonify({"tamam": True, "kaynak": k})
    except ValueError as e:
        return jsonify({"hata": str(e)}), 400


ghost_konu_durum = {"calisiyor": False, "hata": "", "sonuc": None}


@app.post("/api/ghost/konu")
def ghost_konu_post():
    import ghost_kurulum
    v = request.get_json(silent=True) or {}
    if v.get("sil"):
        ghost_kurulum.alan_sil(str(v["sil"]))
        return jsonify({"tamam": True})
    konu = str(v.get("konu") or "").strip()[:200]
    if not konu:
        return jsonify({"hata": "Konuyu yazın"}), 400
    if ghost_konu_durum["calisiyor"]:
        return jsonify({"hata": "Bir konu ekleniyor"}), 409
    ghost_konu_durum.update({"calisiyor": True, "hata": "", "sonuc": None})

    def _calis():
        try:
            ghost_konu_durum["sonuc"] = ghost_kurulum.alan_ekle(konu)
        except Exception as e:  # noqa: BLE001
            ghost_konu_durum["hata"] = str(e)[:300]
        finally:
            ghost_konu_durum["calisiyor"] = False
    threading.Thread(target=_calis, daemon=True).start()
    return jsonify({"tamam": True})
