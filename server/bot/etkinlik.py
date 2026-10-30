"""Etkinlikler, Battle Pass ve Season Pass: botlar takvimdeki etkinliklere oyuncu gibi katılır (oyunun etkinlik_harita.py,
savas_bileti.py, sezon.py ve data/biletler.json kuralları).

  etkinlik    etkin etkinliğin harita bölümü botun haritasını kapsıyorsa: gücü yeten etkinlik uzaylılarını avlar (somutta haritada
              gerçekten doğanları, soyutta bölümün listesinden), düşmeleri ('dusme': etkinlik parası) alır, haritadaki anahtarsız
              etkinlik kutularını toplar (içerik oyunun ETK.roll'u); parası Assembly'nin etkinlik tariflerine gider (ganimet.assembly)
  Battle Pass pass'li etkinlik sürerken oynadıkça pass görevleri biter (oynanan sürenin ve öldürmenin payıyla), her görevin
              ödülü alınır; pass'i alan (200.000 U, zengin ve hırslı bot) görev başına anahtar da alır; anahtarlar değişim
              tablosunda değer / anahtar oranı en iyi ödüle harcanır (sınırıyla)
  Season Pass günlük ve haftalık görevlerden puan (oynanan saatle); seviyenin puan bedeli dolunca ücretsiz sıranın ödülü
Durum: bot.k['pass'] = {'donem', 'tamam', 'satin', 'degisim': {ödül: adet}}, bot.k['sezon'] = {'donem', 'puan', 'seviye'}.
"""
import json, os, random, time

from . import katalog as K

B = json.load(open(os.path.join(K.HERE, 'data', 'biletler.json'), encoding='utf8'))
SEZON = B['sezon']
SB = B['savas_bileti']
PASS_FIYAT = 200000
PASS_GOREV_SN = 2700            # oynanan ~45 dakikada bir pass görevi
SEZON_PUAN_SAAT = 30            # oynanan saatte Season Pass puanı (günlük + haftalık görevler)
_on = {'t': 0, 'bolum': [], 'aktif': set()}


def _tazele():
    import etkinlik_harita as EH, takvim as TKV
    t = time.time()
    if t - _on['t'] > 60:
        _on.update(t=t, bolum=EH.specs(), aktif=set(TKV.active()))
    return _on


def bolumler(harita):
    """Bu haritayı kapsayan etkin etkinlik harita bölümleri [(etkinlik, bölüm)]."""
    import harita as H
    sinif, ad = H.map_class(harita), H.name(harita)
    return [(k, s) for k, s in _tazele()['bolum'] if sinif in s.get('haritalar', ()) or ad in s.get('haritalar', ())]


def etkinlik_turleri(bot, harita):
    """Gücü yeten etkinlik uzaylısı türleri."""
    d = bot.deger()
    out = set()
    for _, s in bolumler(harita):
        for u in s.get('uzaylilar', []):
            tip = str(u['tur']).replace('{x}', 'x%s' % harita_no(harita)) if '{x}' in str(u['tur']) else str(u['tur'])
            v = K.npc_degeri(tip) or K.npc_degeri(str(u['tur']))
            if v and d['dps'] > 0 and v['ehp'] / d['dps'] < 120 and v['dps'] * v['ehp'] / d['dps'] < d['ehp'] * 0.6:
                out.add(tip if K.npc_degeri(tip) else str(u['tur']))
    return out


def harita_no(harita):
    import harita as H
    return H.name(harita).split('-')[-1]


def dusme(bot, harita, tip):
    """Etkinlik uzaylısının (ya da haritanın uzaylısının) etkinlik düşmeleri bota (oyunun ETK.roll'u)."""
    import dunya as DN
    import etkinlik_harita as EH
    from . import ganimet as GB
    if not bot.izin.get('etkinlik', True):
        return
    b = EH.base(tip)
    for _, s in bolumler(harita):
        tab = s.get('dusme', {})
        for loot, a in (tab.get(tip) or tab.get(b) or {}).items():
            n = DN.extra_count(a, 1.0)                    # oyunun okuyuşu: sayı, [en az, en çok] ya da {adet, olasilik} (Agatus)
            if n > 0:
                GB.ver(bot, loot, n)
                bot.ist('etkinlik_dusme', n)
        kd = (s.get('kutu_dusme', {}).get(tip) or s.get('kutu_dusme', {}).get(b))
        if kd and random.random() < kd.get('olasilik', 1.0) * 0.8:            # düşen sandığı çoğunlukla toplar
            for loot, n in EH.roll(kd):
                GB.ver(bot, loot, n)


def kutu_ac(bot, spec):
    import etkinlik_harita as EH
    from . import ganimet as GB
    got = EH.roll(spec)
    for loot, n in got:
        GB.ver(bot, loot, n)
    bot.ist('etkinlik_kutusu')
    return got


