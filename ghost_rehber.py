"""ghost_rehber.py - Kişinin kendi yazdığı bağlam, muhakeme ve yazı rehberi (2026-10-26), Ghost'un yazım ve okur çağrılarına PARÇA PARÇA girer.

Kullanıcı (rehberin 15. bölümü): "Bunu tek bir 'kısa, sakin, ironik yaz' paragrafına indirgeme. ... Her üretimde yalnız işe yarayan bağlamı ve
örnekleri kullan. Bütün referans kadrosunu, özel hayatımı ve eski örneklerin tamamını her taslağa yükleme." Tam metin `profil/rehber.md`
(kişinin kendi sözleri). Burada her bölümün Ghost'a dönük karşılığı var:
- KULLANIM, MERKEZ, DIL: her yazımda (8. bölüm).
- KAYNAK_SINIRI ve OZEL: ayrı bloklar, her yazımda (2, 6 ve 12. bölümler).
- MECRA: tablodan yalnız o metnin satırı (9. bölüm).
- KONU parçaları ve REFERANS: yalnız konu uyuyorsa, en çok 3 referans (5, 6, 7. bölümler).
- KENDINI_ANLATMA: duyuru, kendi işi, LinkedIn (1. bölüm). DUZENLEME: kişinin kendi taslağı düzenlenirken (11. bölüm).
- BLOG_KAPSAMI: yalnız platform='blog' (asıl mesele sektörel, ilk yazılar genelden). KONU_ONERME: konu öneren çağrılara oneri_blogu() ile.
- okur_blogu(): soğuk okur ve hakem için aynı dil kuralları, puan ölçütü olarak.
- dil_notlari() / dil_duzelt(): kodla denetim (uzun tire, şapkalı a, düz yazıda +, övücü sıfat, dayanaksız deneyim, özel bilgi).
"""
import re

KULLANIM = ("NASIL KULLANILIR: Aşağıdakiler görünür bir kontrol listesi değil; metnin işine yarayanı sessizce uygula. Kişinin bu işteki açık isteği "
            "önce gelir, ama tek bir işe özgü istek kalıcı sesini değiştirmez. 'Daha beklenmedik' istemek kaynağın desteklemediği şaşırtıcı yorum "
            "izni değil; 'daha iyi' her seferinde daha sert ya da daha kısa demek değil. Güçlü bir katkı yoksa yazmamak, sayıyı doldurmaktan iyidir.")

MERKEZ = [
    "Bir metinde tek ana düşünce ilerlesin; her paragraf öncekine bağlansın. Derinlik katmak için teknoloji, kapitalizm, yaratıcılık, insanlığın "
    "geleceği gibi büyük konuları metne doldurma.",
    "Açılışı konuya göre seç: somut bir ayrıntı, doğrudan görüş, kısa bir sahne ya da kısa bir espri. 'Önce haber, sonra ayrıntı, sonra yorum' dahil "
    "hiçbir sıra şablon değil.",
    "Uzunluk düşüncenin ihtiyacı kadar: tek cümle yetiyorsa orada bitir; birkaç paragraf gerekiyorsa ara basamakları silme. Kısa yazmak okurun "
    "bağlamı tahmin etmesini beklemek değil. Geçmiş gönderilerin karakter dağılımı yeni metin için kota değil.",
    "Mizah gözlemden çıksın, açıklanmasın. Her metne espri koyma; son cümleyi aforizmaya, vecizeye ya da ders cümlesine çevirme. Düşünce "
    "tamamlandıysa dur.",
    "'Cool' soğuk, kopuk ya da sürekli hüküm veren dil değil: bilgili, meraklı, sıcak, eğlenceli ve açık olabilir; ağırlık ilişkiye göre değişir.",
    "Şüphecilik merakı kapatmasın: yeni bir şeyin ilginç tarafını teslim et, iddianın henüz kanıtlanmamış kısmını da söyle. Karşı çıkmak için karşı çıkma.",
]

