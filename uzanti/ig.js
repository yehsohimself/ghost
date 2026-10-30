// Instagram (yalnızca okuma, 2026-10-22): ekranda gördüğünüz gönderi ve reels'leri Ghost'un story önerileri için Video Hub'a iletir.
// Hiçbir şeye tıklamaz, beğenmez, kaydırmaz; sayfada zaten görünen bağlantı, kullanıcı adı, görsel ve açıklama metnini okur.
// Sponsorlu gönderiler alınmaz. Kullanıcı kullandıkça birikir; Ghost "Story için" listesini yalnızca bunlardan seçer.
(() => {
  const gonderildi = new Set();
  const kodu = h => { const m = String(h || '').match(/\/(p|reel|reels)\/([\w-]{5,})/); return m ? m[2] : ''; };
  const AYRI = /^\/(p|reel|reels|explore|stories|direct|accounts|about|legal|developer)\b/;
  // 22 Ekim: akıştaki gönderilerde <header> yok (kullanıcı adı orada aranıyordu, her gönderi atlanıyordu); kullanıcı adı = gönderideki ilk "/ad/" bağlantısı
  function oku(kok, sayfaKodu){
    const linkler = [...kok.querySelectorAll('a[href]')].map(x => x.getAttribute('href'));
    const link = sayfaKodu ? location.pathname : linkler.find(h => kodu(h) && !/liked_by|comments/.test(h));
    const kod = sayfaKodu || kodu(link); if (!kod || gonderildi.has(kod)) return null;
    const metin = (kok.innerText || '').trim();
    if (/^(.{0,160})(Sponsorlu|Sponsored|Reklam)\b/s.test(metin)) return null;
    const yazar = (linkler.find(h => /^\/[\w.]{2,30}\/$/.test(h || '') && !AYRI.test(h)) || '').replace(/\//g, '');
    const img = [...kok.querySelectorAll('img')].filter(i => (i.naturalWidth || 0) >= 300).sort((a, b) => b.naturalWidth - a.naturalWidth)[0];
    const video = kok.querySelector('video');
    if (!yazar) return null;
    gonderildi.add(kod);
    const reel = !!video || /\/reels?\//.test(link || location.pathname);
    const onerilen = /Senin için önerilenler|Suggested for you/i.test(metin.slice(0, 200));   // takip edilmeyen, Instagram'ın araya soktuğu gönderi
    return {onerilen, kod, url: `https://www.instagram.com/${reel ? 'reel' : 'p'}/${kod}/`, yazar, metin: metin.slice(0, 700), alt: (img?.alt || '').slice(0, 300),
            resim: img?.currentSrc || img?.src || video?.getAttribute('poster') || '', tarih: kok.querySelector('time')?.getAttribute('datetime') || '', tur: reel ? 'reel' : 'post'};
  }
  function tara(){
    const out = [];
    const sk = kodu(location.pathname);
    if (sk){ const k = document.querySelector('main article') || document.querySelector('main'); const x = k && oku(k, sk); if (x) out.push(x); }
    document.querySelectorAll('article').forEach(a => { const x = oku(a); if (x) out.push(x); });
    if (out.length) try{ chrome.runtime.sendMessage({tur: 'ig_gorulen', gonderiler: out.slice(0, 20)}); }catch(e){}
  }
  setInterval(tara, 5000); setTimeout(tara, 2500);
})();
