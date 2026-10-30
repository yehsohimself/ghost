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
