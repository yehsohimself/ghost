"""ghost_kurulum: herkes kendi sesini, konularını ve kaynaklarını kurar (2026-10-29, Ghost herkese açık depo olarak çıkarken)."""
import importlib
import json


def _kurulum(kok, monkeypatch):
    import ghost_kurulum
    importlib.reload(ghost_kurulum)
    for ad in ("x.json", "kaynaklar.json"):
        (kok / "profil" / ad).unlink(missing_ok=True)
    monkeypatch.setattr(ghost_kurulum, "_akis_dene", lambda alan, k: bool(k.get("sorgu")) or "iyi" in str(k.get("url")))
    return ghost_kurulum


def test_kurulmadan_yazmaz_ve_arayuz_kurulum_ister(kok, istemci, monkeypatch):
    g = _kurulum(kok, monkeypatch)
    assert not g.kurulu_mu()
    j = istemci.get("/api/ghost/kurulum").get_json()
    assert j["kurulu"] is False and "en" in j["diller"]
    assert istemci.post("/api/ghost/kurulum", json={}).status_code == 400          # konu yoksa kurulum başlamaz


def test_kur_profil_ve_kaynaklari_yazar(kok, monkeypatch):
    g = _kurulum(kok, monkeypatch)
    import claude_yaz
    yanit = {"kimlik": "Designer who writes about type.", "tarz": "Short, dry.", "persona": {"karakter": "a calm designer", "merkez": "x", "ilkeler": ["one idea"]},
             "alanlar": [{"kod": "Type Design!", "ad": "Type design", "agirlik": 5, "not": "foundries"}, {"kod": "f1", "ad": "Formula 1", "agirlik": 1}],
             "kacin": ["politics"], "trend": ["gb", "zzz"],
             "kaynaklar": {"typedesign": [{"ad": "Iyi Feed", "url": "https://iyi.example/feed"}, {"ad": "Bozuk", "url": "https://bozuk.example/rss"}],
                           "f1": [{"ad": "Kötü", "url": "ftp://x"}], "uydurma": [{"ad": "Z", "url": "https://iyi.example/z"}]}}
    monkeypatch.setattr(claude_yaz, "sor_json", lambda *a, **k: yanit)
    s = g.kur({"kullanici": "@ada_lovelace!", "dil": "en", "kim": "designer", "ornekler": "first post here, long enough\n\nsecond post is also long", "konular": "Type, F1"})
    p = json.loads((kok / "profil" / "x.json").read_text(encoding="utf-8"))
    k = json.loads((kok / "profil" / "kaynaklar.json").read_text(encoding="utf-8"))
    assert p["kullanici"] == "ada_lovelace" and p["dil"] == "en" and len(p["ornekler"]) == 2
    assert [a["kod"] for a in p["alanlar"]] == ["typedesign", "f1"] and p["alanlar"][0]["agirlik"] == 3
    assert [x["ad"] for x in k["alanlar"]["typedesign"]][0] == "Iyi Feed" and "Bozuk" in " ".join(s["atilan"])
    assert "uydurma" not in k["alanlar"]                                              # profilde olmayan alanın kaynağı alınmaz
    assert any(x.get("sorgu") for x in k["alanlar"]["f1"])                             # kaynağı kalmayan alana arama eklenir
    assert k["trend"] == ["GB"] and g.kurulu_mu()


def test_kesif_profildeki_kaynaklari_okur(kok, monkeypatch):
    g = _kurulum(kok, monkeypatch)
    (kok / "profil" / "kaynaklar.json").write_text(json.dumps({"alanlar": {"tasarim": [{"ad": "A", "url": "https://iyi.example/a", "derin": True},
                                                                                        {"ad": "B", "sorgu": "type foundry", "dil": "en"},
                                                                                        {"ad": "C", "url": "https://iyi.example/c", "kapali": True}]},
                                                              "trend": ["us"]}), encoding="utf-8")
    import kesif
    importlib.reload(kesif)
    kaynaklar, derin, trend = kesif.kaynak_listesi()
    assert [a for a, _ in kaynaklar["tasarim"]] == ["A", "B"] and "news.google.com" in kaynaklar["tasarim"][1][1]
    assert derin == {"A"} and trend == ["US"]
    g.kaynak_ekle("tasarim", sorgu="variable fonts")
    try:
        g.kaynak_ekle("tasarim", url="https://bozuk.example/rss")
        assert False, "okunamayan akış eklenmemeliydi"
    except ValueError:
        pass
    g.kaynak_sil("tasarim", "A")
    assert [x["ad"] for x in g.kaynaklar()["alanlar"][0]["kaynaklar"]] == ["B", "C", "variable fonts"]


def test_baska_dilde_turkce_duzeltme_yok(monkeypatch):
    import ghost_rehber
    import claude_yaz
    monkeypatch.setenv("VH_YAZI_DILI", "en")
    assert ghost_rehber.dil_duzelt("salt + pepper") == "salt + pepper"
    assert not ghost_rehber.dil_notlari("plain sentence + more")
    monkeypatch.setenv("VH_YAZI_DILI", "tr")
    assert claude_yaz.yazi_dili_kodu() == "tr" and ghost_rehber.dil_duzelt("tuz + biber") == "tuz ve biber"
