# sunucu/38_claude_butce.py — Claude aboneliğinin dengeleyicisi (claude_butce.py): rapor ucu ve sıkışınca tek bildirim (2026-10-31).
# Kural ve seviyeler claude_butce.py'de; her Claude çağrısı claude_yaz._izin üzerinden ona sorulur.


@app.get("/api/claude/butce")
def claude_butce_get():
    import claude_butce
    if request.args.get("tazele"):
        threading.Thread(target=claude_butce.yokla, daemon=True).start()
    gun = min(31, max(1, int(request.args.get("gun") or 7)))
    return jsonify(claude_butce.rapor(gun))


def _claude_butce_dongu():
    """5 dk'da bir seviyeye bakar; Lab'in arka plan işleri durunca (kritik/sınır) kullanıcıya bir kez söyler (3 saatte en çok bir)."""
    import claude_butce
    isaret = KAYIT / ".claude_butce_bildirim"
    onceki = None
    time.sleep(90)
    while True:
        try:
            sv = claude_butce.seviye()
            s = sv["seviye"]
            yeni_sikisik = s in ("kritik", "sinir") and onceki not in ("kritik", "sinir") and onceki is not None
            try:
                son = isaret.stat().st_mtime
            except OSError:
                son = 0
            if yeni_sikisik and time.time() - son > 3 * 3600:
                isaret.touch()
                _bildir("Claude aboneliği hızlı doluyor",
                        f"{sv['neden']}. Lab'in kendi başına yaptığı işleri bekletiyorum; sizin istekleriniz ve toplantılar sürüyor.")
            onceki = s
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        time.sleep(300)


threading.Thread(target=_claude_butce_dongu, daemon=True).start()
