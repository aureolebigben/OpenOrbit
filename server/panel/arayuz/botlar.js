/* OpenOrbit paneli — Botlar (botlar.py, /api/bot…; belgeler/BOTLAR.md). panel.js'in yardımcılarını kullanır.
   Bot paketi: kadrosu oluşturulurken bir kez üretilen botlar (ad, firma, kişilik) ve ayarları. Paket bir dünyaya atanır; oyuncu o
   dünyada oyuna girince botlar devreye girer. Kipler: Basit (haritalarda dolaşan, harita değiştirmeyen), Normal (gerçek oyuncu gibi
   gelişen, karar veren, sosyal), Gelişmiş (Normal + yerel dil modeli: sohbet ve kararlar).
   Görünümler: kitaplık (paket kartları), sihirbaz (ad ve dünya -> kip -> ayarlar), editör (sekmeler). Değişiklikler kendiliğinden
   kaydedilir. */
'use strict';

Object.assign(IC, {
  bot: '<rect x="4" y="8" width="16" height="12" rx="2"/><path d="M12 8V4"/><circle cx="12" cy="3" r="1"/><circle cx="9" cy="13" r="1.3"/><circle cx="15" cy="13" r="1.3"/><path d="M9 17h6"/>',
  brain: '<path d="M9 4a3 3 0 0 0-3 3v.5A3 3 0 0 0 4 10.5 3 3 0 0 0 5 13a3 3 0 0 0 1 5 3 3 0 0 0 6 1V5a2 2 0 0 0-3-1z"/><path d="M15 4a3 3 0 0 1 3 3v.5a3 3 0 0 1 2 3 3 3 0 0 1-1 2.5 3 3 0 0 1-1 5 3 3 0 0 1-6 1"/>',
  chat: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
  list: '<line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><circle cx="3.5" cy="6" r="1"/><circle cx="3.5" cy="12" r="1"/><circle cx="3.5" cy="18" r="1"/>',
});

const BT = { liste: null, pid: null, d: null, sekme: 'genel', zam: null, bekleyen: {} };
const BT_KIPLER = {
  basit: { ad: N('Basit'), ic: 'bot', ozet: N('Haritalarda NPC gibi dolaşan, harita değiştirmeyen botlar. Uzaylı keser; düşmansa seni görünce gücüne göre saldırır ya da kaçar.') },
  normal: { ad: N('Normal'), ic: 'users', ozet: N('Gerçek oyuncu gibi: üssünde başlar, görev yapar, kasar, gemi ve lazer alır, PvP yapar, klan kurar, arkadaş edinir, sohbet eder. Her botun kişiliği ve kararları kendine.') },
  gelismis: { ad: N('Gelişmiş'), ic: 'brain', ozet: N('Normal kipin üstüne yerel dil modeli (Qwen3 4B): botlar seninle ve birbirleriyle gerçekten konuşur, ricalarını düşünüp karar verir, yardım çağrılarına gelir.') },
};
const BT_ARKETIP = { kasici: N('PvE kasıcı'), avci: N('PvP avcısı'), sosyal: N('Sosyal'), tuccar: N('Tüccar'), gorevci: N('Görevci'), rahat: N('Rahat'), lider: N('Lider') };
const BT_HEDEF = { kasilma: N('Uzaylı kasıyor'), gorev: N('Görev yapıyor'), pvp: N('PvP avında'), alisveris: N('Alışverişte'), dinlenme: N('Dinleniyor'),
  kesif: N('Keşifte'), grup: N('Grupta'), yardim: N('Yardıma gidiyor'), basit: N('Uzaylı kasıyor') };
const BT_IZIN = {
  magaza: [N('Mağaza'), N('Kredi ve uridyumla gemi, lazer, jeneratör ve dron alırlar.')],
  gorev: [N('Görevler'), N('Görev zincirini yaparlar.')],
  pvp: [N('PvP'), N('Botlar birbirleriyle savaşır.')],
  oyuncuya_saldir: [N('Sana saldırma'), N('Düşman firmadaki botlar seni görünce saldırabilir.')],
  sohbet: [N('Sohbet'), N('Global, firma, klan ve grup sohbetine yazar, fısıltına yanıt verirler.')],
  klan: [N('Klana katılma'), N('Kişiliklerine uyan klanlara başvururlar (seninkine de).')],
  klan_kur: [N('Klan kurma'), N('Lider ruhlu, zengin botlar klan kurar ve başvuruları değerlendirir.')],
  arkadas: [N('Arkadaşlık'), N('Arkadaşlık isteğini değerlendirir, birlikte oynadıkları kişilere istek gönderirler.')],
  grup: [N('Grup'), N('Grup davetini kabul edebilir, grupta liderin peşinden giderler.')],
  muzayede: [N('Açık artırma'), N('Açık artırmada teklif verip seninle yarışırlar.')],
  yardim: [N('Yardım çağrıları'), N('Sohbetteki yardım çağrısına (ör. "2-4 yardım") bazı botlar gelir.')],
  kargo: [N('Kargo ve cevher satışı'), N('Uzaylıların kargo kutularını toplarlar; kargo dolunca kendi istasyonlarına (X-1, X-8) dönüp cevheri satarlar.')],
  roket: [N('Roketler'), N("Roket alır ve savaşta atarlar (R-310'dan PLT-3030'a, paralarına göre).")],
  ozel_cephane: [N('Özel cephane'), N("Dayanıklı uzaylılara x2/x3 (MCB-25/50), PvP'de RSB-75 kullanır, uridyumla alırlar. Kapalıysa yalnız LCB-10.")],
  ekstra: [N("CPU'lar ve ekstralar"), N("Onarım robotu, roket CPU'su, kargo CPU'su, HM-7, atlama ve gizlenme CPU'ları, Insta-Shield ve Smart Bomb alıp kullanırlar.")],
  mayin: [N('Mayınlar'), N('Saldırgan botlar mayın alır; senden kaçarken arkalarına mayın bırakırlar.')],
  lab: [N('Arıtma ve laboratuvar'), N('Kargodaki cevheri arıtıp lazerlerine, roketlerine ve kalkanlarına yüklerler (Prometid, Duranium, Promerium, Seprom).')],
  skylab: [N('Skylab'), N('Skylab kurup yükseltirler; ürettiği cevheri gemiye taşıyıp satar ya da laboratuvarda kullanırlar.')],
  teknoloji: [N('Teknoloji eşyaları'), N("Assembly'de teknoloji eşyası üretip (Backup Shields, Battle Repair Bot, Chain Impulse, Energy Leech, Precision Targeter) savaşta kullanırlar.")],
  ganimet: [N('Ganimet kutuları'), N('Haritadaki anahtarlı kutuları anahtarla açarlar; yeşil kutuya değerse uridyumla anahtar alırlar.')],
  assembly: [N('Assembly'), N("Uzaylılardan topladıkları kaynaklarla Assembly'de anahtar, eşya ve cephane üretirler.")],
  kapi: [N('Galaksi Kapıları'), N('Kapı enerjisiyle (ya da uridyumla) üreticide parça toplar, kapıyı kurar ve gücü yetince koşarlar.')],
  etkinlik: [N("Etkinlikler ve pass'ler"), N('Etkinliklere katılırlar (etkinlik uzaylıları, kutuları ve parası), Battle Pass ve Season Pass ilerletip ödül alırlar.')],
  klan_diplomasi: [N('Klan diplomasisi'), N('Bot klan liderleri ittifak, saldırmazlık, savaş ve barış ister ya da gelen isteklere (senin klanınınkiler dahil) yanıt verir. Müttefike saldırmazlar, savaştaki klanın üyesini önceliklerler.')],
  modlar: [N('Etkinlik ve PvE modları'), N('Etkinlik kapıları, Voyagers, Trinity, Astral, Black Light, Echoes, LoW, Vortex, Mimesis, World Boss, Apotheosis, Labirent; Dispatch ve Galaxy Trek. Gücü yettiği moda girer, ulaştığı yere göre ödül alırlar.')],
  kutu_calma: [N('Kargo çalma'), N('Kaba botlar ara sıra başkasının (seninkini de) kargo kutusunu toplar; aynı firmadansa onur kaybeder.')],
};
const BT_SINIF_AD = s => s === '4-X' ? '4-1…4-4' : s;
const btDoldur = (el, ...k) => el.replaceChildren(...k.flat(Infinity).filter(x => x != null && x !== false));
const btFirma = ['MMO', 'EIC', 'VRU'];
function btArt(name, yedek, cls = 'bt-art') {         // görsel gelmediyse (Orders.md) var olan bir görsel
  const im = art(name, cls);
  im.onerror = () => { im.onerror = null; im.src = 'gorsel/' + yedek + '.webp'; };
  return im;
}
const btDunyaAd = id => (BT.liste?.dunyalar || []).find(w => w.id === id)?.ad || T('Atanmamış');