def soyut(bot, dt, y, dps):
    """Soyut: etkinlik uzaylılarını avlar (düşmeleri ve öldürme ödülü) ve haritanın etkinlik kutularına rastlar."""
    if not bot.izin.get('etkinlik', True):
        return
    bl = bolumler(bot.harita)
    if not bl:
        return
    hiz = y.hiz(bot) if y is not None else 1.0
    kalabalik = max(1.0, 0.3 * len(y.haritada.get(bot.harita, ()))) if y is not None else 1.0
    turler = etkinlik_turleri(bot, bot.harita)
    for k, s in bl:
        for u in s.get('uzaylilar', []):
            tip = next((t for t in turler if t == str(u['tur']) or t.startswith(str(u['tur']).split('{')[0])), None)
            v = K.npc_degeri(tip) if tip else None
            if not v:
                continue
            oran = min(u.get('adet', 1) * dt / 60.0 / kalabalik, dt * 0.25 * dps / max(1.0, v['ehp']))    # etkinlik uzaylısı payı
            n = int(oran) + (bot.r.random() < oran - int(oran))
            for _ in range(n):
                o = v['odul']
                bot.odul('npc', hiz, ep=o.get('ep', 0), kredi=o.get('kredi', 0), uridyum=o.get('uridyum', 0), onur=o.get('onur', 0))
                dusme(bot, bot.harita, tip)
            if n:
                bot.ist('etkinlik_npc', n)
                if y is not None:
                    y.npc_oldurdu(bot, tip, n)
        for kt in s.get('kutular', []):
            yen = kt.get('yeniden_sn') or [300, 600]
            if bot.r.random() < kt.get('adet', 1) * dt / (sum(yen) / 2.0) / kalabalik:
                kutu_ac(bot, kt)


# ------------------------------------------------------------------------------------------------------------ Battle Pass
def aktif_pass():
    """Şu an süren pass'in etkinliği (pass'i olan etkin etkinlik) ya da None."""
    aktif = _tazele()['aktif']
    return next((k for k in SB['passler'] if k in aktif), None)


def battle_pass(bot, dt):
    """Oynadıkça pass görevleri biter; ödül ve (pass alındıysa) anahtar; anahtarlar değişime."""
    from . import ganimet as GB
    if not bot.izin.get('etkinlik', True):
        return
    k = aktif_pass()
    if not k:
        return
    st = bot.k.setdefault('pass', {})
    if st.get('donem') != k:
        st.clear()
        st.update(donem=k, tamam=0, satin=False, sure=0.0, degisim={})
    p = SB['passler'][k]
    oduller = list((p.get('oduller') or {}).values())
    if not st['satin'] and not p.get('anahtarsiz') and bot.seviye >= 12 and bot.o('hirs') > 0.6 \
            and bot.k['uridyum'] > PASS_FIYAT * (2 + bot.o('tutumluluk')) and bot.ode('U', PASS_FIYAT * bot.oa.carpan('magaza_fiyat')):
        st['satin'] = True
        bot.ist('battle_pass')
        stok = GB.stok(bot)
        stok['resource_battle-pass-key'] = stok.get('resource_battle-pass-key', 0) + st['tamam']     # o ana dek toplananlar
    st['sure'] += dt
    while st['sure'] >= PASS_GOREV_SN and st['tamam'] < len(oduller):
        st['sure'] -= PASS_GOREV_SN
        o = oduller[st['tamam']]
        st['tamam'] += 1
        for loot, n in o.get('odul', []):
            GB.ver(bot, loot, n)
        if st['satin']:
            stok = GB.stok(bot)
            stok['resource_battle-pass-key'] = stok.get('resource_battle-pass-key', 0) + o.get('anahtar', 0)
        bot.ist('pass_gorev')
    degistir(bot, st)


def degistir(bot, st):
    """Battle Pass anahtarlarını değişim tablosunda en iyi değer / anahtar oranlı ödüle harcar (sınırıyla)."""
    from . import ganimet as GB
    stok = GB.stok(bot)
    tablo = (SB['passler'].get(st['donem']) or {}).get('anahtar_degisimi') or SB['anahtar_degisimi']
    while stok.get('resource_battle-pass-key', 0) > 0:
        uygun = [r for r in tablo if r['cost'] <= stok['resource_battle-pass-key']
                 and st['degisim'].get(r['exchangeReward'], 0) < r.get('limit', 99)]
        if not uygun:
            return
        r = max(uygun, key=lambda r: sum(GB.deger(l['lootId'], l['amount']) for l in r['listOfloot']) / max(1, r['cost']))
        stok['resource_battle-pass-key'] -= r['cost']
        st['degisim'][r['exchangeReward']] = st['degisim'].get(r['exchangeReward'], 0) + 1
        for l in r['listOfloot']:
            GB.ver(bot, l['lootId'], l['amount'])
        bot.ist('pass_degisim')


# ------------------------------------------------------------------------------------------------------------ Season Pass
def sezon_donemi():
    t = time.localtime()
    ay = ((t.tm_mon - 2) // 3) * 3 + 2 if t.tm_mon >= 2 else 11
    return '%d-%02d' % (t.tm_year if t.tm_mon >= 2 else t.tm_year - 1, ay)


def season_pass(bot, dt):
    from . import ganimet as GB
    if not bot.izin.get('etkinlik', True):
        return
    st = bot.k.setdefault('sezon', {})
    d = sezon_donemi()
    if st.get('donem') != d:
        st.clear()
        st.update(donem=d, puan=0.0, seviye=0)
    st['puan'] += SEZON_PUAN_SAAT * dt / 3600.0 * (0.7 + 0.6 * bot.o('hirs'))
    bedel = SEZON['puan_bedeli']
    sira = {lv: (loot, n) for lv, loot, n in SEZON['odul'].get('ucretsiz', [])}
    while st['seviye'] + 1 < len(bedel) and st['puan'] >= bedel[st['seviye'] + 1]:
        st['puan'] -= bedel[st['seviye'] + 1]
        st['seviye'] += 1
        if st['seviye'] in sira:
            GB.ver(bot, *sira[st['seviye']])
        bot.ist('sezon_seviye')
