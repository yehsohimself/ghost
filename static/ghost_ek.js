/* Ghost'la konuşma ve görseller (2026-10-31; kullanıcı: "çok kısıtlı hissediyorum; bir soruya soruyla da karşılık verebilmeliyim, chatbox olmalı;
   deneyim insanlaşmalı; görselleştirme artmalı; bambaşka deneyimler").
   - Sağdan açılan konuşma paneli (telefonda tam ekran): Ghost'un canlı yüzü (bekler, düşünür, konuşur), yanıt yazıldıkça akar, hızlı cevaplar,
     önerilen eylemler (birlikte yazılan gönderi kartı, taslağı düzeltme, Ghost'a yazdırma, görüş/fikir defteri, yazım tercihi, plan değişikliği).
   - Her yerden açılır: sağ alttaki düğme, yazma kutusundaki "Konuş", taslak kartındaki "Konuş", Ghost'un soruları, haftanın planı, puan kartı.
   - Bugün'ün başında Ghost'un selamı (verilerden, hemen; model çağrısı yok).
   - Danışman'da konu yörüngesi (önerilen ↔ paylaşılan, alan alan), taslak ayrıntısında "Okurun gözünden" radarı.
   index.html'deki Ghost işlevlerini sarmalar; panel #gh'nin dışında durur (sayfa her yenilendiğinde konuşma kaybolmasın). */
