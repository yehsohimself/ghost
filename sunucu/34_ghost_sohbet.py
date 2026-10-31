# Ghost'la konuşma (2026-10-31): yanıt yazıldıkça akar, sonunda "\x00SON:" + mesaj kaydı (hızlı cevaplar, önerilen eylemler); hata "\x00HATA:".
# Eylemler yalnız kişi "Uygula" deyince: taslak (Ghost taslaklarına eklenir), duzenle, yaz (tam yazım hattı), gorus, fikir, ogren, plan.
import ghost_sohbet


@app.get("/api/ghost/sohbet")
def ghost_sohbet_gecmis():
    odak = None
    if request.args.get("odak"):
        try:
            odak = json.loads(request.args["odak"])
        except ValueError:
            odak = None
    return jsonify({"mesajlar": ghost_sohbet.mesajlar(60), "karsilama": ghost_sohbet.karsilama(odak=odak)})


@app.delete("/api/ghost/sohbet")
def ghost_sohbet_temizle():
    ghost_sohbet.temizle()
    return jsonify({"tamam": True, "karsilama": ghost_sohbet.karsilama()})


@app.post("/api/ghost/sohbet")
def ghost_sohbet_gonder():
    v = request.get_json(silent=True) or {}
    mesaj = str(v.get("mesaj") or "").strip()
    if not mesaj:
        return jsonify({"hata": "Boş mesaj"}), 400
    odak = v.get("odak") if isinstance(v.get("odak"), dict) else None
    if str(v.get("acilis") or "").strip():             # panelde gösterilen selam/soru da konuşmanın parçası (model neye cevap verildiğini bilsin)
        ghost_sohbet.ekle("ghost", str(v["acilis"])[:1500], acilis=True)

    def _akis():
        try:
            for p in ghost_sohbet.akis(mesaj[:4000], odak):
                if isinstance(p, tuple):
                    yield "\x00SON:" + json.dumps(p[1], ensure_ascii=False)
                else:
                    yield p
        except Exception as e:  # noqa: BLE001
            yield "\x00HATA:" + (str(e)[:200] or "Ghost şu an cevap veremiyor")
    return Response(stream_with_context(_akis()), mimetype="text/plain; charset=utf-8", headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


def _ghost_sohbet_taslak_kaydet(e):
    """Sohbette birlikte yazılan metin → Ghost taslağı (kaynak_tur sohbet; okur kapısı yok: metni kişi onayladı)."""
    import paylasim as paylasim_modulu
    metin = str(e.get("metin") or "").strip()
    temel = paylasim_modulu.ghost_kaydi(metin, "sohbet", "", "", metin, deneyim=metin)
    yol = _py_yol(temel)
    with kilit:
        d = json.loads(yol.read_text(encoding="utf-8"))
        d["veri"]["paylasim"] = {"taslaklar": [{"platform": e.get("platform") or "x", "metin": metin, "karakter": str(len(metin)), "dayanak": "kendi",
                                                "kaynak_tur": "sohbet", "neden": "Ghost'la konuşarak yazdınız", "uzunluk": "uzun" if len(metin) > 280 else "kisa"}],
                                 "zaman": time.time(), "ilk_zaman": time.time(), "model": "claude:sonnet (sohbet)"}
        yol.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return temel


@app.post("/api/ghost/sohbet/eylem")
def ghost_sohbet_eylem():
    v = request.get_json(silent=True) or {}
    mid, i = str(v.get("mesaj") or ""), int(v.get("i") or 0)
    e = ghost_sohbet.eylem_bul(mid, i)
    if not e:
        return jsonify({"hata": "Öneri bulunamadı"}), 404
    if e.get("uygulandi"):
        return jsonify({"tamam": True, "zaten": True, "eylem": e})
    import paylasim as paylasim_modulu
    t, sonuc = e["tur"], {}
    try:
        if t == "taslak":
            metin = str(v.get("metin") or e.get("metin") or "").strip()
            sonuc = {"temel": _ghost_sohbet_taslak_kaydet({**e, "metin": metin}), "mesaj": "Taslaklarınıza eklendi"}
        elif t == "duzenle":
            x = ghost_sohbet.taslak(e.get("anahtar"))
            if not x:
                return jsonify({"hata": "Taslak artık yok"}), 404
            yol, j, ts = x
            with kilit:
                d = json.loads(yol.read_text(encoding="utf-8"))
                T = d["veri"]["paylasim"]["taslaklar"][j]
                T.setdefault("ilk_metin", T.get("metin")); T["metin"] = str(e["metin"]).strip(); T["duzenlendi"] = True; T["karakter"] = str(len(T["metin"]))
                yol.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            sonuc = {"mesaj": "Taslak güncellendi"}
        elif t == "yaz":
            sonuc = {"temel": _ghost_fikirden_yaz(str(e["girdi"])[:1200]), "mesaj": "Ghost yazıyor; bir iki dakikada Bugün’de"}
        elif t == "gorus":
            paylasim_modulu._gorus_yaz([{"konu": str(e.get("baslik") or "")[:60], "gorus": str(e["metin"])[:400], "alan": "", "kanit": str(e["metin"])[:120],
                                         "tarih": time.strftime("%Y-%m-%d"), "kaynak": "kendi sözü (onaylı, sohbet)", "durum": "onayli"}])
            sonuc = {"mesaj": "Görüş defterinize eklendi"}
        elif t == "fikir":
            import ghost_defter
            ghost_defter.not_ekle(str(e["metin"]), "sohbet")
            sonuc = {"mesaj": "Fikir defterinize eklendi"}
        elif t == "ogren":
            ogr = paylasim_modulu.yorum_ogren({"metin": ""}, str(e["metin"]))
            sonuc = {"mesaj": ogr or "Not edildi"}
        elif t == "plan":
            x = ghost_sohbet.plan_degistir(e.get("i", -1), e.get("ne"), e.get("neden") or "")
            if not x:
                return jsonify({"hata": "Plan maddesi bulunamadı"}), 404
            sonuc = {"mesaj": "Haftanın planı güncellendi"}
    except Exception as ex:  # noqa: BLE001
        return jsonify({"hata": f"Olmadı: {str(ex)[:160]}"}), 500
    ghost_sohbet.eylem_isaretle(mid, i, {"zaman": time.time(), **{k: v for k, v in sonuc.items() if k != "mesaj"}})
    return jsonify({"tamam": True, **sonuc})
