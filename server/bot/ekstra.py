"""Ekstralar ve CPU'lar: onarım robotları, R0K-T01, kargo CPU'su, HM-7, atlama, gizlenme, Insta-Shield, Smart Bomb, ekstra yuvası.

Takılanlar bot.k['ekip']['ekstra'] {loot: kalan hak (haklıysa) ya da 1}; yuva sayısı gemininki (esyalar.json gemiler.extra) +
SLE CPU'larının ek_yuva'sı. Alışveriş adayları (alisveris._adaylar): her ekstranın bota faydası güç puanının bir payı olarak,
kişiliğe, seviyeye ve izinlere göre (gerçek oyuncunun öncelik sırası: önce onarım robotu, sonra işine yarayan CPU'lar).
Etkiler: govde (onarım), silah (roket beklemesi), katalog (kargo), hedefler/satis (HM-7), soyut (atlama, gizlenme, PvP).
"""
from . import katalog as K

EKSTRA = K.ESYA['ekstralar']
ONARIM = K.ESYA['onarim_robotlari']
SIRA = ('equipment_extra_repbot_rep-s', 'equipment_extra_repbot_rep-1', 'equipment_extra_repbot_rep-2',
        'equipment_extra_repbot_rep-3', 'equipment_extra_repbot_rep-4')
ROKT = 'equipment_extra_cpu_rok-t01'
KARGO = 'equipment_extra_cpu_g3x-crgo-x'
HM7 = 'equipment_extra_hmd-07'
JP1, JP2 = 'equipment_extra_cpu_jp-01', 'equipment_extra_cpu_jp-02'
GIZLE = ('equipment_extra_cpu_cl04k-xs', 'equipment_extra_cpu_cl04k-m', 'equipment_extra_cpu_cl04k-xl')
ISH, SMB = 'equipment_extra_cpu_ish-01', 'equipment_extra_cpu_smb-01'
AIM1, AIM2 = 'equipment_extra_cpu_aim-01', 'equipment_extra_cpu_aim-02'
SLE = ('equipment_extra_cpu_sle-01', 'equipment_extra_cpu_sle-02', 'equipment_extra_cpu_sle-03', 'equipment_extra_cpu_sle-04')


def takili(bot):
    return bot.k['ekip'].setdefault('ekstra', {})


def var(bot, loot):
    return takili(bot).get(loot, 0) > 0


def yuva(bot):
    g = K.ESYA['gemiler'].get(bot.k['ekip']['gemi']) or {}
    return int(g.get('extra') or 1) + max((EKSTRA[s]['ek_yuva'] for s in SLE if var(bot, s)), default=0)


def hak(loot):
    return (EKSTRA.get(loot) or {}).get('hak', 1)


def kullan(bot, loot):
    """Haklı ekstradan bir hak harcar -> harcandı mı (hak bitince yuvadan çıkar)."""
    t = takili(bot)
    if t.get(loot, 0) <= 0:
        return False
    t[loot] -= 1
    if t[loot] <= 0 and 'hak' in (EKSTRA.get(loot) or {}):
        del t[loot]
        bot.ekip_degisti()
    return True


def onarim_seviyesi(bot):
    """Takılı en iyi onarım robotu 0 (yok) .. 5 (REP-4)."""
    return max((i + 1 for i, r in enumerate(SIRA) if var(bot, r)), default=0)


def onarim_sn(bot):
    """Tam onarım süresi (sn; yoksa None)."""
    for r in reversed(SIRA):
        if var(bot, r):
            v = ONARIM[r]
            return v.get('tam_onarim_sn') or (bot.deger()['can'] / max(1, v.get('dakikada_hp', 1000)) * 60)
    return None


def kargo_carpani(ekip):
    return EKSTRA[KARGO]['kargo_carpan'] if (ekip.get('ekstra') or {}).get(KARGO) else 1.0