// ------------------------------------------------------------------ giriş noktası
async function renderBotlar() {
  const r = await act(() => api('/api/botlar')); if (!r || S.page !== 'botlar') return;
  BT.liste = r;
  if (BT.pid && !r.liste.some(p => p.id === BT.pid)) BT.pid = null;
  if (!BT.pid) return btKitaplik();
  btEditor();
}
function btAc(pid, sekme) { BT.pid = pid; BT.sekme = sekme || 'genel'; renderBotlar(); }

function btFirmaCubugu(f) {
  const top = f.reduce((a, b) => a + b, 0) || 1;
  return h('div', { class: 'bt-firmalar', title: btFirma.map((x, i) => x + ' ' + f[i]).join(' · ') },
    f.map((n, i) => h('i', { class: btFirma[i].toLowerCase(), style: { width: (100 * n / top) + '%' } })));
}

// ================================================================== KİTAPLIK
function btKitaplik() {
  const r = BT.liste;
  const kart = p => h('div', { class: 'bt-kart', onclick: e => { if (!e.target.closest('button')) btAc(p.id); } },
    h('div', { class: 'bt-kart-ust k-' + p.kip }, btArt('bot_kip_' + p.kip, 'dron_editor', 'bt-kart-art'),
      h('div', null, h('b', null, p.ad), h('div', { class: 'small muted' }, T(BT_KIPLER[p.kip].ad) + ' · ' + T('{0} bot', p.adet)))),
    h('div', { class: 'bt-kart-govde' },
      h('div', { class: 'row wrap', style: { gap: '6px' } }, p.dunya ? badge([icon('globe'), btDunyaAd(p.dunya)], 'info') : badge(T('Dünyaya atanmadı'), 'warn'),
        p.kip !== 'basit' ? badge(p.gelisim === 'jumpstart' ? 'Jumpstart' : 'Progressive', '') : null),
      btFirmaCubugu(p.firmalar),
      h('div', { class: 'small muted' }, p.seviye_ort != null ? T('Ortalama seviye {0} · en yüksek {1}', p.seviye_ort, p.seviye_enb)
        : T('Henüz oynanmadı: botlar ilk girişte başlar.')),
      p.aciklama ? h('div', { class: 'small ellipsis' }, p.aciklama) : null),
    h('div', { class: 'bt-kart-alt' }, btn(T('Aç'), () => btAc(p.id), 'sm primary', 'edit'),
      btn('', ev => btPaketMenu(ev.currentTarget, p), 'sm ghost icon', 'more', { title: T('Diğer') })));
  btDoldur($('#content'), h('div', { class: 'stack' },
    h('div', { class: 'card bt-giris' }, btArt('bot_giris', 'dron_hosgeldin', 'bt-giris-art'),
      h('div', null, h('h2', null, icon('bot'), T('Botlar')),
        h('p', { class: 'desc' }, T('Bot paketi oluştur, bir dünyaya ata: o dünyada oynarken botlar gerçek oyuncular gibi haritalarda olur. Kadro bir kez üretilir; her girişte aynı botlarla karşılaşırsın, onlar da sen yokken bile ilerler.')),
        h('div', { class: 'row wrap' }, btn(T('Yeni bot paketi'), () => btSihirbaz(), 'primary', 'plus')))),
    h('div', { class: 'bt-izgara' }, r.liste.map(kart), h('button', { class: 'bt-kart yeni', onclick: () => btSihirbaz() }, icon('plus'), h('span', null, T('Yeni bot paketi'))))));
}

function btPaketMenu(anchor, p) {
  popMenu(anchor, [
    { label: T('Aç'), ic: 'edit', fn: () => btAc(p.id) },
    { label: T('Dünyaya ata'), ic: 'globe', fn: () => btAtaMenu(anchor, p) },
    { label: T('Yeniden adlandır'), ic: 'edit', fn: async () => {
      const ad = await promptBox(T('Yeniden adlandır'), T('Paketin adı'), p.ad); if (ad == null) return;
      if (await act(() => api('/api/bot/guncelle', { id: p.id, ad }), T('Kaydedildi.'))) renderBotlar(); } },
    '-',
    { label: T('Sil'), ic: 'trash', danger: true, fn: async () => {
      if (!await confirmBox(T('"{0}" silinsin mi?', p.ad), T('Paket ve botların ilerlemesi silinir (save/botlar/_silinenler klasöründe saklanır).'), { ok: T('Sil'), danger: true })) return;
      const x = await act(() => api('/api/bot/sil', { id: p.id }), T('Bot paketi silindi.')); if (x) { BT.liste = x; if (BT.pid === p.id) BT.pid = null; renderBotlar(); } } },
  ]);
}

function btAtaMenu(anchor, p) {
  const items = BT.liste.dunyalar.map(w => ({ label: w.ad + (p.dunya === w.id ? '  ✓' : ''), ic: p.dunya === w.id ? 'check' : 'globe',
    fn: () => btAta(p, w.id) }));
  items.push('-', { label: T('Atamayı kaldır'), ic: 'x', fn: () => btAta(p, null), disabled: !p.dunya });
  popMenu(anchor, items);
}
async function btAta(p, did) {
  const eski = did && BT.liste.liste.find(x => x.dunya === did && x.id !== p.id);
  if (eski && !await confirmBox(T('Dünyanın paketi değişsin mi?'), T('"{0}" dünyasında şu an "{1}" paketi var; o paket boşa çıkar.', btDunyaAd(did), eski.ad))) return;
  const x = await act(() => api('/api/bot/ata', { id: p.id, dunya: did }), did ? T('"{0}" artık "{1}" dünyasında.', p.ad, btDunyaAd(did)) : T('Atama kaldırıldı.'));
  if (x) { BT.liste = x; renderBotlar(); }
}

