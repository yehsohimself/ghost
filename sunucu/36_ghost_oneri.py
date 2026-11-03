# Gelen yazı önerileri (2026-10-31; ghost_oneri.py): ChatGPT/dot önerisi olduğu gibi saklanır, Ghost format kararı verir ve son metni yazar,
# kişinin açık eylemleri ChatGPT'ye geri verilebilecek dosyaya çıkar. Yeni bağlantı yok: havuz, seckiler.havuz'un zaten indirdiği yerel kopyadan okunur.
import ghost_oneri

ghost_oneri_durum = {"calisan": set(), "son_tur": 0.0}
GHOST_ONERI_ARALIK = 3 * 3600                     # kendiliğinden değerlendirme aralığı; elle eklenen öneri hemen yazılır


def _ghost_oneri_isle_arka(oid, zorla=False, kullanici=False):
    if oid in ghost_oneri_durum["calisan"]:
        return
    ghost_oneri_durum["calisan"].add(oid)
    try:
        if kullanici:      # kişinin düğmeyle istediği değerlendirme bütçe sırasında beklemez
            import claude_yaz
            with claude_yaz.kullanici_isi():
                ghost_oneri.isle(oid, log=lambda m: print(m, flush=True), zorla=zorla)
        else:
            ghost_oneri.isle(oid, log=lambda m: print(m, flush=True), zorla=zorla)
    except Exception as e:  # noqa: BLE001
        print(f"Gelen öneri yazılamadı ({oid}): {str(e)[:160]}", flush=True)
    finally:
        ghost_oneri_durum["calisan"].discard(oid)


@app.get("/api/ghost/oneriler")
def ghost_oneriler():
    L = ghost_oneri.liste(int(request.args.get("gun") or 60))
    for d in L:
        d["calisiyor"] = d["id"] in ghost_oneri_durum["calisan"]
        d["ayrim"] = ghost_oneri.ayrim(d)
        d["kisi_metni"] = ghost_oneri.kisi_metni(d)
    return jsonify({"oneriler": L, "formatlar": ghost_oneri.FORMAT_AD, "tarama": ghost_oneri.tarama_durumu()})


@app.post("/api/ghost/oneri")
def ghost_oneri_ekle():
    """Yapıştırılan öneri: {metin, baslik, not, editor_notu, olgular, arastirma_notu, kaynak_url, tarih, uretici, yaz}. Aynısı varsa yeni kayıt açılmaz."""
    v = request.get_json(silent=True) or {}
    try:
        d, yeni = ghost_oneri.ekle(v.get("metin"), baslik=v.get("baslik") or "", not_=v.get("not") or "", arastirma_notu=v.get("arastirma_notu") or "",
                                   kaynak_url=v.get("kaynak_url") or "", tarih=v.get("tarih") or "", uretici=v.get("uretici") or "ChatGPT", kanal="yapistirma",
                                   editor_notu=v.get("editor_notu") or "", olgular=v.get("olgular"))
    except ValueError as e:
        return jsonify({"hata": str(e)}), 400
    if yeni and v.get("yaz", True) and d["durum"] == "geldi":
        threading.Thread(target=_ghost_oneri_isle_arka, args=(d["id"],), daemon=True).start()
    return jsonify({"tamam": True, "yeni": yeni, "oneri": d})


