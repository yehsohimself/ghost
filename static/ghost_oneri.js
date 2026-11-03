/* Gelen yazı önerileri (2026-10-31; ghost_oneri.py). Fikirler → "Gelen öneriler": ChatGPT/dot önerisi değişmeden saklanır, Ghost format kararını verir
   (X, zincir, LinkedIn, blog ya da geç) ve son metni yazar; her kartta dört ayrı katman: özgün öneri · üretim · kalite kontrolü · sizin onayınız (durumları ghost_oneri.ayrim,
   kayda yazmadan okur; yeşil yalnız kişinin kendi eylemidir). Taslak ayrıntısında gelen önerinin orijinali. "ChatGPT için dışa aktar": kişinin açıkça seçtiği, düzelttiği, paylaştığını onayladığı ve (ayrı bölümde) reddettiği metinler.
   index.html'deki ghDefter / ghDetay / ghSayfaEylem işlevlerini sarmalar. */
(() => {
if (typeof URUN === 'undefined' || URUN !== 'ghost') return;
const st = document.createElement('style');
st.textContent = `
#gh .go-form textarea,#gh .go-form input{width:100%;box-sizing:border-box;font:15px/1.45 var(--sans);padding:10px 12px;border-radius:12px;border:1px solid var(--line,var(--hair));background:var(--bg);color:var(--ink)}
#gh .go-form textarea{min-height:96px;resize:vertical}
#gh .go-form .go-ikili{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px}
#gh .go-form .go-alt{display:flex;align-items:center;gap:10px;justify-content:flex-end;margin-top:10px}
#gh .go-form .go-alt small{margin-right:auto;color:var(--muted);font-size:12.5px}
#gh .go-kart{border-top:1px solid var(--hair);padding:14px 0 12px}
#gh .go-kart:first-of-type{border-top:0}
#gh .go-ust{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:12.5px;color:var(--muted)}
#gh .go-cip{display:inline-flex;align-items:center;gap:5px;padding:2px 9px;border-radius:999px;font-weight:600;font-size:12px;background:var(--fill);color:var(--ink2)}
#gh .go-cip.tekrar{color:#ff9f0a}
#gh .go-orj{margin:8px 0 0;padding:10px 12px;border-radius:12px;background:color-mix(in srgb,var(--ink) 4%,transparent);border:1px dashed var(--line,var(--hair))}
#gh .go-orj p{margin:0;font-size:14.5px;line-height:1.5;white-space:pre-wrap}
#gh .go-not{margin:6px 0 0;font-size:13px;color:var(--ink2);line-height:1.45}
#gh .go-not b{font-weight:600}
#gh .go-psat{display:flex;justify-content:space-between;gap:12px;padding:9px 0;border-top:1px solid var(--hair)}
#gh .go-psat b{font-weight:600;font-size:14px}#gh .go-psat small{display:block;color:var(--muted);font-size:12.5px;line-height:1.4}
#gh .go-psag{text-align:right;flex:none;max-width:45%}
#gh .go-notform{margin-top:8px}
#gh .go-notform textarea{width:100%;box-sizing:border-box;min-height:84px;font:14px/1.45 var(--sans);padding:9px 11px;border-radius:12px;border:1px solid var(--line,var(--hair));background:var(--bg);color:var(--ink);resize:vertical}
#gh .go-notform small{display:block;margin-top:5px;color:var(--muted);font-size:12.5px;line-height:1.4}
#gh .go-blog{margin:8px 0 0;padding:12px 14px;border-radius:12px;background:var(--bg);border:1px solid var(--line,var(--hair));max-height:320px;overflow:auto;font-size:14px;line-height:1.55;white-space:pre-wrap}
#gh .go-blog textarea{width:100%;min-height:280px;border:0;background:transparent;color:var(--ink);font:14px/1.55 var(--sans);resize:vertical;outline:0}
#gh .go-eyl{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
#gh .go-ozet{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:999px;font-weight:600;font-size:12.5px;background:var(--fill);color:var(--ink2)}
#gh .go-ozet.sizin{color:#30d158;background:rgba(48,209,88,.12)}#gh .go-ozet.bekliyor{color:var(--ink);box-shadow:inset 0 0 0 1px var(--line,var(--hair));background:transparent}
#gh .go-ozet.uyari{color:#ff9f0a;background:rgba(255,159,10,.12)}#gh .go-ozet.sorun{color:#ff453a;background:rgba(255,69,58,.12)}
#gh .go-ozet.calisiyor{color:var(--vurgu);background:rgba(var(--vurgu-rgb,255,61,154),.12)}
#gh .go-ozet.calisiyor::before{content:"";width:7px;height:7px;border-radius:50%;background:currentColor;animation:ghhalo 1.6s ease-in-out infinite}
#gh .go-katlar{list-style:none;margin:12px 0 0;padding:0}
#gh .go-kat{position:relative;padding:0 0 16px 26px}
#gh .go-kat::before{content:"";position:absolute;left:5.5px;top:12px;bottom:-4px;width:1px;background:var(--line,var(--hair))}
#gh .go-kat:last-child{padding-bottom:0}#gh .go-kat:last-child::before{display:none}
#gh .go-kat::after{content:"";position:absolute;left:0;top:4px;width:12px;height:12px;border-radius:50%;box-sizing:border-box;border:1.5px solid color-mix(in srgb,var(--ink) 30%,transparent);background:var(--yuzey,var(--bg))}
#gh .go-kat[data-ton=vurgu]::after{border-color:var(--vurgu);background:var(--vurgu)}
#gh .go-kat[data-ton=calisiyor]::after{border-color:var(--vurgu);animation:ghhalo 1.6s ease-in-out infinite}
#gh .go-kat[data-ton=notr-dolu]::after{border-color:var(--ink2);background:var(--ink2)}
#gh .go-kat[data-ton=uyari]::after{border-color:#ff9f0a;background:#ff9f0a}
#gh .go-kat[data-ton=sorun]::after{border-color:#ff453a;background:#ff453a}
#gh .go-kat[data-ton=sizin]::after{border-color:#30d158;background:#30d158}
#gh .go-kbas{display:flex;align-items:baseline;justify-content:space-between;gap:10px;flex-wrap:wrap;min-height:20px}
#gh .go-kbas b{font-size:13.5px;font-weight:600;color:var(--ink)}
#gh .go-kdur{font-size:12.5px;font-weight:500;color:var(--muted);display:inline-flex;align-items:center;gap:4px}
#gh .go-kdur svg{width:12px;height:12px;fill:none;stroke:currentColor;stroke-width:2}
#gh .go-kat[data-ton=uyari] .go-kdur{color:#ff9f0a}#gh .go-kat[data-ton=sorun] .go-kdur{color:#ff453a}#gh .go-kat[data-ton=sizin] .go-kdur{color:#30d158}#gh .go-kat[data-ton=calisiyor] .go-kdur,#gh .go-kat[data-ton=vurgu] .go-kdur{color:var(--vurgu)}
#gh .go-alt-b{display:block;font-size:12.5px;font-weight:600;color:var(--muted);margin:10px 0 2px}
#gh .go-puan{display:flex;flex-wrap:wrap;gap:4px 12px;margin:6px 0 0;padding:0;list-style:none;font-size:12.5px;color:var(--muted);font-variant-numeric:tabular-nums}
#gh .go-puan b{font-weight:600;color:var(--ink2)}
#gh .go-sade{color:var(--muted)}
#gh .gh-d.go-d .go-orj{margin-top:6px}
@media (max-width:640px){#gh .go-form .go-ikili{grid-template-columns:1fr}}
@media (prefers-reduced-motion:reduce){#gh .go-ozet.calisiyor::before,#gh .go-kat::after{animation:none!important}}`;
document.head.appendChild(st);

const GO = {L: null, yukleniyor: false, acik: {}, duzen: {}, zaman: 0, notAcik: {}, notTaslak: {}, notEski: {}, notHata: {}};
/* Kaydedilmemiş not sayfa yenilense de kaybolmaz: yalnız bu tarayıcıda durur, kaydedilince silinir. */
const notSakla = () => { try{ const t = {}; for (const k of Object.keys(GO.notAcik)) if (GO.notTaslak[k] !== undefined) t[k] = {m: GO.notTaslak[k], eski: GO.notEski[k] ?? ''}; localStorage.setItem('goNotTaslak', JSON.stringify(t)); }catch(e){} };
try{ const t = JSON.parse(localStorage.getItem('goNotTaslak') || '{}'); for (const k of Object.keys(t)) { GO.notAcik[k] = true; GO.notTaslak[k] = t[k].m; GO.notEski[k] = t[k].eski; } }catch(e){}
document.addEventListener('input', e => { const k = e.target?.dataset?.gonot; if (k) { GO.notTaslak[k] = e.target.value; notSakla(); } });
const KILIT = '<svg viewBox="0 0 24 24"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>';
const FMT = {x: 'X gönderisi', zincir: 'X zinciri', linkedin: 'LinkedIn', blog: 'Blog yazısı', gec: 'Paylaşmaya değmez'};
const tarihYaz = t => { if (!t) return ''; const d = new Date(String(t).length === 10 ? t + 'T12:00' : t); return isNaN(d) ? t : d.toLocaleDateString(((window.DIL || {}).locale || 'tr-TR'), {day: 'numeric', month: 'long'}); };
const host = u => { try{ return new URL(u).hostname.replace(/^www\./, ''); }catch(e){ return ''; } };

const saatYaz = t => { if (!t) return ''; const d = new Date(typeof t === 'number' ? t * 1000 : t); return isNaN(d) ? String(t) : d.toLocaleString(((window.DIL || {}).locale || 'tr-TR'), {day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit'}); };
function yukle(zorla){
  if (GO.yukleniyor || (!zorla && GO.L && Date.now() - GO.zaman < 8000)) return;
  GO.yukleniyor = true;
  fetch('/api/ghost/oneriler').then(r => r.json()).then(j => { GO.L = j.oneriler || []; GO.tarama = j.tarama || {}; GO.hataYukle = ''; GO.zaman = Date.now(); GO.yukleniyor = false; ghCiz();
    if (GO.L.some(d => d.calisiyor || d.durum === 'yaziliyor')) setTimeout(() => yukle(true), 8000); })
    .catch(() => { GO.yukleniyor = false; GO.L = GO.L || []; GO.hataYukle = 'Öneriler okunamadı; kayıtlar yerinde duruyor. Biraz sonra yeniden denenecek.'; setTimeout(() => yukle(true), 15000); });
}
const sonSurum = d => (d.surumler || []).slice(-1)[0] || null;
const sonBlog = d => (d.surumler || []).slice().reverse().find(x => x.blog) || null;   // Ghost sonradan 'yazmadım' dese de kişinin metni görünür kalır

/* Sunucu henüz eski koddaysa katmanlar çıkmaz diye kart bozulmaz; yalnız bilinen durum gösterilir, kalite için sonuç uydurulmaz. */
function katman(d){
  const A = d.ayrim || {}, cal = d.calisiyor || d.durum === 'yaziliyor', s = sonSurum(d);
  const ESKI = {geldi: 'Bekliyor', yaziliyor: 'Ghost çalışıyor', yazildi: 'Yazıldı', elendi: 'Metin çıkmadı', gecildi: 'Yazılmadı', tekrar: 'Yazılmadı', hata: 'Tamamlanmadı'};
  const U = A.uretim || {durum: cal ? 'calisiyor' : d.durum, etiket: ESKI[cal ? 'yaziliyor' : d.durum] || d.durum, metin: '', format_ad: FMT[d.karar?.format] || '', neden: d.karar?.neden || '', aci: d.karar?.aci || '', zaman: s?.zaman, temel: s?.aktif !== false ? s?.temel || '' : ''};
  const Q = A.kalite || {durum: 'bilinmiyor', etiket: 'Sonuç kayıtlı değil', metin: 'Kalite sonucu site yeniden başlayınca görünür.', puanlar: [], notlar: []};
  const Y = A.onay || {durum: 'yok', etiket: 'Onay yok', metin: 'Onaylamadınız.', sizin: false};
  const O = A.ozet || {metin: U.etiket, ton: cal ? 'calisiyor' : 'notr'};
  return {U, Q, Y, O, cal};
}
const TON_U = {calisiyor: 'calisiyor', yazildi: 'vurgu', hata: 'sorun', elendi: 'uyari', tekrar: 'uyari', yazilmadi: 'notr-dolu', bekliyor: ''};
const TON_Q = {gecti: 'notr-dolu', notlu: 'uyari', gecmedi: 'uyari', yapilmadi: '', yok: '', bekliyor: '', bilinmiyor: ''};
const katBas = (ad, etiket, ek = '') => `<div class="go-kbas"><b>${ad}</b><span class="go-kdur">${ek}${esc(etiket)}</span></div>`;

function kart(d){
  const o = d.ozgun || {}, s = sonBlog(d), {U, Q, Y, O, cal} = katman(d), ekNot = d.editor_notu_ek;
  let h = `<div class="go-kart" data-go="${esc(d.id)}"><div class="go-ust"><span class="go-ozet ${esc(O.ton)}" data-gooz>${esc(O.metin)}</span>
    <span>${esc(o.uretici || 'Gelen öneri')}${o.tarih ? ' · ' + esc(tarihYaz(o.tarih)) : ''}${o.kanal === 'drive_havuz' ? ' · öneri havuzu' : ''}</span>
    ${o.kaynak_url ? `<a href="${esc(o.kaynak_url)}" target="_blank" rel="noopener">${esc(host(o.kaynak_url))} ↗</a>` : ''}</div>
    <ol class="go-katlar">`;

  /* 1) Özgün öneri: dışarıdan geldiği gibi; onay ya da görüş sayılmaz */
  h += `<li class="go-kat" data-kat="ozgun" data-ton="notr-dolu">${katBas('Özgün öneri', 'Değişmeden saklanıyor', KILIT)}
    ${d.ozgun_saglam === false ? '<p class="go-not" style="color:#ff453a">Parmak izi tutmuyor: saklanan metin ilk hâliyle aynı olmayabilir.</p>' : ''}
    <div class="go-orj"><p>${esc(o.metin)}</p></div>`;
  [o.editor_notu, o.not].filter(Boolean).forEach(n => { h += `<p class="go-not"><b>Editör notu</b> <i>(sizin görüşünüz sayılmaz, öğrenmeye girmez)</i>: ${esc(n)}</p>`; });
  if (ekNot?.metin) h += `<p class="go-not" data-goeknot><b>Eklenen editör notu</b> <span style="color:var(--muted)">${esc(saatYaz(ekNot.zaman))}</span> <i>(sizin görüşünüz sayılmaz, öğrenmeye girmez)</i>: ${esc(ekNot.metin)}</p>`;
  if (GO.notAcik[d.id]) {
    const hata = GO.notHata[d.id];
    h += `<div class="go-notform"><textarea data-gonot="${esc(d.id)}" aria-label="Editör notu" placeholder="Bu öneri için editör notu">${esc(GO.notTaslak[d.id] ?? (ekNot?.metin || ''))}</textarea>
      <small>Yeni öneri açılmaz, önerinin metni değişmez. Not sizin görüşünüz sayılmaz, öğrenmeye girmez. Sizin dokunduğunuz taslak olduğu gibi kalır.</small>
      ${hata ? `<p class="go-not" style="color:#ff453a">${esc(hata)}</p>` : ''}
      <div class="go-eyl"><button class="ghb ana kucuk" type="button" data-g="gonotkaydet">Kaydet ve yeniden değerlendir</button><button class="ghb kucuk" type="button" data-g="gonotvazgec">Vazgeç</button></div></div>`;
  }
  h += `<span class="go-alt-b">Kaynaklı olgular</span>${olgularHtml(d)}`;
  if (o.kaynak_durum) h += `<p class="go-not"><b>Tablodaki durum:</b> ${esc(o.kaynak_durum)} <i>(sizin onayınız sayılmaz)</i></p>`;
  if (d.kaynak_degisti) h += `<p class="go-not" style="color:#ff9f0a">Kaynak bu öneriyi sonradan değiştirdi; orijinal korundu. Yeni hali: ${esc(d.kaynak_degisti.metin)}</p>`;
  h += '</li>';

  /* 2) Üretim: Ghost'un yaptığı */
  h += `<li class="go-kat" data-kat="uretim" data-ton="${TON_U[U.durum] ?? ''}">${katBas('Üretim', U.etiket)}`;
  if (U.metin) h += `<p class="go-not">${esc(U.metin)}${U.zaman && !cal ? ` <span style="color:var(--muted)">${esc(saatYaz(U.zaman))}</span>` : ''}</p>`;
  if (U.neden && !['bekliyor', 'tekrar'].includes(U.durum)) h += `<p class="go-not"><b>Ghost'un gerekçesi:</b> ${esc(U.neden)}${U.aci ? ` <span style="color:var(--muted)">Açı: ${esc(U.aci)}</span>` : ''}</p>`;
  if (d.tekrar?.neden) h += `<p class="go-not" style="color:#ff9f0a">${esc(d.tekrar.neden)}${d.tekrar.tur === 'baska_aci' && ['bekliyor', 'calisiyor'].includes(U.durum) ? '; Ghost başka bir açıyla yazar.' : ''}</p>`;
  if (U.not_sonra) h += `<p class="go-not" style="color:var(--muted)">Editör notu bu sürümden sonra eklendi; metin bu nota göre yazılmadı.</p>`;
  if (d.hata) h += `<p class="go-not" style="color:#ff453a">${d.hata_zamani ? esc(saatYaz(d.hata_zamani)) + ': ' : ''}${esc(d.hata)}</p>`;
  if (s?.blog){
    const b = s.blog, duz = GO.duzen[d.id];
    h += duz ? `<div class="go-blog gh-gir"><textarea data-goblog="${esc(d.id)}">${esc(b.kisi_metni || b.metin)}</textarea></div>`
      : `<div class="go-blog">${esc(b.kisi_metni || b.metin)}</div>${b.kisi_metni ? '<p class="go-not">Sizin düzelttiğiniz hâli gösteriliyor; Ghost\'un metni ayrıca saklı.</p>' : ''}`;
    if (d.kisi_metni && !b.kisi_metni) h += `<p class="go-not"><b>Önceki sürümde sizin düzelttiğiniz metin</b> (silinmedi):</p><div class="go-blog">${esc(d.kisi_metni)}</div>`;
  }
  h += '</li>';

  /* 3) Kalite kontrolü: Ghost'un kendi denetimi; onay değildir */
  h += `<li class="go-kat" data-kat="kalite" data-ton="${TON_Q[Q.durum] ?? ''}">${katBas('Kalite kontrolü', Q.etiket)}<p class="go-not">${esc(Q.metin)}</p>`;
  if ((Q.puanlar || []).length) h += `<ul class="go-puan">${Q.puanlar.map(p => `<li>${esc(p.ad)} <b>${esc(p.puan)}/5</b></li>`).join('')}</ul>`;
  (Q.notlar || []).forEach(n => { h += `<p class="go-not" style="color:#ff9f0a">${esc(n)}</p>`; });
  if (['gecti', 'notlu'].includes(Q.durum)) h += '<p class="go-not go-sade">Bu, Ghost\'un kendi kontrolü; sizin onayınız yerine geçmez.</p>';
  h += '</li>';

  /* 4) Sizin onayınız: yalnız sizin açık eyleminiz */
  h += `<li class="go-kat" data-kat="onay" data-ton="${Y.sizin ? 'sizin' : ''}">${katBas('Sizin onayınız', Y.etiket)}<p class="go-not">${esc(Y.metin)}</p></li></ol>`;

  const E = [];
  if (cal) {}
  else if (d.durum === 'geldi') E.push(`<button class="ghb ana kucuk" type="button" data-g="goyaz">Ghost değerlendirsin</button>`);
  else if (d.durum === 'tekrar') E.push(`<button class="ghb iki kucuk" type="button" data-g="gozorla">Yine de değerlendir</button>`);
  else if (['elendi', 'hata'].includes(d.durum)) E.push(`<button class="${U.temel ? 'ghb iki kucuk' : 'ghb ana kucuk'}" type="button" data-g="goyaz">Yeniden dene</button>`);
  if (U.temel && !cal) E.unshift(`<button class="ghb ana kucuk" type="button" data-g="goac" data-t="${esc(U.temel)}">Taslağı aç</button>`);
  if (s?.blog){
    E.push(GO.duzen[d.id] ? `<button class="ghb ana kucuk" type="button" data-g="goblogkaydet">Kaydet</button><button class="ghb kucuk" type="button" data-g="goblogvazgec">Vazgeç</button>`
      : `<button class="ghb iki kucuk" type="button" data-g="goblogkopya">Kopyala</button><button class="ghb kucuk" type="button" data-g="goblogduzenle">Düzelt</button>`);
  }
  if (!cal && ['yazildi', 'gecildi'].includes(d.durum)) E.push(`<button class="ghb kucuk" type="button" data-g="goyaz" title="Yeni bir sürüm yazar; sizin dokunduğunuz taslak olduğu gibi kalır">Yeniden değerlendir</button>`);
  if (!cal && !GO.notAcik[d.id]) E.push(`<button class="ghb kucuk" type="button" data-g="gonot">${ekNot?.metin ? 'Editör notunu düzenle' : 'Editör notu ekle'}</button>`);
  if (!cal && !['gecildi'].includes(d.durum)) E.push(`<button class="ghb kucuk" type="button" data-g="gogec">Geç</button>`);
  if (E.length) h += `<div class="go-eyl">${E.join('')}</div>`;
  return h + '</div>';
}

function olgularHtml(d){
  const A = d.ayrim || {}, Ky = A.kaynak || {}, o = d.ozgun || {};
  let h = (A.olgular || []).map(x => `<p class="go-not">${esc(x.metin)} <span style="color:var(--muted)">${x.url ? `<a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.kaynak || host(x.url))} ↗</a>` : esc(x.kaynak)}${x.tarih ? ' · ' + esc(tarihYaz(x.tarih)) : ''}</span></p>`).join('');
  if (!h) h = `<p class="go-not" style="color:var(--muted)">${o.kaynak_url ? `Ayrı olgu verilmedi; kaynak bağlantısı: <a href="${esc(o.kaynak_url)}" target="_blank" rel="noopener">${esc(host(o.kaynak_url))} ↗</a>` : 'Kaynak verilmedi.'}${o.tarih ? ' Önerinin tarihi ' + esc(tarihYaz(o.tarih)) + '.' : ' Kaynak tarihi yok.'}</p>`;
  if (Ky.kanit_siniri) h += `<p class="go-not"><b>Kanıt sınırı:</b> ${esc(Ky.kanit_siniri)}</p>`;
  (A.kaynaksiz || []).forEach(m => { h += `<p class="go-not" style="color:#ff9f0a">Kaynağı yok, olgu sayılmadı: ${esc(m)}</p>`; });
  return h;
}
function taramaHtml(){
  const t = GO.tarama || {};
  const p = [t.son_basarili ? `Öneri havuzuna son başarılı bakış ${esc(saatYaz(t.son_basarili))}` : 'Öneri havuzu henüz okunmadı', t.kaynak_tarihi ? `havuzun kopyası ${esc(saatYaz(t.kaynak_tarihi))} tarihli` : ''].filter(Boolean).join(' · ');
  return `<p class="gh-ipucu">${p}.</p>${t.son_hata ? `<p class="go-not" style="color:#ff453a">${t.hata_zamani ? esc(saatYaz(t.hata_zamani)) + ': ' : ''}${esc(t.son_hata)}</p>` : ''}${GO.hataYukle ? `<p class="go-not" style="color:#ff453a">${esc(GO.hataYukle)}</p>` : ''}`;
}
function bolum(){
  yukle();
  const L = GO.L;
  let h = `<section class="gh-sayfa-kart"><header><div><b>Öneri ekle</b><small>ChatGPT ya da başka bir yazı asistanının önerisini yapıştırın. Olduğu gibi saklanır; Ghost hangi biçimde (X, zincir, LinkedIn, blog) yazılacağına karar verir ve son metni kendisi yazar. Öneri sizin onayınız sayılmaz.</small></div></header>
    <div class="go-form"><div class="gh-gir" style="display:block"><textarea id="goMetin" placeholder="Öneri metni"></textarea></div>
      <div class="go-ikili"><input id="goUrl" placeholder="Kaynak bağlantısı (isteğe bağlı)" inputmode="url"><input id="goTarih" placeholder="Öneri tarihi (ör. 31.10.2026)"></div>
      <div class="go-ikili"><input id="goNot" placeholder="Araştırma notu ya da kanıt sınırı (isteğe bağlı)"><input id="goEditor" placeholder="Editör notu (sizin görüşünüz sayılmaz)"></div>
      <div class="go-ikili"><input id="goUretici" placeholder="Üretici" value="ChatGPT"></div>
      <div class="go-alt"><small>Drive'daki öneri havuzunuzdaki yeni satırlar da buraya kendiliğinden gelir.</small><button class="ghb ana" type="button" data-g="goekle">Ekle</button></div></div></section>`;
  h += `<section class="gh-sayfa-kart"><header><div><b>Gelen öneriler</b><small>${L ? (L.length ? `${L.length} öneri · ${L.filter(d => d.durum === 'yazildi').length} yazıldı · ${L.filter(d => d.durum === 'tekrar').length} tekrar` : 'Henüz öneri yok.') : 'Yükleniyor…'}</small></div>
    <button class="ghb iki kucuk" type="button" data-g="godisa" aria-haspopup="menu" title="Açıkça seçtikleriniz, düzelttikleriniz, paylaştıklarınız ve ayrı bölümde reddettikleriniz">ChatGPT için dışa aktar</button></header>${taramaHtml()}`;
  h += L && L.length ? L.map(kart).join('') : '<p class="gh-ipucu">Bir öneri ekleyin; Ghost kararını ve son metnini burada gösterir.</p>';
  return h + '</section>';
}

/* Fikirler'e alt sekme: orijinal işlev 'oneri'yi tanımadığı için bir an 'fikir' sanılır, sonra içerik değiştirilir */
const _ghDefter = ghDefter;
ghDefter = function(){
  const istenen = GH.dsek;
  if (istenen === 'oneri') GH.dsek = 'fikir';
  let h = _ghDefter();
  GH.dsek = istenen;
  const bekle = (GO.L || []).filter(d => ['geldi', 'yaziliyor'].includes(d.durum)).length;
  const dugme = `<button type="button" data-g="dsek" data-v="oneri" aria-pressed="${istenen === 'oneri'}">Gelen öneriler${bekle ? `<i>${bekle}</i>` : ''}</button>`;
  const i = h.indexOf('<div class="gh-alt-sek">');
  if (i < 0) return h;
  const j = h.indexOf('</div>', i);
  if (istenen !== 'oneri') return h.slice(0, j) + dugme + h.slice(j);
  return h.slice(0, j).replace(/aria-pressed="true"/g, 'aria-pressed="false"') + dugme + '</div>' + bolum();
};

/* taslak ayrıntısı: gelen önerinin orijinali ve Ghost'un kararı */
const _ghDetay = ghDetay;
ghDetay = function(x){
  const h = _ghDetay(x);
  if (!x.dis_oneri) return h;
  yukle();
  const d = (GO.L || []).find(o => o.id === x.dis_oneri), o = d?.ozgun || {};
  const fk = x.format_karari || d?.karar || {};
  return `<div class="gh-d go-d"><b>Gelen öneriden</b>${fk.format ? `<p>Ghost'un kararı: <b>${esc(FMT[fk.format] || fk.format)}</b>. ${esc(fk.neden || '')}</p>` : ''}
    ${d ? `<div class="go-orj"><small>${KILIT}${esc(o.uretici || 'Gelen öneri')}${o.tarih ? ' · ' + esc(tarihYaz(o.tarih)) : ''} · değişmeden saklanıyor</small><p>${esc(o.metin)}</p></div>
    ${o.arastirma_notu ? `<p>Kanıt sınırı: ${esc(o.arastirma_notu)}</p>` : ''}
    ${(d.ayrim?.oneri?.notlar || []).map(n => `<p>Editör notu <i>(sizin görüşünüz sayılmaz)</i>: ${esc(n)}</p>`).join('')}
    ${d.ayrim?.kalite?.metin ? `<p>Kalite kontrolü: ${esc(d.ayrim.kalite.metin)}</p>` : ''}
    <p>Sizin onayınız: ${esc(d.ayrim?.onay?.metin || '')}</p>` : '<p class="gh-ipucu">Gelen öneri yükleniyor…</p>'}
    <p><i>Bu taslak dışarıdan gelen bir öneriden yazıldı; düzeltmeleriniz kendiliğinden öğrenilmez, dışa aktarmada görünür.</i></p></div>` + h;
};

/* Profil: hangi bölüm nereden öğreniyor, son ne zaman değişti, son hata */
const GP = {d: null, zaman: 0, hata: ''};
function profilKayitHtml(){
  const d = GP.d;
  if (GP.hata && !d) return `<header><div><b>Profiliniz nasıl güncellenir</b></div></header><p class="go-not" style="color:#ff453a">${esc(GP.hata)}</p>`;
  if (!d) return '<header><div><b>Profiliniz nasıl güncellenir</b><small>Yükleniyor…</small></div></header>';
  const sat = x => `<div class="go-psat"><div><b>${esc(x.ad)}</b><small>${esc(x.nereden)}</small></div><div class="go-psag">${x.ogrenir ? '' : '<span class="go-cip tekrar">Öğrenmeye girmez</span>'}<small>${x.adet} kayıt${x.son ? ' · ' + esc(saatYaz(x.son)) : ''}</small></div></div>`;
  return `<header><div><b>Profiliniz nasıl güncellenir</b><small>Ghost yalnız sizin açık eylemlerinizden öğrenir. Dışarıdan gelen öneriler ve editör notları ayrı saklanır.</small></div>
      <button class="ghb iki kucuk" type="button" data-g="gopk" aria-expanded="${!!GP.acik}">${GP.acik ? 'Gizle' : 'Ayrıntılar'}</button></header>
    ${GP.acik ? d.satirlar.map(sat).join('') : ''}
    <p class="gh-ipucu" style="margin-top:10px">${d.son_basarili ? `Son başarılı kayıt ${esc(saatYaz(d.son_basarili))}.` : 'Henüz kayıt yok.'}${(d.son_degisiklikler || []).length ? ` Son değişenler: ${d.son_degisiklikler.slice(0, 3).map(g => `${esc(g.bolumler.join(', '))} (${esc(saatYaz(g.zaman))})`).join(' · ')}.` : ''}</p>
    ${d.son_hata ? `<p class="go-not" style="color:#ff453a">Son kayıt yapılamadı${d.hata_zamani ? ' (' + esc(saatYaz(d.hata_zamani)) + ')' : ''}: ${esc(d.son_hata)} Profiliniz olduğu gibi duruyor.</p>` : ''}`;
}
const _ghSes = ghSes;
ghSes = function(){
  const h = _ghSes();
  if (Date.now() - GP.zaman > 30000){ GP.zaman = Date.now();
    fetch('/api/ghost/profil-kayit').then(r => { if (!r.ok) throw 0; return r.json(); }).then(j => { GP.d = j; GP.hata = ''; }).catch(() => { GP.hata = 'Profil kaydının durumu okunamadı.'; })
      .finally(() => { const e = document.getElementById('goProfilKayit'); if (e) e.innerHTML = profilKayitHtml(); }); }
  const i = h.indexOf('</header>');
  const kart = `<section class="gh-sayfa-kart" id="goProfilKayit">${profilKayitHtml()}</section>`;
  return i < 0 ? kart + h : h.slice(0, i + 9) + kart + h.slice(i + 9);
};

const post = (u, b) => fetch(u, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(b || {})}).then(async r => ({_ok: r.ok, ...(await r.json().catch(() => ({})))}));
const _ghSayfaEylem = ghSayfaEylem;
ghSayfaEylem = async function(g, b){
  const kid = b?.closest?.('[data-go]')?.dataset.go, d = (GO.L || []).find(x => x.id === kid);
  switch (g){
    case 'gonot': GO.notAcik[kid] = true; GO.notEski[kid] = d?.editor_notu_ek?.metin || ''; delete GO.notTaslak[kid]; delete GO.notHata[kid]; ghCiz(true);
      setTimeout(() => document.querySelector(`[data-gonot="${CSS.escape(kid)}"]`)?.focus(), 30); return;
    case 'gonotvazgec': delete GO.notAcik[kid]; delete GO.notTaslak[kid]; delete GO.notHata[kid]; notSakla(); return ghCiz(true);
    case 'gonotkaydet': { const v = document.querySelector(`[data-gonot="${CSS.escape(kid)}"]`)?.value ?? ''; b.disabled = true;
      const r = await post(`/api/ghost/oneri/${encodeURIComponent(kid)}`, {islem: 'not', metin: v, eski: GO.notEski[kid] ?? '', yaz: true}); b.disabled = false;
      if (!r._ok){ GO.notTaslak[kid] = v; notSakla(); if (r.guncel !== undefined) { GO.notEski[kid] = r.guncel; notSakla(); GO.notHata[kid] = `Bu not başka yerde değişmiş: “${r.guncel}”. Yeniden basarsanız kutudaki metin geçerli olur.`; } else GO.notHata[kid] = r.hata || 'Kaydedilemedi; metniniz kutuda duruyor.'; ghCiz(true); return yukle(true); }
      delete GO.notAcik[kid]; delete GO.notTaslak[kid]; delete GO.notHata[kid]; notSakla();
      const i = (GO.L || []).findIndex(x => x.id === kid); if (i >= 0) GO.L[i] = {...GO.L[i], ...r.oneri, ayrim: GO.L[i].ayrim, calisiyor: !r.suruyor || GO.L[i].calisiyor};
      toast(r.suruyor ? 'Not kaydedildi; süren yazım bitince yeniden değerlendirin' : 'Not kaydedildi; Ghost yeniden değerlendiriyor'); ghCiz(true); return setTimeout(() => yukle(true), 1500); }
    case 'gopk': { GP.acik = !GP.acik; const e = document.getElementById('goProfilKayit'); if (e) e.innerHTML = profilKayitHtml(); return; }
    case 'goekle': {
      const metin = $('#goMetin')?.value.trim(); if (!metin || metin.length < 8){ toast('Öneri metnini yapıştırın'); return; }
      b.disabled = true;
      const r = await post('/api/ghost/oneri', {metin, kaynak_url: $('#goUrl').value.trim(), tarih: $('#goTarih').value.trim(), arastirma_notu: $('#goNot').value.trim(), editor_notu: $('#goEditor').value.trim(),
        uretici: $('#goUretici').value.trim() || 'ChatGPT'});
      b.disabled = false;
      if (!r._ok){ toast(r.hata || 'Eklenemedi'); return; }
      ['#goMetin', '#goUrl', '#goTarih', '#goNot', '#goEditor'].forEach(q => { const e = $(q); if (e) e.value = ''; });
      toast(!r.yeni ? 'Bu öneri zaten kayıtlı' : r.oneri.durum === 'tekrar' ? 'Eklendi; ama bir tekrar gibi görünüyor, Ghost yazmadı' : 'Eklendi; Ghost karar verip yazıyor');
      return yukle(true);
    }
    case 'goyaz': case 'gozorla': { b.disabled = true; const r = await post(`/api/ghost/oneri/${encodeURIComponent(kid)}`, {islem: g === 'gozorla' ? 'zorla' : 'yaz'});
      if (!r._ok){ toast(r.hata || 'Olmadı'); b.disabled = false; return; } toast('Ghost karar verip yazıyor; bir iki dakika sürer'); if (d) d.calisiyor = true; ghCiz(true); return setTimeout(() => yukle(true), 2500); }
    case 'gogec': return popover(b, [['Neden geçiyorsunuz?', null], ['Konu bana göre değil', () => gecle('konu bana göre değil')], ['Söylenen bariz', () => gecle('söylenen bariz')],
      ['Zamanı geçti', () => gecle('zamanı geçti')], ['Sadece geç', () => gecle('')]]);
    case 'goac': { const t = b.dataset.t; GH.on = t + '#0'; GH.acik[GH.on] = true; paylasimlarCiz(); return ghSekme('taslak'); }
    case 'goblogkopya': { const s = sonBlog(d); navigator.clipboard?.writeText(s?.blog?.kisi_metni || s?.blog?.metin || ''); return toast('Blog yazısı kopyalandı'); }
    case 'goblogduzenle': GO.duzen[kid] = true; return ghCiz(true);
    case 'goblogvazgec': delete GO.duzen[kid]; return ghCiz(true);
    case 'goblogkaydet': { const v = document.querySelector(`[data-goblog="${CSS.escape(kid)}"]`)?.value || ''; b.disabled = true;
      const r = await post(`/api/ghost/oneri/${encodeURIComponent(kid)}`, {islem: 'blog', metin: v}); b.disabled = false;
      if (!r._ok){ toast(r.hata || 'Kaydedilemedi'); return; } delete GO.duzen[kid]; toast('Düzeltmeniz kaydedildi; Ghost’un metni ayrıca saklı'); return yukle(true); }
    case 'godisa': return popover(b, [['Son 90 gün', null], ['JSON olarak indir', () => { location.href = '/api/ghost/disa-tercihler?gun=90'; }],
      ['Metin olarak indir (ChatGPT’ye yapıştırmak için)', () => { location.href = '/api/ghost/disa-tercihler?gun=90&bicim=md'; }]]);
  }
  return _ghSayfaEylem(g, b);
  async function gecle(neden){ const r = await post(`/api/ghost/oneri/${encodeURIComponent(kid)}`, {islem: 'gec', neden}); toast(r._ok ? 'Geçildi' : r.hata || 'Olmadı'); yukle(true); }
};
})();