// ================================================================== SİHİRBAZ
function btSihirbaz() {
  const r = BT.liste;
  const w = { ad: '', aciklama: '', dunya: (r.dunyalar.find(d => !r.liste.some(p => p.dunya === d.id)) || r.dunyalar[0] || {}).id || null, kip: 'normal',
    gelisim: 'progressive', adet: 80, dil: 'karisik', ad_dili: 'karisik', firma_dagilimi: [1, 1, 1], ayarlar: { jumpstart_saat: 60, basit_guc: 1, basit_dost: 0.5,
      basit_haritalar: { 'X-1': 2, 'X-2': 2, 'X-3': 2, 'X-4': 2, '4-X': 3, 'X-5': 1, 'X-6': 1, 'X-7': 1, 'X-8': 1, '4-5': 2 } } };
  let adim = 0;
  const govde = h('div', { class: 'stack', style: { gap: '14px' } });
  const ayak = h('div', { class: 'row', style: { gap: '8px', justifyContent: 'flex-end', width: '100%' } });
  const m = modal({ title: T('Yeni bot paketi'), wide: true, body: govde, foot: ayak });
  const adimlar = [T('Ad ve dünya'), T('Kip'), T('Ayarlar')];
  function ciz() {
    const ust = h('div', { class: 'bt-adimlar' }, adimlar.map((a, i) => h('span', { class: i === adim ? 'on' : i < adim ? 'tamam' : '' }, h('b', null, i + 1), a)));
    btDoldur(govde, ust, [btAdim1, btAdim2, btAdim3][adim](w, ciz));
    btDoldur(ayak, btn(T('Vazgeç'), () => m.close(), 'ghost'), h('span', { class: 'spacer' }),
      adim ? btn(T('Geri'), () => { adim--; ciz(); }, 'ghost', 'arrowL') : null,
      adim < 2 ? btn(T('İleri'), () => {
        if (adim === 0 && !w.ad.trim()) return toast(T('Bot paketine bir ad ver.'), 'err');
        adim++; ciz();
      }, 'primary') : btn(T('Oluştur'), async () => {
        const x = await act(() => api('/api/bot/olustur', w), T('Bot paketi oluşturuldu: {0}', w.ad.trim()));
        if (!x) return;
        m.close(); BT.liste = x; btAc(x.yeni, w.kip === 'gelismis' ? 'gelismis' : 'kadro');
      }, 'primary', 'check'));
  }
  ciz();
}

function btAdim1(w) {
  const r = BT.liste;
  const ad = h('input', { class: 'input', value: w.ad, placeholder: T('Örn. Kalabalık Sunucu, Avcılar'), maxlength: 40, oninput: e => { w.ad = e.target.value; } });
  const acik = h('textarea', { class: 'input', rows: 2, maxlength: 240, placeholder: T('Bu paket nasıl bir sunucu? (isteğe bağlı)'), oninput: e => { w.aciklama = e.target.value; } }, w.aciklama);
  const dunya = h('select', { class: 'input', onchange: e => { w.dunya = e.target.value || null; } },
    r.dunyalar.map(d => {
      const p = r.liste.find(x => x.dunya === d.id);
      return h('option', { value: d.id, selected: w.dunya === d.id }, d.ad + (p ? ' — ' + T('şu an: {0}', p.ad) : ''));
    }), h('option', { value: '', selected: !w.dunya }, T('Şimdilik atama')));
  return h('div', { class: 'stack', style: { gap: '14px' } }, field(T('Ad'), ad), field(T('Açıklama'), acik),
    field(T('Çalışacağı dünya'), dunya, h('div', { class: 'small muted' }, T('Oyuncu bu dünyada oyuna girince paket devreye girer. Bir dünyada tek paket olur.'))));
}

function btAdim2(w, ciz) {
  const kart = k => h('button', { type: 'button', class: 'bt-kip' + (w.kip === k ? ' on' : ''), onclick: () => { w.kip = k; ciz(); } },
    btArt('bot_kip_' + k, 'dron_editor', 'bt-kip-art'), h('b', null, icon(BT_KIPLER[k].ic), T(BT_KIPLER[k].ad)), h('div', { class: 'small' }, T(BT_KIPLER[k].ozet)));
  return h('div', { class: 'stack', style: { gap: '12px' } }, h('div', { class: 'bt-kipler' }, ['basit', 'normal', 'gelismis'].map(kart)),
    w.kip === 'gelismis' ? btLlmUyari(true) : null);
}

function btLlmUyari(sihirbaz = false) {
  return h('div', { class: 'alert uyari' }, icon('alert'), h('div', null,
    h('b', null, T('Gelişmiş kip bilgisayarını çok zorlayabilir.')),
    h('div', null, T('Botların sohbeti ve kararları bilgisayarında çalışan Qwen3 4B (Q4_K_M) dil modeliyle verilir: yaklaşık 2,5 GB indirme, 4 GB boş bellek ve güçlü bir işlemci ya da ekran kartı ister. Zayıf bilgisayarlarda oyun yavaşlayabilir.')),
    h('div', { style: { marginTop: '6px' } }, T('Bilgisayarın kaldırmıyorsa Normal kip de çok gelişmiş bir bot deneyimi verir: botlar yine kişiliklerine göre karar verir, gelişir, klan kurar ve kalıplarla sohbet eder.')),
    sihirbaz ? h('div', { class: 'small muted', style: { marginTop: '6px' } }, T('Modeli paket oluşturulduktan sonra Gelişmiş sekmesinden kurup test edeceksin.')) : null));
}

function btSayi(deger, onchange, { min = 0, max = 999, step = 1, cls = 'num' } = {}) {
  return h('input', { class: 'input ' + cls, type: 'number', value: deger, min, max, step, onchange: e => {
    let v = Number(e.target.value); if (!isFinite(v)) v = min; v = Math.max(min, Math.min(max, v)); e.target.value = v; onchange(v); } });
}
function btKaydirac(deger, onchange, { min, max, step, fmt = v => v }) {
  const etiket = h('span', { class: 'bt-deger' }, fmt(deger));
  // dolgu (panel.css: --p) değerle birlikte: parıltı tutamağı izler
  const boya = el => el.style.setProperty('--p', (100 * (Number(el.value) - min) / ((max - min) || 1)) + '%');
  const r = h('input', { type: 'range', min, max, step, value: deger, class: 'bt-range',
    oninput: e => { etiket.textContent = fmt(Number(e.target.value)); boya(e.target); }, onchange: e => onchange(Number(e.target.value)) });
  boya(r);
  return h('div', { class: 'row', style: { gap: '10px' } }, r, etiket);
}
function btSeg(secenekler, deger, onchange) {
  // seçim hemen görünür (yeniden çizim beklemez: Kadro'da yalnız Uygula'dan sonra görünüyordu)
  const el = h('div', { class: 'seg' }, secenekler.map(([v, ad]) => h('button', { type: 'button', class: v === deger ? 'on' : '', onclick: e => {
    el.querySelectorAll('button').forEach(b => b.classList.toggle('on', b === e.currentTarget)); onchange(v);
  } }, ad)));
  return el;
}
// adların ve sohbetin dili (bot/diller/<kod>.json); dil adları kendi dillerinde
const BT_DILLER = [['tr', 'Türkçe'], ['en', 'English'], ['de', 'Deutsch'], ['es', 'Español'], ['fr', 'Français'], ['pl', 'Polski'],
  ['pt', 'Português'], ['ru', 'Русский']];