(() => {
if (typeof URUN === 'undefined' || URUN !== 'ghost') return;
const css = document.createElement('link'); css.rel = 'stylesheet'; css.href = '/static/ghost_ek.css?v=3'; document.head.appendChild(css);

const GS = {acik: false, odak: null, mesajlar: [], kars: null, acilis: null, akiyor: false, yuklendi: false, kaydedilen: {}};
let AV_N = 0;
const AV = (cls = '') => { const g = 'gsIs' + (++AV_N); return `<span class="gs-av ${cls}" aria-hidden="true"><svg viewBox="0 0 40 40"><defs><radialGradient id="${g}" cx="50%" cy="40%" r="60%"><stop offset="0" stop-color="#ff7cc0"/><stop offset="1" stop-color="#ff3d9a"/></radialGradient></defs>
  <g class="gs-av-g"><path class="gs-av-b" fill="url(#${g})" d="M9 34V19a11 11 0 0 1 22 0v15l-3.7-2.9-3.6 2.9-3.7-2.9-3.7 2.9-3.6-2.9z"/><g class="gs-av-goz"><circle cx="16.4" cy="19" r="1.9"/><circle cx="23.6" cy="19" r="1.9"/></g></g></svg></span>`; };
const IK = {
  konus: '<svg viewBox="0 0 24 24"><path d="M4 5.5h16v10H9.5L5 19.5v-4H4z"/><path d="M8 9.5h8M8 12.5h5"/></svg>',
  gonder: '<svg viewBox="0 0 24 24"><path d="M5 12h13M13 6l6 6-6 6"/></svg>',
  x: '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg>',
  taslak: '<svg viewBox="0 0 24 24"><path d="M5 6.5h14M5 12h14M5 17.5h9"/></svg>',
  yaz: '<svg viewBox="0 0 24 24"><path d="M4 20h4L19 9l-4-4L4 16z"/></svg>',
  gorus: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><path d="M8.5 12.5 11 15l4.5-5"/></svg>',
  fikir: '<svg viewBox="0 0 24 24"><path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9V16h7v-2.1A6 6 0 0 0 12 3z"/></svg>',
  ogren: '<svg viewBox="0 0 24 24"><path d="M3 8.5 12 4l9 4.5-9 4.5z"/><path d="M7 10.5V15c0 1.5 2.2 3 5 3s5-1.5 5-3v-4.5"/></svg>',
  plan: '<svg viewBox="0 0 24 24"><rect x="3.5" y="5" width="17" height="15.5" rx="3"/><path d="M3.5 10h17M8 3v4M16 3v4"/></svg>',
  tik: '<svg viewBox="0 0 24 24"><path d="M5 12.5 10 17l9-10"/></svg>',
};
const EY_AD = {taslak: 'Gönderi taslağı', duzenle: 'Taslağı düzelt', yaz: 'Ghost yazsın', gorus: 'Görüş defterine', fikir: 'Fikir defterine', ogren: 'Bunu öğren', plan: 'Planı değiştir'};
const EY_IK = {taslak: 'taslak', duzenle: 'yaz', yaz: 'yaz', gorus: 'gorus', fikir: 'fikir', ogren: 'ogren', plan: 'plan'};
const md = s => esc(s).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').split(/\n{2,}/).map(p => /^\s*[-•] /m.test(p)
  ? '<ul>' + p.split('\n').filter(l => l.trim()).map(l => `<li>${l.replace(/^\s*[-•]\s*/, '')}</li>`).join('') + '</ul>' : `<p>${p.replace(/\n/g, '<br>')}</p>`).join('');
const saat = t => new Date(t * 1000).toLocaleTimeString(((window.DIL || {}).locale || 'tr-TR'), {hour: '2-digit', minute: '2-digit'});
const gunAd = t => { const d = new Date(t * 1000), b = new Date(); const fark = Math.round((new Date(b.toDateString()) - new Date(d.toDateString())) / 864e5);
  return fark === 0 ? 'Bugün' : fark === 1 ? 'Dün' : d.toLocaleDateString(((window.DIL || {}).locale || 'tr-TR'), {weekday: 'long', day: 'numeric', month: 'long'}); };
const getJ = u => fetch(u).then(r => r.json()).catch(() => null);

/* ---------------------------------------------------------------- panel iskeleti */
const panel = document.createElement('aside');
panel.id = 'ghSohbet'; panel.className = 'gs'; panel.hidden = true; panel.setAttribute('aria-label', 'Ghost’la konuşma');
panel.innerHTML = `<header class="gs-bas">${AV('buyuk')}<div class="gs-kim"><b>Ghost</b><small id="gsDurum">İletişim danışmanınız ve yazı ortağınız</small></div>
    <button class="gs-ib" type="button" data-gs="menu" title="Diğer" aria-label="Diğer"><svg viewBox="0 0 24 24"><circle cx="5" cy="12" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="19" cy="12" r="1.4"/></svg></button>
    <button class="gs-ib" type="button" data-gs="kapat" title="Kapat (Esc)" aria-label="Kapat">${IK.x}</button></header>
  <div class="gs-akis" id="gsAkis" aria-live="polite"></div>
  <div class="gs-alt"><div class="gs-hizli" id="gsHizli"></div><div class="gs-odak" id="gsOdak" hidden></div>
    <div class="gs-gir"><textarea id="gsGir" rows="1" placeholder="Ghost’a yazın; soru da sorabilirsiniz" aria-label="Mesajınız"></textarea>
      <button class="gs-ib gs-mik" type="button" data-gs="mik" title="Sesli söyleyin" aria-label="Sesli söyleyin">${GH_SVG.mik}</button>
      <button class="gs-gonder" type="button" data-gs="gonder" title="Gönder (↩)" aria-label="Gönder" disabled>${IK.gonder}</button></div></div>`;
document.body.appendChild(panel);
const fab = document.createElement('button');
fab.type = 'button'; fab.className = 'gs-fab'; fab.title = 'Ghost’la konuşun (⌘J)'; fab.innerHTML = AV() + '<span>Konuş</span>';
document.body.appendChild(fab);
const gosterFab = () => { fab.hidden = GS.acik || $('#gh')?.classList.contains('hidden') || $('#gh')?.classList.contains('gh-kurulumda'); };
setInterval(gosterFab, 1500);

function durum(t, cls){ $('#gsDurum').textContent = t; panel.querySelector('.gs-bas .gs-av').className = 'gs-av buyuk ' + (cls || ''); }

/* ---------------------------------------------------------------- açma, kapama, yükleme */
async function gsAc(odak, gonder){
  GS.acik = true; panel.hidden = false; document.body.classList.add('gs-acik'); gosterFab();
  requestAnimationFrame(() => panel.classList.add('acik'));
  try{ sessionStorage.setItem('gsAcik', '1'); }catch(e){}
  const yeniOdak = odak !== undefined && JSON.stringify(odak) !== JSON.stringify(GS.odak);
  if (odak !== undefined) GS.odak = odak;
  if (!GS.yuklendi || yeniOdak){
    const j = await getJ('/api/ghost/sohbet' + (GS.odak ? '?odak=' + encodeURIComponent(JSON.stringify(GS.odak)) : ''));
    if (j){ GS.mesajlar = j.mesajlar || []; GS.acilis = j.karsilama; GS.yuklendi = true; }
  }
  const son = GS.mesajlar[GS.mesajlar.length - 1];
  if (!yeniOdak && son && Date.now() / 1000 - son.zaman < 6 * 3600 && !GS.odak) GS.acilis = null;      // süren konuşma: yeniden selam verme
  ciz(true);
  if (gonder) gsGonder(gonder);
  else setTimeout(() => $('#gsGir').focus(), 120);
}
function gsKapat(){ GS.acik = false; panel.classList.remove('acik'); document.body.classList.remove('gs-acik'); try{ sessionStorage.removeItem('gsAcik'); }catch(e){}
  setTimeout(() => { if (!GS.acik) panel.hidden = true; gosterFab(); }, 220); }
window.gsAc = gsAc;

/* ---------------------------------------------------------------- çizim */
function eylemHtml(m, e, i){
  const u = e.uygulandi, k = m.id + ':' + i;
  if (e.tur === 'taslak'){
    const metin = GS.kaydedilen[k]?.metin || e.metin, n = metin.length, li = e.platform === 'linkedin';
    return `<div class="gs-tk" data-m="${m.id}" data-i="${i}"><div class="gs-tk-ust">${AV('kucuk')}<b>${li ? 'LinkedIn gönderisi' : 'X gönderisi'}</b><small class="gs-say${!li && n > 280 ? ' asim' : ''}">${li || n > 280 ? n : n + '/280'}</small></div>
      <textarea class="gs-tk-m" rows="3" spellcheck="false" ${u ? 'readonly' : ''}>${esc(metin)}</textarea>
      <div class="gs-tk-alt">${u ? `<span class="gs-ok">${IK.tik}Taslaklarınızda</span><button class="gs-b" type="button" data-gs="tkgit">Aç</button>`
        : `<button class="gs-b" type="button" data-gs="tkkopya">Kopyala</button><button class="gs-b" type="button" data-gs="tkx">${li ? 'LinkedIn’de aç' : 'X’te paylaş'}</button><button class="gs-b ana" type="button" data-gs="uygula">Taslaklara ekle</button>`}</div></div>`;
  }
  const alt = e.tur === 'duzenle' ? `“${esc(e.metin)}”` : e.tur === 'yaz' ? esc(e.girdi) : e.tur === 'plan' ? esc(e.ne || '') + (e.neden ? ` <i>${esc(e.neden)}</i>` : '') : esc(e.metin || '');
  return `<div class="gs-ey${u ? ' tamam' : ''}" data-m="${m.id}" data-i="${i}"><i class="gs-ey-ik">${IK[EY_IK[e.tur]] || ''}</i><span><b>${esc(e.baslik || EY_AD[e.tur])}</b><small>${alt}</small></span>
    ${u ? `<span class="gs-ok">${IK.tik}Yapıldı</span>` : `<button class="gs-b ana" type="button" data-gs="uygula">${e.tur === 'yaz' ? 'Yazsın' : 'Uygula'}</button>`}</div>`;
}
function mesajHtml(m, sonGhost){
  if (m.rol === 'ben') return `<div class="gs-m ben"><div class="gs-balon">${md(m.metin)}</div><time>${saat(m.zaman)}</time></div>`;
  const E = (m.eylemler || []).map((e, i) => eylemHtml(m, e, i)).join('');
  return `<div class="gs-m ghost${m.hata ? ' hata' : ''}" data-id="${m.id || ''}">${AV(m.akiyor ? 'konusuyor' : '')}<div class="gs-ic"><div class="gs-metin">${m.akiyor && !m.metin ? '<span class="gs-dusun"><i></i><i></i><i></i></span>' : md(m.metin)}${m.akiyor && m.metin ? '<span class="gs-imlec"></span>' : ''}</div>${E}${m.zaman && !m.akiyor ? `<time>${saat(m.zaman)}</time>` : ''}</div></div>`;
}
function ciz(asagi){
  const A = $('#gsAkis'), yakin = A.scrollHeight - A.scrollTop - A.clientHeight < 80;
  let h = '', onceki = '';
  const L = GS.mesajlar.slice(-50);
  if (!L.length && !GS.acilis) h += `<div class="gs-bos">${AV('buyuk')}<p>Aklınızdakini yazın. Soru sorun, itiraz edin, “emin değilim” deyin; birlikte düşünürüz.</p></div>`;
  L.forEach(m => { const g = gunAd(m.zaman); if (g !== onceki){ h += `<div class="gs-gun"><span>${esc(g)}</span></div>`; onceki = g; } h += mesajHtml(m); });
  if (GS.acilis && !GS.akiyor){ if (onceki !== 'Bugün' && L.length) h += `<div class="gs-gun"><span>Bugün</span></div>`; h += mesajHtml({rol: 'ghost', metin: GS.acilis.metin, id: 'acilis'}); }
  A.innerHTML = h;
  const son = L[L.length - 1];
  const S = GS.akiyor ? [] : GS.acilis ? (GS.acilis.secenekler || []) : son && son.rol === 'ghost' ? (son.secenekler || []) : [];
  $('#gsHizli').innerHTML = S.map(s => `<button class="gs-cip" type="button" data-gs="cip">${esc(s)}</button>`).join('');
  const o = $('#gsOdak'); o.hidden = !GS.odak;
  if (GS.odak) o.innerHTML = `<span>${esc(odakAd(GS.odak))}</span><button class="gs-ib" type="button" data-gs="odaksil" title="Genel konuşmaya dön" aria-label="Odağı kaldır">${IK.x}</button>`;
  $$('#gsAkis .gs-tk-m').forEach(boy);
  if (asagi || yakin) A.scrollTop = A.scrollHeight;
}
function odakAd(o){
  if (o.tur === 'taslak') return 'Bu taslak üzerine: ' + String(o.ozet || '').slice(0, 70) + (String(o.ozet || '').length > 70 ? '…' : '');
  if (o.tur === 'soru') return 'Ghost’un sorusu üzerine';
  if (o.tur === 'plan') return 'Haftanın planı: ' + String(o.ne || '').slice(0, 60);
  if (o.tur === 'puan') return 'Puan kartı: ' + (o.ad || '');
  if (o.tur === 'gundem') return 'Gündem: ' + String(o.baslik || '').slice(0, 60);
  return '';
}
function boy(t){ t.style.height = 'auto'; t.style.height = Math.min(t.scrollHeight + 2, 320) + 'px'; }

/* ---------------------------------------------------------------- gönderme (akış) */
async function gsGonder(metin){
  metin = String(metin || '').trim(); if (!metin || GS.akiyor) return;
  const acilis = GS.acilis?.metin || ''; GS.acilis = null;
  if (acilis) GS.mesajlar.push({rol: 'ghost', metin: acilis, zaman: Date.now() / 1000, id: 'a' + Date.now()});
  GS.mesajlar.push({rol: 'ben', metin, zaman: Date.now() / 1000});
  const yer = {rol: 'ghost', metin: '', akiyor: true, zaman: Date.now() / 1000};
  GS.mesajlar.push(yer); GS.akiyor = true; $('#gsGir').value = ''; boy($('#gsGir')); guncelleGonder();
  durum('Düşünüyor…', 'dusunuyor'); ciz(true);
  let tam = '';
  try{
    const r = await fetch('/api/ghost/sohbet', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({mesaj: metin, odak: GS.odak, acilis})});
    if (!r.ok || !r.body){ const j = await r.json().catch(() => ({})); throw new Error(j.hata || 'Ghost şu an cevap veremiyor'); }
    const rd = r.body.getReader(), dc = new TextDecoder();
    let ilk = true;
    for (;;){
      const {value, done} = await rd.read(); if (done) break;
      tam += dc.decode(value, {stream: true});
      const gor = tam.split('\x00')[0];
      if (gor && ilk){ ilk = false; durum('Yazıyor…', 'konusuyor'); }
      yer.metin = gor; akisCiz(yer);
    }
    const hata = tam.indexOf('\x00HATA:'), son = tam.indexOf('\x00SON:');
    if (hata >= 0) throw new Error(tam.slice(hata + 6));
    if (son >= 0){ const m = JSON.parse(tam.slice(son + 5)); Object.assign(yer, m, {akiyor: false}); }
    else Object.assign(yer, {akiyor: false, zaman: Date.now() / 1000});
  }catch(e){
    Object.assign(yer, {akiyor: false, hata: true, zaman: Date.now() / 1000, metin: (yer.metin ? yer.metin + '\n\n' : '') + 'Şu an cevap veremiyorum: ' + String(e.message || e).slice(0, 160)});
  }
  GS.akiyor = false; durum('İletişim danışmanınız ve yazı ortağınız'); ciz(true); guncelleGonder();
}
function akisCiz(m){
  const el = $$('#gsAkis .gs-m.ghost').slice(-1)[0]; if (!el) return ciz(true);
  const A = $('#gsAkis'), yakin = A.scrollHeight - A.scrollTop - A.clientHeight < 120;
  el.querySelector('.gs-metin').innerHTML = md(m.metin) + '<span class="gs-imlec"></span>';
  el.querySelector('.gs-av')?.classList.add('konusuyor');
  if (yakin) A.scrollTop = A.scrollHeight;
}
function guncelleGonder(){ $('#gsGir') && ($('[data-gs="gonder"]').disabled = GS.akiyor || !$('#gsGir').value.trim()); }

