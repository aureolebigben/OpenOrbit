"""Teknoloji eşyaları ve roket fırlatıcısı (oyuncu gibi: Assembly tarifleri, savas_esya, teknoloji.py).

Teknoloji eşyaları Assembly'nin para tarifleriyle üretilir (data/tarifler.json: Backup Shields ve Battle Repair Bot 2.800 U,
Chain Impulse 1.800 U, Energy Leech 6.500 U, Precision Targeter 250 U); etkinlik kaynağı isteyen tarifler botlara kapalı. Stok
bot.k['stok']'ta. Kullanım:
  somut  canı %40'ın altına inince Backup Shields (kalkan) ya da Battle Repair Bot (onarım); yakında 3+ uzaylı varken Chain Impulse
  soyut  PvP karşılaşmasında Backup Shields ve Battle Repair Bot güç katar; dayanıklı uzaylıda Precision Targeter (roketler hep
         isabet) ve Energy Leech (verim)
Roket fırlatıcısı (HST-1 kredi, HST-2 uridyum): salvo kapasitesi 3/5, roket başına 1 sn dolum; ECO-10 (kredi) ya da HSTRM-01
(uridyum) ile dayanıklı uzaylıda ve PvP'de.
"""
from . import katalog as K

TEK = K.ESYA['teknoloji']['esyalar']
TARIF = {'tech_backup-shields': ('U', 2800), 'tech_battle-repair-bot': ('U', 2800), 'tech_chain-impulse': ('U', 1800),
         'tech_energy-leech': ('U', 6500), 'tech_precision-targeter': ('U', 250)}
FIRCATICI = K.ESYA['savas_esyalari']['fircatici']
FCEPHANE = K.ESYA['savas_esyalari']['fircatici_cephane']
HST = ('equipment_weapon_rocketlauncher_hst-1', 'equipment_weapon_rocketlauncher_hst-2')
FROKET = ('ammunition_rocketlauncher_eco-10', 'ammunition_rocketlauncher_hstrm-01')


def _stok(bot):
    from . import silah as SL
    return SL.stok(bot)


def izinli(bot):
    return bot.izin.get('teknoloji', True)


# ------------------------------------------------------------------------------------------------------------ üretim
def uret(bot):
    """Assembly: stokta olmayan işe yarar teknoloji eşyalarını para tarifiyle üretir (8. seviyeden, uridyumu yetiyorsa)."""
    if not izinli(bot) or bot.seviye < 8:
        return {}
    s = _stok(bot)
    t = bot.o('tutumluluk')
    istek = ['tech_precision-targeter'] if bot.izin.get('roket', True) else []
    if bot.izin.get('pvp', True) and bot.o('saldirganlik') + bot.o('risk') > 0.8:
        istek += ['tech_backup-shields', 'tech_battle-repair-bot']
    if bot.seviye >= 12:
        istek += ['tech_chain-impulse', 'tech_energy-leech']
    out = {}
    for e in istek:
        para, fiyat = TARIF[e]
        fiyat *= bot.oa.carpan('magaza_fiyat')
        if s.get(e, 0) < 2 and bot.k['uridyum'] > fiyat * (3 + 3 * t) and bot.ode(para, fiyat):
            s[e] = s.get(e, 0) + 1
            out[e] = 1
            bot.ist('assembly')
    return out


def kullan(bot, e):
    s = _stok(bot)
    if s.get(e, 0) <= 0 or not izinli(bot):
        return False
    if not bot.oa.get('sonsuz_teknoloji'):
        s[e] -= 1
        if not s[e]:
            del s[e]
    bot.ist('teknoloji')
    return True


def pvp_carpani(bot):
    """PvP karşılaşmasında savunma teknolojileri: her biri bir kez harcanır."""
    k = 1.0
    for e, v in (('tech_backup-shields', 0.15), ('tech_battle-repair-bot', 0.12)):
        if _stok(bot).get(e, 0) > 0 and kullan(bot, e):
            k += v
    return k


# ------------------------------------------------------------------------------------------------------------ fırlatıcı
def fircatici(bot):
    f = bot.k['ekip'].get('fircatici')
    return f if f in FIRCATICI['turler'] else None


def froket_sec(bot):
    if not bot.izin.get('roket', True) or not fircatici(bot):
        return None
    s = _stok(bot)
    return next((r for r in reversed(FROKET) if s.get(r, 0) > 0), None)


def salvo(bot):
    """(kapasite, salvo arası sn)."""
    f = fircatici(bot)
    kap = FIRCATICI['turler'][f]['kapasite'] if f else 0
    return kap, kap * FIRCATICI['dolum_sn'] + 1.3


def fircatici_dps(bot, roket):
    kap, ara = salvo(bot)
    return FCEPHANE[roket]['hasar'] * kap / ara if roket and kap else 0.0


def adaylar(bot):
    """Alışveriş adayları: fırlatıcı (roket izni, 8./10. seviyeden; faydası güç payı)."""
    if not bot.izin.get('roket', True) or fircatici(bot) == HST[1]:
        return []
    guc = bot.deger()['guc']
    out = []
    for f, lv, pay in ((HST[0], 8, 0.12), (HST[1], 10, 0.25)):
        fi = K.fiyat(f)
        if bot.seviye >= lv and fi and fircatici(bot) != f:
            out.append((guc * pay * (0.6 + 0.8 * bot.o('saldirganlik')), fi[0], fi[1], f))
    return out


def ikmal(bot):
    """Fırlatıcı roketi: HSTRM-01 (uridyum) zenginse, yoksa ECO-10 (kredi) -> alınan."""
    if not fircatici(bot) or not bot.izin.get('roket', True) or not bot.izin.get('magaza', True):
        return {}
    s = _stok(bot)
    if sum(s.get(r, 0) for r in FROKET) >= 50:
        return {}
    t = bot.o('tutumluluk')
    for r, para, esik in ((FROKET[1], 'uridyum', 20000), (FROKET[0], 'kredi', 2000000)):
        fi = K.fiyat(r)
        if fi and bot.k[para] > esik * (1 + t):
            n = int(min(200, bot.k[para] * 0.1 // fi[1]))
            if n > 0 and bot.ode(fi[0], n * fi[1]):
                s[r] = s.get(r, 0) + n
                return {r: n}
    return {}
