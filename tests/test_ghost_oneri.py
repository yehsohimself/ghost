"""ghost_oneri: dışarıdan gelen yazı önerileri (2026-10-31). Hepsi sanal klasörde, örnek verilerle; Claude çağrıları sahte."""
import importlib
import json
import shutil
import time


def _temiz(kok):
    import ghost_oneri
    importlib.reload(ghost_oneri)
    shutil.rmtree(kok / "kayitlar" / "ghost_oneriler", ignore_errors=True)
    for f in (kok / "ghost").glob("*.json") if (kok / "ghost").exists() else []:
        f.unlink()
    import kitaplik_onbellek
    importlib.reload(kitaplik_onbellek)
    ghost_oneri._dis_onbellek["t"] = 0.0
    return ghost_oneri


def _ghost(kok, ad, taslaklar, **veri):
    (kok / "ghost").mkdir(exist_ok=True)
    (kok / "ghost" / f"{ad}.json").write_text(json.dumps({"veri": {"baslik": "d", "kaynak_tur": "kesif", **veri,
                                                                   "paylasim": {"zaman": time.time(), "ilk_zaman": time.time(), "taslaklar": taslaklar}},
                                                          "segmentler": []}), encoding="utf-8")


def test_orijinal_degismeden_saklanir_ve_tekrar_acilmaz(kok):
    g = _temiz(kok)
    d, yeni = g.ekle("Yapay zekâ çağında bilerek zorlanmak: yetişkin yaratıcılar için kasıtlı pratik", kaynak_url="https://www.newyorker.com/x?utm_source=tw",
                     arastirma_notu="Kaynak yeniden okunmadı.", tarih="21.09.2026", uretici="ChatGPT · dot")
    assert yeni and d["durum"] == "geldi" and d["ozgun"]["tarih"] == "2026-09-21" and d["ozgun"]["uretici"] == "ChatGPT · dot"
    assert d["ozgun"]["arastirma_notu"] == "Kaynak yeniden okunmadı." and d["ozgun_sha"]
    d2, yeni2 = g.ekle("Yapay zekâ çağında bilerek zorlanmak: yetişkin yaratıcılar için kasıtlı pratik")
    assert not yeni2 and d2["id"] == d["id"]
    bozuk = {**d, "ozgun": {**d["ozgun"], "metin": "değiştirilmiş"}}
    try:
        g._yaz(bozuk)
        assert False, "orijinal değiştirilebildi"
    except ValueError:
        pass
    assert g._oku(d["id"])["ozgun"]["metin"].startswith("Yapay zekâ çağında")


def test_kaynak_aci_tarih_ile_tekrar(kok):
    g = _temiz(kok)
    a, _ = g.ekle("Kulüp taraftar oylamasıyla üçüncü forma seçiyor ama renkler kulübün elinde", kaynak_url="https://site.com/forma/")
    b, _ = g.ekle("Kulüp üçüncü formayı taraftar oylamasıyla seçiyor; renk kulübün elinde kalıyor", kaynak_url="https://www.site.com/forma?utm_medium=x")
    assert b["durum"] == "tekrar" and b["tekrar"]["ile"] == a["id"]
    c, _ = g.ekle("Forma tasarımcılarının telif hakkı kimde: üretici mi, kulüp mü", kaynak_url="https://site.com/forma")
    assert c["durum"] == "geldi" and c["tekrar"]["tur"] == "baska_aci"
    _ghost(kok, "20261031100000_aaaa", [{"metin": "Bebek cildinde pişikten koruyan kremler üzerine kısa bir not", "paylas_link": "https://ornek.org/pisik",
                                          "paylasildi": True}])
    importlib.reload(__import__("kitaplik_onbellek"))
    e, _ = g.ekle("Bebek cildinde pişik kremleri: koruyan krem üzerine not", kaynak_url="https://ornek.org/pisik/")
    assert e["durum"] == "tekrar" and "paylaşıldı" in e["tekrar"]["neden"]


