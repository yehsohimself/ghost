"""ghost_tempo: kullanıcının ilgisine göre üretim temposu (2026-10-27)."""
import importlib
import json
import time


def _tempo(kok, veri):
    import ghost_tempo
    importlib.reload(ghost_tempo)
    ghost_tempo.DOSYA = kok / "kayitlar" / ".ghost_ziyaret.json"
    ghost_tempo.DOSYA.parent.mkdir(parents=True, exist_ok=True)
    ghost_tempo.DOSYA.write_text(json.dumps(veri), encoding="utf-8")
    ghost_tempo.acik = lambda: True
    return ghost_tempo


def test_kayit_yokken_aktif(kok):
    t = _tempo(kok, {})
    assert t.durum()["mod"] == "aktif" and t.gunluk_hedef(12) == 12


def test_sakin_ve_uzakta(kok):
    simdi = time.time()
    t = _tempo(kok, {"ziyaret": [simdi - 3600], "etkilesim": [simdi - 5 * 86400]})
    assert t.durum()["mod"] == "sakin" and t.gunluk_hedef(12) == 8 and t.yan_isler_uygun()
    t = _tempo(kok, {"ziyaret": [simdi - 3 * 86400], "etkilesim": [simdi - 5 * 86400]})
    assert t.durum()["mod"] == "uzakta" and t.gunluk_hedef(12) == 5 and not t.yan_isler_uygun()
    t.etkilesim()
    assert t.durum()["mod"] == "aktif" and t.gunluk_hedef(12) == 12


def test_ogle_turu(kok):
    simdi = time.time()
    t = _tempo(kok, {"ziyaret": [simdi - 10 * 3600]})
    assert not t.ogle_turu_gerekli(sabah_turu=simdi - 5 * 3600)
    t.ziyaret()
    assert t.ogle_turu_gerekli(sabah_turu=simdi - 5 * 3600)


def test_elden_gecirme_kararlari(kok, istemci):
    """Kalsın (begendi) öğrenilir ve geri alınır; nedenli kaldırma kendi türünde öğrenilir, geri alınınca öğrenilen de silinir; ziyaret kaydı."""
    import paylasim
    gid = "20261027090000_test"
    t = {"metin": "Deneme gönderisi: bir tasarım kararının arkası.", "alan": "Kreatif", "karisim_tur": "gorus", "konu": "deneme"}
    (kok / "ghost" / f"{gid}.json").write_text(json.dumps({"veri": {"baslik": "Günün akışı", "kaynak_tur": "karisim",
        "paylasim": {"taslaklar": [dict(t), dict(t, metin="İkinci deneme gönderisi.")], "zaman": time.time()}}, "segmentler": []}), encoding="utf-8")
    temel = f"ghost__{gid}"
    assert istemci.post(f"/api/paylasim/{temel}/0", json={"begendi": True}).status_code == 200
    assert any(b.get("metin") == t["metin"] for b in paylasim.profil().get("begenilen") or [])
    istemci.post(f"/api/paylasim/{temel}/0", json={"begendi": False})
    assert not any(b.get("metin") == t["metin"] for b in paylasim.profil().get("begenilen") or [])
    istemci.post(f"/api/paylasim/{temel}/1", json={"gizli": True, "neden": "açı zayıf"})
    assert any(r.get("ilk") == "İkinci deneme gönderisi." and r.get("tur") == "aci" for r in paylasim.profil()["reddedilen"])
    istemci.post(f"/api/paylasim/{temel}/1", json={"gizli": False})
    assert not any(r.get("ilk") == "İkinci deneme gönderisi." for r in paylasim.profil()["reddedilen"])
    j = istemci.get("/api/paylasimlar?z=1").get_json()
    assert j["tempo"]["mod"] == "aktif" and j["tempo"]["son_ziyaret"] > 0 and j["tempo"]["son_etkilesim"] > 0


def test_karisim_uzunluk_ve_yorumcu_notu(kok):
    """27 Ekim ölçümü: türüne göre 280'i aşan ve yorumcu cümlesi kuran taslak not alır; 'kendi' türü uzun olabilir."""
    import karisim
    uzun = "Bir haberin içindeki karar ilginçti. " * 9
    assert any("280" in n for n in karisim._kod_notlari({"metin": uzun, "tur": "haber", "katki": "x"}, ""))
    assert not any("280" in n for n in karisim._kod_notlari({"metin": uzun, "tur": "kendi", "katki": "x"}, ""))
    assert any("Yorumcu" in n for n in karisim._kod_notlari({"metin": "Kart değişti. Açık kalan şu: kim öder?", "tur": "gorus", "katki": "x"}, ""))


def test_karisim_alan_dengesi(kok):
    """27 Ekim: yazıma giden haberler alan alan seçilir; reklamcılık ve gusto malzemesi varsa istem en az birer gönderi ister."""
    import karisim
    L = [{"alan": "kreatif", "i": i} for i in range(6)] + [{"alan": "gusto", "i": 6}, {"alan": "reklamcilik", "i": 7}]
    S = karisim._alan_dengeli(L, 6, 2)
    assert {o["alan"] for o in S} == {"kreatif", "gusto", "reklamcilik"} and len(S) == 4 and S == sorted(S, key=L.index)
    assert "ALAN TABANI" in karisim._alan_tabani_metni({"haber": [{"alan": "gusto"}]})
    assert karisim._alan_tabani_metni({"haber": [{"alan": "futbol"}]}) == ""


def test_karisim_karakter_denetimleri(kok):
    """28 Ekim: dayanaksız geri dönüş, çekince, sayı yığını ve kendi işinde teknik ayrıntı kod notu alır; ironi yalnız konuşulan konuya."""
    import karisim
    n = lambda m, tur="gorus", geri="": " ".join(karisim._kod_notlari({"metin": m, "tur": tur, "katki": "x", "geri": geri}, ""))
    assert "eski bir sözüne" in n("haziranda yazdıklarımın arkasındayım.")
    assert "eski bir sözüne" not in n("haziranda yazdıklarımın arkasındayım.", geri="r:i:1")
    assert "Çekinceli" in n("Bu ölçü aynı şey olmayabilir.")
    assert "sayı" in n("1 milyon, 2 bin ve 34 kişi.")
    assert "Teknik" in n("Dosyayı 1080x1920 yapıyor.", tur="kendi")
    assert karisim.konusulan({"kaynak_sayisi": 3}) and not karisim.konusulan({"kaynak_sayisi": 1})
