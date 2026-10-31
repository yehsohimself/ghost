"""ghost_danisman: uzman görüşmesi, puan kartı, yaklaşan gündem ve ChatGPT seçkisinin keşfe girmesi (2026-10-30)."""
import importlib
import json
import time


def _modul(kok):
    import ghost_danisman
    importlib.reload(ghost_danisman)
    for ad in ("profil/ghost_danisman.json", "kayitlar/ghost_gundem.json"):
        (kok / ad).unlink(missing_ok=True)
    return ghost_danisman


def _ghost_kaydi(kok, zaman, taslaklar):
    (kok / "ghost").mkdir(exist_ok=True)
    ad = time.strftime("%Y%m%d%H%M%S", time.localtime(zaman)) + f"_{int(zaman) % 9999:04d}"
    (kok / "ghost" / f"{ad}.json").write_text(json.dumps({"veri": {"baslik": "d", "kaynak_tur": "kesif", "paylasim": {"zaman": zaman, "taslaklar": taslaklar}}, "segmentler": []}), encoding="utf-8")


def test_gorusme_kaydeder_ve_istem_blogu_uretir(kok, istemci):
    g = _modul(kok)
    assert g.gorusme_gerekli() and g.strateji_blogu() == ""
    j = istemci.get("/api/ghost/danisman").get_json()
    assert j["gorusme_gerekli"] and len(j["sorular"]) == 8 and j["puan"]["genel"] is None   # veri yokken puan uydurulmaz
    assert istemci.post("/api/ghost/danisman/gorusme", json={"cevaplar": {"amac": "yok"}}).status_code == 400
    r = istemci.post("/api/ghost/danisman/gorusme", json={"cevaplar": {"amac": "is", "tempo": "7", "keskinlik": "sivri", "x": "y"}, "konum": "Reklamcı"})
    assert r.status_code == 200
    s = g.strateji()
    assert s["cevaplar"] == {"amac": "is", "tempo": "7", "keskinlik": "sivri"} and s["haftalik_hedef"] == 7
    b = g.strateji_blogu()
    assert "iş ve müşteri" in b and "sivri" in b and "KONUM CÜMLESİ: Reklamcı" in b and not g.gorusme_gerekli()
    import paylasim
    assert "İLETİŞİM STRATEJİSİ" in paylasim._strateji_blogu()


def test_puan_karti_veriden_hesaplanir(kok, monkeypatch):
    g = _modul(kok)
    import paylasim
    paylasim.profil_kaydet(alanlar=[{"kod": "futbol", "ad": "Futbol", "agirlik": 3}, {"kod": "tasarim", "ad": "Tasarım", "agirlik": 3}, {"kod": "yemek", "ad": "Yemek", "agirlik": 3}],
                           strateji={"cevaplar": {"tempo": "4"}, "haftalik_hedef": 4, "zaman": time.time()})
    simdi = time.time()
    T = [{"paylasildi": True, "paylasim_zaman": simdi - i * 86400 * 1.5, "alan": "futbol" if i < 5 else "tasarim", "dayanak": "gorus" if i % 3 == 0 else "",
          "paylas_link": "https://x" if i % 2 else "", "duzenlendi": i % 4 == 0, "metin": f"gönderi {i}"} for i in range(8)]
    _ghost_kaydi(kok, simdi - 60, T[:4]); _ghost_kaydi(kok, simdi - 120, T[4:])
    import kitaplik_onbellek
    importlib.reload(kitaplik_onbellek)
    monkeypatch.setattr(g, "_gercek_gonderiler", lambda gun=28: [])
    P = g.puan(28)
    kod = {b["kod"]: b for b in P["boyutlar"]}
    assert P["paylasilan"] == 8 and kod["okur"]["puan"] is None               # uzantı verisi yok → okur tepkisi ölçülmez, uydurulmaz
    assert 0 < kod["duzen"]["puan"] <= 10 and "haftada 2" in kod["duzen"]["veri"]
    assert kod["cesitlilik"]["puan"] is not None and "tek alanda" in kod["cesitlilik"]["eksik"] and "Yemek" in kod["cesitlilik"]["aksiyon"]["ad"]   # 5/8 futbol; yazılmayan alan aksiyonda
    assert kod["derinlik"]["puan"] is not None and kod["ses"]["puan"] is not None
    assert P["genel"] is not None and P["eksikler"] and all(b.get("aksiyon", {}).get("ad") for b in P["eksikler"])