def test_havuz_notlari_onay_sayilmaz(kok):
    g = _temiz(kok)
    (kok / "kayitlar" / "secki").mkdir(parents=True, exist_ok=True)
    (kok / "kayitlar" / "secki" / "havuz.json").write_text(json.dumps([
        {"id": "I-001", "oneri": "AI çağında bilerek zorlanmak", "ne": "Önce blog, sonra kısa X.", "durum": "Seçildi", "test": "Bir paragraf yaz.",
         "kaynak": "https://www.newyorker.com/a", "kanit": "Editör yazı fikrini olumlu bulmuş; yayımlanma kanıtı yok.", "tarih": "21.09.2026"},
        {"id": "I-002", "oneri": "", "ne": "boş satır"}]), encoding="utf-8")
    assert g.havuzdan_al() == 1 and g.havuzdan_al() == 0
    d = g.liste()[0]
    assert d["durum"] == "geldi" and d["ozgun"]["kanal"] == "drive_havuz" and d["ozgun"]["kaynak_durum"] == "Seçildi"
    assert "olumlu" in d["ozgun"]["arastirma_notu"] and not d.get("kisi_karari")


def test_format_karari_son_metin_ve_duzeltme_ezilmez(kok, monkeypatch):
    g = _temiz(kok)
    import ghost_kurulum
    import paylasim
    monkeypatch.setattr(ghost_kurulum, "kurulu_mu", lambda: True)
    kararlar = iter([{"format": "x", "neden": "Tek ayrıntı, tek gönderi.", "uygunluk": 4, "aci": "renk oylaması"},
                     {"format": "x", "neden": "Yine X.", "uygunluk": 3, "aci": "ikinci açı"},
                     {"format": "x", "neden": "Üçüncü.", "uygunluk": 3, "aci": "üçüncü"}])
    monkeypatch.setattr(paylasim, "_claude_json", lambda *a, **k: next(kararlar))
    sayac = {"n": 0}

    def sahte_uret(yol, log=print, en_cok=3):
        sayac["n"] += 1
        d = json.loads(yol.read_text(encoding="utf-8"))
        assert d["veri"]["kaynak_tur"] == "dis_oneri" and "kişinin sözü değil" in d["veri"]["girdi_metin"]
        d["veri"]["paylasim"] = {"taslaklar": [{"metin": f"Ghost'un {sayac['n']}. metni: kulüp rengi oylamaya açmadı", "platform": "x"}], "zaman": time.time(),
                                 "ilk_zaman": time.time()}
        yol.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(paylasim, "uret", sahte_uret)
    o, _ = g.ekle("Kulüpler forma oylamasını taraftara açıyor ama rengi kendileri seçiyor; bunu ironik yaz", kaynak_url="https://site.com/oylama")
    d = g.isle(o["id"], log=lambda m: None)
    assert d["durum"] == "yazildi" and d["karar"]["format"] == "x" and len(d["surumler"]) == 1
    yol = kok / "ghost" / f"{d['surumler'][0]['temel'][7:]}.json"
    t = json.loads(yol.read_text(encoding="utf-8"))["veri"]["paylasim"]["taslaklar"][0]
    assert t["dis_oneri"] == o["id"] and t["format_karari"]["format"] == "x" and t["kaynak"]["tur"] == "ChatGPT önerisi" and t["kaynak"]["link"]
    v = json.loads(yol.read_text(encoding="utf-8"))           # kişi düzeltti
    v["veri"]["paylasim"]["taslaklar"][0].update(ilk_metin=t["metin"], metin="Kişinin kendi düzelttiği metin", duzenlendi=True)
    yol.write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")
    d = g.isle(o["id"], log=lambda m: None)                   # yeniden değerlendir: yeni sürüm, eskisi ezilmez
    t1 = json.loads(yol.read_text(encoding="utf-8"))["veri"]["paylasim"]["taslaklar"][0]
    assert t1["metin"] == "Kişinin kendi düzelttiği metin" and not t1.get("gizli")
    assert len(d["surumler"]) == 2 and d["surumler"][0]["aktif"] and d["surumler"][1]["aktif"]
    g.isle(o["id"], log=lambda m: None)                       # dokunulmamış ikinci sürüm üçüncü gelince gizlenir (öğrenme yok)
    yol2 = kok / "ghost" / f"{d['surumler'][1]['temel'][7:]}.json"
    t2 = json.loads(yol2.read_text(encoding="utf-8"))["veri"]["paylasim"]["taslaklar"][0]
    assert t2["gizli"] and t2["degistirildi"] and "yeni sürüm" in t2["red_nedeni"]
    assert g._oku(o["id"])["ozgun"]["metin"].startswith("Kulüpler forma oylamasını")


