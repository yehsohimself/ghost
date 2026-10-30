// background.js - Ghost uzantısı: x.js ve ig.js'in YALNIZCA OKUDUĞU gönderileri bu Mac'teki Ghost'a iletir. Hiçbir sitede tıklamaz, yazmaz, paylaşmaz.
// Ghost reads only: x.js / ig.js collect what is on your screen and this worker forwards it to the Ghost app on 127.0.0.1. Nothing is posted.
const SITE = 'http://127.0.0.1:8767';
const YOLLAR = {x_gorulen: '/api/x/gorulen', x_kartli: '/api/x/kartli', x_yerimi: '/api/x/yerimleri', x_akis: '/api/x/akis',
                ig_gorulen: '/api/ig/gorulen', x_istatistik: '/api/x/istatistik'};

async function post(yol, govde){
  try{ const r = await fetch(SITE + yol, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(govde)}); ikon(r.ok ? '' : '!'); }
  catch(e){ ikon('!'); }
}
function ikon(t){ try{ chrome.action.setBadgeText({text: t}); chrome.action.setBadgeBackgroundColor({color: '#ff2d78'});
  chrome.action.setTitle({title: t ? 'Ghost · the app is not running on this Mac' : 'Ghost'}); }catch(e){} }

chrome.runtime.onMessage.addListener(m => {
  const yol = YOLLAR[m && m.tur]; if (!yol) return;
  const {tur, ...govde} = m;
  post(yol, tur === 'x_gorulen' ? {gonderi: m.gonderi} : govde);
});

// İzlenen hesaplar (x.js ana akışta yalnız bunları okur): yarım saatte bir Ghost'tan
async function hesaplarAl(){ try{ const r = await fetch(SITE + '/api/x/hesaplar'); if (r.ok){ const j = await r.json(); await chrome.storage.local.set({x_hesaplar: j.x || [], ig_hesaplar: j.ig || []}); } }catch(e){} }
chrome.alarms.create('hesaplar', {periodInMinutes: 30}); hesaplarAl();
chrome.alarms.onAlarm.addListener(a => { if (a.name === 'hesaplar') hesaplarAl(); });