def test_gundem_web_yanitini_ayiklar_ve_hatirlatir(kok, istemci, monkeypatch):
    g = _modul(kok)
    import claude_yaz
    import paylasim
    from datetime import date, timedelta
    paylasim.profil_kaydet(alanlar=[{"kod": "reklam", "ad": "Reklamcılık", "agirlik": 3}])
    yakin = (date.today() + timedelta(days=2)).isoformat(); uzak = (date.today() + timedelta(days=40)).isoformat()
    yanit = ('Buldum:\n```json\n{"maddeler": [{"tarih": "' + yakin + '", "ad": "Effie Türkiye kısa listesi", "alan": "Reklamcılık", "neden": "Kısa liste konuşulur", '
             '"hazirlik": "Geçen yılın kazananıyla bu yılın farkını yaz", "kaynak": "https://example.org/effie"}, '
             '{"tarih": "' + uzak + '", "ad": "Çok uzak", "alan": "Reklamcılık"}, {"tarih": "bozuk", "ad": "x"}]}\n```')
    monkeypatch.setattr(claude_yaz, "hazir", lambda: True)
    monkeypatch.setattr(claude_yaz, "sor", lambda *a, **k: yanit)
    d = g.gundem(zorla=True, log=lambda m: None)
    assert [m["ad"] for m in d["maddeler"]] == ["Effie Türkiye kısa listesi"] and d["maddeler"][0]["alan"] == "reklam"
    assert len(g.yaklasan(3)) == 1 and not g.yaklasan(1)
    mid = d["maddeler"][0]["id"]
    girdi = g.hazirlik_girdisi(d["maddeler"][0])
    assert "2 gün sonra" in girdi and paylasim.girdi_turu(girdi) == "fikir"
    assert istemci.post(f"/api/ghost/danisman/gundem/{mid}", json={"gizli": True}).status_code == 200
    assert not g.yaklasan(3) and istemci.post("/api/ghost/danisman/gundem/yok", json={"gizli": True}).status_code == 404
    monkeypatch.setattr(claude_yaz, "sor", lambda *a, **k: "hiç json yok")
    assert g.gundem(zorla=True, log=lambda m: None)["maddeler"][0]["gizli"]   # okunamayan yanıt eskiyi silmez


def test_secki_kesfe_madde_olur(kok, monkeypatch):
    import kesif
    import paylasim
    import seckiler
    paylasim.profil_kaydet(alanlar=[{"kod": "futbol", "ad": "Futbol", "agirlik": 2}, {"kod": "teknoloji", "ad": "Teknoloji ve yapay zekâ", "agirlik": 3}])
    monkeypatch.setattr(seckiler, "son", lambda n=2: {"tarih": "2026-10-30", "konular": [
        {"baslik": "Yapay zekâ ajanları için yeni standart", "metin": "Açık standart yayımlandı.", "neden": "Teknoloji şirketleri hizalanıyor", "kanit_siniri": "Tek kaynak", "kaynaklar": ["https://example.org/a"]},
        {"baslik": "Kaynaksız konu", "metin": "x", "kaynaklar": []}]})
    M = kesif.secki_maddeleri(log=lambda m: None)
    assert len(M) == 1 and M[0]["alan"] == "teknoloji" and M[0]["kesif_secki"] == "2026-10-30" and "Kanıt sınırı" in M[0]["ozet"]
    assert kesif.derin_mi(M[0]) and M[0]["resim"] == ""