function btDilSec(deger, onchange, karisikAd, kilitli) {
  return h('select', { class: 'input bt-dil', disabled: !!kilitli, onchange: e => onchange(e.target.value) },
    [['karisik', karisikAd]].concat(BT_DILLER).map(([v, ad]) => h('option', { value: v, selected: v === deger }, ad)));
}
function btSohbetDili(kip, deger, onchange) {
  return kip === 'gelismis' ? btDilSec('en', () => {}, T('Her bot adının dilinde'), true) : btDilSec(deger, onchange, T('Her bot adının dilinde'));
}
function btDagilim(f, onchange) {
  return h('div', { class: 'row bt-dagilim', style: { gap: '8px' } }, btFirma.map((x, i) => h('label', { class: 'row', style: { gap: '4px' } },
    badge(x, x.toLowerCase()), btSayi(f[i], v => { f[i] = v; onchange(f); }, { min: 0, max: 100 }))));
}

function btAdim3(w, ciz) {
  if (w.kip === 'basit') return btBasitAyar(w.ayarlar, () => ciz(), true);
  return h('div', { class: 'stack', style: { gap: '14px' } },
    field(T('Toplam bot'), btKaydirac(w.adet, v => { w.adet = v; }, { min: 5, max: 3000, step: 5 }),
      h('div', { class: 'small muted' }, T('Aynı anda hepsi çevrimiçi olmaz: her botun kendi oyun saatleri var. Yüzlerce bot sorun değil; haritanda gemi olarak görünenler sınırlı.'))),
    field(T('Firma dağılımı (oran)'), btDagilim(w.firma_dagilimi, f => { w.firma_dagilimi = f; })),
    field(T('Gelişim'), btSeg([['progressive', 'Progressive'], ['jumpstart', 'Jumpstart']], w.gelisim, v => { w.gelisim = v; ciz(); }),
      h('div', { class: 'small muted' }, w.gelisim === 'progressive'
        ? T('Herkes oyunun başında olduğu gibi 1. seviyede, Phoenix ile kendi üssünde başlar ve gerçek oyuncu gibi gelişir.')
        : T('Kadro gerçekçi bir dağılımla başlar: çok acemi, çok orta seviye, az güçlü oyuncu. Donanımları, paraları ve seviyeleri tutarlı.'))),
    w.gelisim === 'jumpstart' ? field(T('Ortalama oyun süresi (saat)'), btKaydirac(w.ayarlar.jumpstart_saat, v => { w.ayarlar.jumpstart_saat = v; }, { min: 5, max: 500, step: 5 })) : null,
    field(T('Adların dili'), btDilSec(w.ad_dili, v => { w.ad_dili = v; }, T('Karışık')),
      h('div', { class: 'small muted' }, T('Botların kullanıcı adları bu dilin oyuncularına benzer.'))),
    field(T('Sohbet dili'), btSohbetDili(w.kip, w.dil, v => { w.dil = v; }),
      h('div', { class: 'small muted' }, w.kip === 'gelismis' ? T('Gelişmiş kipte botlar yalnız İngilizce konuşur (dil modeli öteki dillerde zayıf).')
        : T('Botların sohbette kullandığı dil. "Her bot adının dilinde" seçilirse adı Almanca olan Almanca konuşur.'))));
}

function btBasitAyar(a, ciz, sihirbaz = false, kaydet = null) {
  const top = () => Object.entries(a.basit_haritalar).reduce((s, [k, v]) => s + v * (k === '4-X' ? 4 : ['4-5'].includes(k) ? 1 : 3), 0);
  const toplam = h('b', null, top());
  const ust = h('div', { class: 'bt-siniflar' }, (BT.liste?.siniflar || Object.keys(a.basit_haritalar)).map(s => h('label', { class: 'bt-sinif' },
    h('span', null, BT_SINIF_AD(s)), btSayi(a.basit_haritalar[s] ?? 0, v => { a.basit_haritalar[s] = v; toplam.textContent = top(); kaydet && kaydet(); }, { min: 0, max: 20 }))));
  return h('div', { class: 'stack', style: { gap: '14px' } },
    field(T('Harita başına bot'), ust, h('div', { class: 'small muted' }, T('Firma haritalarında her firmanın haritasına ayrı ayrı (X-3 = 1-3, 2-3, 3-3), ortak haritalara (4-1…4-5) bir kez. Toplam: '), toplam)),
    field(T('Güç oranı'), btKaydirac(a.basit_guc, v => { a.basit_guc = v; kaydet && kaydet(); }, { min: 0.3, max: 3, step: 0.1, fmt: v => '×' + v.toFixed(1) }),
      h('div', { class: 'small muted' }, T('Haritanın tipik oyuncusunun donanımına göre: 1 aynı, 2 iki kat güçlü, 0,5 zayıf.'))),
    field(T('Dost bot payı'), btKaydirac(a.basit_dost, v => { a.basit_dost = v; kaydet && kaydet(); }, { min: 0, max: 1, step: 0.05, fmt: v => '%' + Math.round(v * 100) }),
      h('div', { class: 'small muted' }, T('Firma haritasındaki botların ne kadarı haritanın firmasından (geri kalanı düşman).'))));
}

// ================================================================== EDİTÖR
const BT_SEKMELER = [
  ['genel', N('Genel'), 'sliders'], ['kadro', N('Kadro'), 'users'], ['davranis', N('Davranış'), 'target'], ['erisim', N('Erişimler'), 'shield'],
  ['sohbet', N('Sohbet'), 'chat'], ['basit', N('Basit kip'), 'bot'], ['gelismis', N('Gelişmiş kip'), 'brain'],
];

