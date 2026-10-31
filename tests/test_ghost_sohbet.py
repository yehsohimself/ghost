"""ghost_sohbet: Ghost'la konuşma (2026-10-31). Akış ayrımı, selam, eylemler ve uç noktalar; Claude çağrısı sahte."""
import importlib
import json
import time


def _modul(kok):
    import ghost_sohbet
    importlib.reload(ghost_sohbet)
    (kok / "profil" / "ghost_sohbet.json").unlink(missing_ok=True)
    for f in (kok / "ghost").glob("*.json") if (kok / "ghost").exists() else []:
        f.unlink()
    return ghost_sohbet


def _sahte_akis(monkeypatch, yanit):
    import claude_yaz
    def akis(istem, sistem="", zaman_asimi=300, model_adi=None):
        akis.istem = istem
        for i in range(0, len(yanit), 7):                 # parça parça; ayraç da bölünerek gelsin
            yield yanit[i:i + 7]
    monkeypatch.setattr(claude_yaz, "sor_akis", akis)
    return akis


def test_ayir_ve_eylem_suzgeci(kok):
    s = _modul(kok)
    metin, ek = s.ayir('Bence önce kısa yaz.\n@@@\n{"secenekler": ["Neden?", "Tamam"], "eylemler": [{"tur": "taslak", "metin": "#reklam ilk cümle"},'
                       ' {"tur": "duzenle", "anahtar": "yok#0", "metin": "x"}, {"tur": "bilinmeyen"}, {"tur": "yaz", "girdi": ""}, {"tur": "gorus", "metin": "Kısa yazmak saygıdır"}]}')
    assert metin == "Bence önce kısa yaz." and ek["secenekler"] == ["Neden?", "Tamam"]
    assert [e["tur"] for e in ek["eylemler"]] == ["taslak", "gorus"]           # olmayan taslağa düzeltme, boş yazım, bilinmeyen tür atılır
    assert "#" not in ek["eylemler"][0]["metin"]                                 # gönderi metni temizlenir (hashtag yok)
    assert s.ayir("yalnız metin") == ("yalnız metin", {})


def test_akis_ayraci_gostermez_ve_kaydeder(kok, monkeypatch):
    s = _modul(kok)
    _sahte_akis(monkeypatch, 'Haklısın, bunu daha somut yazalım.\n@@@\n{"secenekler": ["Yaz"], "eylemler": [{"tur": "fikir", "metin": "Somut ayrıntı önce"}]}')
    P = list(s.akis("Bu taslak bana fazla genel geldi, sence?"))
    gorunen = "".join(p for p in P if isinstance(p, str))
    assert "@" not in gorunen and gorunen.strip() == "Haklısın, bunu daha somut yazalım."
    son = P[-1][1]
    assert P[-1][0] == "SON" and son["rol"] == "ghost" and son["eylemler"][0]["tur"] == "fikir"
    L = s.mesajlar()
    assert [m["rol"] for m in L] == ["ben", "ghost"]
    _sahte_akis(monkeypatch, "Tamam.")
    list(s.akis("Peki neden?"))
    assert "Bu taslak bana fazla genel" in s.istem("x")                          # önceki konuşma istemde


def test_karsilama_saate_ve_odaga_gore(kok):
    s = _modul(kok)
    k = s.karsilama(saat=8)
    assert k["metin"].startswith("Günaydın") and k["secenekler"]
    assert s.karsilama(saat=21)["metin"].startswith("İyi akşamlar")
    q = s.karsilama(odak={"tur": "soru", "soru": "Bu hafta seni en çok ne şaşırttı?"})
    assert q["metin"] == "Bu hafta seni en çok ne şaşırttı?" and "Bunu neden soruyorsun?" in q["secenekler"]