def test_plan_takibi_ve_ritim(kok, monkeypatch):
    """Haftalık plan gün gün izlenir: o gün paylaşım varsa 'paylasildi', geçtiyse 'kacirildi', bugün 'bugun'; ritim haftalık sayıları ve seriyi verir."""
    from datetime import date, timedelta
    g = _modul(kok)
    for f in (kok / "ghost").glob("*.json"):                    # önceki testlerin paylaşılmış kayıtları günleri boyamasın
        f.unlink()
    assert g._gun_no("Cumartesi") == 5 and g._gun_no("Cuma") == 4 and g._gun_no("Pzt") == 0 and g._gun_no("hiç") is None
    bugun = date.today(); dun = bugun - timedelta(days=1); yarin = bugun + timedelta(days=1)
    gun_ad = lambda d: g.GUN_ADLARI[d.weekday()].capitalize()   # noqa: E731
    # tarihsiz plan: gün adından bugünden sonraki ilk karşılık; bozuk tarih de düzeltilir
    H = g._hafta_tarihle([{"gun": gun_ad(yarin), "ne": "a"}, {"gun": "Salı", "tarih": "2001-01-01", "ne": "b"}], bugun)
    assert H[0]["tarih"] == yarin.isoformat() if H[0]["ne"] == "a" else True
    assert all(bugun <= date.fromisoformat(x["tarih"]) <= bugun + timedelta(days=7) for x in H)
    d = g._oku(); d["rapor"] = {"zaman": time.time() - 86400, "not": "n", "hafta": [
        {"gun": gun_ad(dun), "tarih": dun.isoformat(), "ne": "dünkü", "neden": "", "mecra": "X"},
        {"gun": gun_ad(bugun), "tarih": bugun.isoformat(), "ne": "bugünkü", "neden": "", "mecra": "LinkedIn"},
        {"gun": gun_ad(yarin), "tarih": yarin.isoformat(), "ne": "yarınki", "neden": "", "mecra": "X"}]}; g._yaz(d)
    monkeypatch.setattr(g, "_gercek_gonderiler", lambda gun=28: [])
    p = g.plan()
    assert [x["durum"] for x in p["maddeler"]] == ["kacirildi", "bugun", "bekliyor"] and p["ozet"]["kacirilan"] == 1 and p["ozet"]["bugun"]["ne"] == "bugünkü"
    assert "LinkedIn" in g.plan_girdisi(p["maddeler"][1]) and g.plan_girdisi(p["maddeler"][2]).startswith("yarınki")
    # dün bir şey paylaşılmışsa kaçırılmış sayılmaz; bugün taslak yazıldıysa 'hazir', paylaşılınca 'paylasildi'
    _ghost_kaydi(kok, time.time() - 86400, [{"metin": "x", "alan": "futbol", "paylasildi": True, "paylasim_zaman": time.time() - 86400}])
    (kok / "ghost" / "20990101000000_plan.json").write_text(json.dumps({"veri": {"baslik": "p", "kaynak_tur": "fikir", "paylasim": {"taslaklar": [{"metin": "t"}]}}, "segmentler": []}), encoding="utf-8")
    g.plan_isaretle(1, hazirlandi="ghost__20990101000000_plan")
    p = g.plan()
    assert p["maddeler"][0]["durum"] == "paylasildi" and p["maddeler"][1]["taslak"] == "hazir" and p["maddeler"][1]["durum"] == "bugun"
    (kok / "ghost" / "20990101000000_plan.json").write_text(json.dumps({"veri": {"baslik": "p", "kaynak_tur": "fikir", "paylasim": {"taslaklar": [{"metin": "t", "paylasildi": True, "paylasim_zaman": time.time()}]}}, "segmentler": []}), encoding="utf-8")
    p = g.plan()
    assert p["maddeler"][1]["durum"] == "paylasildi" and p["ozet"]["paylasilan"] == 2
    r = g.ritim(4)
    assert len(r["haftalar"]) == 4 and r["haftalar"][-1]["bu"] and r["seri"] >= 1 and r["bu_hafta"] >= 1
    assert g.plan_saati() == 10


def test_plan_ucu_taslak_yazar_ve_isaretler(kok, istemci, monkeypatch):
    from datetime import date
    g = _modul(kok)
    for f in (kok / "ghost").glob("*.json"):
        f.unlink()
    bugun = date.today()
    d = g._oku(); d["rapor"] = {"zaman": time.time(), "not": "n", "hafta": [{"gun": g.GUN_ADLARI[bugun.weekday()].capitalize(), "tarih": bugun.isoformat(), "ne": "bugünkü plan", "neden": "çünkü", "mecra": "X"}]}; g._yaz(d)
    monkeypatch.setattr(g, "_gercek_gonderiler", lambda gun=28: [])
    import vh_site
    yazilan = {}
    monkeypatch.setattr(vh_site, "_ghost_fikirden_yaz", lambda girdi, deneyim="", ek=None: yazilan.update(girdi=girdi, ek=ek) or "ghost__deneme", raising=False)
    assert istemci.post("/api/ghost/danisman/plan/7", json={"hazirlan": True}).status_code == 404
    r = istemci.post("/api/ghost/danisman/plan/0", json={"hazirlan": True}).get_json()
    assert r["temel"] == "ghost__deneme" and yazilan["girdi"].startswith("bugünkü plan") and yazilan["ek"]["plan"] == bugun.isoformat()
    j = istemci.get("/api/ghost/danisman").get_json()
    assert j["plan"]["maddeler"][0]["hazirlandi"] == "ghost__deneme" and "ritim" in j
    assert istemci.post("/api/ghost/danisman/plan/0", json={"paylasildi": True}).get_json()["tamam"]
    assert istemci.get("/api/ghost/danisman").get_json()["plan"]["maddeler"][0]["durum"] == "paylasildi"