def test_blog_ve_gec(kok, monkeypatch):
    g = _temiz(kok)
    import claude_yaz
    import ghost_kurulum
    import paylasim
    monkeypatch.setattr(ghost_kurulum, "kurulu_mu", lambda: True)
    monkeypatch.setattr(paylasim, "_claude_json", lambda *a, **k: {"format": "blog", "neden": "Bağlam ister.", "uygunluk": 5, "aci": "kasıtlı zorluk"})
    monkeypatch.setattr(claude_yaz, "sor", lambda *a, **k: "# Bilerek zorlanmak\n\n" + "Bir paragraf düşünce. " * 60 + "\n\n## Kaynaklar\n- https://x.org")
    o, _ = g.ekle("Yetişkinlerin öğrenmesinde zorluğun yeri üzerine uzun bir yazı")
    d = g.isle(o["id"], log=lambda m: None)
    assert d["durum"] == "yazildi" and d["surumler"][0]["blog"]["metin"].startswith("# Bilerek")
    g.blog_duzelt(o["id"], "# Benim başlığım\n\nKendi düzeltmem")
    s = g._oku(o["id"])["surumler"][0]["blog"]
    assert s["metin"].startswith("# Bilerek") and s["kisi_metni"].startswith("# Benim")    # Ghost'un metni ayrı kalır
    p, _ = g.ekle("Bugün hava güzel, paylaşalım mı")
    monkeypatch.setattr(paylasim, "_claude_json", lambda *a, **k: {"format": "gec", "neden": "Söylenecek bir şey yok.", "uygunluk": 1})
    assert g.isle(p["id"], log=lambda m: None)["durum"] == "gecildi"


def test_ogrenme_disi(kok, monkeypatch):
    g = _temiz(kok)
    import paylasim
    o, _ = g.ekle("Orijinal ChatGPT önerisinin uzun cümlesi burada duruyor ve öğrenilmemeli")
    _ghost(kok, "20261031110000_bbbb", [{"metin": "Ghost'un önerinin fikrinden yazdığı son metin", "ilk_metin": "Ghost'un ilk hali", "dis_oneri": o["id"]}],
           kaynak_tur="dis_oneri")
    importlib.reload(__import__("kitaplik_onbellek"))
    g._dis_onbellek["t"] = 0
    assert g.ogrenme_disi("Ghost'un önerinin fikrinden yazdığı son metin") and g.ogrenme_disi("Ghost'un ilk hali")
    assert g.ogrenme_disi("Orijinal ChatGPT önerisinin uzun cümlesi burada duruyor ve öğrenilmemeli")
    assert not g.ogrenme_disi("Kişinin tamamen kendi yazdığı başka bir gönderi")
    havuz_once = paylasim.havuz()
    paylasim.havuza_ekle({"metin": "Ghost'un önerinin fikrinden yazdığı son metin", "dis_oneri": o["id"]})
    assert paylasim.havuz() == havuz_once
    once = list(paylasim.profil().get("paylasilan") or [])
    paylasim.ogren("paylasilan", "Ghost'un önerinin fikrinden yazdığı son metin")
    assert list(paylasim.profil().get("paylasilan") or []) == once
    paylasim.ogren("paylasilan", "Kişinin tamamen kendi yazdığı başka bir gönderi")
    assert "Kişinin tamamen kendi yazdığı başka bir gönderi" in paylasim.profil().get("paylasilan")


