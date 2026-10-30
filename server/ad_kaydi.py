"""Bot adlarının değişim ve silinme kaydı: panelin Botlar sayfası yazar, oyun her yere uygular.

Botun adı oyunun birçok yerinde adıyla tutulur: klanın üyeleri, lideri, başvuruları (klan.py), oyuncunun klan kopyası (profil
'klan'), rehberler (profil 'rehber': arkadaş, istek, engelli), öteki botların hafızası ve rehberleri. Panel bir botun adını
değiştirince, kadroyu baştan üretince, bot sayısını azaltınca ya da paketi silince buraya sıralı olaylar ekler:
  {'n': sıra, 't': zaman, 'tur': 'ad', 'eski': ad, 'yeni': ad}     ad değişti
  {'n', 't', 'tur': 'sil', 'ad': ad}                                bot artık yok (her yerden çıkar)
  {'n', 't', 'tur': 'klan_cik', 'ad': ad}                           ilerlemesi sıfırlandı: klanlardan çıkar, tanışıklıkları kalır
Her tüketici en son uyguladığı sırayı saklar (profil 'bot_ad_kaydi', klan dosyası 'bot_ad_kaydi', paket durum.json) ve yalnız
yenilerini bir kez uygular: oyun kapalıyken yapılan değişiklik sonraki girişte, açıkken panel kanalıyla (panel_kanali /bot/ad_kaydi)
hemen uygulanır. Silinen ada sonradan başkası sahip olsa da eski olay ona dokunmaz.
Ada göre çalışır: kadro baştan üretilince yeni botlar eskilerin kimliğini (1800000000 + sıra) alır.
Gönderilmiş ve alınmış postalar geçmiştir, olduğu gibi kalır.
"""
import json, os, threading, time

import yollar as YOL

LOCK = threading.RLock()
_ON = {'mtime': None, 'olaylar': []}
BOT_UID = (1800000000, 1900000000)        # bot kimlikleri (bot/durum.BOT_UID_TABAN ...): klan liderliği insana geçerken


def dosya():
    return os.path.join(YOL.SAVE, 'botlar', '_ad_kaydi.json')


def oku():
    """Bütün olaylar (dosya değişmedikçe önbellekten)."""
    p = dosya()
    try:
        m = os.path.getmtime(p)
    except OSError:
        return []
    with LOCK:
        if _ON['mtime'] != m:
            try:
                with open(p, encoding='utf8') as f:
                    _ON['olaylar'] = json.load(f).get('olaylar') or []
            except (OSError, ValueError):
                _ON['olaylar'] = []
            _ON['mtime'] = m
        return _ON['olaylar']


def son():
    o = oku()
    return o[-1]['n'] if o else 0


def ekle(olaylar):
    """Panel: olayları ekle (ad değişimi, silinme). -> son sıra."""
    olaylar = [x for x in olaylar if x]
    if not olaylar:
        return son()
    with LOCK:
        hepsi = list(oku())
        n = hepsi[-1]['n'] if hepsi else 0
        t = time.time()
        for x in olaylar:
            n += 1
            hepsi.append(dict(x, n=n, t=t))
        p = dosya()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p + '.tmp', 'w', encoding='utf8') as f:
            json.dump({'olaylar': hepsi}, f, ensure_ascii=False)
        os.replace(p + '.tmp', p)
        _ON['mtime'] = None
        return n


def yeniler(n):
    return [x for x in oku() if x['n'] > int(n or 0)]


# ------------------------------------------------------------------------------------------------------------ uygulama
def _k(ad):
    return str(ad or '').strip().lower()


def liste_uygula(lst, olaylar):
    """Ad listesi (rehber): yeniden adlandırma ve silinme -> yeni liste ya da None (değişmedi)."""
    out, degisti = list(lst), False
    for e in olaylar:
        if e['tur'] == 'ad':
            yeni = []
            for x in out:
                if _k(x) == _k(e['eski']):
                    x, degisti = e['yeni'], True
                if not any(_k(y) == _k(x) for y in yeni):
                    yeni.append(x)
            out = yeni
        elif e['tur'] == 'sil':
            kalan = [x for x in out if _k(x) != _k(e['ad'])]
            degisti = degisti or len(kalan) != len(out)
            out = kalan
    return out if degisti else None


