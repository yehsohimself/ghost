"""oranlar.py - Tuttuğu takımın (profil `takim`) maçları: fikstür, sonuç ve bahis piyasasının olasılıkları (2026-10-24; Ghost büyük işi 6: "bahis oranı karşılaştırması").

Kaynak: ESPN'in herkese açık maç verisi (site.api.espn.com scoreboard; anahtar/giriş yok). Oran = ESPN'in gösterdiği DraftKings kapanış/son
moneyline'ı (Amerikan biçimi) → örtük olasılık → kâr payı (overround) çıkarılarak üç sonuca normalize. Bahis OYNANMAZ, yalnız karşılaştırma:
kullanıcının maç tahmini karnesinde "siz / piyasa" Brier puanı ve maç kartında "piyasa ne diyor". Ayrıca: maç günü tespiti haber başlıklarından
daha güvenilir (fikstür + saat), maç bitince sonuç kendiliğinden karneye işlenir.
"""
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

KLASOR = Path(__file__).resolve().parent
ONB = KLASOR / "kayitlar" / "mac"
LIGLER = ["tur.1", "uefa.champions", "uefa.europa", "tur.cup", "uefa.conference"]
def _takim():
    import ortak
    return ortak.kimlik()["takim"]                          # tuttuğu takım profil/x.json `takim`; boşsa maç kartı çıkmaz
TSI = timezone(timedelta(hours=3))


TR_AD = {"Fenerbahce": "Fenerbahçe", "Besiktas": "Beşiktaş", "Istanbul Basaksehir": "Başakşehir", "Caykur Rizespor": "Çaykur Rizespor",
         "Goztepe": "Göztepe", "Kasimpasa": "Kasımpaşa", "Eyupspor": "Eyüpspor", "Genclerbirligi": "Gençlerbirliği", "Kocaelispor": "Kocaelispor",
         "Fatih Karagumruk": "Fatih Karagümrük", "Turkish Super Lig": "Süper Lig", "UEFA Champions League": "Şampiyonlar Ligi",
         "UEFA Europa League": "Avrupa Ligi", "Turkish Cup": "Türkiye Kupası", "UEFA Conference League": "Konferans Ligi"}


def _tr(ad):
    return TR_AD.get(ad, ad)


def _amerikan(o):
    try:
        o = float(str(o).replace("+", ""))
    except (TypeError, ValueError):
        return None
    if o == 0:
        return None
    return 100 / (o + 100) if o > 0 else -o / (-o + 100)


def _oran_coz(c):
    """ESPN competitions[0] → {ev, beraber, deplasman} olasılıkları (normalize) ya da None."""
    o = (c.get("odds") or [None])[0] or {}
    ml = o.get("moneyline") or {}

    def al(taraf):
        t = ml.get(taraf) or {}
        return (t.get("close") or {}).get("odds") or (t.get("current") or {}).get("odds") or (t.get("open") or {}).get("odds")
    ev, dep = _amerikan(al("home")), _amerikan(al("away"))
    ber = _amerikan((o.get("drawOdds") or {}).get("moneyLine"))
    if not (ev and dep and ber):
        return None
    t = ev + dep + ber
    return {"ev": round(ev / t, 3), "beraber": round(ber / t, 3), "deplasman": round(dep / t, 3), "kaynak": (o.get("provider") or {}).get("name", "ESPN")}


def mac(gun=None):
    """O gün takımın maçı: {var, rakip, ev_sahibi, saat (TSİ), turnuva, durum, skor, sonuc G|B|M, piyasa {G,B,M}}."""
    gun = gun or date.today().isoformat()
    d = gun.replace("-", "")
    for lig in LIGLER:
        try:
            j = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{lig}/scoreboard", params={"dates": d}, timeout=15).json()
        except Exception:  # noqa: BLE001
            continue
        for e in j.get("events") or []:
            if _takim().lower() not in e.get("name", "").lower():
                continue
            c = e["competitions"][0]
            T = {x["homeAway"]: x for x in c["competitors"]}
            ev = _takim().lower() in T["home"]["team"]["displayName"].lower()
            biz, onlar = (T["home"], T["away"]) if ev else (T["away"], T["home"])
            bas = datetime.fromisoformat(e["date"].replace("Z", "+00:00")).astimezone(TSI)
            durum = c["status"]["type"]["name"]
            out = {"var": True, "rakip": _tr(onlar["team"]["displayName"]), "ev_sahibi": ev, "saat": bas.strftime("%H.%M"), "bas": bas.timestamp(),
                   "turnuva": _tr((j.get("leagues") or [{}])[0].get("name", lig)), "durum": durum, "espn_id": e.get("id")}
            if durum in ("STATUS_FULL_TIME", "STATUS_FINAL", "STATUS_FINAL_AET", "STATUS_FINAL_PEN"):
                a, b = int(biz.get("score") or 0), int(onlar.get("score") or 0)
                out["skor"] = f"{a}-{b}"
                out["sonuc"] = "G" if a > b else "B" if a == b else "M"
                if durum == "STATUS_FINAL_PEN" or biz.get("winner") is True and a == b:
                    out["sonuc"] = "G" if biz.get("winner") else ("M" if onlar.get("winner") else "B")
            p = _oran_coz(c)
            if p:
                out["piyasa"] = {"G": p["ev"] if ev else p["deplasman"], "B": p["beraber"], "M": p["deplasman"] if ev else p["ev"], "kaynak": p["kaynak"]}
            return out
    return {"var": False}


def piyasa_kaydet(gun=None):
    """Maç öncesi piyasa olasılığını günün kaydına yazar (sonradan ESPN oranı kaldırabilir; karşılaştırma maç öncesi orana göre yapılır)."""
    gun = gun or date.today().isoformat()
    m = mac(gun)
    if not m.get("var"):
        return m
    yol = ONB / f"piyasa_{gun}.json"
    ONB.mkdir(parents=True, exist_ok=True)
    try:
        eski = json.loads(yol.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        eski = {}
    if m.get("piyasa") and m.get("durum") == "STATUS_SCHEDULED":
        eski = {"piyasa": m["piyasa"], "zaman": time.time(), "rakip": m["rakip"]}
        yol.write_text(json.dumps(eski, ensure_ascii=False), encoding="utf-8")
    m["piyasa_once"] = eski.get("piyasa")
    return m


if __name__ == "__main__":
    import sys
    print(json.dumps(mac(sys.argv[1] if len(sys.argv) > 1 else None), ensure_ascii=False, indent=1))