def test_uclar_ve_eylemler(kok, istemci, monkeypatch):
    s = _modul(kok)
    _sahte_akis(monkeypatch, 'Şöyle yazalım.\n@@@\n{"eylemler": [{"tur": "taslak", "metin": "Kısa ve net bir gönderi.", "platform": "x"}, {"tur": "fikir", "metin": "Kısa yaz"}]}')
    assert istemci.post("/api/ghost/sohbet", json={"mesaj": ""}).status_code == 400
    r = istemci.post("/api/ghost/sohbet", json={"mesaj": "Birlikte yazalım", "acilis": "Günaydın, ne yazalım?"})
    govde = r.get_data(as_text=True)
    assert "Şöyle yazalım." in govde and "\x00SON:" in govde
    son = json.loads(govde.split("\x00SON:")[1])
    assert [m["rol"] for m in s.mesajlar()] == ["ghost", "ben", "ghost"]          # açılış da konuşmanın parçası
    assert istemci.post("/api/ghost/sohbet/eylem", json={"mesaj": "yok", "i": 0}).status_code == 404
    j = istemci.post("/api/ghost/sohbet/eylem", json={"mesaj": son["id"], "i": 0, "metin": "Kısa ve net bir gönderi, düzelttim."}).get_json()
    assert j["tamam"] and j["temel"].startswith("ghost__")
    kayit = json.loads((kok / "ghost" / f"{j['temel'][7:]}.json").read_text(encoding="utf-8"))["veri"]
    assert kayit["kaynak_tur"] == "sohbet" and kayit["paylasim"]["taslaklar"][0]["metin"] == "Kısa ve net bir gönderi, düzelttim."
    assert istemci.post("/api/ghost/sohbet/eylem", json={"mesaj": son["id"], "i": 0}).get_json()["zaten"]       # iki kez eklenmez
    assert istemci.post("/api/ghost/sohbet/eylem", json={"mesaj": son["id"], "i": 1}).get_json()["tamam"]
    import ghost_defter
    assert ghost_defter.notlar(3)[0]["metin"] == "Kısa yaz"
    g = istemci.get("/api/ghost/sohbet").get_json()
    assert len(g["mesajlar"]) == 3 and g["karsilama"]["metin"]
    istemci.delete("/api/ghost/sohbet")
    assert s.mesajlar() == []


def test_duzenle_ve_plan_eylemi(kok, istemci, monkeypatch):
    s = _modul(kok)
    (kok / "ghost").mkdir(exist_ok=True)
    (kok / "ghost" / "20261031100000_abcd.json").write_text(json.dumps({"veri": {"baslik": "d", "paylasim": {"zaman": time.time(), "taslaklar": [{"metin": "eski metin"}]}}, "segmentler": []}), encoding="utf-8")
    import ghost_danisman
    importlib.reload(ghost_danisman)
    ghost_danisman._yaz({"rapor": {"zaman": time.time(), "hafta": [{"gun": "Cuma", "tarih": "2026-10-30", "ne": "Eski plan", "mecra": "X", "hazirlandi": "ghost__x"}]}})
    _sahte_akis(monkeypatch, 'Tamam.\n@@@\n{"eylemler": [{"tur": "duzenle", "anahtar": "ghost__20261031100000_abcd#0", "metin": "yeni metin"}, {"tur": "plan", "i": 0, "ne": "Yeni plan", "neden": "daha taze"}]}')
    son = json.loads(istemci.post("/api/ghost/sohbet", json={"mesaj": "Düzelt"}).get_data(as_text=True).split("\x00SON:")[1])
    assert istemci.post("/api/ghost/sohbet/eylem", json={"mesaj": son["id"], "i": 0}).get_json()["tamam"]
    T = json.loads((kok / "ghost" / "20261031100000_abcd.json").read_text(encoding="utf-8"))["veri"]["paylasim"]["taslaklar"][0]
    assert T["metin"] == "yeni metin" and T["ilk_metin"] == "eski metin" and T["duzenlendi"]
    assert istemci.post("/api/ghost/sohbet/eylem", json={"mesaj": son["id"], "i": 1}).get_json()["tamam"]
    H = ghost_danisman._oku()["rapor"]["hafta"][0]
    assert H["ne"] == "Yeni plan" and H["ne_eski"] == "Eski plan" and "hazirlandi" not in H
