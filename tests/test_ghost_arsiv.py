"""ghost_arsiv: gündemi geçmiş öneriler arşive (2026-11-01). Sanal klasörde, örnek verilerle."""
import importlib
import json
import time


def _ghost(kok, ad, zaman, taslaklar, **veri):
    (kok / "ghost").mkdir(exist_ok=True)
    (kok / "ghost" / f"{ad}.json").write_text(json.dumps({"veri": {"baslik": "d", "kaynak_tur": "karisim", **veri,
                                                                   "paylasim": {"zaman": zaman, "ilk_zaman": zaman, "taslaklar": taslaklar}}, "segmentler": []}), encoding="utf-8")


def _hazir(kok):
    for f in (kok / "ghost").glob("*.json") if (kok / "ghost").exists() else []:
        f.unlink()
    import kitaplik_onbellek
    import ghost_arsiv
    importlib.reload(kitaplik_onbellek)
    importlib.reload(ghost_arsiv)
    return ghost_arsiv


def test_omur_kurallari_ve_dokunulmayanlar(kok):
    a = _hazir(kok)
    simdi = time.time()
    _ghost(kok, "20261028100000_aa01", simdi - 3 * 86400, [
        {"metin": "haber eski", "karisim_tur": "haber"},
        {"metin": "görüş eski ama zamansız", "karisim_tur": "gorus"},
        {"metin": "paylaşılmış", "karisim_tur": "haber", "paylasildi": True},
        {"metin": "kaldırılmış", "karisim_tur": "haber", "gizli": True, "red_nedeni": "konu uymuyor"},
        {"metin": "düzenlenmiş haber", "karisim_tur": "haber", "duzenlendi": True}])
    _ghost(kok, "20261031100000_aa02", simdi - 30 * 3600, [{"metin": "yanıt dünkü", "karisim_tur": "yanit"}, {"metin": "haber dünkü", "karisim_tur": "haber"}])
    _ghost(kok, "20261024100000_aa03", simdi - 8 * 86400, [{"metin": "eski fikir"}], kaynak_tur="fikir")
    importlib.reload(__import__("kitaplik_onbellek"))
    r = a.arsivle(simdi, log=lambda m: None)
    assert r["sayi"] == 3
    L1 = json.loads((kok / "ghost" / "20261028100000_aa01.json").read_text(encoding="utf-8"))["veri"]["paylasim"]["taslaklar"]
    assert [bool(t.get("arsiv")) for t in L1] == [True, False, False, False, False]          # zamansız 7 gün, dokunulan +5 gün, paylaşılan/kaldırılan dokunulmaz
    assert L1[0]["arsiv_neden"] == "gündemi geçti" and not L1[0].get("gizli")
    L2 = json.loads((kok / "ghost" / "20261031100000_aa02.json").read_text(encoding="utf-8"))["veri"]["paylasim"]["taslaklar"]
    assert L2[0]["arsiv"] and not L2[1].get("arsiv")                                         # yanıt 1 gün, haber 2 gün
    assert json.loads((kok / "ghost" / "20261024100000_aa03.json").read_text(encoding="utf-8"))["veri"]["paylasim"]["taslaklar"][0]["arsiv"]


def test_liste_ayri_geri_getir_ve_sohbet_tarihleri(kok, istemci):
    a = _hazir(kok)
    simdi = time.time()
    _ghost(kok, "20261028110000_bb01", simdi - 3 * 86400, [{"metin": "eski haber taslağı", "karisim_tur": "haber"}])
    _ghost(kok, "20261101090000_bb02", simdi, [{"metin": "bugünün taslağı", "karisim_tur": "haber"}])
    importlib.reload(__import__("kitaplik_onbellek"))
    a.arsivle(simdi, log=lambda m: None)
    import vh_site
    vh_site._paylasim_memo["v"] = None
    j = istemci.get("/api/paylasimlar").get_json()
    assert [t["metin"] for t in j["arsiv"]] == ["eski haber taslağı"] and "eski haber taslağı" not in [t["metin"] for t in j["taslaklar"]]
    import ghost_sohbet
    importlib.reload(ghost_sohbet)
    b = ghost_sohbet.baglam()
    assert "eski haber taslağı" not in b                                                       # arşivdeki öneri konuşmaya girmez
    assert istemci.post("/api/paylasim/ghost__20261028110000_bb01/0", json={"arsiv": False}).get_json()["tamam"]
    t = json.loads((kok / "ghost" / "20261028110000_bb01.json").read_text(encoding="utf-8"))["veri"]["paylasim"]["taslaklar"][0]
    assert t["arsiv"] is False and t["arsiv_geri"]
    importlib.reload(__import__("kitaplik_onbellek"))
    assert a.arsivle(simdi + 3600, log=lambda m: None)["sayi"] == 0                            # geri getirilen üç gün arşive gitmez
    _ghost(kok, "20261031180000_bb03", simdi - 20 * 3600, [{"metin": "dünün taslağı", "karisim_tur": "haber"}])
    importlib.reload(__import__("kitaplik_onbellek"))
    b = ghost_sohbet.baglam()
    import datetime as dt
    if dt.date.fromtimestamp(simdi - 20 * 3600) != dt.date.today():                          # gece yarısına yakın koşuda ikisi de bugündür
        assert "DÜN ÖNERDİĞİN" in b and "dünün taslağı" in b and "[tarih " in b