async function btEditor() {
  const d = await act(() => api('/api/bot?id=' + encodeURIComponent(BT.pid))); if (!d || S.page !== 'botlar') return;
  BT.d = d;
  const sekmeler = BT_SEKMELER.filter(([k]) => (k !== 'basit' || d.kip === 'basit') && (k !== 'gelismis' || d.kip === 'gelismis')
    && (d.kip !== 'basit' || !['davranis', 'sohbet'].includes(k)));
  if (!sekmeler.some(([k]) => k === BT.sekme)) BT.sekme = 'genel';
  btDoldur($('#content'), h('div', { class: 'stack' },
    h('div', { class: 'card bt-cubuk' }, btn('', () => { BT.pid = null; renderBotlar(); }, 'ghost icon', 'arrowL', { title: T('Bot paketleri') }),
      btArt('bot_kip_' + d.kip, 'dron_editor', 'bt-cubuk-art'),
      h('div', { class: 'bt-cubuk-ad' }, h('div', { class: 'row', style: { gap: '8px' } }, h('b', null, d.ad), badge(T(BT_KIPLER[d.kip].ad), 'orange'),
        d.dunya ? badge([icon('globe'), btDunyaAd(d.dunya)], 'info') : badge(T('Dünyaya atanmadı'), 'warn')),
        h('div', { class: 'muted small ellipsis' }, T('{0} bot', d.adet) + (d.seviye_ort != null ? ' · ' + T('ortalama seviye {0}', d.seviye_ort) : ''))),
      h('span', { class: 'spacer' }), h('span', { class: 'de-kayit', id: 'bt-kayit' }),
      btn(T('Dünyaya ata'), ev => btAtaMenu(ev.currentTarget, d), 'sm', 'globe'),
      btn('', ev => btPaketMenu(ev.currentTarget, d), 'sm ghost icon', 'more', { title: T('Diğer') })),
    d.sunucu_bu_pakette ? h('div', { class: 'alert ' + (d.yeniden_gerekli ? 'uyari' : 'bilgi') }, icon(d.yeniden_gerekli ? 'alert' : 'info'),
      h('div', null, d.yeniden_gerekli ? T('Paket oyun açıldıktan sonra değişti: değişiklikler sunucu yeniden başlayınca geçerli olur.')
        : T('Bu paket şu an oyunda çalışıyor. Kadro listesi sunucunun dakikalık kaydından.')),
      d.yeniden_gerekli ? btn(T('Sunucuyu yeniden başlat'), () => act(() => api('/api/bot/sunucu_yeniden', {}), T('Sunucu yeniden başlatılıyor.')).then(() => setTimeout(btEditor, 1500)), 'sm orange', 'refresh') : null) : null,
    h('div', { class: 'seg bt-sekmeler' }, sekmeler.map(([k, ad, ic]) => h('button', { type: 'button', class: BT.sekme === k ? 'on' : '',
      onclick: () => { BT.sekme = k; btEditor(); } }, icon(ic), T(ad)))),
    h('div', { id: 'bt-alan' }, ({ genel: btGenel, kadro: btKadro, davranis: btDavranis, erisim: btErisim, sohbet: btSohbet, basit: btBasit, gelismis: btGelismis })[BT.sekme](d))));
}

function btKayit(durum) {
  const el = $('#bt-kayit'); if (!el) return;
  el.className = 'de-kayit ' + durum;
  btDoldur(el, ...(durum === 'kaydediliyor' ? [h('span', { class: 'spin' }), T('Kaydediliyor…')] : durum === 'kaydedildi' ? [icon('check'), T('Kaydedildi')] : []));
}
// değişiklik: 450 ms bekleyip tek istekte (ayarlar birleştirilir)
function btYama(alanlar) {
  for (const [k, v] of Object.entries(alanlar)) {
    if (k === 'ayarlar') BT.bekleyen.ayarlar = Object.assign(BT.bekleyen.ayarlar || {}, v);
    else BT.bekleyen[k] = v;
  }
  btKayit('kaydediliyor');
  clearTimeout(BT.zam);
  BT.zam = setTimeout(async () => {
    const govde = Object.assign({ id: BT.pid }, BT.bekleyen); BT.bekleyen = {};
    const x = await act(() => api('/api/bot/guncelle', govde));
    if (!x) return btKayit('');
    const kip = BT.d.kip;
    BT.d = x; btKayit('kaydedildi');
    if (govde.kip && govde.kip !== kip || govde.ad) btEditor();
  }, 450);
}
const btA = (k, v) => btYama({ ayarlar: { [k]: v } });

function btSatir(ad, aciklama, ctl) {
  return h('div', { class: 'set-row' }, h('div', null, h('div', { class: 'name' }, ad), aciklama ? h('div', { class: 'help' }, aciklama) : null), h('div', { class: 'ctl' }, ctl));
}
function btAnahtar(deger, onchange) {
  return h('label', { class: 'switch' }, h('input', { type: 'checkbox', checked: !!deger, onchange: e => onchange(e.target.checked) }), h('span'));
}

// ------------------------------------------------------------------ Genel
function btGenel(d) {
  const a = d.ayarlar;
  const ad = h('input', { class: 'input', value: d.ad, maxlength: 40, onchange: e => btYama({ ad: e.target.value }) });
  const acik = h('input', { class: 'input', value: d.aciklama || '', maxlength: 240, placeholder: T('Açıklama yok.'), onchange: e => btYama({ aciklama: e.target.value }) });
  const kipSec = async v => {
    if (v === d.kip) return;
    if (v === 'gelismis' && !await confirmBox(T('Gelişmiş kipe geçilsin mi?'), btLlmUyari(), { ok: T('Gelişmiş kipe geç') })) return;
    if ((v === 'basit') !== (d.kip === 'basit') && !await confirmBox(T('Kip değişsin mi?'),
      T('Basit kipte kadro haritalara dağıtılır ve sayısı harita ayarlarından gelir; Normal ve Gelişmiş kipte botlar kendi başına gelişir. İlerleme korunur.'))) return;
    btYama({ kip: v });
  };
  const fg = a.firma_guc || [1, 1, 1];
  return h('div', { class: 'stack' },
    h('div', { class: 'card' }, h('h2', null, icon('edit'), T('Paket')),
      btSatir(T('Ad'), null, ad), btSatir(T('Açıklama'), null, acik),
      btSatir(T('Kip'), T(BT_KIPLER[d.kip].ozet), btSeg(['basit', 'normal', 'gelismis'].map(k => [k, T(BT_KIPLER[k].ad)]), d.kip, kipSec)),
      d.kip !== 'basit' ? btSatir(T('Gelişim'), d.gelisim === 'jumpstart' ? T('Kadro gerçekçi bir dağılımla başlar (ilk açılışta).') : T('Herkes 1. seviyede, kendi üssünde başlar.'),
        btSeg([['progressive', 'Progressive'], ['jumpstart', 'Jumpstart']], d.gelisim, v => btYama({ gelisim: v }))) : null,
      d.kip !== 'basit' && d.gelisim === 'jumpstart' ? btSatir(T('Ortalama oyun süresi (saat)'), T('Jumpstart dağılımının ortası: birkaç bot bunun katlarıyla, çoğu altında başlar.'),
        btSayi(a.jumpstart_saat, v => btA('jumpstart_saat', v), { min: 1, max: 2000 })) : null),
    d.kip !== 'basit' ? h('div', { class: 'card' }, h('h2', null, icon('clock'), T('Zaman ve gelişim')),
      btSatir(T('İlerleme hızı'), T('Kazançların çarpanı: 1 gerçek oyuncu temposu.'), btKaydirac(a.hiz, v => btA('hiz', v), { min: 0.1, max: 10, step: 0.1, fmt: v => '×' + v.toFixed(1) })),
      btSatir(T('Çevrimiçi olma eğilimi'), T('Botların oyun saatlerine göre çevrimiçi olma isteği; yüksekse aynı anda daha çok bot.'),
        btKaydirac(a.cevrimici_oran, v => btA('cevrimici_oran', v), { min: 0.05, max: 2, step: 0.05, fmt: v => '%' + Math.round(v * 100) })),
      btSatir(T('Aynı anda en çok çevrimiçi'), T('0: sınırsız.'), btSayi(a.en_cok_cevrimici, v => btA('en_cok_cevrimici', v), { min: 0, max: 3000 })),
      btSatir(T('Sen yokken ilerleme (saat)'), T('Oyuna dönünce geçen sürenin en çok bu kadarı benzetilir. 0: botlar yalnız sen oynarken ilerler.'),
        btSayi(a.telafi_saat, v => btA('telafi_saat', v), { min: 0, max: 48 })),
      d.gelisim !== 'jumpstart' ? btSatir(T('Yeni pilot kaydı (saniye)'), T('Progressive: her firmaya ortalama bu kadar saniyede bir yeni pilot kayıt olup oyuna başlar (yeni açılmış bir sunucu gibi; hepsi aynı anda doğmaz). 0: hepsi baştan kayıtlı.'),
        btSayi(a.kayit_sn ?? 15, v => btA('kayit_sn', v), { min: 0, max: 300 })) : null,
      btSatir(T('Firmaların gücü'), T('Firmanın botlarının gelişim çarpanı (1 eşit).'), h('div', { class: 'row', style: { gap: '8px' } }, btFirma.map((x, i) =>
        h('label', { class: 'row', style: { gap: '4px' } }, badge(x, x.toLowerCase()), btSayi(fg[i], v => { fg[i] = v; btA('firma_guc', fg); }, { min: 0.2, max: 5, step: 0.1 })))))) : null,
    btOyunAyariKart(d),
    h('div', { class: 'card' }, h('h2', null, icon('trash'), T('İlerleme')),
      btSatir(T('İlerlemeyi sıfırla'), T('Botların seviyesi, parası, donanımı, klanları ve ilişkileri silinir; adlar ve kişilikler kalır.'),
        btn(T('Sıfırla'), async () => {
          if (!await confirmBox(T('İlerleme sıfırlansın mı?'), T('Botlar baştan başlar (Jumpstart\'ta yeniden dağıtılır).'), { ok: T('Sıfırla'), danger: true })) return;
          const x = await act(() => api('/api/bot/sifirla', { id: d.id }), T('İlerleme sıfırlandı.')); if (x) { BT.d = x; btEditor(); }
        }, 'sm danger', 'trash'))));
}

