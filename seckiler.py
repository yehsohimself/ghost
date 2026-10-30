"""seckiler.py - ChatGPT'nin Drive'a bıraktığı günlük "Okuma ve Yayın Seçkisi" ve "Öneri Havuzu" tablosu (2026-10-21; kullanıcı: "ChatGPT de
sürekli bunu yapıyor, ek kaynak olarak bak"). İş bölümü: ChatGPT okuma masası (kaynak, kanıt sınırı, hipotez), Ghost yazı masası.
ChatGPT seçkide "Yayın potansiyeli: 0 · eksik olan kullanıcının gerçek iş kanıtı" diyor; Ghost bu yüzden her konuda kullanıcıya "Bunun sizde
karşılığı var mı?" diye sorar ve yazıyı o cümlenin etrafında kurar.

Drive'a yalnızca OKUMA izniyle bağlanılır (rclone uzak `gdrive_oku`, scope drive.readonly; site Ayarlar'dan kurar). Belge Google Docs →
docx olarak indirilir, başlık düzeyleri korunarak markdown'a çevrilir, bölümlere ayrılır. Sonuç `kayitlar/secki/<tarih>.json`.
"""
import csv
import io
import json
import re
import subprocess
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
RCLONE = "/opt/homebrew/bin/rclone"
UZAK = "gdrive_oku"
SECKI = KLASOR / "kayitlar" / "secki"
SECKI_KLASOR_ID = ""        # ayarlar.json `secki_klasor_id`: seçki belgelerinin Drive klasörü
HAVUZ_ID = ""               # ayarlar.json `secki_havuz_id`: öneri havuzu tablosu


def _ayar():
    import ortak                                           # tek sürüm (sırlar dahil; 2026-10-25)
    return ortak.ayar()


def bagli():
    try:
        p = subprocess.run([RCLONE, "listremotes"], capture_output=True, text=True, timeout=15)
        return f"{UZAK}:" in p.stdout.split()
    except Exception:  # noqa: BLE001
        return False


def _rclone(*arg, zaman=120):
    p = subprocess.run([RCLONE, *arg], capture_output=True, text=True, timeout=zaman)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout).strip().splitlines()[-1] if (p.stderr or p.stdout).strip() else "Drive okunamadı")
    return p.stdout


# ---------------------------------------------------------------- belge → markdown → bölümler
def docx_md(yol):
    """docx paragraflarını başlık düzeyleriyle markdown satırlarına çevirir ('# ', '## ')."""
    import docx
    d = docx.Document(str(yol))
    satirlar = []
    for p in d.paragraphs:
        t = p.text.strip()
        if not t:
            continue
        ad = (p.style.name or "").lower()
        m = re.search(r"(heading|başlık)\s*(\d)", ad)
        if ad == "title":
            satirlar.append("# " + t)
        elif m:
            satirlar.append("#" * int(m.group(2)) + " " + t)
        else:
            satirlar.append(t)
    return "\n\n".join(satirlar)


def _temiz(t):
    return re.sub(r"\\([\\.\-_*()#\[\]])", r"\1", re.sub(r"\*\*(.+?)\*\*", r"\1", str(t))).strip()


def _urller(t):
    return list(dict.fromkeys(u.rstrip(">).,") for u in re.findall(r"https?://[^\s<>)]+", t)))