/* ---------------------------------------------------------------- eylemler */
async function uygula(kutu){
  const mid = kutu.dataset.m, i = +kutu.dataset.i, m = GS.mesajlar.find(x => x.id === mid), e = m?.eylemler?.[i]; if (!e) return;
  const b = kutu.querySelector('[data-gs="uygula"]'); if (b) b.disabled = true;
  const govde = {mesaj: mid, i}; if (e.tur === 'taslak') govde.metin = kutu.querySelector('.gs-tk-m').value.trim();
  const r = await ghPost('/api/ghost/sohbet/eylem', govde);
  if (!r._ok || r.hata){ toast(r.hata || 'Olmadı'); if (b) b.disabled = false; return null; }
  e.uygulandi = {zaman: Date.now() / 1000, temel: r.temel}; if (govde.metin) e.metin = govde.metin;
  toast(r.mesaj || 'Yapıldı'); ciz(); if (['taslak', 'duzenle', 'yaz', 'plan'].includes(e.tur)){ GH.dan = undefined; paylasimlarCiz(); }
  return r;
}
panel.addEventListener('click', async ev => {
  const b = ev.target.closest('[data-gs]'); if (!b || b.disabled) return;
  const kutu = b.closest('.gs-tk, .gs-ey');
  switch (b.dataset.gs){
    case 'kapat': return gsKapat();
    case 'gonder': return gsGonder($('#gsGir').value);
    case 'cip': return gsGonder(b.textContent);
    case 'odaksil': GS.odak = null; GS.acilis = null; return ciz();
    case 'mik': return ghMik(b, $('#gsGir'));
    case 'menu': return popover(b, [['Yeni konuşma başlat', async () => { const j = await fetch('/api/ghost/sohbet', {method: 'DELETE'}).then(r => r.json()).catch(() => null);
      GS.mesajlar = []; GS.odak = null; GS.acilis = j?.karsilama || null; ciz(); toast('Yeni konuşma; eskisi saklandı'); }], ['Danışman sayfasını aç', () => { gsKapat(); ghSekme('danisman'); }]]);
    case 'uygula': return uygula(kutu);
    case 'tkkopya': { const t = kutu.querySelector('.gs-tk-m').value; navigator.clipboard?.writeText(t); return toast('Kopyalandı'); }
    case 'tkx': { const t = kutu.querySelector('.gs-tk-m').value.trim(), m = GS.mesajlar.find(x => x.id === kutu.dataset.m), e = m?.eylemler?.[+kutu.dataset.i];
      if (e?.platform === 'linkedin'){ navigator.clipboard?.writeText(t); window.open('https://www.linkedin.com/feed/?shareActive=true', '_blank', 'noopener'); toast('Metin panoda; LinkedIn’e yapıştırın'); }
      else window.open('https://x.com/intent/post?text=' + encodeURIComponent(t), '_blank', 'noopener');
      const r = await uygula(kutu); if (r) toast('Taslaklarınıza da eklendi; paylaştıysanız orada işaretleyin'); return; }
    case 'tkgit': gsKapat(); return ghSekme('taslak');
  }
});
panel.addEventListener('input', ev => { const t = ev.target;
  if (t.id === 'gsGir'){ boy(t); guncelleGonder(); }
  if (t.classList.contains('gs-tk-m')){ boy(t); const n = t.value.length, s = t.closest('.gs-tk').querySelector('.gs-say'), li = s.textContent.indexOf('/') < 0 && n <= 280;
    s.textContent = n > 280 || li ? n : n + '/280'; s.classList.toggle('asim', n > 280); GS.kaydedilen[t.closest('.gs-tk').dataset.m + ':' + t.closest('.gs-tk').dataset.i] = {metin: t.value}; } });
