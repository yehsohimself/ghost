"""ghost_kaynak.py - Kaynak anlamını koruyan denetim (2026-10-25; kullanıcının ChatGPT ile yaptığı Ghost değerlendirmesinden, en ciddi bulgu).

Sorun: Ghost bazen haberi yanlış anlayıp üzerine kendinden emin bir yorum kuruyordu. Investing.com'un yapay zekâ sisteminin SEÇTİĞİ Kohl's hissesi
"yapay zekâyı KULLANIP %31 yükselen perakendeci" diye okunmuş ve "kazanç zincirin ucuna kayıyor" sonucu kurulmuştu. "Kaldırılan 51 uygulamanın 15'i
AI editörü" bilgisinden, neden kaldırıldıkları bilinmediği halde "sorun talep değil, giriş eşiği" denmişti. Daha iyi cümle bunu çözmez; cümle akıcı
hale geldikçe yanlış yorum daha ikna edici olur.

Kural: yorum serbesttir (kişinin çıkarımı olabilir), ama yorumun DAYANDIĞI olgu kaynakla tutarlı olmalı. Yazımdan SONRA, kaynağın metniyle:
  1) kim_ne_yapti: kaynağa göre kim, neyi, kime yaptı (tek cümle; yorumdan önce çözülür ve taslakta saklanır)
  2) taslağın olgu iddiaları (kişinin duygu/deneyim iddiaları dahil) kaynakta var mı, çelişiyor mu, hiç yok mu
  3) kaynağın bilmediği bir NEDENİ ya da ölçülmemiş bir GENELLEMEYİ ("en çok", "hep", "herkes", "sorun X değil Y") olgu gibi kuruyor mu
Karar: tamam | duzelt (yalnız yanlış kısım çıkarılır ya da bilinmeyen soruya/sınıra çevrilir; ses ve uzunluk korunur) | at (yorumun tamamı yanlış
okumaya dayanıyorsa). Düzeltilmiş metin aynı denetimden bir kez daha geçer; geçmezse taslak çıkmaz. Aynı kaynaktan çıkan bütün metinler aynı
`kim_ne_yapti` ve aynı bilgi sınırıyla denetlenir (bir taslak "neden kaldırıldı?" diye sorarken öbürü nedeni biliyormuş gibi yazamaz).
"""
import json
import re


def _istem(G):
    return (
        "Aşağıda X gönderisi taslakları ve her birinin dayandığı KAYNAK metni var. Görevin yazıyı güzelleştirmek DEĞİL; kaynağın doğru okunup okunmadığını "
        "denetlemek.\nHer taslak için:\n"
        "1) kim_ne_yapti: kaynağa göre kim, neyi, kime yaptı; tek cümle, kaynağın kendi ilişkisiyle (ör. 'Investing.com'un yapay zekâ sistemi Kohl's hissesini "
        "seçti; hisse ekimde %31 yükseldi'; 'perakendeci yapay zekâ kullandı' DEĞİL).\n"
        "2) sorunlar: taslaktaki her OLGU iddiasını (kim, ne, sayı, tarih, neden-sonuç, kişinin kendi deneyimi ya da duygusu) kaynakla karşılaştır. Sorun "
        "türleri: celiski (kaynağın söylediğinin tersi ya da başka bir ilişki), kaynakta_yok_neden (kaynağın bilmediği bir nedeni olgu gibi kuruyor), "
        "genelleme (ölçülmemiş genel bulgu: 'en çok', 'hep', 'herkes', 'sorun X değil Y'), uydurma_deneyim (kişiye kaynakta olmayan bir duygu/deneyim mal "
        "ediyor), ters_okunur (cümle ilk okumada ters anlaşılıyor, ör. çift olumsuz).\n"
        "SORUN OLMAYANLAR (bunları işaretleme): kişinin görüşü, yorumu, zevki, esprisi, iğnelemesi, taraftar abartısı ('en istikrarlı olduğu iş'); soru; "
        "çekinceyle söylenmiş tahmin ('açıklıyor olabilir', 'bence'); iki ayrı konuyu yan yana koyan ironi; herkesin bildiği genel bilgi (kaynakta geçmese de, "
        "yanlış ya da eskimiş olduğunu biliyorsan o zaman celiski). Yanıt taslaklarında kaynak yanıtlanan gönderidir; yanıt kendi bilgisini ve görüşünü "
        "ekleyebilir, yalnızca gönderiyi yanlış aktarıyorsa sorundur. Kaynak yalnız başlıksa ve olgu başlıktan çıkarılamıyorsa kaynakta_yok sayılır; "
        "başlığın makul okuması destekliyorsa sorun değildir. genelleme yalnızca dünyaya dair ÖLÇÜLMÜŞ bir bulgu gibi kesin dille kurulmuşsa ve gönderinin "
        "ana fikrini taşıyorsa sorundur.\n"
        "3) karar: tamam | duzelt | at. Sorun yoksa ya da yalnızca küçük, ana fikri taşımayan bir pürüz varsa tamam. at: yorumun ANA FİKRİ yanlış okumaya "
        "(celiski) ya da kaynakta olmayan bir nedene dayanıyorsa; düzeltmeden sonra geriye söylemeye değer bir düşünce kalmayacaksa (yalnızca 'belli değil', "
        "'erken' diyen sulandırılmış bir metin) da at. duzelt: yalnız sorunlu kısmı çıkar ya da bilinmeyeni açıkça soru/sınır olarak yaz ('neden "
        "kaldırıldıkları belli değil'); kalan düşünceyi, esprisini ve kişinin sesini koru, uzunluğu fazla değiştirme, yeni olgu ekleme, 'bence' ekleme, sona "
        "öğüt ya da vecize ekleme. Esprili bir metni düzeltirken espriyi öldürüyorsan at.\n"
        'JSON: {"taslaklar": [{"no": 0, "kim_ne_yapti": "...", "sorunlar": [{"tur": "celiski", "iddia": "...", "not": "..."}], "karar": "tamam", '
        '"duzeltilmis": ""}]}\n\n'
        + "\n\n".join(f"[{i}] TASLAK{' (' + str(g.get('tur') or g.get('karisim_tur')) + ')' if (g.get('tur') or g.get('karisim_tur')) else ''}:\n{g['metin']}\nKAYNAK ({g.get('kaynak_baslik', '')[:160]}):\n{(g.get('kaynak_metni') or '(kaynak metni yok)')[:3500]}"
                      for i, g in enumerate(G)))