def ayristir(md):
    """Seçki markdown'ı → {ozet, konular[{no, baslik, metin, neden, kanit_siniri, kaynaklar, geldigi}], hipotez{baslik, metin}, yayin, yap}."""
    bolumler, h1, h2, buf = [], "", "", []

    def kapat():
        if buf or h2:
            bolumler.append((h1, h2, "\n\n".join(buf).strip()))

    for satir in md.splitlines():
        s = satir.strip()
        if not s:
            continue
        m = re.match(r"^(#{1,3})\s+(.*)", s)
        if m and len(m.group(1)) == 1:
            kapat(); h1, h2, buf = _temiz(m.group(2)), "", []
        elif m:
            kapat(); h2, buf = _temiz(m.group(2)), []
        else:
            buf.append(s)
    kapat()
    out = {"ozet": "", "konular": [], "hipotez": {}, "yayin": "", "yap": ""}
    for b1, b2, metin in bolumler:
        k1 = b1.lower()
        if not out["ozet"] and re.search(r"kısa sonu[çc]|okuma notu", (b2 + " " + metin[:200]).lower()):
            out["ozet"] = _temiz(re.sub(r"^.*?(kısa sonu[çc]u?|okuma notu)\s*:\s*", "", b2 or metin.split("\n")[0], flags=re.I))
        if "bilmeye değer" in k1 and b2:
            neden = re.search(r"(?:Neden önemli|(?:Benim|Senin|Sizin) için (?:anlamı|neden önemli))\s*:?\**\s*:?\s*(.+?)(?:\n\n|$)", metin, re.S)
            sinir = re.search(r"Kanıt sınırı\s*:?\**\s*:?\s*(.+?)(?:\n\n|$)", metin, re.S)
            geldigi = re.search(r"Geldiği yer\s*:?\**\s*:?\s*(.+?)(?:\n|$)", metin)
            govde = re.split(r"\n\n(?:\**)?(?:Neden önemli|Kanıt sınırı|Benim için|Senin için|Sizin için|Geldiği yer|Özgün|Önceki kanıt|Birincil|Bağımsız|Kurum yanıtı|Kantan keşif)", metin)[0]
            no = re.match(r"^(\d+)[.)]?\s*", b2)
            out["konular"].append({"no": int(no.group(1)) if no else len(out["konular"]) + 1, "baslik": _temiz(re.sub(r"^\d+[.)]?\s*", "", b2)),
                                   "metin": _temiz(re.sub(r"https?://\S+", "", govde))[:2500], "neden": _temiz(neden.group(1))[:800] if neden else "",
                                   "kanit_siniri": _temiz(sinir.group(1))[:800] if sinir else "", "kaynaklar": _urller(metin)[:8],
                                   "geldigi": _temiz(geldigi.group(1))[:200] if geldigi else ""})
        elif "aslında ne oluyor" in k1:
            out["hipotez"] = {"baslik": _temiz(re.sub(r"^.*?hipotez\s*:\s*", "", b2, flags=re.I)) if b2 else "", "metin": _temiz(metin)[:2500]}
        elif "yayın potansiyeli" in k1:
            out["yayin"] = _temiz(metin)[:600]
        elif k1.startswith("yap"):
            out["yap"] = _temiz(metin)[:1200]
    return out


# ---------------------------------------------------------------- Drive'dan getir
def _bugun_adi(gun):
    return f"{gun.isoformat()} · Günlük Okuma ve Yayın Seçkisi"


def getir(gun=None, zorla=False):
    """O günün seçkisi (yoksa en yeni) → ayrıştırılmış sözlük; önbellek kayitlar/secki/<tarih>.json. Bağlı değilse None."""
    SECKI.mkdir(parents=True, exist_ok=True)
    gun = gun or date.today()
    onb = SECKI / f"{gun.isoformat()}.json"
    if onb.exists() and not zorla:
        return json.loads(onb.read_text(encoding="utf-8"))
    if not bagli():
        return None
    kid = _ayar().get("secki_klasor_id") or SECKI_KLASOR_ID
    adlar = [a.strip() for a in _rclone("lsf", f"{UZAK}:", "--drive-root-folder-id", kid, "--drive-export-formats", "docx", "--files-only").splitlines()]
    adaylar = sorted([a for a in adlar if re.match(r"^\d{4}-\d{2}-\d{2} · ", a)], reverse=True)
    hedef = next((a for a in adaylar if a.startswith(gun.isoformat())), None)
    if not hedef:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        _rclone("copyto", f"{UZAK}:{hedef}", f"{tmp}/s.docx", "--drive-root-folder-id", kid, "--drive-export-formats", "docx")
        md = docx_md(Path(tmp) / "s.docx")
    s = ayristir(md)
    s.update({"tarih": gun.isoformat(), "ad": hedef.rsplit(".", 1)[0], "zaman": time.time(), "kaynak": "ChatGPT · Günlük Okuma ve Yayın Seçkisi"})
    onb.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    return s