panel.addEventListener('keydown', ev => { if (ev.target.id === 'gsGir' && ev.key === 'Enter' && !ev.shiftKey && !ev.isComposing){ ev.preventDefault(); gsGonder(ev.target.value); } });
document.addEventListener('keydown', ev => {
  if (ev.key === 'Escape' && GS.acik && !popEl){ gsKapat(); return; }
  if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === 'j' && !$('#gh')?.classList.contains('hidden')){ ev.preventDefault(); GS.acik ? gsKapat() : gsAc(); }
});
fab.addEventListener('click', () => gsAc());

/* ---------------------------------------------------------------- giriş noktaları: mevcut işlevleri sarmala */
const _ghSayfaEylem = ghSayfaEylem;
ghSayfaEylem = async function(g, b){
  switch (g){
    case 'gskonus': return gsAc(null);
    case 'gscip': return gsAc(null, b.textContent);
    case 'gskonusyaz': { const t = $('#ghGirdi'), v = t.value.trim(); t.value = ''; t.dispatchEvent(new Event('input', {bubbles: true})); return gsAc(null, v || undefined); }
    case 'gssoru': { const q = ((GH.f?.sorular || {}).sorular || [])[+b.dataset.i]; if (q) return gsAc({tur: 'soru', soru: q.soru}); return; }
    case 'gsplan': { const x = (GH.dan?.plan?.maddeler || []).find(m => m.i === +b.dataset.i); if (x) return gsAc({tur: 'plan', i: x.i, ne: x.ne}); return; }
    case 'gspuan': return gsAc({tur: 'puan', ad: b.dataset.ad || 'genel'});
    case 'gsalan': return gsAc(null, `${b.dataset.ad} hakkında neden az paylaşıyorum? Bana uyan bir şey önerir misin?`);
  }
  return _ghSayfaEylem(g, b);
};
const _ghEylem = ghEylem;
ghEylem = async function(a, b, el){
  if (a === 'konus'){ const x = ghVeri(el); if (!x) return; return gsAc({tur: 'taslak', anahtar: ghAnahtar(x), ozet: x.metin}); }
  return _ghEylem(a, b, el);
};
const _ghKart = ghKart;
ghKart = function(x, acik, gunsuz){
  return _ghKart(x, acik, gunsuz).replace('<button class="ghb kucuk ikon" type="button" data-a="daha"',
    `<button class="ghb kucuk gs-kk" type="button" data-a="konus" title="Bu taslak hakkında Ghost’la konuşun: neden, nasıl, başka ne">${IK.konus}Konuş</button><button class="ghb kucuk ikon" type="button" data-a="daha"`);
};
const _ghSizden = ghSizden;
ghSizden = function(){
  const Q = (GH.f?.sorular || {}).sorular || [];
  return _ghSizden().replace(/<div class="gh-q"><button type="button" data-g="soruac">([\s\S]*?)<\/button>/g, (tam, s) => {
    const i = Q.findIndex(q => esc(q.soru) === s && !q.cevap);
    return i < 0 ? tam : tam + `<button class="gh-q-konus" type="button" data-g="gssoru" data-i="${i}" title="Cevap yerine soru sorabilir, itiraz edebilirsiniz">${IK.konus}Konuşalım</button>`;
  });
};
const _ghPlanEylem = ghPlanEylem;
ghPlanEylem = function(x, ana){
  const h = _ghPlanEylem(x, ana);
  return x.durum === 'paylasildi' ? h : h + `<button class="ghb kucuk gs-kk" type="button" data-g="gsplan" data-i="${x.i}" title="Bunu Ghost’la konuşun: neden bu, nasıl yazılır, başka ne olabilir">${IK.konus}</button>`;
};

