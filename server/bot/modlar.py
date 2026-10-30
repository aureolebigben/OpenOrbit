"""Etkinliğe özel modlar ve PvE modları: botlar oyuncunun girebildiği her moda aynı kurallarla girer (soyut koşu).

Her mod (Mod alt sınıfı) oyunun verisinden: açık mı (takvim, saat penceresi), girebilir mi (seviye, bilet/anahtar/CPU, günlük /
yıllık / bekleme sınırı, firma), bedel (bilet harcanır ya da uridyumla alınır), dalgalar [(can+kalkan, aynı anda vuranların
saniyede hasarı, uzaylıların öldürme ödülleri)], can hakkı, süre sınırı ve bitiş ödülü (ulaşılan dalgaya göre: yıldız, rift,
basamak, seviye). Koşu (kos) dalga dalga ilerler: botun en iyi cephanesiyle hasarı (kapi.tahmin'in yöntemi), ölümler can hakkını
bitirince durur; öldürme ödülleri ulaşılan dalgalarınki, bitiş ödülü modun kuralıyla. Bot koşu boyunca modun haritasındadır
(senin haritandan kalkar; hedefler/mod_kosusu.py).

Modlar: etkinlik kapıları (Gauntlet of Plutus, Trial of Terrors, Birthday, Quarantine Zone, Compromising Invasion, Permafrost,
The Breach, Devolarium Attack), Voyagers' Ascent, Trinity Trials, Astral Ascension, Eternal Black Light, Deep Space Echoes,
Battle of LoW, Vortex of Greed, Mimesis Mutiny, World Boss, Kristallon Apotheosis, Frozen Labyrinth. Pasifler (Dispatch,
Galaxy Trek) pasif() ile karar anında.
"""
import json, os, random, time

from . import katalog as K

D = lambda f: json.load(open(os.path.join(K.HERE, 'data', f), encoding='utf8'))
PVE = D('pve_modlari.json')
EKK = D('etkinlik_kapilari.json')
BUYUK = D('buyuk_icerikler.json')
LOW = D('low.json')
EK = D('ek_etkinlikler.json')
DISP = D('dispatch.json')


def _tk():
    import takvim as TK
    return TK


def tur_degeri(tip):
    """Uzaylı türü -> (hp, kalkan, hasar, ödül): PvE türleri, npc.json ya da modun kendi tablosu."""
    t = PVE['turler'].get(tip) or K.NPC['tipler'].get(str(tip))
    if not t:
        return None
    return t.get('hp', 0), t.get('kalkan', 0), t.get('hasar', 0), t.get('odul') or {}


def dalga(gruplar, can=1.0, hasar=1.0, tablo=None):
    """[[[tür, adet], …], …] (gruplar) -> (can+kalkan, saniyede gelen hasar, öldürme ödülleri)."""
    ehp = dps = 0.0
    odul = {}
    for grup in gruplar:
        for x in grup:
            tip, n = x[0], x[1]                          # [tür, adet] ya da [tür, adet, patron mu]
            v = (tablo or {}).get(tip)
            v = (v.get('hp', 0), v.get('kalkan', 0), v.get('hasar', 0), v.get('odul') or {}) if v else tur_degeri(tip)
            if not v:
                continue
            hp, kl, hs, od = v
            ehp += n * (hp + kl) * can
            dps += min(n, 2) * hs * hasar * K.SAVAS['npc_isabet'] * 0.6 / K.NPC_ARALIK
            for k, x in od.items():
                odul[k] = odul.get(k, 0) + x * n
    return ehp, dps, odul


def uzaylilar_dalgasi(uz):
    """Etkinlik kapısı biçimi: [{hp, kalkan, hasar, adet, odul}] -> dalga."""
    tablo = {str(i): u for i, u in enumerate(uz)}
    return dalga([[[str(i), u.get('adet', 1)] for i, u in enumerate(uz)]], tablo=tablo)


# ------------------------------------------------------------------------------------------------------------ ödül
def ver_liste(bot, rows, rng=random):
    """[[loot, adet ya da [en az, en çok]], …] -> bota."""
    from . import ganimet as GB
    for r in rows or []:
        loot, n = r[0], r[1]
        n = rng.randint(*n) if isinstance(n, list) else n
        if n:
            GB.ver(bot, loot, n)


