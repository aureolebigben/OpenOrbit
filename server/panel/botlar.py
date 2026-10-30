"""Botlar sayfasının deposu (panel.py'nin /api/bot… uçları; belgeler/BOTLAR.md).

Bot paketi save/botlar/<kimlik>.json:
  {surum, ad, aciklama, dunya, kip ('basit' | 'normal' | 'gelismis'), gelisim ('progressive' | 'jumpstart'), tohum, dil,
   firma_dagilimi [MMO, EIC, VRU], ayarlar {...}, kadro [{no, ad, firma, kisilik}], olusturma, guncelleme}
Paketin ilerlemesi save/botlar/<kimlik>/durum.json'da (oyun sunucusu yazar: bot/yonetici.py); paket silinince ikisi de
_silinenler'e taşınır. Bir dünyaya en çok bir paket atanır (OYNA o dünyanın paketiyle açar: DO_BOT).
Kadro oluşturulurken bir kez üretilir (bot/kisilik.kadro_uret, tohumlu): her girişte aynı botlar.
"""
import copy, datetime, json, os, random, re, shutil, threading

import yollar as YOL
import ad_kaydi as AK
from dil import t as _

SURUM = 1
KIPLER = ('basit', 'normal', 'gelismis')
GELISIMLER = ('progressive', 'jumpstart')
from bot.dil_verisi import KODLAR as _KODLAR
DILLER = ('karisik',) + _KODLAR          # adların ve sohbetin dili (bot/diller/<kod>.json); karışık: her bot adının dilinde
AD_UZUNLUK, ACIKLAMA_UZUNLUK = 40, 240
ADET_EN_AZ, ADET_EN_COK = 1, 3000
_KILIT = threading.Lock()

# ayar -> (tür, en az, en çok, varsayılan); bot/yonetici.VARSAYILAN ile aynı anahtarlar
AYARLAR = {
    'hiz': ('sayi', 0.1, 20.0, 1.0),
    'cevrimici_oran': ('sayi', 0.05, 2.0, 0.6),
    'en_cok_cevrimici': ('tam', 0, 3000, 0),
    'telafi_saat': ('tam', 0, 48, 4),
    'telafi_oran': ('sayi', 0.0, 1.0, 0.35),
    'kayit_sn': ('tam', 0, 300, 15),
    'jumpstart_saat': ('tam', 1, 2000, 60),
    'pvp_seviye': ('tam', 1, 32, 6),
    'yabanci_harita': ('bool', None, None, True),
    'sohbet_dk': ('tam', 0, 60, 6),
    'yardim_en_cok': ('tam', 0, 20, 3),
    'somut_en_cok': ('tam', 1, 150, 40),
    'klan_basina': ('tam', 3, 100, 12),
    'basit_guc': ('sayi', 0.3, 3.0, 1.0),
    'basit_dost': ('sayi', 0.0, 1.0, 0.5),
    'llm_toplu': ('tam', 1, 16, 4),
    'llm_sohbet': ('bool', None, None, True),
    'llm_karar_dk': ('tam', 0, 120, 10),
}
IZINLER = ('magaza', 'gorev', 'pvp', 'oyuncuya_saldir', 'sohbet', 'klan', 'klan_kur', 'arkadas', 'grup', 'muzayede', 'yardim', 'kutu_calma', 'kargo', 'roket', 'ozel_cephane', 'ekstra', 'mayin', 'lab', 'skylab', 'teknoloji', 'ganimet', 'assembly', 'kapi', 'etkinlik', 'modlar', 'klan_diplomasi')
BASIT_SINIFLAR = ('X-1', 'X-2', 'X-3', 'X-4', '4-X', 'X-5', 'X-6', 'X-7', 'X-8', '4-5')


class BotHatasi(ValueError):
    """Kullanıcıya gösterilen hata (panel.py 400 döner)."""


def klasor():
    return os.path.join(YOL.SAVE, 'botlar')


def _yol(pid):
    if not isinstance(pid, str) or not re.fullmatch(r'[a-z0-9_]{1,40}', pid):
        raise BotHatasi(_('Bot paketi bulunamadı.'))
    return os.path.join(klasor(), pid + '.json')


def durum_yolu(pid):
    _yol(pid)                                         # kimlik denetimi: '..' gibi bir kimlik paket klasörünün dışına çıkamaz
    return os.path.join(klasor(), pid, 'durum.json')