DIL = [
    "Uzun tire (—) ya da ayraç gibi kullanılan kısa tire ( – ) yok; virgül, nokta ya da iki nokta.",
    "Şapkalı a yok: hala, zeka, hikaye, kar. Özel adlar ve aynen alıntılanan kaynak metni olduğu gibi kalır.",
    "Düz yazıda artı işareti yerine 've' (Disney+, C++ gibi adlar kalır).",
    "Övücü sıfat yok ('vizyoner', 'oyun değiştiren', 'eşsiz', 'muhteşem', 'inanılmaz'); ne yapıldığını somut söyle. Kendini küçültme de yok.",
    "Kişi adına 'denedim', 'gördüm', 'yaşadım', 'yoruldum', 'sonuç aldım', yıl sayısı ya da unvan ancak dayanağı varsa (kişinin kendi notu, "
    "çalışma kaydı). Geliştirme kaydı bir özelliğin yapıldığını gösterir, kişinin ne hissettiğini göstermez.",
    "Türkçeyi Türkçe düşünerek kur: somut fiil, doğal cümle sırası; isimleştirme yığını, ajans jargonu, çeviri metafor, kurumsal manifesto dili "
    "yok. Yerleşik İngilizce terimler (creator, brief, skill, agent, know-how) kalabilir; okur bilmiyorsa doğal biçimde anlaşılır kıl.",
    "'Bence' bir görüşü sahiplenebilir, 'dikkatimi çekti' gerçekten ilginç bir ayrıntıya giriş olabilir; yasak değiller. Cümlede iş yapmıyorlarsa "
    "çıkar, aynı açılışı tekrar etme.",
    "Samimiyeti otomatik argo, 'ya', 'falan' ya da emoji ekleyerek üretme. Kişinin hızlı yazarken yaptığı yazım hatalarını ve tekrarları kopyalama.",
    "'Olabilir', 'gibi', 'henüz' bilgi sınırını doğru gösteriyorsa kalsın; güçlü görünmek için silme. Belirsizlik sözcüğü de dayanaksız iddiayı "
    "sağlamlaştırmaz.",
]

KAYNAK_SINIRI = [
    "Dört şey ayrı kalır: kaynağın söylediği, kişinin kendi söylediği (notu, görüş defteri, yayımlanmış gönderisi), senin çıkardığın ve senin "
    "önerdiğin. Metinde kimin ne dediği belli olsun.",
    "Şirketin iddiası bağımsız sonuç değil; duyuru ile çalışan ürün, prototip ile kullanılabilir ürün, ürün ile sürdürülebilir iş ayrı.",
    "Kaynağın desteklemediği iddia metne girmez; açıyı kısaltırken ya da keskinleştirirken değiştirme. Büyük iddia daha çok dayanak ister: tek "
    "haberden bütün dünya hakkında sonuç çıkarma.",
    "Yalnız başlık ya da kısa özet okunduysa tam metni okumuş gibi ayrıntı ekleme.",
    "Haber ya da araştırma yorumunda kaynak bağlantısı görünür kalır (kart, alıntı ya da ilk yanıt). Bir X gönderisine yanıtın gerektirdiği bağlam "
    "ile bağımsız paylaşımınki farklıdır.",
    "Ghost'un önceki taslakları ve önerileri kişinin görüşü ya da geçmişi değil; onları kişinin yaşadığı şey gibi yeniden kullanma.",
    "Teknik, hukuki, tıbbi ya da finansal konuda kesin hüküm verme; bilgi sınırını açık tut.",
]

OZEL = ("ÖZEL BİLGİ: Aile ve ev hayatı, sağlık, para durumu, müşteri işleri ve özel konuşmalar kamusal metnin malzemesi değil. Kişi bu girdide "
        "kendisi vermediyse metne koyma; verdiyse de yalnız metnin işine yarayan kadarını kullan. Bir bilgiyi bilmek onu yayımlama yetkisi değil.")

KENDINI_ANLATMA = ("KENDİNİ ANLATIRKEN: Geçmiş unvan ve başarı sergisi yok; bugün ne yaptığı ve bunun karşı tarafta ne işe yaradığı anlaşılsın, "
                   "özgüven açık tariften gelsin. Ürünü sade anlat ve okurun ne yapabileceğini söyle; uydurma kurucu hikayesi yok. Prototipi ticari "
                   "ürün, ürünü kanıtlanmış iş modeli gibi sunma. Yapay zeka kullandığını ancak anlatının işine yarıyorsa öne çıkar. Bir işteki "
                   "rolünü o işin bağlamından bil; her sonucun tek sahibi gibi yazma.")

