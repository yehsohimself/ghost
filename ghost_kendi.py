"""ghost_kendi.py - Kendi işlerinden somut konu (2026-10-24; Ghost'un öz değerlendirmesinden kabul edilen öneri).

Ölçüm: kişinin o hafta kendi yazdığı 7 gönderinin 4'ü kurduğu araçlarla ilgiliydi ("Transcript vol. 2", Dots → Duet taşıma, "GitHub repolu creative
director"); Ghost'un 4 kendi_arac önerisine ise hiç dokunulmadı (genel "kendi aracını yap" fikirleri). Sebep: karışım yalnızca son 36 saatin tek tek
çalışma kayıtlarını görüyordu.

Burada günde bir kez (sonnet, tek çağrı): son 7 günün çalışma kayıtları (git; müşteri, Ghost ve paylaşım işleri çıkarılır) + kişinin son 14 günde
kendi yazdığı gönderiler → 3-6 "bu hafta ne yaptı" maddesi: ne_yapti (somut), derdi (nerede zorlandı/ne fark etti; YALNIZCA kanıt varsa: aynı işin
art arda düzeltilmesi, "hata", "düzeltildi" kayıtları ya da kendi gönderisinde söylediği), seri (kendi kalıbı: "vol. N"), kanit (kayıt kodları),
paylasti (kendi gönderilerinde zaten anlattıysa). Karışımın 'kendi' malzemesi önce bunlardan beslenir. Ürün adları yalnızca Studio, Meet ve Content.
"""
import json
import re
import subprocess
import time
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
ONB = KLASOR / "kayitlar" / "ghost_kendi"
GIZLI = re.compile(r"ghost|paylaşım|taslak|yazıcı|okur|hakem|\bx\b|kesif|keşif|açı elemesi|persona|tweet|gönderi|instagram|story|asana|müşteri|"
                   r"toplantı adı|kişi profili|davetli|couple|" + "|".join(re.escape(x.lower()) for x in __import__("ortak").sirket_adlari()), re.I)
KENDI_GONDERI = re.compile(r"(yaptım|kurdum|yazdım|geliştir|uygulama|araç|vol\.|kendime|kendi uygulama|repo|github|claude|ürünleştir|taşı|transcript|studio|meet|dots|duet)", re.I)


def _git(gun=7):
    try:
        L = __import__("ortak").git_kayitlari(f"{gun} days ago", KLASOR, 200)    # ayarlar.json `kendi_depolar`
        return [(h, t, s.replace("Transcript", "Meet")[:260]) for h, t, s in L if not GIZLI.search(s)][:80]
    except Exception:  # noqa: BLE001
        return []


def _kendi_gonderileri(gun=14):
    try:
        import performans
        return [x for x in performans.liste(gun) if not x.get("ghost") and KENDI_GONDERI.search(str(x.get("metin") or ""))][:12]
    except Exception:  # noqa: BLE001
        return []


def isler(zorla=False, log=print):
    """Bugünün 'bu hafta ne yaptı' maddeleri (günlük önbellek). Döner: [{id, is, derdi, seri, kayit, tarih, paylasti}]."""
    yol = ONB / f"{time.strftime('%Y-%m-%d')}.json"
    if not zorla:
        try:
            return json.loads(yol.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    G = _git()
    if len(G) < 3:
        return []
    K = _kendi_gonderileri()
    import paylasim
    c = paylasim._claude_json(
        "Bir kişi kendi kullandığı araçları kendisi yapıyor (programcı değil; Claude ile kuruyor) ve bunu X'te paylaşmayı seviyor. Aşağıda son 7 günün "
        "çalışma kayıtları ve kişinin bu konuda kendi yazdığı son gönderiler var. Bu haftanın paylaşmaya değer EN SOMUT 3-6 işini çıkar.\n"
        "Her madde: ne_yapti (tek cümle, somut, okurun anlayacağı dille; teknik terim yok; ürün adı yalnızca 'Studio', 'Meet' ya da 'Content' olabilir; müşteri, "
        "marka, kişi adı YOK), derdi (yaparken nerede zorlandı ya da ne fark etti; YALNIZCA kanıt varsa: aynı işin art arda düzeltilmesi, 'hata/düzeltildi/"
        "kaldırıldı/geri alındı' kayıtları ya da kendi gönderisinde söylediği; kanıt yoksa boş bırak, UYDURMA), seri (kişinin kendi kalıbına uyuyorsa "
        "öneri, ör. 'Günlük hayatta ihtiyaç duyduğum şeyleri kendime ürünleştiriyorum vol. 3'; yoksa boş), kanit (dayandığı kayıt kodları), paylasti "
        "(kişi bunu kendi gönderilerinde zaten anlattıysa true).\n"
        "İç işler (test, notlar, yeniden düzenleme, küçük düzeltmeler) madde OLMAZ; dışarıdan bakan birinin 'bunu nasıl yaptın' diyeceği işler olur. Tek başına "
        "bir hatanın düzeltilmesi madde olmaz (içinden başkasının işine yarayacak bir fikir çıkmıyorsa). derdi bir DUYGU değil, olgudur (nerede zorlandı, ne "
        "fark etti); duygu ifadesi yalnızca kişinin kendi gönderisinde o iş için söylenmişse.\n"
        'JSON: {"isler": [{"ne_yapti": "...", "derdi": "", "seri": "", "kanit": ["abc1234"], "paylasti": false}]}\n\n'
        "ÇALIŞMA KAYITLARI:\n" + "\n".join(f"{h} · {t} · {s}" for h, t, s in G) +
        ("\n\nKİŞİNİN KENDİ İŞLERİ ÜZERİNE YAZDIKLARI:\n" + "\n---\n".join(str(x.get("metin") or "")[:400] for x in K) if K else ""),
        model_adi="sonnet", zaman_asimi=240)
    kodlar = {h for h, _, _ in G}
    tarih = {h: t for h, t, _ in G}
    out = []
    for x in c.get("isler") or []:
        m = str(x.get("ne_yapti") or "").strip()
        kanit = [k for k in x.get("kanit") or [] if k in kodlar]
        if not m or not kanit or GIZLI.search(m):
            continue                                       # kanıtsız ya da gizli iş sızdıran madde alınmaz
        out.append({"id": "k:h:" + kanit[0], "is": m[:300], "derdi": str(x.get("derdi") or "")[:240], "seri": str(x.get("seri") or "")[:160],
                    "kayit": ", ".join(kanit[:4]), "tarih": tarih.get(kanit[0], ""), "paylasti": bool(x.get("paylasti"))})
    ONB.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"Kendi işleri: {len(out)} madde (son 7 günün {len(G)} kaydından)")
    return out


def ornekler(n=6):
    """Kişinin kendi işi üzerine yazdığı gerçek gönderiler (ses örneği)."""
    return [str(x.get("metin") or "") for x in _kendi_gonderileri(30)][:n]


if __name__ == "__main__":
    for x in isler(zorla=True):
        print(x)