// ------------------------------------------------------------------ Kadro
function btKadro(d) {
  const ark = {};
  d.kadro.forEach(b => { ark[b.arketip] = (ark[b.arketip] || 0) + 1; });
  const f = d.firma_dagilimi.slice();
  let adet = d.adet, dil = d.dil || 'karisik', adDili = d.ad_dili || dil;
  const kontrol = d.kip === 'basit' ? h('div', { class: 'alert bilgi' }, icon('info'), h('div', null, T('Basit kipte bot sayısı Basit kip sekmesindeki harita sayılarından gelir.')))
    : h('div', { class: 'stack', style: { gap: '10px' } },
      btSatir(T('Bot sayısı'), T('Artırınca yeni botlar eklenir, azaltınca sondakiler çıkar; var olanlar değişmez.'), btSayi(adet, v => { adet = v; }, { min: 1, max: 3000 })),
      btSatir(T('Firma dağılımı (oran)'), T('Yeni eklenen botlara ve baştan üretime uygulanır.'), btDagilim(f, x => { f.splice(0, 3, ...x); })),
      btSatir(T('Adların dili'), T('Yeni eklenen botlara ve baştan üretime uygulanır; var olan botların adı değişmez.'),
        btDilSec(adDili, v => { adDili = v; }, T('Karışık'))),
      btSatir(T('Sohbet dili'), d.kip === 'gelismis' ? T('Gelişmiş kipte botlar yalnız İngilizce konuşur (dil modeli öteki dillerde zayıf).')
        : T('Uygula ile bütün botlar bu dilde konuşur.'), btSohbetDili(d.kip, dil, v => { dil = v; })),
      h('div', { class: 'row wrap', style: { justifyContent: 'flex-end' } },
        btn(T('Uygula'), async () => { const x = await act(() => api('/api/bot/kadro', { id: d.id, adet, firma_dagilimi: f, dil, ad_dili: adDili }), T('Kadro güncellendi.')); if (x) { BT.d = x; btEditor(); } }, 'sm primary', 'check'),
        btn(T('Baştan üret'), async () => {
          if (!await confirmBox(T('Kadro baştan üretilsin mi?'), T('Bütün botlar yeni adlar ve kişiliklerle yeniden üretilir, ilerlemeleri silinir.'), { ok: T('Baştan üret'), danger: true })) return;
          const x = await act(() => api('/api/bot/kadro', { id: d.id, adet, firma_dagilimi: f, dil, ad_dili: adDili, yeniden: true }), T('Kadro yeniden üretildi.')); if (x) { BT.d = x; btEditor(); }
        }, 'sm danger', 'refresh')));
  const satir = b => h('tr', null,
    h('td', null, h('a', { href: '#', class: 'bt-ad', title: T('Yeniden adlandır'), onclick: async e => {
      e.preventDefault();
      const ad = await promptBox(T('Botun adı'), T('3-20 karakter: harf, rakam, _ . -'), b.ad); if (ad == null) return;
      const x = await act(() => api('/api/bot/ad', { id: d.id, no: b.no, ad }), T('Kaydedildi.')); if (x) { BT.d = x; btEditor(); }
    } }, b.ad)),
    h('td', null, badge(btFirma[b.firma - 1], btFirma[b.firma - 1].toLowerCase())),
    h('td', null, T(BT_ARKETIP[b.arketip] || b.arketip), h('div', { class: 'small muted' }, btOzellikOzeti(b.ozellik))),
    h('td', { class: 'num' }, b.seviye),
    h('td', null, String(b.gemi || '').replace('ship_', '').replace(/^\w/, c => c.toUpperCase())),
    h('td', null, b.harita || '—'),
    h('td', null, b.hedef ? T(BT_HEDEF[b.hedef] || b.hedef) : h('span', { class: 'muted' }, '—')),
    h('td', { class: 'num small' }, fmtN(b.istat.npc || 0) + ' / ' + fmtN(b.istat.oyuncu || 0) + ' / ' + fmtN(b.istat.olum || 0)));
  return h('div', { class: 'stack' },
    h('div', { class: 'card' }, h('h2', null, icon('users'), T('Kadro')),
      h('p', { class: 'desc' }, T('Kişilikler kadro üretilirken bir kez belirlendi: her botun arketipi, özellikleri (saldırganlık, sabır, sosyallik …), oyun saatleri ve yazım üslubu kendine.')),
      h('div', { class: 'row wrap', style: { gap: '6px', marginBottom: '12px' } }, Object.entries(ark).sort((a, b) => b[1] - a[1]).map(([k, n]) => badge(T(BT_ARKETIP[k] || k) + ' ' + n, ''))),
      kontrol),
    h('div', { class: 'card' }, h('h2', null, icon('list'), T('Botlar')),
      h('p', { class: 'desc' }, d.durum_var ? T('Seviye, gemi, harita ve iş sunucunun son kaydından (oyun açıkken dakikada bir).') : T('Botlar henüz oynamadı: bu dünyada oyuna girince başlarlar.')),
      h('div', { class: 'bt-tablo' }, h('table', { class: 'table' }, h('thead', null, h('tr', null,
        [T('Ad'), T('Firma'), T('Kişilik'), T('Seviye'), T('Gemi'), T('Harita'), T('Ne yapıyor'), T('Uzaylı / oyuncu / ölüm')].map(x => h('th', null, x)))),
        h('tbody', null, d.kadro.map(satir))))));
}