def klan_uygula(k, olaylar):
    """Klan kaydı (asıl kayıt ya da profildeki kopya) -> 'bos' (kimse kalmadı), True (değişti) ya da False. Lider giderse liderlik
    insan üyeye (yoksa sıradakine) geçer."""
    degisti = False
    for e in olaylar:
        if e['tur'] == 'ad':
            eski, yeni = _k(e['eski']), _k(e['yeni'])
            if eski in k['uyeler'] and eski != yeni:
                k['uyeler'][yeni] = dict(k['uyeler'].pop(eski), ad=e['yeni'])
                if k['lider'] == eski:
                    k['lider'] = yeni
                degisti = True
            for b in k.get('basvurular', []):
                if _k(b.get('ad')) == eski:
                    b.update(ad=yeni, isim=e['yeni'])
                    degisti = True
            k['retler'] = [yeni if _k(r) == eski else r for r in k.get('retler', [])]
        else:                                            # sil, klan_cik
            a = _k(e['ad'])
            if a in k['uyeler']:
                del k['uyeler'][a]
                degisti = True
                if k['lider'] == a:
                    if not k['uyeler']:
                        return 'bos'
                    insan = [x for x, u in k['uyeler'].items() if not BOT_UID[0] <= int(u.get('uid') or 0) < BOT_UID[1]]
                    k['lider'] = (insan or list(k['uyeler']))[0]
            n = len(k.get('basvurular', []))
            k['basvurular'] = [b for b in k.get('basvurular', []) if _k(b.get('ad')) != a]
            degisti = degisti or n != len(k['basvurular'])
            if e['tur'] == 'sil':
                k['retler'] = [r for r in k.get('retler', []) if _k(r) != a]
    return degisti


def profil_uygula(p):
    """Profilin rehberine ve klan kopyasına bekleyen olaylar (oturum açılırken, rehber okunurken) -> değişti mi."""
    yeni = yeniler(p.d.get('bot_ad_kaydi', 0))
    if not yeni:
        return False
    degisti = False
    with p.lock:
        r = p.d.get('rehber') or {}
        for ad in ('arkadas', 'gelen', 'giden', 'reddeden', 'engelli'):
            if isinstance(r.get(ad), list):
                x = liste_uygula(r[ad], yeni)
                if x is not None:
                    r[ad], degisti = x, True
        k = p.d.get('klan')
        if k and 'uyeler' in k:
            s = klan_uygula(k, yeni)
            if s == 'bos':
                p.d['klan'] = None
                p.d['pilot'].update(clanId=0, clanTag='')
            degisti = degisti or bool(s)
        p.d['bot_ad_kaydi'] = yeni[-1]['n']
        p.dirty = True
    return degisti


def klanlar_uygula(KL):
    """Asıl klan kayıtlarına (klan.KLANLAR) bekleyen olaylar; boşalan klan silinir (diplomasisi de) -> değişen klanlar."""
    yeni = yeniler(KL.BOT_AD_N)
    if not yeni:
        return []
    out = []
    with KL.LOCK:
        for cid, k in list(KL.KLANLAR.items()):
            s = klan_uygula(k, yeni)
            if s == 'bos':
                KL.KLANLAR.pop(cid, None)
                KL.SILINEN[cid] = k.get('anahtar')
                for c in KL.KLANLAR.values():
                    c['diplomasi'] = [d for d in c.get('diplomasi', []) if d['klan'] != cid]
                    c['diplo_istek'] = [r for r in c.get('diplo_istek', []) if cid not in (r['kimden'], r['kime'])]
            elif s:
                out.append(k)
        KL.BOT_AD_N = yeni[-1]['n']
    for k in out:
        KL.degisti(k)                                    # sürüm artar, bağlı üyelerin kopyaları yenilenir
    KL.kaydet()
    return out