DUZENLEME = ("KİŞİNİN KENDİ METNİNİ DÜZENLERKEN: Önce neyin korunacağını gör: anlam, ses, sıra, ilişki, kabul edilmiş cümleler, somut istek. Metin "
             "çalışıyorsa yalnız gereken yeri değiştir; doğal cümleyi profesyonel görünsün diye soyutlaştırma. 'Çok soğuk' kime ve nasıl "
             "konuşulduğuna bakmak demek, birkaç samimi sözcük eklemek değil. 'Çok uzun' tekrarları çıkarmak demek, mantık bağını kesmek değil. "
             "'Bariz' açıya geri dönmek demek, eşanlamlıyla cilalamak değil. Kabul edilmiş bir başlık ya da yol varsa sebepsiz başka fikir açma.")

# Blog kapsamı (2026-10-26, blog açılırken; kişi: "Blog sadece kendi işlerimden oluşmamalı", ardından "Böyle futbol falan yazmamalıyım.
# Bu nolursa olsun sektörel bir şey olmalı. Teması futbol ya da başka bir şey olabilir. Ama günün sonunda asıl mesele o olmamalı.", "Blog yeni
# açıldı. Haliyle niş konulardansa, önce daha genelden başlayan yazılar yazalım. İlk yazılar bunlar farkında olalım."). YALNIZ blog için: X'te futbol
# yalnızca taraftarlık olabilir (rehber 2. bölüm), bu kural oraya taşınmaz.
BLOG_KAPSAMI = ("BLOG KAPSAMI: Blog, bir düşüncenin bağlamını geliştirdiği yer; yazının asıl meselesi kişinin uzmanlık alanı ya da okurunun derdi "
                "olsun. Bir tema (spor, film, şehir...) giriş ya da malzeme olabilir. Çıkış noktası bir kitap, araştırma, başkasının işi ya da gündelik bir "
                "ayrıntı olabilir; yalnız kişinin kendi işleriyle sınırlı değil. Geniş başlık değil, belirli bir soru.")
# Kişiye özel kapsam, referanslar ve özel adlar profil/rehber.json'da (2026-10-29, Ghost herkese açılırken; bkz. _kisisel()).

# Konu önerirken (aynı gün): başlık değil soru; açı kişinin tezi değil.
KONU_ONERME = ("KONU ÖNERİRKEN: Geniş başlık verme. Her öneride belirli soruyu, başlanabilecek gözlemi ya da kaynağı ve henüz bilinmeyeni göster. "
               "Açıyı kişinin benimsediği tez gibi yazma; o bir öneri, kararı kişi verir. Her konuyu yapay zekaya, reklamcılığa, girişimciliğe ya "
               "da kişisel markaya bağlama. Yazı ders, tahmin ya da öneriyle bitmek zorunda değil. Kişinin yaşamadığı deneyimi, okumadığı kitabı, "
               "benimsemediği görüşü ona atfetme.")

# Mecra tablosu (9. bölüm). Anahtar: platform ya da metnin işi.
MECRA = {
    "x": "X: gündelik, meraklı, çevik. İyi bir ayrıntı, kısa gözlem, mizah ya da gerekçeli yorum. Haber kaynağı görünür; uzunluk konuya göre.",
    "linkedin": "LinkedIn: gerçek iş, somut karar ve mesleki güven; ne yaptığı anlaşılır. Kendini kutlayan metin, kariyer vaazı, yapay başarı "
                "hikayesi yok.",
    "blog": "Blog: bir düşüncenin bağlamını ve karşı argümanını geliştirebildiği alan. Haberleri arka arkaya sıralamak yerine aralarında gerçekten "
            "bulunan ilişkiyi kur. Asıl mesele sektörel (aşağıdaki BLOG KAPSAMI).",
    "whatsapp": "WhatsApp: konuşmanın akışına ve insanlara gerçek karşılık; arkadaşına ya da meslektaşına konuşur gibi, küçük bir "
                "denemeye ya da düşünceye yararlı katkı.",
    "yorum": "Tanıdığı birinin paylaşımına yorum ya da yanıt: ilişkinin sıcaklığını koru. Gerekirse önce yazısına karşılık ver, sonra kendi katkını "
             "ekle. Her yorumu bağımsız makale gibi başlatma.",
    "sunum": "Müşteri sunumu: başlık ve açıklamanın görevi ayrı. Kısa metin fikri anlaşılır kılar; konuşmacı notları müşteriye gerçekten "
             "söylenecek cümlelerdir.",
    "creator": "Creator metni: kamerada bir insanın söyleyebileceği akış; sunum diliyle konuşan karakter yok. İşe özgü format ve kabul edilmiş "
               "anlatım kararları korunur.",
    "web": "Web sitesi / ürün tanıtımı: ne yaptığı, kime yaradığı, nasıl kullanılacağı açık. Özellik listesini insanın çözülen ihtiyacına bağla.",
    "story": "Instagram Story: önce görüntü, an ya da yapılan iş; gerekiyorsa kısa not ve kaynak. Uzun X metnini zorla görsel karta çevirme.",
}