function btOzellikOzeti(o) {
  const en = Object.entries(o || {}).sort((a, b) => b[1] - a[1]).slice(0, 2);
  const ad = { saldirganlik: N('saldırgan'), rekabet: N('rekabetçi'), sosyallik: N('sosyal'), sabir: N('sabırlı'), risk: N('riskçi'), sadakat: N('sadık'),
    yardimseverlik: N('yardımsever'), konuskanlik: N('konuşkan'), tutumluluk: N('tutumlu'), hirs: N('hırslı') };
  return en.map(([k]) => T(ad[k] || k)).join(', ');
}

// ------------------------------------------------------------------ Davranış, Erişimler, Sohbet
function btDavranis(d) {
  const a = d.ayarlar;
  return h('div', { class: 'card' }, h('h2', null, icon('target'), T('Davranış')),
    btSatir(T('PvP için en düşük seviye'), T('Bu seviyenin altındaki botlar PvP avına çıkmaz.'), btSayi(a.pvp_seviye, v => btA('pvp_seviye', v), { min: 1, max: 32 })),
    btSatir(T('Başka firmanın haritaları'), T('Botlar düşman firmaların haritalarına girebilir.'), btAnahtar(a.yabanci_harita, v => btA('yabanci_harita', v))),
    btSatir(T('Haritanda gemi olarak en çok'), T('Bulunduğun haritadaki botlardan en çok bu kadarı gemi olarak görünür; ötekiler arka planda oynar (performans).'),
      btSayi(a.somut_en_cok, v => btA('somut_en_cok', v), { min: 1, max: 150 })),
    btSatir(T('Kaç bota bir bot klanı'), T('Botların kurabileceği klan sayısı kadroya göre.'), btSayi(a.klan_basina, v => btA('klan_basina', v), { min: 3, max: 100 })),
    btSatir(T('Yardım çağrısına en çok'), T('Sohbetteki bir yardım çağrısına gelen en çok bot.'), btSayi(a.yardim_en_cok, v => btA('yardim_en_cok', v), { min: 0, max: 20 })));
}

function btErisim(d) {
  const iz = Object.assign({}, d.ayarlar.izinler);
  const izinler = (BT.liste?.izinler || Object.keys(BT_IZIN)).filter(k => d.kip !== 'basit' || ['pvp', 'oyuncuya_saldir'].includes(k));
  return h('div', { class: 'card' }, h('h2', null, icon('shield'), T('Erişimler')),
    h('p', { class: 'desc' }, T('Botların oyunun hangi bölümlerini kullanacağı. Kapatılan bölümü hiçbir bot kullanmaz.')),
    izinler.map(k => btSatir(T(BT_IZIN[k][0]), T(BT_IZIN[k][1]), btAnahtar(iz[k] !== false, v => { iz[k] = v; btA('izinler', { [k]: v }); }))));
}

function btSohbet(d) {
  const a = d.ayarlar;
  return h('div', { class: 'card' }, h('h2', null, icon('chat'), T('Sohbet')),
    btSatir(T('Sohbet'), T(BT_IZIN.sohbet[1]), btAnahtar(a.izinler.sohbet !== false, v => btA('izinler', { sohbet: v }))),
    btSatir(T('Kanal yoğunluğu'), T('Global ve firma sohbetinde dakikada en çok bot satırı (sohbet sele dönmesin).'),
      btKaydirac(a.sohbet_dk, v => btA('sohbet_dk', v), { min: 0, max: 30, step: 1, fmt: v => T('{0}/dk', v) })),
    h('div', { class: 'alert bilgi' }, icon('info'), h('div', null, d.kip === 'gelismis'
      ? T('Gelişmiş kipte botlar dil modeliyle konuşur; model yetişemezse kalıp cümlelere döner.')
      : T('Normal kipte botlar duruma ve kişiliklerine göre kalıp cümlelerle konuşur: selamlaşır, seviye atlayınca yazar, yardım çağrılarına ve fısıltına yanıt verir.'))));
}

function btBasit(d) {
  const a = JSON.parse(JSON.stringify(d.ayarlar));
  const kaydet = () => btYama({ ayarlar: { basit_haritalar: a.basit_haritalar, basit_guc: a.basit_guc, basit_dost: a.basit_dost } });
  return h('div', { class: 'card' }, h('h2', null, icon('bot'), T('Basit kip')),
    h('p', { class: 'desc' }, T('Botlar haritalara seviyelerine göre dağıtılır ve orada kalır: uzaylı keser, düşmansa seni görünce gücüne göre saldırır ya da kaçar, ölünce aynı haritada doğar.')),
    btBasitAyar(a, null, false, kaydet));
}

function btGelismis(d) {
  return typeof btLlmKart === 'function' ? btLlmKart(d) : h('div', { class: 'card' }, btLlmUyari());
}

// ------------------------------------------------------------------ Gelişmiş kip: dil modeli (llm_kurulum.py, /api/bot/llm)
function btLlmKart(d) {
  const kutu = h('div');
  const a = d.ayarlar;
  btLlmIzle(kutu);
  return h('div', { class: 'stack' },
    h('div', { class: 'card' }, h('h2', null, icon('brain'), T('Dil modeli')),
      h('div', { class: 'bt-llm' }, btArt('bot_llm', 'dron_ayarlar', 'bt-llm-art'), h('div', { class: 'stack', style: { gap: '10px' } }, btLlmUyari(), kutu))),
    h('div', { class: 'card' }, h('h2', null, icon('sliders'), T('Gelişmiş kip ayarları')),
      btSatir(T('Aynı anda düşünen bot'), T('Modelin paralel yuvaları: istekler toplu işlenir. Yüksekse daha çok bot aynı anda konuşur ama bilgisayar daha çok zorlanır.'),
        btSayi(a.llm_toplu, v => btA('llm_toplu', v), { min: 1, max: 16 })),
      btSatir(T('Sohbet modelle'), T('Kapalıysa botlar Normal kipteki gibi kalıplarla konuşur; model yalnız kararlarda kullanılır.'), btAnahtar(a.llm_sohbet, v => btA('llm_sohbet', v))),
      btSatir(T('Kararları gözden geçirme (dakika)'), T('Her bot bu kadar dakikada bir durumunu modele danışır (0: hiç). Kısa süre daha canlı ama daha ağır.'),
        btSayi(a.llm_karar_dk, v => btA('llm_karar_dk', v), { min: 0, max: 120 }))));
}

function btLlmIzle(kutu) {
  let imza = '';
  const ciz = s => { imza = JSON.stringify(s); btDoldur(kutu, btLlmKutu(s, ciz)); };
  api('/api/bot/llm').then(ciz).catch(e => btDoldur(kutu, h('div', { class: 'alert hata' }, icon('alert'), h('div', null, e.message))));
  const id = setInterval(async () => {
    if (!kutu.isConnected) return clearInterval(id);
    let s; try { s = await api('/api/bot/llm'); } catch (e) { return; }
    if (JSON.stringify(s) !== imza) ciz(s);
  }, 1000);
}