def denetle(G, log=print):
    """G: [{metin, kaynak_metni, kaynak_baslik}]. Her öğeye `kaynak_denetimi` {kim_ne_yapti, sorunlar, karar} yazar, düzeltileni `metin`e koyar
    (eskisi `kaynak_oncesi`). Döner: (geçenler, atılanlar). Claude yanıt vermezse hepsi geçer (denetim olmadan yazım durmasın) ama işaretlenir."""
    import paylasim
    G = [g for g in G if g.get("metin")]
    if not G:
        return [], []
    try:
        c = paylasim._claude_json(_istem(G), model_adi="sonnet", zaman_asimi=300)
    except Exception as e:  # noqa: BLE001
        log(f"Kaynak denetimi yapılamadı ({e})")
        c = {}
    D = {}
    for x in c.get("taslaklar") or []:
        try:
            D[int(x.get("no"))] = x
        except (TypeError, ValueError):
            continue
    gecen, atilan, tekrar = [], [], []
    for i, g in enumerate(G):
        x = D.get(i)
        if not x:
            g["kaynak_denetimi"] = {"karar": "bakılamadı"}
            gecen.append(g); continue
        sor = [{"tur": str(s.get("tur") or ""), "iddia": str(s.get("iddia") or "")[:200], "not": str(s.get("not") or "")[:240]}
               for s in x.get("sorunlar") or [] if isinstance(s, dict)][:5]
        g["kaynak_denetimi"] = {"kim_ne_yapti": str(x.get("kim_ne_yapti") or "")[:300], "sorunlar": sor, "karar": x.get("karar") or "tamam"}
        if x.get("karar") == "at":
            atilan.append(g); continue
        if x.get("karar") == "duzelt" and str(x.get("duzeltilmis") or "").strip():
            g["kaynak_oncesi"] = g["metin"]; g["metin"] = paylasim._temiz(str(x["duzeltilmis"])).strip()
            tekrar.append(g); continue
        gecen.append(g)
    if tekrar:                                             # düzeltilen metin bir kez daha aynı denetimden
        try:
            c2 = paylasim._claude_json(_istem(tekrar), model_adi="sonnet", zaman_asimi=300)
            D2 = {int(x.get("no")): x for x in c2.get("taslaklar") or [] if str(x.get("no", "")).isdigit()}
        except Exception:  # noqa: BLE001
            D2 = {}
        for i, g in enumerate(tekrar):
            x = D2.get(i) or {}
            if x.get("karar") in ("tamam", None) and x:
                gecen.append(g)
            else:
                atilan.append(g)
    if atilan or tekrar:
        log(f"Kaynak denetimi: {len(G)} taslak → {len(tekrar)} düzeltildi, {len(atilan)} çıkmadı (kaynağı yanlış okuyordu)")
    return gecen, atilan


def kaynak_metni_bul(link, yedek=""):
    """Bağlantının metni (asıl kaynak); okunamazsa yedek (başlık/özet)."""
    if not str(link or "").startswith("http") or re.search(r"(x|twitter)\.com/", link):
        return yedek
    try:
        import kesif
        import paylasim
        if "news.google." in link:
            link = kesif.gn_coz(link)
        b, m = paylasim.sayfa_metni(link)
        return (b + "\n" + m)[:6000]
    except Exception:  # noqa: BLE001
        return yedek


if __name__ == "__main__":
    print(json.dumps(denetle([{"metin": "Ekimde teknoloji hisseleri düşerken AI seçimi bir perakendecinin %31 yükselmesi küçük ama net bir sinyal. Piyasa modeli yapanın "
                                         "karını sorgulamaya başladı, onu kendi işine koyup sonuç alanı ise ödüllendiriyor. Kazanç zincirin ucuna kayıyor gibi.",
                               "kaynak_baslik": "Teknoloji hisseleri düşerken yapay zeka seçimi perakendeci ekimde %31 yükseldi",
                               "kaynak_metni": kaynak_metni_bul("https://tr.investing.com/news/stock-market-news/teknoloji-hisseleri-duserken-yapay-zeka-secimi-perakendeci-ekimde-31-yukseldi-4116472")}])[0],
                     ensure_ascii=False, indent=1)[:2500])