# Konu parçaları: yalnız konu uyuyorsa girer. kokler: küçük harfli kelime başları.
KONU = {
    "teknoloji": (("yapay zek", " ai ", "llm", "model", "agent", "ajan", "claude", "openai", "chatgpt", "gemini", "anthropic",
                   "robot", "yazılım", "uygulama", "app store", "app ", "gpu", "çip", "startup", "girişim", "kod", "otomasyon", "algoritma"),
                  "TEKNOLOJİ: Önce gerçekte ne olduğunu anla. Bir şey gerçekten kolaylaşıyor mu, yoksa yük yalnızca başka bir yere mi taşınıyor? "
                  "Kimin davranışı, maliyeti ya da gücü değişiyor, değer kimde birikiyor? Demo, prototip, kullanılabilir ürün ve iş modeli "
                  "farkını koru; 'bununla ne yapılabilir' sorusu açık kalsın."),
    "futbol": (("futbol", "football", "soccer", "maç", "gol", "derbi", "transfer", "forma", "lig", "teknik direktör", "şampiyon", "stadyum",
                "kulüp", "uefa", "fifa", "taraftar", "premier", "kadro"),
               "FUTBOL: Bazen yalnızca taraftarlık, heyecan ya da mizahtır; her futbol paylaşımını marka, toplum ya da veri dersine çevirme. "
               "Taraftar sesi samimi olabilir."),
    "reklam": (("reklam", "kampanya", "marka", "ajans", "brief", "cannes", "kreatif", "logo", "kimlik", "tasarım", "slogan", "creator",
                "işbirliği", "iş birliği", "brand", "campaign", "agency", "design", "lego"),
               "REKLAM VE KREATİF: Fikri slogandan öte gör: insan ne görüyor, ne yapıyor, neyi farklı anlıyor; marka burada ne yapıyor? Ödüllü "
               "işin görünüşüne değil hangi problemi nasıl çözdüğüne bak. 'Paylaşılır' diyorsan insanların neden paylaşacağını söyle. Müşteri "
               "için kabul edilmiş bir başlığın biçimi kişisel yazının kuralı değil."),
    "is": (("iş modeli", "gelir", "ürün", "satış", "fiyat", "abonelik", "büyüme", "yatırım", "şirket", "sahiplik", "bağımsız", "freelance",
            "müşteri", "istihdam", "çalışan", "employment", "hiring", "jobs", "layoff", "işten çıkar"),
           "İŞ VE ÜRÜN: Her işi ürüne, her ürünü iş modeline çevirme. Bir fırsattan söz ediyorsan kime fayda sağladığını ve ilk küçük denemenin ne "
           "olacağını somut söyle. Gelir ile dikkat, bağımsızlık ve bakım yükü birlikte tartılır."),
    "kultur": (("kültür", "müzik", "film", "dizi", "kitap", "edebiyat", "sanat", "toplum", "şehir", "nostalji", "kuşak",
                "gen z", "festival", "albüm", "yemek", "gusto"),
               "KÜLTÜR VE TOPLUM: Bağlamı koru, kavramları dikkatli kullan, kolay genellemeden kaçın. Kültürel bir keşfi gelir fırsatına ya da "
               "derse çevirme; bazen paylaşmanın değeri şeyin kendisindedir."),
}

# Referanslar: bir konuya yalnız o konuyla ilgili referans; en çok 3; adları anılmaz, sesleri taklit edilmez. Kişinin kendi referans kadrosu
# profil/rehber.json "referanslar" ({konu: ["Ad: hangi özelliği"]}); kodda yok (herkese açık depoda kimsenin listesi olmasın).
REFERANS = {}