function btLlmKutu(s, ciz) {
  const cagir = (yol, msg) => act(() => api('/api/bot/llm/' + yol, {}), msg).then(x => { if (x) ciz(x); });
  const pct = s.toplam ? Math.floor(100 * s.alinan / s.toplam) : 0;
  const t = s.test || {};
  const az = s.bellek_gb != null && s.bellek_gb < s.en_az_bellek_gb;
  const donanim = h('div', { class: 'small muted' }, T('Bu bilgisayar: {0} GB bellek, {1} çekirdek.', s.bellek_gb ?? '?', s.cekirdek ?? '?'),
    az ? h('b', { style: { color: 'var(--warn)', marginLeft: '6px' } }, T('Önerilen en az {0} GB.', s.en_az_bellek_gb)) : null);
  if (!s.destekli) return h('div', { class: 'alert hata' }, icon('alert'), h('div', null, T('Bu bilgisayarın işlemcisi için hazır dil modeli sunucusu yok: Normal kipi kullan.')));
  const adim1 = s.calisiyor
    ? h('div', { class: 'dl-box' }, h('b', null, s.durum === 'kuruluyor' ? T('Kuruluyor…') : T('İndiriliyor: %{0}', pct)),
      h('div', { class: 'meter' }, h('div', { class: 'meter-bar' }, h('span', { style: { width: pct + '%' } }))),
      h('div', { class: 'small muted dl-info' }, [`${fmtBytes(s.alinan)} / ${fmtBytes(s.toplam)}`, s.hiz ? `${fmtBytes(s.hiz)}/${T('sn')}` : null,
        s.kalan_sn != null && s.hiz ? T('kalan {0}', fmtDur(s.kalan_sn)) : null, s.parca].filter(Boolean).join(' · ')),
      h('div', { class: 'row' }, btn(T('Durdur'), () => cagir('durdur', T('İndirme durduruluyor…')), 'ghost sm', 'stop')))
    : ['kurulu', 'hazir'].includes(s.durum)
      ? h('div', { class: 'bt-llm-adim' }, icon('check'), h('div', null, h('b', null, T('Kuruldu')), h('div', { class: 'small muted' }, s.model + ' · llama.cpp ' + s.surum)),
        btn(T('Kaldır'), async () => { if (await confirmBox(T('Dil modeli silinsin mi?'), T('İndirilen 2,5 GB silinir; Gelişmiş kip yeniden kurulana dek Normal kip gibi çalışır.'), { ok: T('Sil'), danger: true })) cagir('sil', T('Silindi.')); }, 'ghost sm', 'trash'))
      : h('div', { class: 'bt-llm-adim' }, icon('download'), h('div', null, h('b', null, s.durum === 'hata' ? T('Kurulamadı') : s.durum === 'durdu' ? T('İndirme durduruldu') : T('1. Dil modelini kur')),
        h('div', { class: 'small muted' }, s.durum === 'hata' ? s.hata : T('{0} indirilir (yarım kalırsa kaldığı yerden sürer).', fmtBytes(s.boyut))), donanim),
        btn(s.durum === 'hata' || s.durum === 'durdu' || s.yarim ? T('Sürdür') : T('İndir ve kur'), () => cagir('kur'), 'primary sm', 'download'));
  const kuruldu = ['kurulu', 'hazir'].includes(s.durum);
  const adim2 = h('div', { class: 'bt-llm-adim' }, icon(s.durum === 'hazir' ? 'check' : 'play'),
    h('div', null, h('b', null, s.durum === 'hazir' ? T('Kurulum tamamlandı: model çalışıyor') : T('2. Test et')),
      h('div', { class: 'small muted' }, t.durum === 'calisiyor' ? T('Model açılıyor ve kısa bir soru soruluyor (ilk açılış yarım dakikayı bulabilir)…')
        : t.durum === 'hata' ? t.hata : t.durum === 'ok' || s.son_test ? T('Açılış {0} sn, yanıt {1} sn: "{2}"', (t.acilis_sn ?? s.son_test?.acilis_sn), (t.sure_sn ?? s.son_test?.sure_sn), (t.yanit ?? s.son_test?.yanit ?? ''))
        : T('Model bir kez açılıp kısa bir soruya yanıt verir; yanıt gelirse kurulum tamamdır.'))),
    t.durum === 'calisiyor' ? h('span', { class: 'spin' }) : btn(T('Test et'), () => cagir('test'), (kuruldu && s.durum !== 'hazir' ? 'primary' : 'ghost') + ' sm', 'play', { disabled: !kuruldu }));
  return h('div', { class: 'stack', style: { gap: '4px' } }, adim1, adim2,
    s.durum === 'hazir' ? h('div', { class: 'alert bilgi' }, icon('info'), h('div', null, T('Oyun açılınca model de açılır; botların sohbeti ve kararları onunla verilir. Model yetişemezse botlar Normal kipteki gibi davranır.'))) : null);
}

// ------------------------------------------------------------------ botların oyun ayarı profili (bot/oyun_ayari.py)
function btOyunAyariKart(d) {
  const oa = JSON.parse(JSON.stringify(d.ayarlar.oyun_ayari || { profil: 'standart', degerler: {} }));
  const bilgi = BT.liste?.oyun_ayarlari || { hazir: [], alanlar: [] };
  const secenekler = [['standart', T('Standart (oyunun kendi değerleri)')], ['oyuncu', T('Benim oyun ayarlarım')]]
    .concat(bilgi.hazir.map(x => [x.id, T(x.ad)]), [['ozel', T('Özel')]]);
  const kaydet = () => btA('oyun_ayari', oa);
  const sec = h('select', { class: 'input', onchange: e => { oa.profil = e.target.value; kaydet(); btDoldur(ozel, ozelCiz()); aciklama.textContent = acikla(); } },
    secenekler.map(([v, ad]) => h('option', { value: v, selected: oa.profil === v }, ad)));
  const acikla = () => {
    const hz = bilgi.hazir.find(x => x.id === oa.profil);
    return hz ? T(hz.aciklama) : oa.profil === 'oyuncu' ? T('Botlar da Oyun Ayarları sayfasındaki çarpanlarla oynar (kolay ayarda onlar da hızlı gelişir).')
      : oa.profil === 'ozel' ? T('Aşağıdaki çarpanlar yalnız botlara uygulanır.') : T('Botlar oyunun kendi ödülleri ve uzaylılarıyla oynar; senin oyun ayarların onları etkilemez.');
  };
  const aciklama = h('div', { class: 'help' }, acikla());
  const ozelCiz = () => oa.profil !== 'ozel' ? null : bilgi.alanlar.map(a => btSatir(T(a.ad), T(a.aciklama),
    btKaydirac(oa.degerler[a.anahtar] ?? 1, v => { oa.degerler[a.anahtar] = v; kaydet(); }, { min: a.en_az, max: a.en_cok, step: 0.05, fmt: v => '×' + v.toFixed(2) })));
  const ozel = h('div', null, ozelCiz());
  return h('div', { class: 'card' }, h('h2', null, icon('sliders'), T('Oyun ayarları')),
    h('p', { class: 'desc' }, T('Botların ödül ve zorluk çarpanları senin oyun ayarlarından ayrı: kendine kolay ayar seçsen de botlar burada seçtiğinle gelişir.')),
    h('div', { class: 'set-row' }, h('div', null, h('div', { class: 'name' }, T('Profil')), aciklama), h('div', { class: 'ctl' }, sec)), ozel);
}