def son(gun_say=3):
    """Bugün yoksa son birkaç günün en yenisi (önbellekten ya da Drive'dan)."""
    for n in range(gun_say):
        try:
            s = getir(date.today() - timedelta(days=n))
        except Exception:  # noqa: BLE001
            s = None
        if s and s.get("konular"):
            return s
    return None


def havuz(zorla=False):
    """Öneri Havuzu'ndaki 'Paylaşım' satırları (yayımlanmamış): [{id, oneri, ne, durum, test, kaynak, kanit}]. 6 saat önbellek."""
    SECKI.mkdir(parents=True, exist_ok=True)
    onb = SECKI / "havuz.json"
    if onb.exists() and not zorla and time.time() - onb.stat().st_mtime < 6 * 3600:
        return json.loads(onb.read_text(encoding="utf-8"))
    if not bagli():
        return []
    hid = _ayar().get("secki_havuz_id") or HAVUZ_ID
    with tempfile.TemporaryDirectory() as tmp:
        _rclone("backend", "copyid", f"{UZAK}:", hid, f"{tmp}/", "--drive-export-formats", "csv")
        dosya = next(Path(tmp).glob("*.csv"), None)
        if not dosya:
            return []
        satirlar = list(csv.reader(io.StringIO(dosya.read_text(encoding="utf-8-sig"))))
    bas = next((i for i, r in enumerate(satirlar) if r and r[0].strip() == "ID"), None)
    if bas is None:
        return []
    ad = [h.strip() for h in satirlar[bas]]
    al = lambda r, k: (r[ad.index(k)].strip() if k in ad and ad.index(k) < len(r) else "")   # noqa: E731
    out = []
    for r in satirlar[bas + 1:]:
        if not r or not r[0].strip() or al(r, "Alan").lower() != "paylaşım":
            continue
        durum = al(r, "Durum")
        if re.search(r"yayın|kapandı|elendi|iptal", durum, re.I):
            continue
        out.append({"id": r[0].strip(), "oneri": al(r, "Öneri"), "ne": al(r, "Ne yapılacak?"), "durum": durum, "test": al(r, "En küçük test"),
                    "kaynak": al(r, "Özgün kaynak URL"), "kanit": al(r, "Kanıt ve sınır"), "tarih": al(r, "Öneri tarihi")})
    onb.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def ghost_girdisi(konu, deneyim="", secki=None):
    """Seçki konusu (ya da havuz fikri) + kullanıcının kendi karşılığı → Ghost'a verilecek metin."""
    if "oneri" in konu:      # Öneri Havuzu satırı
        g = f"FİKİR: {konu['oneri']}\nNE YAPILACAK: {konu.get('ne', '')}\n" + (f"KAYNAK: {konu['kaynak']}\n" if konu.get("kaynak") else "")
    else:
        g = (f"KONU: {konu['baslik']}\n{konu.get('metin', '')}\n" + (f"NEDEN ÖNEMLİ: {konu['neden']}\n" if konu.get("neden") else "")
             + (f"KANIT SINIRI (bunun ötesini iddia etme): {konu['kanit_siniri']}\n" if konu.get("kanit_siniri") else "")
             + (f"KAYNAKLAR: {', '.join(konu.get('kaynaklar') or [])}\n" if konu.get("kaynaklar") else ""))
        if secki and (secki.get("hipotez") or {}).get("baslik"):
            g += f"O GÜNÜN HİPOTEZİ (ChatGPT seçkisi): {secki['hipotez']['baslik']}\n"
    if deneyim.strip():
        g += f"\nKİŞİNİN KENDİ KARŞILIĞI (gönderinin merkezi bu; kendi işinden/gözleminden; olduğu gibi kullan, büyütme):\n{deneyim.strip()}\n"
    return g


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and Path(sys.argv[1]).exists():
        print(json.dumps(ayristir(Path(sys.argv[1]).read_text(encoding="utf-8")), ensure_ascii=False, indent=1))
    else:
        print("bağlı" if bagli() else "bağlı değil")