def dosya_yolu(pid):
    """Sunucunun paket dosyası (DO_BOT) ya da None."""
    if not pid:
        return None
    try:
        p = _yol(pid)
    except BotHatasi:
        return None
    return p if os.path.isfile(p) else None


def _oku_dosya(p):
    try:
        with open(p, encoding='utf8') as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def oku(pid):
    d = _oku_dosya(_yol(pid))
    if d is None:
        raise BotHatasi(_('Bot paketi bulunamadı.'))
    return d


def _kaydet(pid, d):
    os.makedirs(klasor(), exist_ok=True)
    d['surum'] = SURUM
    d['guncelleme'] = _simdi()
    p = _yol(pid)
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf8') as fh:
        json.dump(d, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def _simdi():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def var(pid):
    return dosya_yolu(pid) is not None


# ------------------------------------------------------------------ doğrulama
def ayarlari_temizle(a, eski=None):
    """Panelin gönderdiği ayarlar -> geçerli değerler (bilinmeyen anahtarlar atılır, sayılar sınırlara çekilir)."""
    out = copy.deepcopy(eski) if eski else {}
    a = a if isinstance(a, dict) else {}
    for k, (tur, lo, hi, vars_) in AYARLAR.items():
        if k not in a:
            out.setdefault(k, vars_)
            continue
        v = a[k]
        try:
            if tur == 'bool':
                v = bool(v)
            elif tur == 'tam':
                v = max(lo, min(hi, int(v)))
            else:
                v = round(max(lo, min(hi, float(v))), 3)
        except (TypeError, ValueError):
            v = out.get(k, vars_)
        out[k] = v
    iz = dict(out.get('izinler') or {})
    for k in IZINLER:
        if isinstance(a.get('izinler'), dict) and k in a['izinler']:
            iz[k] = bool(a['izinler'][k])
        iz.setdefault(k, True)
    out['izinler'] = iz
    fg = a.get('firma_guc', out.get('firma_guc', [1.0, 1.0, 1.0]))
    try:
        out['firma_guc'] = [round(max(0.2, min(5.0, float(x))), 2) for x in list(fg)[:3]] + [1.0] * (3 - len(list(fg)[:3]))
    except (TypeError, ValueError):
        out['firma_guc'] = [1.0, 1.0, 1.0]
    oa = a.get('oyun_ayari', out.get('oyun_ayari'))            # botların oyun ayarı profili (bot/oyun_ayari.py)
    from bot import oyun_ayari as OA
    import ayar as AY
    if not isinstance(oa, dict) or oa.get('profil') not in OA.PROFILLER:
        oa = {'profil': 'standart', 'degerler': {}}
    deg = {}
    for k, v in (oa.get('degerler') or {}).items():
        s = AY.BY_KEY.get(k)
        if k in OA.ALANLAR and s:
            try:
                deg[k] = round(max(s.get('min', 0.0), min(s.get('max', 50.0), float(v))), 3)
            except (TypeError, ValueError):
                pass
    out['oyun_ayari'] = {'profil': oa['profil'], 'degerler': deg}
    bh = a.get('basit_haritalar', out.get('basit_haritalar'))
    if isinstance(bh, dict):
        out['basit_haritalar'] = {s: max(0, min(20, int(bh.get(s, 0) or 0))) for s in BASIT_SINIFLAR}
    else:
        from bot import basit
        out['basit_haritalar'] = dict(basit.VARSAYILAN_HARITALAR)
    return out


def _ad_temizle(ad):
    ad = ' '.join(str(ad or '').split())[:AD_UZUNLUK]
    if not ad:
        raise BotHatasi(_('Bot paketine bir ad ver.'))
    return ad


def _yeni_kimlik(ad):
    tr = str.maketrans('çğıöşüâîûÇĞİÖŞÜ', 'cgiosuaiuCGIOSU')
    k = re.sub(r'[^a-z0-9]+', '_', ad.translate(tr).lower()).strip('_')[:30] or 'botlar'
    pid, n = k, 2
    while os.path.exists(_yol(pid)):
        pid, n = '%s_%d' % (k, n), n + 1
    return pid


def _dagilim(fd):
    try:
        fd = [max(0, int(x)) for x in list(fd)[:3]]
    except (TypeError, ValueError):
        fd = [1, 1, 1]
    return fd if len(fd) == 3 and sum(fd) > 0 else [1, 1, 1]


def kadro_uret(tohum, adet, dagilim, dil, mevcut=(), ad_dili=None):
    from bot import kisilik as KS
    return KS.kadro_uret(tohum, adet, firma_dagilimi=dagilim, dil=dil if dil in DILLER else 'karisik', mevcut=mevcut,
                         ad_dili=ad_dili if ad_dili in DILLER else None)


def ad_dili(d):
    """Paketin ad dili (eski paketlerde ad ve sohbet tek ayardı)."""
    return d.get('ad_dili') or d.get('dil') or 'karisik'


def sohbet_dili_uygula(d):
    """Sohbet dili değişti: var olan botlar da yeni dilde konuşur (karışık: her bot adının dilinde). Adlar değişmez."""
    for x in d['kadro']:
        k = x['kisilik']
        k.setdefault('ad_dili', k.get('dil'))
        k['dil'] = d['dil'] if d['dil'] in DILLER[1:] else (k.get('ad_dili') or k.get('dil') or 'en')


def _adet(d):
    """Basit kipte kadro harita yerlerinin sayısı kadar."""
    if d.get('kip') == 'basit':
        from bot import basit
        return max(1, basit.yer_sayisi(d['ayarlar'].get('basit_haritalar') or basit.VARSAYILAN_HARITALAR))
    return None


# ------------------------------------------------------------------ depo
def olustur(ad, aciklama='', dunya=None, kip='normal', gelisim='progressive', adet=60, dil='karisik', firma_dagilimi=(1, 1, 1),
            ayarlar=None, oyuncular=(), ad_dili_=None):
    """Yeni paket: kadro tohumla üretilir (oyuncuların adları kullanılmaz)."""
    if kip not in KIPLER:
        raise BotHatasi(_('Bilinmeyen bot kipi.'))
    with _KILIT:
        ad = _ad_temizle(ad)
        pid = _yeni_kimlik(ad)
        if kip == 'gelismis':
            dil = 'en'                         # dil modeli yalnız İngilizce (bot/llm.py)
        d = {'ad': ad, 'aciklama': str(aciklama or '')[:ACIKLAMA_UZUNLUK], 'dunya': None, 'kip': kip,
             'gelisim': gelisim if gelisim in GELISIMLER else 'progressive', 'tohum': random.randrange(1, 2 ** 31),
             'dil': dil if dil in DILLER else 'karisik', 'ad_dili': ad_dili_ if ad_dili_ in DILLER else 'karisik',
             'firma_dagilimi': _dagilim(firma_dagilimi),
             'ayarlar': ayarlari_temizle(ayarlar or {}), 'olusturma': _simdi()}
        n = _adet(d) or max(ADET_EN_AZ, min(ADET_EN_COK, int(adet or 60)))
        d['kadro'] = kadro_uret(d['tohum'], n, d['firma_dagilimi'], d['dil'], oyuncular, d['ad_dili'])
        _kaydet(pid, d)
    if dunya:
        ata(pid, dunya)
    return pid


def guncelle(pid, ad=None, aciklama=None, kip=None, gelisim=None, ayarlar=None):
    with _KILIT:
        d = oku(pid)
        if ad is not None:
            d['ad'] = _ad_temizle(ad)
        if aciklama is not None:
            d['aciklama'] = str(aciklama)[:ACIKLAMA_UZUNLUK]
        eski_kip = d['kip']
        if kip is not None:
            if kip not in KIPLER:
                raise BotHatasi(_('Bilinmeyen bot kipi.'))
            d['kip'] = kip
        if gelisim is not None and gelisim in GELISIMLER:
            d['gelisim'] = gelisim
        if ayarlar is not None:
            d['ayarlar'] = ayarlari_temizle(ayarlar, d.get('ayarlar'))
        n = _adet(d)
        if n is not None and (n != len(d['kadro']) or eski_kip != d['kip']):
            d['kadro'] = _boyutla(d, n)
        _kaydet(pid, d)


def _boyutla(d, n, oyuncular=()):
    """Kadro n bota: fazlası sondan çıkar, eksik yeni botlarla (aynı tohumdan devam; var olanların adı ve kişiliği değişmez)."""
    k = d['kadro'][:n]
    if len(k) < n:
        ek = kadro_uret(d['tohum'] + len(k) * 7919, n - len(k), d['firma_dagilimi'], d.get('dil', 'karisik'),
                        [x['ad'] for x in k] + list(oyuncular), ad_dili(d))
        son = max([x['no'] for x in k], default=0)
        for i, x in enumerate(ek, 1):
            x['no'] = son + i
        k += ek
    return k


def kadro(pid, adet=None, dil=None, firma_dagilimi=None, yeniden=False, oyuncular=(), ad_dili_=None):
    """Kadroyu boyutla (adet) ya da baştan üret (yeniden: yeni tohum, ilerleme sıfırlanır). Sohbet dili var olan botlara hemen
    uygulanır; ad dili yeni eklenen botlara ve baştan üretime (var olanların adı değişmez)."""
    with _KILIT:
        d = oku(pid)
        if ad_dili_ in DILLER:
            d['ad_dili'] = ad_dili_
        elif not d.get('ad_dili'):
            d['ad_dili'] = d.get('dil') or 'karisik'
        if d.get('kip') == 'gelismis':
            dil = 'en'                         # dil modeli yalnız İngilizce (bot/llm.py)
        if dil in DILLER and dil != d.get('dil'):
            d['dil'] = dil
            sohbet_dili_uygula(d)
        if firma_dagilimi is not None:
            d['firma_dagilimi'] = _dagilim(firma_dagilimi)
        n = _adet(d) or max(ADET_EN_AZ, min(ADET_EN_COK, int(adet or len(d['kadro']))))
        eskiler = [x['ad'] for x in d['kadro']]
        if yeniden:
            d['tohum'] = random.randrange(1, 2 ** 31)
            d['kadro'] = kadro_uret(d['tohum'], n, d['firma_dagilimi'], d['dil'], oyuncular, d['ad_dili'])
            giden = eskiler                              # baştan üretim: eski pilotların hepsi gider
        else:
            d['kadro'] = _boyutla(d, n, oyuncular)
            giden = eskiler[n:]                          # azaltma: sondakiler gider
        _kaydet(pid, d)
    AK.ekle([{'tur': 'sil', 'ad': a} for a in giden])
    if yeniden:
        sifirla(pid, olay=False)


def bot_adi(pid, no, ad, oyuncular=()):
    """Bir botun adını değiştir (ilerlemesi kalır)."""
    from bot import kisilik as KS
    ad = str(ad or '').strip()
    if not KS.AD_DESEN.match(ad):
        raise BotHatasi(_('Ad 3-20 karakter olmalı: harf, rakam, _ . -'))
    with _KILIT:
        d = oku(pid)
        if any(x['ad'].lower() == ad.lower() and x['no'] != no for x in d['kadro']) or ad.lower() in {str(o).lower() for o in oyuncular}:
            raise BotHatasi(_('Bu ad kullanılıyor.'))
        x = next((x for x in d['kadro'] if x['no'] == int(no)), None)
        if x is None:
            raise BotHatasi(_('Bot bulunamadı.'))
        eski, x['ad'] = x['ad'], ad
        _kaydet(pid, d)
        if eski != ad:
            AK.ekle([{'tur': 'ad', 'eski': eski, 'yeni': ad}])      # klanlar, rehberler, hafızalar (oyun uygular)


def sifirla(pid, olay=True):
    """Paketin ilerlemesini sil (botlar baştan başlar; jumpstart'ta yeniden dağıtılır). Botlar klanlardan çıkar (oyuncunun klanı
    dahil: ad_kaydi 'klan_cik'); adları ve tanışıklıkları kalır."""
    if olay:
        AK.ekle([{'tur': 'klan_cik', 'ad': x['ad']} for x in oku(pid)['kadro']])
    p = durum_yolu(pid)
    for f in (p, os.path.join(os.path.dirname(p), 'klanlar.json')):
        if os.path.isfile(f):
            os.remove(f)


def sil(pid):
    """Paket _silinenler'e taşınır; botları her yerden çıkar (klanlar, rehberler: ad_kaydi, oyun sonraki açılışta uygular)."""
    p = _yol(pid)
    if not os.path.isfile(p):
        raise BotHatasi(_('Bot paketi bulunamadı.'))
    AK.ekle([{'tur': 'sil', 'ad': x['ad']} for x in oku(pid)['kadro']])
    hedef = os.path.join(klasor(), '_silinenler')
    os.makedirs(hedef, exist_ok=True)
    damga = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    os.replace(p, os.path.join(hedef, '%s_%s.json' % (pid, damga)))
    dz = os.path.join(klasor(), pid)
    if os.path.isdir(dz):
        shutil.move(dz, os.path.join(hedef, '%s_%s' % (pid, damga)))


def ata(pid, dunya):
    """Paketi bir dünyaya ata (o dünyanın önceki paketi boşa çıkar); dunya None: atamayı kaldır."""
    with _KILIT:
        d = oku(pid)
        if dunya:
            for x in liste_kimlik():
                if x != pid:
                    o = _oku_dosya(_yol(x))
                    if o and o.get('dunya') == dunya:
                        o['dunya'] = None
                        _kaydet(x, o)
        d['dunya'] = dunya or None
        _kaydet(pid, d)


def liste_kimlik():
    if not os.path.isdir(klasor()):
        return []
    return [f[:-5] for f in os.listdir(klasor()) if f.endswith('.json') and not f.startswith('_')
            and re.fullmatch(r'[a-z0-9_]{1,40}', f[:-5])]


def dunya_paketi(dunya):
    """Dünyanın paketi (kimlik) ya da None."""
    for pid in liste_kimlik():
        d = _oku_dosya(_yol(pid))
        if d and d.get('dunya') == dunya:
            return pid
    return None


# ------------------------------------------------------------------ özetler
def canli(pid):
    """Sunucunun son kaydı: no -> bot durumu (seviye, gemi, harita, klan, istatistik) ve kaydın anı."""
    d = _oku_dosya(durum_yolu(pid)) or {}
    return d.get('t'), {int(k): v for k, v in (d.get('botlar') or {}).items()}


def ozet(pid):
    d = oku(pid)
    t, c = canli(pid)
    firmalar = [sum(1 for x in d['kadro'] if x['firma'] == f) for f in (1, 2, 3)]
    seviyeler = [c[x['no']].get('seviye', 1) for x in d['kadro'] if x['no'] in c]
    return {'id': pid, 'ad': d['ad'], 'aciklama': d.get('aciklama', ''), 'dunya': d.get('dunya'), 'kip': d['kip'],
            'gelisim': d.get('gelisim'), 'adet': len(d['kadro']), 'firmalar': firmalar, 'guncelleme': d.get('guncelleme'),
            'son_oyun': t, 'seviye_ort': round(sum(seviyeler) / len(seviyeler), 1) if seviyeler else None,
            'seviye_enb': max(seviyeler) if seviyeler else None}


def liste():
    out = []
    for pid in liste_kimlik():
        try:
            out.append(ozet(pid))
        except BotHatasi:
            pass
    out.sort(key=lambda x: x['guncelleme'] or '', reverse=True)
    return out


def ayrinti(pid):
    """Paket + kadronun canlı durumu (son kayıttan)."""
    d = oku(pid)
    t, c = canli(pid)
    rows = []
    for x in d['kadro']:
        s = c.get(x['no'], {})
        e = s.get('ekip') or {}
        rows.append({'no': x['no'], 'ad': x['ad'], 'firma': x['firma'], 'arketip': x['kisilik']['arketip'],
                     'aliskanlik': x['kisilik'].get('aliskanlik'), 'dil': x['kisilik'].get('dil'),
                     'ad_dili': x['kisilik'].get('ad_dili') or x['kisilik'].get('dil'),
                     'ozellik': x['kisilik']['ozellik'], 'seviye': s.get('seviye', 1), 'gemi': e.get('gemi', 'ship_phoenix'),
                     'harita': s.get('harita'), 'klan': s.get('klan'), 'hedef': s.get('hedef'), 'istat': s.get('istat') or {},
                     'kredi': s.get('kredi', 0), 'uridyum': s.get('uridyum', 0), 'onur': s.get('onur', 0)})
    out = dict(ozet(pid), ayarlar=d['ayarlar'], dil=d.get('dil'), ad_dili=ad_dili(d), diller=list(DILLER),
               firma_dagilimi=d.get('firma_dagilimi'), kadro=rows,
               durum_var=bool(c))
    return out


def imza(pid):
    """Sunucunun yeniden başlaması gereken değişiklik: paket dosyasının içeriği (durum.json değil)."""
    p = dosya_yolu(pid)
    if not p:
        return None
    import hashlib
    with open(p, 'rb') as fh:
        return os.path.normcase(p), hashlib.sha1(fh.read()).hexdigest()