def test_disa_aktarma_bolumleri_karismaz(kok, istemci):
    g = _temiz(kok)
    o, _ = g.ekle("Önerinin orijinali: kulüp renkleri oylamada değil", kaynak_url="https://site.com/r", uretici="ChatGPT")
    _ghost(kok, "20261031120000_cccc", [
        {"metin": "seçtiği", "begendi": True},
        {"metin": "kişinin son hali", "ilk_metin": "ghost metni", "duzenlendi": True, "paylasildi": True, "dis_oneri": o["id"]},
        {"metin": "sistem eşleştirdi", "paylasildi": True, "oto_tanindi": True},
        {"metin": "reddettiği", "gizli": True, "red_nedeni": "konu uymuyor"},
        {"metin": "sistemin değiştirdiği", "gizli": True, "degistirildi": True, "red_nedeni": "daha güçlü bir öneriyle değiştirildi"},
        {"metin": "dokunulmamış"}])
    importlib.reload(__import__("kitaplik_onbellek"))
    v = g.disa_aktar(30)
    metinler = lambda b: [x["son_metin"] for x in v[b]]   # noqa: E731
    assert metinler("secilen") == ["seçtiği"] and metinler("reddedilen") == ["reddettiği"]
    assert metinler("paylasilan") == ["kişinin son hali"] and metinler("duzeltilen") == ["kişinin son hali"]
    assert v["duzeltilen"][0]["ghost_metni"] == "ghost metni" and metinler("sistem_eslestirdi") == ["sistem eşleştirdi"]
    hepsi = [m for b in ("secilen", "duzeltilen", "paylasilan", "sistem_eslestirdi") for m in metinler(b)]
    assert "reddettiği" not in hepsi and "sistemin değiştirdiği" not in hepsi + metinler("reddedilen") and "dokunulmamış" not in hepsi
    on = next(x for x in v["oneriler"] if x["id"] == o["id"])
    assert on["orijinal"].startswith("Önerinin orijinali") and on["kisinin_sonucu"] == "paylasti"
    r = istemci.get("/api/ghost/disa-tercihler?gun=30&bicim=md")
    assert r.status_code == 200 and "attachment" in r.headers["Content-Disposition"] and "Reddettikleri (örnek değil)" in r.get_data(as_text=True)
    j = istemci.get("/api/ghost/disa-tercihler?gun=30")
    assert j.get_json()["sema"] == "ghost/kullanici-tercihleri@1"


def test_uclar(kok, istemci):
    _temiz(kok)
    assert istemci.post("/api/ghost/oneri", json={"metin": "kısa"}).status_code == 400
    r = istemci.post("/api/ghost/oneri", json={"metin": "Bir öneri metni: oylama ve renk", "kaynak_url": "https://a.com", "yaz": False}).get_json()
    assert r["yeni"] and r["oneri"]["durum"] == "geldi"
    assert istemci.post("/api/ghost/oneri", json={"metin": "Bir öneri metni: oylama ve renk", "yaz": False}).get_json()["yeni"] is False
    L = istemci.get("/api/ghost/oneriler").get_json()["oneriler"]
    assert len(L) == 1 and L[0]["ozgun_saglam"]
    assert istemci.post(f"/api/ghost/oneri/{L[0]['id']}", json={"islem": "gec", "neden": "bana göre değil"}).get_json()["oneri"]["durum"] == "gecildi"
    assert istemci.post("/api/ghost/oneri/..%2fx", json={"islem": "gec"}).status_code in (400, 404, 405)