def ver_odul(bot, o, rng=random, hiz=1.0):
    """Etkinlik kapısı / genel ödül sözlüğü: ep, onur, kredi, uridyum, esyalar, sans [[loot, n, olasılık]], biri [[loot, n, ağırlık]]."""
    if not o:
        return
    para = {k: o[k] for k in ('ep', 'onur', 'kredi', 'uridyum') if o.get(k)}
    if para:
        bot.odul('gorev', hiz, **para)
    ver_liste(bot, o.get('esyalar'), rng)
    for loot, n, p in o.get('sans') or []:
        if rng.random() < p:
            ver_liste(bot, [[loot, n]], rng)
    if o.get('biri'):
        r = rng.choices(o['biri'], weights=[x[2] if len(x) > 2 else 1 for x in o['biri']])[0]
        ver_liste(bot, [r[:2]], rng)


def durum(bot, mod):
    return bot.k.setdefault('modlar', {}).setdefault(mod, {})


def gun():
    return time.strftime('%Y-%m-%d')


# ------------------------------------------------------------------------------------------------------------ modlar
class Mod:
    ad = ''
    kimlik = ''
    harita = None              # koşu boyunca botun haritası (senin haritandan kalkar)
    can = 1
    seviye = 1
    sure_sinir = None          # koşunun en uzun süresi (sn; süreli modlar)
    tip = 'kosu'

    def acik(self, now):
        return True

    def girebilir(self, bot, now):
        return bot.seviye >= self.seviye

    def bedel(self, bot):
        return True

    def odenebilir(self, bot):
        """Giriş bedeli şimdi ödenebilir mi (harcamadan): aday seçimi için."""
        return True

    def dalgalar(self, bot):
        return []

    def bitir(self, bot, ulasilan, toplam, sure, rng):
        pass

    def kaydet(self, bot, ulasilan, toplam):
        durum(bot, self.kimlik).update(son=time.time(), gun=gun(), sayi=durum(bot, self.kimlik).get('sayi', 0) + 1)


def _stok(bot):
    from . import silah as SL
    return SL.stok(bot)


def _var_ya_da_alinabilir(bot, loot, uridyum=None):
    if _stok(bot).get(loot, 0) > 0:
        return True
    f = K.fiyat(loot)
    fiyat = uridyum if uridyum else (f[1] if f and f[0] == 'U' else None)
    return bool(fiyat) and bot.izin.get('magaza', True) and \
        bot.k['uridyum'] >= fiyat * bot.oa.carpan('magaza_fiyat') * (3 + 3 * bot.o('tutumluluk'))


def _harca_ya_da_al(bot, loot, uridyum=None):
    """Bilet/anahtar/CPU stokta varsa harcar; yoksa uridyumla alınabiliyorsa (fiyat ya da verilen) ve bot zenginse alır."""
    s = _stok(bot)
    if s.get(loot, 0) > 0:
        s[loot] -= 1
        if not s[loot]:
            del s[loot]
        return True
    f = K.fiyat(loot)
    fiyat = uridyum if uridyum else (f[1] if f and f[0] == 'U' else None)
    if not fiyat or not bot.izin.get('magaza', True):
        return False
    fiyat *= bot.oa.carpan('magaza_fiyat')
    if bot.k['uridyum'] < fiyat * (3 + 3 * bot.o('tutumluluk')):
        return False
    return bot.ode('U', fiyat)