/* ---------------------------------------------------------------- Bugün: Ghost'un selamı */
function selamYukle(){ if (GS.selamYukleniyor || (GS.kars && Date.now() - GS.kars.t < 10 * 60000)) return;
  GS.selamYukleniyor = true; getJ('/api/ghost/sohbet').then(j => { GS.selamYukleniyor = false; if (j){ GS.kars = {...j.karsilama, t: Date.now()}; if (!GS.yuklendi){ GS.mesajlar = j.mesajlar || []; } ghCiz(); } }); }
const _ghBugun = ghBugun;
ghBugun = function(){
  const h = _ghBugun();
  if (GH.gun) return h;                                   // geçmiş gün görünümünde selam yok
  selamYukle(); const k = GS.kars; if (!k) return h;
  const kart = `<section class="gs-selam">${AV()}<div><p>${esc(k.metin)}</p><div class="gs-selam-c">${(k.secenekler || []).slice(0, 3).map(s => `<button class="gs-cip" type="button" data-g="gscip">${esc(s)}</button>`).join('')}<button class="gs-cip ana" type="button" data-g="gskonus">${IK.konus}Konuşalım</button></div></div></section>`;
  return kart + h;
};

/* ---------------------------------------------------------------- yazma kutusunda "Konuş" */
(function(){ const y = $('#ghYaz'); if (!y || $('#ghKonus')) return;
  const b = document.createElement('button'); b.className = 'ghb iki'; b.type = 'button'; b.id = 'ghKonus'; b.dataset.g = 'gskonusyaz'; b.title = 'Yazdıklarınızı gönderiye çevirmek yerine Ghost’la konuşun (soru da olabilir)';
  b.innerHTML = IK.konus + 'Konuş'; y.parentElement.insertBefore(b, y); })();

