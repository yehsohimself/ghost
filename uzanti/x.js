// X (x.com) — yalnızca OKUR. Kullanıcı kendi profiline ya da kendi gönderisine baktığında ekrandaki sayıları (görüntülenme, beğeni, yanıt,
// yeniden gönderi, yer işareti) toplar ve Ghost'a iletir. Hiçbir şeye tıklamaz, yazmaz, paylaşmaz.
(() => {
  let kullanici = '', gonderilen = new Map(), zaman = null;   // kendi X hesabı sayfadan okunur (profil bağlantısı); kodda hesap adı yok (2026-10-25)
  const kendiHesap = () => { try{ const h = (document.querySelector('a[data-testid="AppTabBar_Profile_Link"]') || {}).getAttribute?.('href') || ''; return h.replace(/^\//, '').split(/[/?]/)[0] || ''; }catch(_){ return ''; } };
  chrome.storage.local.get('x_kullanici').then(s => { if (s.x_kullanici) kullanici = s.x_kullanici.replace(/^@/, '').toLowerCase(); if (!kullanici) kullanici = kendiHesap().toLowerCase(); });
  const sayi = t => { if (!t) return 0; t = t.replace(/\s/g, '').replace(',', '.'); const m = /([\d.]+)\s*(B|K|Mn|M|bin)?/i.exec(t); if (!m) return 0;
    let n = parseFloat(m[1]); const k = (m[2] || '').toLowerCase(); if (k === 'b' || k === 'k' || k === 'bin') n *= 1e3; if (k === 'm' || k === 'mn') n *= 1e6; return Math.round(n); };
  function oku(a){
    const zm = a.querySelector('time'), bag = zm && zm.closest('a'); if (!bag) return null;
    const yol = (bag.getAttribute('href') || '').toLowerCase(); const m = /^\/([^/]+)\/status\/(\d+)/.exec(yol); if (!m || m[1] !== kullanici) return null;
    if (a.querySelector('[data-testid="socialContext"]')?.innerText.match(/repost|yeniden gönder/i)) return null;   // başkasının gönderisini yeniden paylaşım
    const grup = a.querySelector('[role="group"][aria-label]'); const et = (grup?.getAttribute('aria-label') || '').toLowerCase();
    const al = (...k) => { for (const x of k){ const r = new RegExp('([\\d.,]+\\s*(?:b|k|mn|m|bin)?)\\s*' + x, 'i').exec(et); if (r) return sayi(r[1]); } return 0; };
    let gor = al('views', 'görüntülenme', 'görüntüleme');
    if (!gor){ const v = a.querySelector('a[href$="/analytics"]'); if (v) gor = sayi(v.innerText); }
    return {id: m[2], tarih: zm.getAttribute('datetime'), metin: (a.querySelector('[data-testid="tweetText"]')?.innerText || '').slice(0, 4000),
            yanit: al('replies', 'reply', 'yanıt'), repost: al('reposts', 'repost', 'yeniden gönderi'), begeni: al('likes', 'like', 'beğeni'),
            yerimi: al('bookmarks', 'bookmark', 'yer işareti'), goruntulenme: gor, medya: !!a.querySelector('[data-testid="tweetPhoto"], video')};
  }
  // Açılan bir gönderi sayfası (x.com/<kişi>/status/<id>): ana gönderiyi YALNIZCA OKUR ve Ghost'a "son açılanlar" olarak iletir (alıntılayarak yazmak için)
  let sonAcilan = '';
  function acilan(){
    const m = /^\/([^/]+)\/status\/(\d+)/.exec(location.pathname); if (!m || m[2] === sonAcilan) return;
    const a = [...document.querySelectorAll('article[data-testid="tweet"]')].find(x => (x.querySelector('time')?.closest('a')?.getAttribute('href') || '').includes('/status/' + m[2]));
    const metin = a?.querySelector('[data-testid="tweetText"]')?.innerText || ''; if (!a) return;
    sonAcilan = m[2];
    const ad = (a.querySelector('[data-testid="User-Name"]')?.innerText || '').split('\n')[0];
    try{ chrome.runtime.sendMessage({tur: 'x_gorulen', gonderi: {id: m[2], kullanici: m[1], ad, metin: metin.slice(0, 2000), tarih: a.querySelector('time')?.getAttribute('datetime') || '', medya: !!a.querySelector('[data-testid="tweetPhoto"], video')}}); }catch(e){}
  }
  // Habere bağlantı veren gönderiler (akışta, aramada, profil sayfalarında ekranda görünenler) ve arama sonuçları: YALNIZCA OKUR → Ghost bunları
  // taslağın haberiyle eşleştirip "alıntılanacak en uygun gönderi" olarak önerir (2026-10-22). Tıklamaz, kaydırmaz, yazmaz.
  const kartGonderilen = new Set();
  function kartlilar(){
    const arama = location.pathname === '/search', out = [];
    document.querySelectorAll('article[data-testid="tweet"]').forEach(a => {
      const bag = a.querySelector('time')?.closest('a'); const m = /^\/([^/]+)\/status\/(\d+)/.exec(bag?.getAttribute('href') || ''); if (!m || kartGonderilen.has(m[2])) return;
      const kart = a.querySelector('[data-testid="card.wrapper"]');
      if (!kart && !arama) return;
      const kartMetin = kart ? [kart.innerText || '', ...[...kart.querySelectorAll('a[aria-label]')].map(x => x.getAttribute('aria-label'))].join(' ').replace(/\s+/g, ' ').slice(0, 600) : '';
      kartGonderilen.add(m[2]);
      out.push({id: m[2], kullanici: m[1], ad: (a.querySelector('[data-testid="User-Name"]')?.innerText || '').split('\n')[0],
                metin: (a.querySelector('[data-testid="tweetText"]')?.innerText || '').slice(0, 1500), kart: kartMetin,
                tarih: a.querySelector('time')?.getAttribute('datetime') || '', arama: arama ? decodeURIComponent(new URLSearchParams(location.search).get('q') || '') : ''});
    });
    if (out.length) try{ chrome.runtime.sendMessage({tur: 'x_kartli', gonderiler: out}); }catch(e){}
  }
  // İzlenen hesaplar (2026-10-24, uzantı 3.3; Ghost'un 100 hesaplık listesi, `hesaplar.py`): X'te bir LİSTE sayfası açıkken ekrandaki bütün
  // gönderiler, ana akışta yalnız izlenen hesapların gönderileri YALNIZCA OKUNUR → Ghost keşfi ve alıntı önerisi. Tıklamaz, kaydırmaz, yazmaz.
  let izlenen = new Set();
  const hesapYukle = () => chrome.storage.local.get('x_hesaplar').then(s => { izlenen = new Set((s.x_hesaplar || []).map(x => String(x).toLowerCase())); }).catch(() => {});
  hesapYukle(); setInterval(hesapYukle, 10 * 60 * 1000);
  const akisGonderilen = new Set();
  function akis(){
    const liste = /^\/i\/lists\/\d+/.test(location.pathname), out = [];
    document.querySelectorAll('article[data-testid="tweet"]').forEach(a => {
      const bag = a.querySelector('time')?.closest('a'); const m = /^\/([^/]+)\/status\/(\d+)/.exec(bag?.getAttribute('href') || ''); if (!m || akisGonderilen.has(m[2])) return;
      if (!liste && !izlenen.has(m[1].toLowerCase())) return;
      if (a.querySelector('[data-testid="socialContext"]')?.innerText.match(/repost|yeniden gönder/i) && !liste) return;
      const kart = a.querySelector('[data-testid="card.wrapper"]');
      const kartMetin = kart ? [kart.innerText || '', ...[...kart.querySelectorAll('a[aria-label]')].map(x => x.getAttribute('aria-label'))].join(' ').replace(/\s+/g, ' ').slice(0, 600) : '';
      const kartLink = kart ? (kart.querySelector('a[href^="http"]')?.getAttribute('href') || '') : '';
      akisGonderilen.add(m[2]);
      out.push({id: m[2], kullanici: m[1], ad: (a.querySelector('[data-testid="User-Name"]')?.innerText || '').split('\n')[0],
                metin: (a.querySelector('[data-testid="tweetText"]')?.innerText || '').slice(0, 1500), kart: kartMetin, kart_link: kartLink,
                tarih: a.querySelector('time')?.getAttribute('datetime') || ''});
    });
    if (out.length) try{ chrome.runtime.sendMessage({tur: 'x_akis', liste, gonderiler: out}); }catch(e){}
  }
  // Yer imleri (2026-10-24, uzantı 3.5/3.6): kişi x.com/i/bookmarks sayfasını açınca ekrandaki gönderiler YALNIZCA OKUNUR → Ghost. Yer imleri
  // çoğunlukla kişinin "kendi sistemlerim için Claude okusun" diye bıraktıkları (GitHub listesi, okuma); Ghost okuyup öneriye çevirir. Tıklamaz, yazmaz.
  const yerimiGonderilen = new Set();
  function yerimleri(){
    // 25 Ekim: X yer imlerini "History → Bookmarks" sekmesine taşıdı (/i/history; beğeniler /i/history/likes). Sayfadan bağımsız da: yer imine
    // eklenmiş her gönderi "Bookmarked" (data-testid="removeBookmark") düğmesi taşır; nerede görünürse okunur.
    const sayfa = location.pathname === '/i/bookmarks' || location.pathname === '/i/history';
    const out = [];
    document.querySelectorAll('article[data-testid="tweet"]').forEach(a => { try{
      if (!sayfa && !a.querySelector('[data-testid="removeBookmark"]')) return;
      const bag = a.querySelector('time')?.closest('a'); const m = /^\/([^/]+)\/status\/(\d+)/.exec(bag?.getAttribute('href') || ''); if (!m || yerimiGonderilen.has(m[2])) return;
      const kart = a.querySelector('[data-testid="card.wrapper"]');
      const linkler = [...a.querySelectorAll('[data-testid="tweetText"] a[href^="http"]')].map(x => x.href).slice(0, 6);   // GitHub listesi, okuma bağlantısı
      yerimiGonderilen.add(m[2]);
      out.push({id: m[2], kullanici: m[1], ad: (a.querySelector('[data-testid="User-Name"]')?.innerText || '').split('\n')[0],
                metin: (a.querySelector('[data-testid="tweetText"]')?.innerText || (!kart ? (a.innerText || '').replace(/\s+/g, ' ').slice(0, 800) : '')).slice(0, 1200),   // X makalesi: tweetText yok
                kart: kart ? (kart.innerText || '').replace(/\s+/g, ' ').slice(0, 400) : '', kart_link: kart ? (kart.querySelector('a[href^="http"]')?.getAttribute('href') || '') : '',
                linkler, tarih: a.querySelector('time')?.getAttribute('datetime') || ''});
    }catch(e){} });
    if (out.length) try{ chrome.runtime.sendMessage({tur: 'x_yerimi', gonderiler: out}); }catch(e){}
  }
  function tara(){
    // 25 Ekim: tek bir gönderideki beklenmedik yapı (ör. telif nedeniyle kaldırılmış medya) bir okuyucuyu hata verdirince sonraki her tarama kesiliyordu
    for (const f of [acilan, kartlilar, akis, yerimleri]){ try{ f(); }catch(e){} }
    const yeni = [];
    document.querySelectorAll('article[data-testid="tweet"]').forEach(a => { let g = null; try{ g = oku(a); }catch(e){} if (!g) return; const imza = [g.goruntulenme, g.begeni, g.yanit].join('|');
      if (gonderilen.get(g.id) !== imza){ gonderilen.set(g.id, imza); yeni.push(g); } });
    if (yeni.length) try{ chrome.runtime.sendMessage({tur: 'x_istatistik', gonderiler: yeni}); }catch(e){}
  }
  // 25 Ekim: sürekli değişen sayfalarda (oynayan video, sayaçlar) eski "her değişimde ertele" düzeni okumayı hiç çalıştırmıyordu; artık en geç 2 sn'de bir
  new MutationObserver(() => { if (!zaman) zaman = setTimeout(() => { zaman = null; tara(); }, 2000); }).observe(document.documentElement, {childList: true, subtree: true});
  setTimeout(tara, 3000);
})();