class EtkinlikKapisi(Mod):
    """data/etkinlik_kapilari.json kapilar.<anahtar>: etkinlik, kural (gunluk+grup, yillik, donem, bekleme_sn, seviye,
    azami_seviye, firma, bir_kez, cpu, gorev), can, dalgalar (uzaylilar), odul."""

    def __init__(self, k, g):
        self.kimlik, self.g = 'ekapi_' + k, g
        self.ad = g['ad']
        self.harita = (g.get('haritalar') or [None])[0]
        self.can = min(int(g.get('can', 1)), 50)
        self.kural = g.get('kural') or {}
        self.seviye = self.kural.get('seviye', 1)

    def acik(self, now):
        e = self.g.get('etkinlik')
        if e and not _tk().is_active(e, now):
            return False
        don = self.kural.get('donem')
        if don:
            md = time.strftime('%m-%d', time.localtime(now))
            return any((a <= md <= b) if a <= b else (md >= a or md <= b) for a, b in don)
        return True

    def girebilir(self, bot, now):
        k, st = self.kural, durum(bot, self.kimlik)
        if bot.seviye < k.get('seviye', 1) or bot.seviye > k.get('azami_seviye', 99):
            return False
        if k.get('firma') and k['firma'] != bot.firma:
            return False
        if k.get('bir_kez') and st.get('sayi'):
            return False
        if k.get('gunluk'):
            grup = k.get('grup') or self.kimlik
            if durum(bot, 'grup_' + grup).get('gun') == gun():
                return False
        if k.get('yillik') and st.get('yil') == time.strftime('%Y'):
            return False
        if k.get('bekleme_sn') and now - st.get('son', 0) < k['bekleme_sn']:
            return False
        if k.get('gorev'):
            g = bot.k.get('gorev') or {}
            if str(g.get('id')) != str(k['gorev']):
                return False
        if k.get('cpu') and _stok(bot).get(k['cpu'], 0) <= 0 and not K.fiyat(k['cpu']):
            return False
        return True

    def bedel(self, bot):
        cpu = self.kural.get('cpu')
        return _harca_ya_da_al(bot, cpu) if cpu else True

    def odenebilir(self, bot):
        cpu = self.kural.get('cpu')
        return _var_ya_da_alinabilir(bot, cpu) if cpu else True

    def dalgalar(self, bot):
        return [uzaylilar_dalgasi(d.get('uzaylilar', [])) for d in self.g.get('dalgalar', [])]

    def bitir(self, bot, ulasilan, toplam, sure, rng):
        if ulasilan >= toplam:
            ver_odul(bot, self.g.get('odul'), rng)

    def kaydet(self, bot, ulasilan, toplam):
        super().kaydet(bot, ulasilan, toplam)
        k = self.kural
        if k.get('gunluk'):
            durum(bot, 'grup_' + (k.get('grup') or self.kimlik))['gun'] = gun()
        if k.get('yillik'):
            durum(bot, self.kimlik)['yil'] = time.strftime('%Y')


class Voyagers(Mod):
    kimlik, ad, tip = 'voyagers', "Voyagers' Ascent", 'arena'
    V = PVE['voyagers']
    harita = V['harita'] if isinstance(V['harita'], int) else 0
    seviye = 8

    def zorluk(self, bot):
        st = durum(bot, self.kimlik)
        d = 0
        while d + 1 < len(self.V['zorluklar']) and st.get('yildiz', {}).get(str(d), 0) >= 3:
            d += 1
        return d

    def girebilir(self, bot, now):
        return bot.seviye >= self.seviye

    def bedel(self, bot):
        st = durum(bot, self.kimlik)
        if st.get('ucretsiz') != gun():
            st['ucretsiz'] = gun()
            return True
        return _harca_ya_da_al(bot, self.V['jeton'])

    def odenebilir(self, bot):
        return durum(bot, self.kimlik).get('ucretsiz') != gun() or _var_ya_da_alinabilir(bot, self.V['jeton'])

    def dalgalar(self, bot):
        z = self.V['zorluklar'][self.zorluk(bot)]
        return [dalga(d['gruplar']) for d in z['dalgalar']]

    def bitir(self, bot, ulasilan, toplam, sure, rng):
        if ulasilan < toplam:
            return
        sn = self.V['yildiz_sn']
        yildiz = 3 if sure <= sn[0] else 2 if sure <= sn[1] else 1
        d = self.zorluk(bot)
        st = durum(bot, self.kimlik).setdefault('yildiz', {})
        st[str(d)] = max(st.get(str(d), 0), yildiz)
        ver_liste(bot, self.V['zorluklar'][d]['oduller'].get(str(yildiz)), rng)