/* ---------------------------------------------------------------- Danışman: konu yörüngesi + puan kartını konuşma */
function yorunge(H){
  H = (H || []).filter(a => a && a.kod); if (H.length < 3) return '';
  const dar = window.innerWidth < 560, W = dar ? 360 : 680, Hh = dar ? 380 : 330, cx = W / 2, cy = Hh / 2 - 6, rx = dar ? 128 : 250, ry = dar ? 138 : 112;
  const mo = Math.max(1, ...H.map(a => a.oneri)), mp = Math.max(1, ...H.map(a => a.paylasilan));
  let s = `<svg class="gs-yor${ghCanli('yorunge')}" viewBox="0 -34 ${W} ${Hh + 44}" role="img" aria-label="Alan alan önerilen ve paylaşılan gönderiler">`;
  s += `<ellipse class="iz" cx="${cx}" cy="${cy}" rx="${rx}" ry="${ry}"/><ellipse class="iz ic" cx="${cx}" cy="${cy}" rx="${rx * .55}" ry="${ry * .55}"/>`;
  const N = H.map((a, i) => { const t = -Math.PI / 2 + i * 2 * Math.PI / H.length; return {...a, x: cx + rx * Math.cos(t), y: cy + ry * Math.sin(t)}; });
  N.forEach((a, i) => { s += `<path class="kol${(a.agirlik || 0) >= 3 ? ' akan' : ''}" d="M${cx} ${cy}L${a.x.toFixed(1)} ${a.y.toFixed(1)}" style="--i:${i};stroke-width:${(.6 + (a.agirlik || 1) * .45).toFixed(2)}"/>`; });
  s += `<circle class="merkez" cx="${cx}" cy="${cy}" r="22"/><text class="merkez-t" x="${cx}" y="${cy + 4}" text-anchor="middle">Siz</text>`;
  N.forEach((a, i) => {
    const ro = 9 + 21 * Math.sqrt(a.oneri / mo), rp = a.paylasilan ? 4 + (ro - 5) * Math.sqrt(a.paylasilan / mp) : 0, bos = (a.agirlik || 0) >= 3 && !a.paylasilan;
    const ad = ghAlan(a.ad)[2], alt = a.y > cy + 4, ty = a.y + (alt ? ro + 15 : -ro - 18);
    s += `<g class="dugum${bos ? ' bos' : ''}" style="--i:${i}" data-g="gsalan" data-ad="${esc(a.ad)}" tabindex="0" role="button"><title>${esc(a.ad)}: Ghost ${a.oneri} öneri, siz ${a.paylasilan} paylaşım (son 28 gün)</title>
      <circle class="oneri" cx="${a.x.toFixed(1)}" cy="${a.y.toFixed(1)}" r="${ro.toFixed(1)}"/>${rp ? `<circle class="pay" cx="${a.x.toFixed(1)}" cy="${a.y.toFixed(1)}" r="${rp.toFixed(1)}"/>` : ''}
      <text class="ad" x="${a.x.toFixed(1)}" y="${ty.toFixed(1)}" text-anchor="middle">${esc(ad)}</text><text class="say" x="${a.x.toFixed(1)}" y="${(ty + 13).toFixed(1)}" text-anchor="middle">${a.oneri} · ${a.paylasilan}</text></g>`;
  });
  return s + '</svg>';
}
function yorungeCumle(H){
  H = (H || []).filter(a => a && a.kod); if (!H.length) return '';
  const o = [...H].sort((a, b) => b.oneri - a.oneri)[0], p = [...H].sort((a, b) => b.paylasilan - a.paylasilan)[0];
  const bos = H.filter(a => (a.agirlik || 0) >= 3 && !a.paylasilan).map(a => ghAlan(a.ad)[2]);
  let c = `Ghost en çok ${ghAlan(o.ad)[2]} önerdi (${o.oneri})` + (p.paylasilan ? `, siz en çok ${ghAlan(p.ad)[2]} paylaştınız (${p.paylasilan}).` : '; bu ay paylaşım ölçülmedi.');
  if (o.kod !== p.kod && p.paylasilan) c += ' Önerilerle sizin seçtikleriniz ayrışıyor.';
  if (bos.length) c += ` Önem verip bu ay hiç paylaşmadıklarınız: ${bos.slice(0, 3).join(', ')}.`;
  return c;
}
const _ghDanisman = ghDanisman;
ghDanisman = function(){
  let h = _ghDanisman();
  const H = GH.dan?.harita;
  if (H && H.length >= 3 && h.indexOf('gh-puan-ic') > 0){
    const kart = `<section class="gh-sayfa-kart gs-yor-kart"><header><div><b>Konu yörüngesi</b><small>${esc(yorungeCumle(H))}</small></div><button class="ghb kucuk gs-kk" type="button" data-g="gsalan" data-ad="konu dengem">${IK.konus}Konuşalım</button></header>
      ${yorunge(H)}<div class="gs-yor-ana"><span><i class="o"></i>Ghost’un önerdiği</span><span><i class="p"></i>Sizin paylaştığınız</span><span><i class="k"></i>Kalın kol: önem verdiğiniz alan</span><span>Son 28 gün · bir alana dokunun, Ghost’la konuşun</span></div></section>`;
    const i = h.indexOf('<section class="gh-sayfa-kart', h.indexOf('gh-puan-ic'));
    h = i > 0 ? h.slice(0, i) + kart + h.slice(i) : h + kart;
  }
  return h.replace('<div class="gh-puan-ic">', `<button class="gs-puan-konus" type="button" data-g="gspuan" data-ad="genel">${AV('kucuk')}Bu kartı Ghost’la konuşun: neden böyle, ne yapmalı?</button><div class="gh-puan-ic">`);
};