@app.post("/api/ghost/oneri/<oid>")
def ghost_oneri_eylem(oid):
    """{islem: yaz (yeniden değerlendir; yeni sürüm, eskisi ezilmez) | zorla (tekrar olsa da yaz) | gec {neden} | blog {metin} | not {metin, eski, yaz}}."""
    v = request.get_json(silent=True) or {}
    try:
        d = ghost_oneri._oku(oid)
    except ValueError:
        return jsonify({"hata": "Geçersiz öneri"}), 400
    if not d:
        return jsonify({"hata": "Öneri bulunamadı"}), 404
    islem = v.get("islem")
    if islem in ("yaz", "zorla"):
        if oid in ghost_oneri_durum["calisan"]:
            return jsonify({"tamam": True, "zaten": True})
        threading.Thread(target=_ghost_oneri_isle_arka, args=(oid, islem == "zorla", True), daemon=True).start()
        return jsonify({"tamam": True})
    if islem == "not":
        try:
            d = ghost_oneri.editor_notu_kaydet(oid, v.get("metin"), v.get("eski"))
        except ghost_oneri.Degisti as e:
            return jsonify({"hata": "Bu not başka yerde değişmiş.", "guncel": str(e)}), 409
        suruyor = oid in ghost_oneri_durum["calisan"]
        if v.get("yaz", True) and not suruyor:          # tekrar sayılan öneride de kişi açıkça istedi
            threading.Thread(target=_ghost_oneri_isle_arka, args=(oid, True, True), daemon=True).start()
        return jsonify({"tamam": True, "oneri": d, "suruyor": suruyor})
    if islem == "gec":
        return jsonify({"tamam": True, "oneri": ghost_oneri.gec(oid, v.get("neden") or "")})
    if islem == "blog":
        try:
            return jsonify({"tamam": True, "oneri": ghost_oneri.blog_duzelt(oid, v.get("metin") or "")})
        except ValueError as e:
            return jsonify({"hata": str(e)}), 400
    return jsonify({"hata": "Bilinmeyen işlem"}), 400


@app.get("/api/ghost/profil-kayit")
def ghost_profil_kayit():
    """Profilin hangi bölümü nereden öğreniyor, kaç kayıt var, son ne zaman değişti, son hata. Yalnız sayı ve tarih; içerik dönmez."""
    import ghost_profil
    return jsonify(ghost_profil.durum())


@app.get("/api/ghost/disa-tercihler")
def ghost_disa_tercihler():
    """Kişinin açık eylemleri (seçilen, düzeltilen, paylaşılan; ayrı bölümde reddedilen) + gelen önerilerin sonuçları. Yalnız indirme; gönderim yok."""
    gun = max(7, min(365, int(request.args.get("gun") or 90)))
    v = ghost_oneri.disa_aktar(gun)
    ad = f"ghost-tercihler-{time.strftime('%Y-%m-%d')}"
    if request.args.get("bicim") == "md":
        r = make_response(ghost_oneri.disa_md(v))
        r.headers["Content-Type"] = "text/markdown; charset=utf-8"
        r.headers["Content-Disposition"] = f'attachment; filename="{ad}.md"'
        return r
    r = make_response(json.dumps(v, ensure_ascii=False, indent=1))
    r.headers["Content-Type"] = "application/json; charset=utf-8"
    r.headers["Content-Disposition"] = f'attachment; filename="{ad}.json"'
    return r


def _ghost_oneri_dongu():
    """10 dk'da bir havuzun yerel kopyasındaki yeni öneriler kayda alınır (token yok); Claude ile değerlendirme 3 saatte bir, en çok 2 öneri."""
    while True:
        time.sleep(600)
        try:
            if not _ghost_kurulu() or not ayarlar_oku().get("ghost_dis_oneri_oto", True):
                continue
            ghost_oneri.havuzdan_al()
            import claude_yaz
            if not claude_yaz.arka_plan_uygun() or ghost_oneri_durum["calisan"]:
                continue
            isaret = KAYIT / ".gh_oneri_son"                # Claude ile değerlendirme 3 saatte bir (kullanıcı, 31 Ekim: "10 dakikada bir çok token yer")
            if isaret.exists() and time.time() - isaret.stat().st_mtime < GHOST_ONERI_ARALIK:
                continue
            bek = ghost_oneri.bekleyenler(2)
            if bek:
                isaret.touch()
            for oid in bek:
                _ghost_oneri_isle_arka(oid)
        except Exception as e:  # noqa: BLE001
            print(f"Gelen öneri döngüsü: {str(e)[:160]}", flush=True)


threading.Thread(target=_ghost_oneri_dongu, daemon=True).start()

_mesgul_onceki_oneri = mesgul_nedenler


def mesgul_nedenler():   # noqa: F811 — Ghost bir gelen öneriyi yazarken yeniden başlatma bekler
    n = _mesgul_onceki_oneri()
    if ghost_oneri_durum["calisan"]:
        n.append("Ghost gelen öneriyi yazıyor")
    return n
