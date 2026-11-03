"""Arayüzde yapay zekâ izi denetimi (2026-11-03): renkli parlama, gradyan yazı, süs emoji.

Kural CLAUDE.md'de ("Arayüz: yapay zekâ izi yok"). Odak halkası (bulanıklıksız `0 0 0 3px`), nötr gölge,
kayıt noktasının nabzı (@keyframes) ve işlev taşıyan ✓ ✕ ⚙ gibi işaretler sorun sayılmaz.
Elle: python arayuz_denetim.py
"""
import re
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
SUS_EMOJI = "🎉💡🎵💬📌🔍📎🍽✨🚀🔥⭐🎯🤖🧠⚡💎🌟"
GOLGE = re.compile(r"box-shadow:([^;}]+)")
PARLAK_SUZGEC = re.compile(r"filter:\s*drop-shadow\(0 0[^;}]*")
GRADYAN_YAZI = re.compile(r"linear-gradient\([^;}]*;[^}]*background-clip:\s*text")
ANIMASYON = re.compile(r"@keyframes[^{]+\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}")
RENK_DISI = re.compile(r"(?:rgba?|hsla?|var|color-mix)\((?:[^()]|\([^()]*\))*\)|#[0-9a-fA-F]{3,8}|inset|!important")


def _parcala(deger):
    parcalar, derinlik, birikim = [], 0, ""
    for c in deger:
        derinlik += (c == "(") - (c == ")")
        if c == "," and derinlik == 0:
            parcalar.append(birikim)
            birikim = ""
        else:
            birikim += c
    return [p.strip() for p in parcalar + [birikim] if p.strip()]


def _notr(golge):
    m = re.search(r"rgba?\((\d+),\s*(\d+),\s*(\d+)", golge)
    if m:
        return len(set(m.groups())) == 1
    return bool(re.search(r"#(000|fff|000000|ffffff)\b|\b(black|white)\b|var\(--(shadow|hair|bg|surface|fill)", golge, re.I))


def parlama_mi(golge):
    """Renkli ve bulanık gölge parlamadır; bulanıklığı olmayan halka değildir."""
    if "inset" in golge or _notr(golge) or not re.search(r"var\(--|rgba?\(|#[0-9a-f]{3,8}|color-mix|hsl", golge, re.I):
        return False
    sayilar = re.findall(r"-?[\d.]+(?=px|\b)", RENK_DISI.sub("", golge))
    return len(sayilar) >= 3 and float(sayilar[2]) >= 4


def metni_denetle(metin):
    bulgular = []
    duz = ANIMASYON.sub(lambda m: "\n" * m.group(0).count("\n"), metin)
    for m in GOLGE.finditer(duz):
        if any(parlama_mi(p) for p in _parcala(m.group(1))):
            bulgular.append((duz.count("\n", 0, m.start()) + 1, "parlama", m.group(0)[:70]))
    for m in PARLAK_SUZGEC.finditer(duz):
        bulgular.append((duz.count("\n", 0, m.start()) + 1, "parlama", m.group(0)[:70]))
    for m in GRADYAN_YAZI.finditer(duz):
        bulgular.append((duz.count("\n", 0, m.start()) + 1, "gradyan yazı", m.group(0)[:70]))
    for i, satir in enumerate(metin.split("\n"), 1):
        for e in set(satir) & set(SUS_EMOJI):
            bulgular.append((i, "süs emoji", e))
    return bulgular


def denetle(kok=KLASOR):
    sonuc = []
    for f in sorted((Path(kok) / "static").glob("*")):
        if f.suffix in (".html", ".css", ".js") and f.name != "couple.html":
            for satir, tur, parca in metni_denetle(f.read_text(encoding="utf8", errors="ignore")):
                sonuc.append({"dosya": f.name, "satir": satir, "tur": tur, "parca": parca})
    return sonuc


if __name__ == "__main__":
    bulunan = denetle()
    for b in bulunan:
        print(f"{b['dosya']}:{b['satir']} {b['tur']}: {b['parca']}")
    print(f"{len(bulunan)} bulgu")