# ------------------------------------------------------------------------------------------------------------ alışveriş
def fayda(bot, loot):
    """Ekstranın bota faydası: güç puanının payı (0: almaz)."""
    iz, lv, o = bot.izin, bot.seviye, bot.o
    if loot in SIRA:
        i = SIRA.index(loot) + 1
        return max(0.0, 0.04 * i - 0.04 * onarim_seviyesi(bot)) * (0.6 + 0.6 * (1 - o('risk')))
    if loot == ROKT:
        return (0.06 + 0.08 * o('saldirganlik')) if iz.get('roket', True) and lv >= 6 else 0.0
    if loot == KARGO:
        return 0.08 if iz.get('kargo', True) and lv >= 5 else 0.0
    if loot == HM7:
        return 0.1 if iz.get('kargo', True) and lv >= 8 else 0.0
    if loot in (JP1, JP2):
        return 0.05 + 0.04 * o('sabir') if lv >= 5 and not var(bot, JP1) and not var(bot, JP2) else 0.0
    if loot in GIZLE:
        return 0.05 * (1 - o('risk')) if lv >= 8 and iz.get('pvp', True) and not any(var(bot, g) for g in GIZLE) else 0.0
    if loot in (ISH, SMB):
        return 0.05 * o('saldirganlik') if lv >= 12 and iz.get('pvp', True) else 0.0
    if loot in (AIM1, AIM2):
        sky = (bot.k.get('skylab') or {}).get('mod', {}).get('XENO_MODULE', 0)
        return 0.06 * o('rekabet') if lv >= 14 and sky >= 3 and not var(bot, AIM1) and not var(bot, AIM2) else 0.0
    if loot in SLE:
        bos = yuva(bot) - len(takili(bot))
        ek = EKSTRA[loot]['ek_yuva'] - max((EKSTRA[s]['ek_yuva'] for s in SLE if var(bot, s)), default=0)
        return 0.02 * ek if bos <= 0 and ek > 0 else 0.0
    return 0.0


def adaylar(bot):
    """Alışveriş adayları [(güç artışı, para, fiyat, loot)]: boş yuva varsa (ya da yuva CPU'su) faydalı ve sahip olunmayan ekstralar."""
    if not bot.izin.get('ekstra', True):
        return []
    guc = bot.deger()['guc']
    bos = yuva(bot) - len(takili(bot))
    out = []
    for loot in list(SIRA) + [ROKT, KARGO, HM7, JP1, JP2, GIZLE[1], ISH, SMB, AIM2, AIM1] + list(SLE):
        if var(bot, loot) or (bos <= 0 and loot not in SLE and loot not in SIRA):
            continue
        f = K.fiyat(loot)
        p = fayda(bot, loot)
        if f and f[1] > 0 and p > 0:
            out.append((guc * p, f[0], f[1], loot))
    return out


def tak(bot, loot):
    """Satın alınan ekstra takılır; onarım robotu eskisinin yerine (tek yuva); yuva doluysa en az faydalısı çıkar."""
    t = takili(bot)
    if loot in SIRA:
        for r in SIRA:
            t.pop(r, None)
    elif loot in SLE:
        for s in SLE:
            t.pop(s, None)
    if len(t) >= yuva(bot) and loot not in SLE:
        dus = min(t, key=lambda x: fayda(bot, x) if x not in SIRA else 1.0)
        del t[dus]
    t[loot] = hak(loot)
    bot.ekip_degisti()


# ------------------------------------------------------------------------------------------------------------ kullanım
def atlama(bot, hedef):
    """Atlama CPU'su bu yolculuğu kısaltır mı: hedef üs (X-1), CPU'nun izin verdiği haritadan, hakkı var -> kullanılan CPU ya da None."""
    if hedef != K.ev(bot.firma) or not bot.izin.get('ekstra', True):
        return None
    import harita as H
    ad = H.name(bot.harita)
    sinif = H.map_class(bot.harita)
    for cpu in (JP2, JP1):
        if not var(bot, cpu):
            continue
        a = EKSTRA[cpu]['atlama']
        if 'haritalar' in a and sinif not in a['haritalar']:
            continue
        if any(ad.startswith(p) for p in a.get('yasak', ())):
            continue
        return cpu
    return None


def gizlen(bot):
    """Güçlü düşmandan gizlenme CPU'suyla kaçar -> kullanıldı mı."""
    if not bot.izin.get('ekstra', True):
        return False
    return any(kullan(bot, g) for g in GIZLE if var(bot, g))


def pvp_carpani(bot):
    """Insta-Shield ve Smart Bomb PvP'de güce katkı."""
    return 1.0 + 0.12 * var(bot, ISH) + 0.1 * var(bot, SMB)
