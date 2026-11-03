/* Taslak arşivi (2026-11-01; ghost_arsiv.py): gündemi geçmiş öneriler Taslaklar listesinden çıkar, burada katlanır bir bölümde durur ve geri getirilir.
   Arşiv bir ret değildir; öğrenmeye girmez. Geçmiş gün görünümünde o günün arşivlenenleri de listelenir. ghTaslak / ghGecmisGun / ghSayfaEylem sarmalanır. */
(() => {
if (typeof URUN === 'undefined' || URUN !== 'ghost') return;
const satir = x => `<div class="gh-sat"><div><small>${esc(ghTarih(x.olusma || 0))}${x.alan ? ' · ' + esc(ghAlan(x.alan)[2]) : ''}${x.arsiv_neden ? ' · ' + esc(x.arsiv_neden) : ''}</small>
  <p>${esc(String(x.metin || '').slice(0, 220))}${String(x.metin || '').length > 220 ? '…' : ''}</p></div><div class="eyl"><button class="ghb iki kucuk" type="button" data-g="arsivgeri" data-t="${esc(x.temel)}" data-i="${x.i}" title="Taslaklara geri getirir; üç gün arşive gitmez">Geri getir</button></div></div>`;
const _ghTaslak = ghTaslak;
ghTaslak = function(){
  let h = _ghTaslak();
  const A = (GH.d || {}).arsiv || [];
  if (A.length) h += `<details class="gh-katla"><summary>Arşiv <small>${A.length} · gündemi geçen ve paylaşılmayan öneriler</small></summary><div>
    <p class="gh-ipucu">Gündeme bağlı öneriler iki gün, yanıt önerileri bir gün, zamansız fikirler bir hafta sonra buraya gelir. Bu bir ret sayılmaz.</p>${A.slice(0, 60).map(satir).join('')}</div></details>`;
  return h;
};
const _ghGecmisGun = ghGecmisGun;
ghGecmisGun = function(){
  let h = _ghGecmisGun();
  const A = ((GH.d || {}).arsiv || []).filter(x => x.gun === GH.gun);
  if (A.length) h += `<details class="gh-katla"><summary>Arşivlenen öneriler <small>${A.length}</small></summary><div>${A.map(satir).join('')}</div></details>`;
  return h;
};
const _ghSayfaEylem = ghSayfaEylem;
ghSayfaEylem = async function(g, b){
  if (g === 'arsivgeri'){
    b.disabled = true;
    const r = await fetch(`/api/paylasim/${encodeURIComponent(b.dataset.t)}/${b.dataset.i}`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({arsiv: false})}).catch(() => null);
    if (!r || !r.ok){ toast('Olmadı'); b.disabled = false; return; }
    toast('Taslaklara geri geldi'); return paylasimlarCiz();
  }
  return _ghSayfaEylem(g, b);
};
})();