def _kisisel():
    """profil/rehber.json: referanslar, blog_kapsami, ozel_adlar (özel hayattan kamusal metne girmemesi gereken adlar), konu_ek ({konu: [kökler]}),
    whatsapp_ad. Dosya yoksa genel kurallar."""
    import json
    from pathlib import Path
    try:
        d = json.loads((Path(__file__).resolve().parent / "profil" / "rehber.json").read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _norm(t):
    """Türkçe küçük harf ve düz küçük harf yan yana (İngilizce 'AI' Türkçe kuralla 'aı' olur)."""
    t = re.sub(r"[^\w+]+", " ", str(t or ""))
    return " " + t.replace("İ", "i").replace("I", "ı").lower() + " | " + t.lower() + " "


def konular(metin, is_turu=None):
    """Metnin değdiği konu parçaları (KONU anahtarları). Taraftar işi futbol sayılır."""
    t = _norm(metin)
    ek = _kisisel().get("konu_ek") or {}
    out = [k for k, (kokler, _) in KONU.items() if any(x in t for x in tuple(kokler) + tuple(ek.get(k) or ()))]
    if is_turu == "taraftar" and "futbol" not in out:
        out.insert(0, "futbol")
    return out


def mecra_anahtari(platform="x", is_turu=None):
    if is_turu in ("yanit", "alinti"):
        return ["yorum", platform if platform in MECRA else "x"]
    return [platform if platform in MECRA else "x"]


def blok(konu="", is_turu=None, platform="x", kisa=False):
    """Yazım çağrısına giren rehber parçaları. kisa=True: konu parçaları ve referanslar yok (karışım gibi çok konulu çağrılar)."""
    K = [] if kisa else konular(konu, is_turu)
    b = [KULLANIM, "YAZININ MERKEZİ:\n" + "\n".join(f"- {x}" for x in MERKEZ), "DİL:\n" + "\n".join(f"- {x}" for x in DIL),
         "KAYNAK / GÖRÜŞ SINIRI:\n" + "\n".join(f"- {x}" for x in KAYNAK_SINIRI), OZEL,
         "MECRA (bu metnin yeri):\n" + "\n".join(f"- {MECRA[m]}" for m in mecra_anahtari(platform, is_turu))
         + "\n- Aynı fikir başka mecrada farklı kurulur; metni bir mecradan ötekine yalnız uzatıp kısaltarak taşıma."]
    if is_turu == "duyuru" or platform == "linkedin" or ("kendi" in _norm(konu) and is_turu in (None, "duyuru", "dusunce")):
        b.append(KENDINI_ANLATMA)
    kis = _kisisel()
    if platform == "blog":
        b.append(kis.get("blog_kapsami") or BLOG_KAPSAMI)
    if K:
        b.append("BU KONUYA ÖZGÜ:\n" + "\n".join(f"- {KONU[k][1]}" for k in K[:2]))
    R = []
    for k in K[:2] + (["espri"] if is_turu == "espri" else []) or ["genel"]:
        R += [r for r in ((kis.get("referanslar") or {}).get(k) or REFERANS.get(k) or []) if r not in R]
    if not kisa and R:
        b.append("REFERANS (yalnız şu özellikleri düşünmek için; adlarını anma, seslerini taklit etme, karar onlara bırakılmaz):\n"
                 + "\n".join(f"- {r}" for r in R[:3]))
    return "\n\n".join(b)


def oneri_blogu(platform=""):
    """Konu öneren çağrılar için (keşif adayları, açı elemesi, konu toplantısı). platform='blog' ise blog kapsamı da girer."""
    return KONU_ONERME + ("\n" + (_kisisel().get("blog_kapsami") or BLOG_KAPSAMI) if platform == "blog" else "")


def okur_blogu():
    """Soğuk okur ve hakem için: dil ve kaynak kuralları, ihlal ölçütü olarak."""
    return ("KİŞİNİN DİL VE KAYNAK KURALLARI (ihlal varsa 'sorunlar'a somut yaz ve ses en çok 2):\n" + "\n".join(f"- {x}" for x in DIL)
            + "\n- Kaynağın iddiasını kişinin bağımsız sonucu gibi sunmak, kaynağın desteklemediği iddia, okunmamış ayrıntı uydurmak.\n"
            "- Kamusal metne girmiş özel bilgi (aile, sağlık, para, müşteri işi) kişi vermediyse.\n"
            "- Her metne konmuş espri ya da aforizma, vecize, ders cümlesiyle kapanış; düşünce bitmişken uzatma.")


# ---------------------------------------------------------------- kodla denetim
DIL_DENETIM = [
    (r"—|\s–\s", "uzun tire; virgül, nokta ya da iki nokta kullan"),
    (r"[âÂ]", "şapkalı a; 'hala', 'zeka', 'hikaye' diye yaz"),
    (r"(?<=[^\W\d_])\s\+\s(?=[^\W\d_])", "düz yazıda '+'; yerine 've'"),
    (r"\b(vizyoner\w*|oyun değiştir\w*|eşsiz|benzersiz|muhteşem|mükemmel|kusursuz|harika|inanılmaz|muazzam|olağanüstü|son derece|dahice|"
     r"efsanevi|devrimsel|çığır açan)\b", "övücü ya da büyük sıfat; ne yapıldığını somut söyle"),
]
# 'denedim', 'yaşadım' gibi fiiller paylasim.DENEYIM / BIRINCI_SAHIS'ta; burada yalnız onların kapsamadığı duygu, sonuç ve yıl iddiaları
DAYANAKSIZ = re.compile(r"\b(yoruldum|yorulduk|sonuç aldım|sonuç aldık|(?:\d+|on|yirmi|otuz) yıl(?:dır|dan beri) \w+(?:ım|im|um|üm|ız|iz|uz|üz)|"
                        r"(?:\d+|on|yirmi|otuz) yıllık (?:deneyim|tecrübe|geçmiş|kariyer)\w*)\b", re.I)
OZEL_KOK = (r"eşim\w*|karım\w*|kocam\w*|oğlum\w*|kızım\w*|ailem\w*|köpeğim\w*|kedim\w*|doktorum\w*|hastalı\w*m|ilacım\w*|maaşım\w*|borcum\w*|"
            r"kiram\w*|müşterim\w*|my wife|my husband|my son|my daughter|my doctor|my salary|my client\w*")


def _ozel_desen():
    adlar = "|".join(re.escape(str(a).lower()) for a in _kisisel().get("ozel_adlar") or [] if str(a).strip())
    return re.compile(r"\b(" + OZEL_KOK + ("|" + adlar if adlar else "") + r")\b", re.I)


def dil_notlari(m, kendi_deneyim=False):
    """Rehberin dil kuralları, kodla. kendi_deneyim: kişinin kendi notu var (deneyim ve özel bilgi ondan gelebilir)."""
    n = [ad for desen, ad in (DIL_DENETIM if _turkce() else DIL_DENETIM[:1]) if re.search(desen, m or "", re.I)]
    if not kendi_deneyim:
        d = sorted({x.lower() for x in DAYANAKSIZ.findall(m or "")})
        if d:
            n.append(f"dayanaksız deneyim ya da yıl iddiası ({', '.join(d)}); kişi bunu söylemedi, çıkar")
        o = sorted({x.lower() for x in _ozel_desen().findall(m or "")})
        if o:
            n.append(f"özel bilgi ({', '.join(o)}); kişi bu girdide vermedi, kamusal metne koyma")
    return n


SAPKALI_SOZ = {"hâlâ": "hala", "zekâ": "zeka", "hikâye": "hikaye", "kâr": "kar", "kâğıt": "kağıt", "dükkân": "dükkan", "rüzgâr": "rüzgar",
               "yâni": "yani", "lâzım": "lazım", "kâfi": "kafi", "hâl": "hal", "nâdir": "nadir", "mekân": "mekan", "kâtip": "katip"}


def dil_duzelt(m):
    """Anlamı değiştirmeyen düzeltmeler (model çağrısı yok): şapkalı a (büyük harfle başlayan özel adlar dışında) ve düz yazıda ' + ' → ' ve '."""
    def _kelime(x):
        w = x.group(0)
        if w[0].isupper() and not w.lower().startswith(tuple(SAPKALI_SOZ)):
            return w                                         # özel ad olabilir (ör. Kâzım): olduğu gibi
        return w.replace("â", "a").replace("Â", "A")
    if not _turkce():                                        # başka dilde yazarken Türkçe yazım düzeltmesi yok
        return str(m or "")
    m = re.sub(r"\w*[âÂ]\w*", _kelime, str(m or ""))
    return re.sub(r"(?<=[^\W\d_])\s\+\s(?=[^\W\d_])", " ve ", m)


def _turkce():
    try:
        import claude_yaz
        return (claude_yaz.yazi_dili_kodu() or "tr") == "tr"
    except Exception:  # noqa: BLE001
        return True
