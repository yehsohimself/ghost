"""dil_cevir.py - Arayüz ve sunucu metinlerinin İngilizce sözlüğünü üretir (2026-10-25; kullanıcı: "Studio İngilizce de kullanılabilmeli").

Girdi: static/dil/kaynak_tr.json (Türkçe metin listesi; index.html, studio_ek.js, misafir.js ve sunucu mesajlarından çıkarılır).
Çıktı: static/dil/en.json  {"exact": {tr: en}, "patterns": [[düzenli ifade, karşılık], ...]}
  - `${...}` (JS şablonu) ve `{...}` (Python f-string) yer tutucuları kalıba çevrilir: "${ad} eklendi" → ^(.*?) eklendi$  →  "$1 added".
Çeviri: Claude (claude_yaz.sor_json), 120'lik gruplar, 4 paralel; var olan en.json'daki karşılıklar korunur (yalnız yeni metinler çevrilir).
Kullanım: python dil_cevir.py            yeni metinleri çevirir
          python dil_cevir.py --hepsi    hepsini baştan
Elle düzeltme: static/dil/en.json içinde "exact" değerini değiştirin; bir daha çevrilmez.
"""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
KAYNAK = KLASOR / "static" / "dil" / "kaynak_tr.json"
HEDEF = KLASOR / "static" / "dil" / "en.json"
YER = re.compile(r"\$\{[^}]*\}|\{[^{}\s][^{}]*\}")

SISTEM = ("You translate the user-interface strings of a macOS web app (video transcription, subtitles, clips, dubbing, publishing kit) from "
          "Turkish to natural, concise English, the way Apple writes UI copy: sentence case, no slogans, 'you' voice, imperative buttons "
          "('Download', 'Copy'). Keep placeholders EXACTLY as they are (`${...}`, `{...}`, `%s`, HTML entities like &#10;, arrows, '·', '→'). "
          "Keep product names (Studio, Meet, Ghost, Couple, Content, PT, Claude, Whisper, YouTube, Word, Shorts, Drive, Asana). Keep the same "
          "length class (a 2-word button stays short). Do not translate file names, URLs or code. 'Yazıya dök' = 'Transcribe', "
          "'Transkript' = 'Transcript', 'Kısaca' = 'In short', 'Öne çıkan anlar' = 'Highlights', 'Kitaplık' = 'Library', 'İndirilenler' = 'Downloads', "
          "'Davet' = 'Invite', 'Davetli' = 'Guest', 'Yayın paketi' = 'Publishing kit', 'Kurgu' = 'Edit', 'Kesit' = 'Section', 'Dublaj' = 'Dubbing', "
          "'Konuşmacı' = 'Speaker', 'Özet' = 'Summary', 'Çeviri' = 'Translation', 'Altyazı' = 'Subtitles', 'Kapak' = 'Thumbnail', 'Kanal takibi' = 'Channel watch'.")


def _grup_cevir(grup):
    import claude_yaz
    istem = ("Translate each Turkish string to English. Return JSON {\"ceviriler\": [\"...\", ...]} with EXACTLY " + str(len(grup)) +
             " items in the same order; each item is the translation of the item at the same index. Strings:\n" +
             json.dumps(grup, ensure_ascii=False, indent=0))
    c = claude_yaz.sor_json(istem, sistem=SISTEM, zaman_asimi=600, model_adi="sonnet")
    out = c.get("ceviriler") or []
    if len(out) != len(grup):
        raise RuntimeError(f"sayı uyuşmadı: {len(out)} / {len(grup)}")
    return list(zip(grup, [str(x) for x in out]))


def kalip(tr, en):
    """Yer tutuculu metin → (düzenli ifade, karşılık). Yer tutucular sırayla $1, $2..."""
    parcalar = YER.split(tr); yerler = YER.findall(tr)
    if not yerler:
        return None
    rx = "^" + "(.*?)".join(re.escape(p) for p in parcalar) + "$"
    kars = en
    for i, y in enumerate(yerler, 1):
        if y in kars:
            kars = kars.replace(y, f"${i}", 1)
    if any(f"${i}" not in kars for i in range(1, len(yerler) + 1)):
        return None                                        # çeviri yer tutucuyu düşürdüyse kalıp güvenilmez
    return [rx, kars]


def calistir(hepsi=False, log=print):
    kaynak = json.loads(KAYNAK.read_text(encoding="utf-8"))
    eski = json.loads(HEDEF.read_text(encoding="utf-8")) if HEDEF.exists() and not hepsi else {"exact": {}, "patterns": []}
    exact = dict(eski.get("exact") or {})
    yeni = [t for t in kaynak if t not in exact]
    log(f"{len(kaynak)} metin, {len(yeni)} çevrilecek")
    gruplar = [yeni[i:i + 120] for i in range(0, len(yeni), 120)]
    with ThreadPoolExecutor(4) as ex:
        for i, sonuc in enumerate(ex.map(lambda g: _dene(g, log), gruplar), 1):
            for tr, en in sonuc:
                if en.strip():
                    exact[tr] = en.strip()
            log(f"  grup {i}/{len(gruplar)} tamam")
    patterns = []
    for tr, en in exact.items():
        k = kalip(tr, en)
        if k:
            patterns.append(k)
    HEDEF.write_text(json.dumps({"exact": exact, "patterns": patterns}, ensure_ascii=False, indent=0), encoding="utf-8")
    log(f"yazıldı: {len(exact)} karşılık, {len(patterns)} kalıp → {HEDEF}")


def _dene(grup, log):
    for d in range(3):
        try:
            return _grup_cevir(grup)
        except Exception as e:  # noqa: BLE001
            log(f"  grup yeniden ({d + 1}): {e}")
    return []


if __name__ == "__main__":
    calistir(hepsi="--hepsi" in sys.argv)