/* ---------------------------------------------------------------- taslak ayrıntısı: okurun gözünden */
const OKUR = [['anlasilir', 'Anlaşılır'], ['tamlik', 'Tam'], ['deger', 'Değer'], ['kanca', 'İlk cümle'], ['ses', 'Ses'], ['tazelik', 'Taze'], ['paylasilir', 'Paylaşılır']];
const _ghDetay = ghDetay;
ghDetay = function(x){
  const o = x.okur || {}, B = OKUR.filter(([k]) => typeof o[k] === 'number').map(([k, ad]) => ({ad, puan: o[k] * 2}));
  if (B.length < 3) return _ghDetay(x);
  const zayif = [...B].sort((a, b) => a.puan - b.puan)[0];
  return `<div class="gh-d gs-okur"><b>Okurun gözünden</b><div class="gs-okur-ic">${ghRadar(B)}<p>Bu taslağı bağlamı bilmeyen bir okur puanladı (5 üzerinden). En zayıf yer: <b>${esc(zayif.ad.toLocaleLowerCase('tr'))}</b> (${zayif.puan / 2}).${o.not ? ` Notu: “${esc(String(o.not).slice(0, 220))}”` : ''}</p></div></div>` + _ghDetay(x);
};

/* ---------------------------------------------------------------- açılış */
try{ if (sessionStorage.getItem('gsAcik') === '1') setTimeout(() => !$('#gh')?.classList.contains('hidden') && gsAc(), 800); }catch(e){}
if (typeof ghCiz === 'function') setTimeout(() => ghCiz(), 50);
})();