class Trinity(Mod):
    kimlik, ad, tip = 'trinity', 'Trinity Trials', 'arena'
    T = PVE['trinity']
    harita = next(iter(T['haritalar'].values()))[0] if isinstance(T['haritalar'], dict) else T['haritalar'][0]
    seviye = 8

    def arena(self):
        g = time.localtime().tm_wday
        return next((a for a, gunler in self.T['gunler'].items() if g in gunler), '1')

    def bedel(self, bot):
        st = durum(bot, self.kimlik)
        if st.get('ucretsiz') != gun():
            st['ucretsiz'] = gun()
            return True
        return _harca_ya_da_al(bot, self.T['jeton'])

    def odenebilir(self, bot):
        return durum(bot, self.kimlik).get('ucretsiz') != gun() or _var_ya_da_alinabilir(bot, self.T['jeton'])

    def zorluk(self, bot):
        return min(len(self.T['zorluklar']) - 1, max(0, bot.seviye // 6 - 1))

    def dalgalar(self, bot):
        z = self.T['zorluklar'][self.zorluk(bot)]
        ar = z['arenalar'].get(self.arena()) or next(iter(z['arenalar'].values()))
        return [dalga(d['gruplar']) for d in ar]

    def bitir(self, bot, ulasilan, toplam, sure, rng):
        km = ulasilan // 5                                   # 5 dalgada bir kilometre taşı: Quantum Prism ve Xyralith
        d = self.zorluk(bot) + 1
        if km:
            ver_liste(bot, [[self.T['kp'], km], [self.T['xy'], km * 10 * d]], rng)


class Astral(Mod):
    kimlik, ad = 'astral', 'Astral Ascension'
    A = PVE['astral']
    harita = A['haritalar'][0]
    seviye = 12

    def girebilir(self, bot, now):
        return bot.seviye >= self.seviye and (_stok(bot).get(self.A['cpu'], 0) > 0 or bool(K.fiyat(self.A['cpu'])))

    def bedel(self, bot):
        return _harca_ya_da_al(bot, self.A['cpu'])

    def odenebilir(self, bot):
        return _var_ya_da_alinabilir(bot, self.A['cpu'])

    def dalgalar(self, bot):
        o = self.A['olcek']
        out = []
        for r, rift in enumerate(self.A['riftler'], 1):
            s = random.choice(rift['setler'])
            can = (1 + o['rift_can'] * r) * o['patron_can'].get(str(r), 1)
            hs = (1 + o['rift_hasar'] * r) * o['patron_hasar'].get(str(r), 1)
            out.append(_birlesik([dalga(d['gruplar'], can, hs) for d in s]))
        return out

    def bitir(self, bot, ulasilan, toplam, sure, rng):
        row = next((r for r in self.A['odul'] if r['en_az'] <= ulasilan <= r['en_cok']), None)
        if row:
            ver_liste(bot, [['resource_collectable_astralite', row.get('astralite', 0)],
                            ['resource_collectable_salvage-core', row.get('kurtarma', 0)],
                            ['resource_booty-key-astral', row.get('anahtar', 0)]], rng)


class Ebl(Mod):
    kimlik, ad = 'ebl', 'Eternal Black Light'
    E = PVE['ebl']
    harita = E['haritalar'][0]
    seviye = E['seviye']

    def girebilir(self, bot, now):
        return bot.seviye >= self.seviye and (_stok(bot).get(self.E['cpu'], 0) > 0 or bool(K.fiyat(self.E['cpu'])))

    def bedel(self, bot):
        return _harca_ya_da_al(bot, self.E['cpu'])

    def odenebilir(self, bot):
        return _var_ya_da_alinabilir(bot, self.E['cpu'])

    def dalgalar(self, bot):
        out = []
        for tur in range(3):                                 # en çok 3 tur (her tur x1,8): çoğu pilot ilkinde düşer
            k = self.E['carpan_tur'] ** tur
            out += [dalga(d['gruplar'], d.get('carpan', 1) * k, d.get('carpan', 1) * k) for d in self.E['dalgalar']]
        return out

    def bitir(self, bot, ulasilan, toplam, sure, rng):
        row = next((r for r in self.E['olum_odulu'] if r['en_az'] <= ulasilan <= r['en_cok']), self.E['olum_odulu'][-1]
                   if ulasilan > self.E['olum_odulu'][-1]['en_cok'] else None)
        if row:
            ver_liste(bot, [['resource_collectable_blacklight-shard', row.get('parca', 0)]], rng)


class Echoes(Mod):
    kimlik, ad = 'echoes', 'Deep Space Echoes'
    E = PVE['echoes']
    harita = E['haritalar'][0]
    seviye = E['seviye_sarti']
    sure_sinir = E['sure_sn']

    def seviye_no(self, bot):
        return min(len(self.E['seviyeler']) - 1, durum(bot, self.kimlik).get('gecilen', 0))

    def bedel(self, bot):
        return _harca_ya_da_al(bot, self.E['bilet'], self.E['bilet_fiyati'])

    def odenebilir(self, bot):
        return _var_ya_da_alinabilir(bot, self.E['bilet'], self.E['bilet_fiyati'])

    def dalgalar(self, bot):
        s = self.E['seviyeler'][self.seviye_no(bot)]
        k = 1 + self.E['olcek_seviye'] * s['seviye']
        return [dalga(d['gruplar'], k, k) for d in s['dalgalar']]

    def bitir(self, bot, ulasilan, toplam, sure, rng):
        if ulasilan < toplam:
            return
        st = durum(bot, self.kimlik)
        s = self.E['seviyeler'][self.seviye_no(bot)]
        t = self.E['tekrar']
        if st.get('gecilen', 0) <= self.seviye_no(bot):
            ver_liste(bot, s.get('ilk'), rng)
            st['gecilen'] = self.seviye_no(bot) + 1
        ver_liste(bot, [['currency_uridium', t['uridyum_taban'] + t['uridyum_seviye'] * s['seviye']],
                        ['ammunition_laser_ucb-100', t['ucb_taban'] + t['ucb_seviye'] * s['seviye']]], rng)


class Low(Mod):
    kimlik, ad = 'low', 'Battle of LoW'
    harita = LOW['harita']
    seviye = 10
    tip = 'tam'                                          # ödülü bitirmekte: yarısını geçemeyeceği koşuya girmez

    def girebilir(self, bot, now):
        return bot.seviye >= self.seviye and now - durum(bot, self.kimlik).get('son', 0) > 6 * 3600     # arada bir

    def dalgalar(self, bot):
        return [dalga([[[t, n]]]) for t, n in LOW['dalgalar']] + [dalga([[[LOW['boss'], 1]]])]


class VortexGreed(Mod):
    kimlik, ad = 'vog', 'Vortex of Greed'
    V = BUYUK['vortex']
    harita = V['harita']
    seviye = V['seviye']
    sure_sinir = V['seans_sn']

    def acik(self, now):
        if not _tk().is_active(self.V['etkinlik'], now):
            return False
        t = time.localtime(now)
        dk = t.tm_hour * 60 + t.tm_min
        return any(0 <= dk - (int(s[:2]) * 60 + int(s[3:])) < self.V['seans_sn'] // 60 for s in self.V['seanslar'])

    def girebilir(self, bot, now):
        st = durum(bot, self.kimlik)
        return bot.seviye >= self.seviye and st.get('seans') != time.strftime('%Y-%m-%d %H')

    def dalgalar(self, bot):
        uz = self.V['uzaylilar']
        n = self.V['seans_sn'] // self.V['dalga_sn']
        return [dalga([[[k, max(1, v.get('adet', 3))] for k, v in uz.items()]], tablo=uz) for _ in range(n)]

    def bitir(self, bot, ulasilan, toplam, sure, rng):
        from . import ganimet as GB
        st = durum(bot, self.kimlik)
        st['seans'] = time.strftime('%Y-%m-%d %H')
        hafta = time.strftime('%Y-%W')
        if st.get('hafta') != hafta:
            st.update(hafta=hafta, coin=0)
        coin = int(ulasilan * self.V['dalga_kutu'] * self.V['kutu_sc'] * 0.4)       # kutuların bir payını toplar, tahliye eder
        coin = min(coin, self.V['haftalik_sinir'] - st['coin'])
        if coin > 0:
            st['coin'] += coin
            GB.ver(bot, self.V['para'], coin)


class Mimesis(Mod):
    kimlik, ad = 'mimesis', 'Mimesis Mutiny'
    M = BUYUK['mimesis']
    harita = M['haritalar'].get(str(1)) if isinstance(M['haritalar'], dict) else M['haritalar'][0]
    sure_sinir = M['sure_sn']
    seviye = 10

    def acik(self, now):
        return _tk().is_active(self.M['etkinlik'], now) and time.localtime(now).tm_hour in self.M['saatler']

    def girebilir(self, bot, now):
        return bot.seviye >= self.seviye and durum(bot, self.kimlik).get('saat') != time.strftime('%Y-%m-%d %H')

    def bedel(self, bot):
        return _harca_ya_da_al(bot, self.M['anahtar'], self.M.get('anahtar_uridyum'))

    def odenebilir(self, bot):
        return _var_ya_da_alinabilir(bot, self.M['anahtar'], self.M.get('anahtar_uridyum'))

    def dalgalar(self, bot):
        tablo = self.M['turler']
        d = self.M['dalgalar']
        return [dalga([d['baslangic']], tablo=tablo)] + [dalga([g], tablo=tablo) for g in d['noktalar']]

    def bitir(self, bot, ulasilan, toplam, sure, rng):
        durum(bot, self.kimlik)['saat'] = time.strftime('%Y-%m-%d %H')
        puan = ulasilan * self.M['nokta_puani'] + (self.M['varis_bonusu'] if ulasilan >= toplam else 0)
        row = next((r for r in reversed(self.M['sefer_kademeleri']) if puan >= r['den']), None)
        if row:
            ver_liste(bot, row['oduller'], rng)


class DunyaPatronu(Mod):
    kimlik, ad = 'world_boss', 'World Boss'
    W = BUYUK['dunya_patronu']
    harita = W['harita']
    seviye = 12

    def acik(self, now):
        if not _tk().is_active(self.W['etkinlik'], now):
            return False
        hm = time.strftime('%H:%M', time.localtime(now))
        return any(a <= hm < b for a, b in self.W['pencereler'])

    def girebilir(self, bot, now):
        return bot.seviye >= self.seviye and durum(bot, self.kimlik).get('pencere') != time.strftime('%Y-%m-%d %H')

    def dalgalar(self, bot):
        f = self.W['npcler'].get('dreadfyre_fortress') or next(iter(self.W['npcler'].values()))
        pay = 0.02                                           # kalabalık sunucuda botun hasar payı
        return [(((f['hp'] + f['kalkan']) * pay), 0.0, {})]

    def bitir(self, bot, ulasilan, toplam, sure, rng):
        durum(bot, self.kimlik)['pencere'] = time.strftime('%Y-%m-%d %H')
        if ulasilan:
            g = bot.deger()['guc']
            kademe = self.W['kademe'][min(len(self.W['kademe']) - 1, int(g // 25))]
            ver_liste(bot, kademe['oduller'], rng)


class Apotheosis(Mod):
    kimlik, ad = 'apotheosis', 'Kristallon Apotheosis'
    A = BUYUK['kristallon_apotheosis']
    harita = A['harita']
    seviye = 12

    def acik(self, now):
        if not _tk().is_active(self.A['etkinlik'], now):
            return False
        hm = time.strftime('%H:%M', time.localtime(now))
        return any(a <= hm < b for a, b in self.A['pencereler'])

    def girebilir(self, bot, now):
        return bot.seviye >= self.seviye and durum(bot, self.kimlik).get('pencere') != time.strftime('%Y-%m-%d %H')

    def dalgalar(self, bot):
        p = self.A['patron']
        return [((p['hp'] + p['kalkan']) * 0.03, p['hasar'] * 0.6 * K.SAVAS['npc_isabet'] / K.NPC_ARALIK, {})]

    def bitir(self, bot, ulasilan, toplam, sure, rng):
        durum(bot, self.kimlik)['pencere'] = time.strftime('%Y-%m-%d %H')
        k = self.A['katilim']
        ver_liste(bot, k[min(len(k) - 1, int(bot.deger()['guc'] // 30))], rng)


class Labirent(Mod):
    kimlik, ad = 'labirent', 'Frozen Labyrinth'
    L = EKK['labirent']
    harita = (L['baslangic'] if isinstance(L.get('baslangic'), int) else (list(L['haritalar'])[0] if L.get('haritalar') else 0))
    seviye = 12

    def acik(self, now):
        if not _tk().is_active(self.L['etkinlik'], now):
            return False
        saatler = self.L['saatler_hafta_sonu'] if time.localtime(now).tm_wday >= 5 else self.L['saatler']
        return time.localtime(now).tm_hour in (saatler or range(24))

    def girebilir(self, bot, now):
        return bot.seviye >= self.seviye and now - durum(bot, self.kimlik).get('son', 0) > 3600

    def dalgalar(self, bot):
        uz = self.L['uzaylilar']
        uz = uz if isinstance(uz, list) else [dict(v, tur=k) for k, v in uz.items()]
        return [dalga([[[str(u.get('tur')), u.get('adet', 5)] for u in uz]]) for _ in range(4)]

    def bitir(self, bot, ulasilan, toplam, sure, rng):
        uz = self.L['uzaylilar']
        uz = uz if isinstance(uz, list) else list(uz.values())
        anahtar = sum((u.get('anahtar') or 0) * u.get('adet', 5) * 0.3 for u in uz if isinstance(u.get('anahtar'), (int, float)))
        if anahtar:
            ver_liste(bot, [['resource_key_labyrinth', int(anahtar * ulasilan)]], rng)


def _birlesik(dalgalar):
    ehp = sum(d[0] for d in dalgalar)
    dps = max([d[1] for d in dalgalar] or [0])
    odul = {}
    for d in dalgalar:
        for k, v in d[2].items():
            odul[k] = odul.get(k, 0) + v
    return ehp, dps, odul


def _kapilar():
    import etkinlik_kapi as EKP
    return [EtkinlikKapisi(k, g) for k, g in EKP.GATES.items()]


MODLAR = []


def modlar():
    if not MODLAR:
        MODLAR.extend(_kapilar() + [Voyagers(), Trinity(), Astral(), Ebl(), Echoes(), Low(), VortexGreed(), Mimesis(),
                                    DunyaPatronu(), Apotheosis(), Labirent()])
    return MODLAR


# ------------------------------------------------------------------------------------------------------------ koşu
def tahmin(bot, mod, dalgalar=None):
    """Koşu tahmini -> (ulaşılan dalga, toplam, süre sn, öldürme ödülleri). Kapıdaki yöntem: en iyi cephane, aynı anda vuranlar,
    dalga arasında onarım; ölümler can hakkını bitirince durur; süre sınırı varsa orada biter."""
    from . import silah as SL
    dalgalar = mod.dalgalar(bot) if dalgalar is None else dalgalar
    d = bot.deger()
    s = SL.stok(bot)
    carp = max([SL.carpan(c) for c in ('ammunition_laser_ucb-100', SL.MCB50, SL.MCB25, SL.LCB) if s.get(c, 0) > 1000] or [1])
    dps = max(1.0, d['dps'] * carp * 1.15)
    sure = olum = 0.0
    odul = {}
    ulasilan = 0
    for ehp, gelen, od in dalgalar:
        t = ehp / dps
        if mod.sure_sinir and sure + t > mod.sure_sinir:
            break
        olum += t * gelen / max(1.0, d['ehp'] * 3)
        if olum >= mod.can:
            break
        sure += t
        ulasilan += 1
        for k, v in od.items():
            odul[k] = odul.get(k, 0) + v
    return ulasilan, len(dalgalar), sure, odul


def deger(bot, mod):
    """Modun bota beklenen değeri (kredi/saat kabaca): öldürme ödülleri ve bitiş, ilerleme payıyla; geçemeyeceği mod 0."""
    ul, top, sure, odul = tahmin(bot, mod)
    if top == 0 or ul == 0 or (mod.tip in ('tam', 'kosu') and ul < top * 0.5):
        return 0.0                                       # ilerlemeyle ödül vermeyen modun yarısını geçemiyorsa girmez
    v = odul.get('kredi', 0) + odul.get('uridyum', 0) * 100 + odul.get('ep', 0) * 0.3 + odul.get('onur', 0) * 3
    v += 200000 * ul / top                                    # bitiş ödülleri (eşya, kaynak, anahtar) kabaca
    return v / max(600.0, sure) * 3600


def adaylar(bot, now):
    """Şu an girilebilecek modlar (açık, koşulu sağlanan, en az ilk dalgayı geçeceği)."""
    if not bot.izin.get('modlar', True):
        return []
    out = []
    for m in modlar():
        try:
            if m.acik(now) and m.girebilir(bot, now) and m.odenebilir(bot) and deger(bot, m) > 0:
                out.append(m)
        except (KeyError, TypeError, ValueError, IndexError):
            continue                                       # verisi beklenmedik biçimde olan mod: atla
    return out


def kos(bot, mod, rng=random):
    """Koşunun sonucu -> (ulaşılan, toplam, süre, öldürme ödülleri); süre gerçek koşu payıyla uzatılır."""
    dalgalar = mod.dalgalar(bot)
    ul, top, sure, odul = tahmin(bot, mod, dalgalar)
    if ul < top and rng.random() < 0.3:
        ul = min(top, ul + 1)                               # şans
    return ul, top, sure * rng.uniform(1.1, 1.5) + 90, odul


# ------------------------------------------------------------------------------------------------------------ pasif
def dispatch(bot, now):
    """Dispatch: zengin bot toplayıcı gönderir (kredi ücreti), süresi dolunca listesinden 4 ödül (taban adetlerle)."""
    if not bot.izin.get('modlar', True) or bot.seviye < 10:
        return
    st = durum(bot, 'dispatch')
    if st.get('bitis') and now >= st['bitis']:
        t = DISP['toplayicilar'][st['tur']]
        liste = DISP['oduller'].get(t['kod']) or []
        carp = 1 + (t.get('kademe', 1) - 1) * DISP.get('kademe_artisi', 0.5)
        if _tk().is_active('dispatch_gunu', now):
            carp *= DISP.get('dispatch_gunu_carpani', 2)
        for loot in random.sample(liste, min(DISP['odul_sayisi'], len(liste))):
            n = DISP['taban_adet'].get(loot, 1)
            ver_liste(bot, [[loot, n if loot in DISP['tekil'] else int(n * carp)]])
        st.pop('bitis')
        bot.ist('dispatch')
    if st.get('bitis'):
        return
    uygun = [(k, t) for k, t in DISP['toplayicilar'].items()
             if all(bot.k[{'currency_credits': 'kredi', 'currency_uridium': 'uridyum'}.get(p, 'kredi')] > n * (3 + 3 * bot.o('tutumluluk'))
                    for p, n in t.get('ucret', {}).items())]
    if not uygun:
        return
    k, t = max(uygun, key=lambda x: x[1].get('kademe', 1))
    for p, n in t.get('ucret', {}).items():
        bot.ode('C' if p == 'currency_credits' else 'U', n)
    st.update(tur=k, bitis=now + t['sure_sn'])


def galaxy_trek(bot, now):
    """Galaxy Trek: etkinlik sürerken günlük FTL anahtarlarıyla keşif (olaylar tablosundan ödül)."""
    g = EK['galaxy_trek']
    if not bot.izin.get('modlar', True) or not _tk().is_active('galaxy_trek', now):
        return
    st = durum(bot, 'galaxy_trek')
    if st.get('gun') == gun():
        return
    st['gun'] = gun()
    olaylar = g.get('olaylar')
    rows = olaylar if isinstance(olaylar, list) else list((olaylar or {}).values())
    for _ in range(int(g.get('gunluk', 10)) // max(1, int(g.get('maliyet', 1)))):
        r = random.choice(rows) if rows else None
        if isinstance(r, dict):
            ver_liste(bot, r.get('oduller') or r.get('esyalar') or [])
        elif isinstance(r, list) and r and isinstance(r[0], str):
            ver_liste(bot, [r[:2]])
    bot.ist('galaxy_trek')


def pasif(bot, now):
    dispatch(bot, now)
    galaxy_trek(bot, now)
