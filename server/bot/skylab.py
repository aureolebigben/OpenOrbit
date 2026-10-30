"""Botların Skylab'ı: oyuncununkiyle aynı tablolar ve kurallar (data/skylab.json; oyunun skylab.py'si), soyut ve tembel hesap.

Durum bot.k['skylab'] = {'mod': {modül: seviye}, 'depo': {cevher: adet}, 'son': an, 'insa': [modül, bitiş] | None, 'tasima': an}
  üretim     toplayıcılar ham cevher, Xeno modülü Xenomit, rafineriler depodaki girdilerden sırayla (Prometid/Duranium ->
             Promerium -> Seprom); depo sınırı depo modülünün seviyesinden; çalışan modüllerin enerjisi güneşi aşamaz (aşan
             modül en son kurulan sırayla kapalı sayılır)
  yükseltme  kredi + depodan P/E/T kaynağı, süreli (tek iş); taban modülü tavan, Promerium rafinerisi Xeno modülünü geçemez
  taşıma     cevher başına 7,2 sn (saatte 500): bot istasyonda satış yaparken birikmiş taşıma hakkı kadar cevher gemiye gelir
             (değerliler önce), satılır ya da laboratuvara gider (lab.py)
Yükseltme sırası gerçek oyuncunun sırası: toplayıcılar, enerji yetmezse güneş, depo dolarsa depo, sonra rafineriler ve Xeno.
"""
import json, os

from . import katalog as K

S = json.load(open(os.path.join(K.HERE, 'data', 'skylab.json'), encoding='utf8'))
ROW = S['seviyeler']
MOD = S['moduller']
COSTS = S['maliyetler']
ORES = S['cevherler']                       # skylab cevheri -> [ad, depo sütunu, kargo cevheri]
COLLECTORS = S['toplayicilar']              # modül -> cevher
REFINERIES = S['rafineriler']               # modül -> [ürün, girdiler, sütun]
REFINE_ORDER = ('PROMETID_REFINERY', 'DURANIUM_REFINERY', 'PROMERIUM_REFINERY', 'SEPROM_REFINERY')
XENO = S['xeno']
TASIMA_SN = S['tasima']['birim_sn']
KAYNAK = ('1', '2', '3')                    # yükseltmenin kaynakları: Prometium, Endurium, Terbium (her birinden 'kaynak' kadar)
ADIM_SN = 1800.0
SIRA = ('PROMETIUM_COLLECTOR', 'ENDURIUM_COLLECTOR', 'TERBIUM_COLLECTOR', 'PROMETID_REFINERY', 'DURANIUM_REFINERY',
        'XENO_MODULE', 'PROMERIUM_REFINERY', 'SEPROM_REFINERY')


def row(lv):
    return ROW[max(1, min(len(ROW), lv)) - 1]


def durum(bot, now):
    st = bot.k.get('skylab')
    if st is None:
        st = bot.k['skylab'] = {'mod': {m: lv for m, (lv, _) in S['baslangic']['moduller'].items()},
                                'depo': {o: float(n) for o, n in S['baslangic']['depo'].items()}, 'son': now, 'insa': None,
                                'tasima': now}
    return st


def seviye(st, m):
    return st['mod'].get(m, 0)


def enerji(m, lv):
    return row(lv)['enerji'] if lv > 0 and m != 'SOLAR_MODULE' else 0


def calisanlar(st):
    """Enerjisi yeten modüller (güneş, taban, depo, taşıma hep açık; ötekiler SIRA'yla, güneş biterse sonrakiler kapalı)."""
    gunes = row(seviye(st, 'SOLAR_MODULE'))['gunes']
    harcanan = sum(enerji(m, seviye(st, m)) for m in ('BASE_MODULE', 'STORAGE_MODULE'))
    acik = set()
    for m in SIRA:
        e = enerji(m, seviye(st, m))
        if seviye(st, m) > 0 and harcanan + e <= gunes:
            acik.add(m)
            harcanan += e
    return acik


def kapasite(st, ore):
    return row(seviye(st, 'STORAGE_MODULE'))['depo'][ORES[ore][1]]


def uretim(st, m):
    lv = seviye(st, m)
    if lv <= 0:
        return 0
    if m in COLLECTORS:
        return row(lv)['uretim']['ham']
    if m in REFINERIES:
        return row(lv)['uretim'][REFINERIES[m][2]]
    if m == 'XENO_MODULE':
        return row(lv)['uretim'][XENO['sutun']]
    return 0


def uret(st, saat, carpan=1.0):
    dep = st['depo']
    acik = calisanlar(st)

    def ekle(ore, n):
        dep[ore] = min(kapasite(st, ore), dep.get(ore, 0) + n)
    for m, ore in COLLECTORS.items():
        if m in acik:
            ekle(ore, uretim(st, m) * saat * carpan)
    if 'XENO_MODULE' in acik:
        ekle(XENO['cevher'], uretim(st, 'XENO_MODULE') * saat * carpan)
    for m in REFINE_ORDER:
        if m not in acik:
            continue
        cikti, girdi, _ = REFINERIES[m]
        n = min([uretim(st, m) * saat * carpan, kapasite(st, cikti) - dep.get(cikti, 0)] + [dep.get(o, 0) / k for o, k in girdi.items()])
        if n <= 0:
            continue
        for o, k in girdi.items():
            dep[o] = max(0.0, dep.get(o, 0) - n * k)
        ekle(cikti, n)


def ilerlet(bot, now):
    """Son hesaptan bu yana üretim ve biten yükseltme (soyut, adım adım) -> durum."""
    st = durum(bot, now)
    t = max(st['son'], now - 24 * 3600)                 # uzun boşlukta en çok bir günlük üretim (telafi sınırı gibi)
    k = bot.oa.carpan('skylab_uretim')
    while t < now:
        bitis = st['insa'][1] if st.get('insa') else None
        nxt = min(now, t + ADIM_SN, bitis if bitis and bitis > t else now)
        uret(st, (nxt - t) / 3600.0, k)
        t = nxt
        if st.get('insa') and st['insa'][1] <= t:
            m = st['insa'][0]
            st['mod'][m] = seviye(st, m) + 1
            st['insa'] = None
            bot.olay('skylab', modul=m, seviye=st['mod'][m])
    st['son'] = now
    return st


# ------------------------------------------------------------------------------------------------------------ yükseltme
def maliyet(st, m):
    g, lv = MOD[m]['grup'], seviye(st, m)
    if not g or lv >= MOD[m]['azami']:
        return None
    return COSTS[g][lv]


def yukseltilebilir(st, m):
    if maliyet(st, m) is None or st.get('insa'):
        return False
    if m != 'BASE_MODULE' and seviye(st, m) + 1 > seviye(st, 'BASE_MODULE'):
        return False
    if m == 'PROMERIUM_REFINERY' and seviye(st, m) + 1 > seviye(st, 'XENO_MODULE'):
        return False
    return True


def siradaki(st):
    """Gerçek oyuncunun sırası: enerji yetmiyorsa güneş, depo doluysa depo; taban tavana dayandıysa taban; sonra SIRA'daki en
    düşük seviyeli (toplayıcılar önce)."""
    gunes = row(seviye(st, 'SOLAR_MODULE'))['gunes']
    ihtiyac = sum(enerji(m, seviye(st, m)) for m in st['mod'] if m != 'SOLAR_MODULE')
    if ihtiyac > gunes * 0.9 and yukseltilebilir(st, 'SOLAR_MODULE'):
        return 'SOLAR_MODULE'
    if any(st['depo'].get(o, 0) > 0.9 * kapasite(st, o) for o in st['depo']) and yukseltilebilir(st, 'STORAGE_MODULE'):
        return 'STORAGE_MODULE'
    adaylar = [m for m in SIRA if yukseltilebilir(st, m)]
    if not adaylar:
        return 'BASE_MODULE' if yukseltilebilir(st, 'BASE_MODULE') else None
    m = min(adaylar, key=lambda m: (seviye(st, m) + (2 if m in REFINERIES or m == 'XENO_MODULE' else 0), SIRA.index(m)))
    if seviye(st, m) >= seviye(st, 'BASE_MODULE') and yukseltilebilir(st, 'BASE_MODULE'):
        return 'BASE_MODULE'
    return m


def yatirim(bot, now):
    """Skylab'ı yükseltir (izin 'skylab', 3. seviyeden; tek iş): sıradaki modülün kredisi bütçeye (kredinin bir payı, tutumlu
    daha çok yatırır: uzun vadeli kazanç) ve kaynağı depoya yetiyorsa -> başlatılan modül ya da None."""
    if not bot.izin.get('skylab', True) or bot.seviye < 3:
        return None
    st = ilerlet(bot, now)
    m = siradaki(st)
    c = maliyet(st, m) if m else None
    if not c:
        return None
    kredi = c['kredi'] * bot.oa.carpan('hizmet_fiyat', 'skylab')
    if bot.k['kredi'] < kredi * (2.5 - bot.o('tutumluluk') - 0.5 * bot.o('sabir')) or any(st['depo'].get(o, 0) < c['kaynak'] for o in KAYNAK):
        return None
    if not bot.ode('C', kredi):
        return None
    for o in KAYNAK:
        st['depo'][o] -= c['kaynak']
    st['insa'] = [m, now + c['sure_sn']]
    bot.ist('skylab_yukseltme')
    return m


# ------------------------------------------------------------------------------------------------------------ taşıma
DEGER = {'14': 0, '13': 1, '4': 2, '11': 3, '12': 4, '3': 5, '2': 6, '1': 7}       # önce değerli: Seprom, Promerium, Xenomit …


def tasi(bot, now, en_cok):
    """İstasyonda: son taşımadan bu yana hakkı kadar (saatte 3600/7,2) cevher depodan kargoya (değerliler önce; en_cok birim)
    -> taşınan {kargo cevheri: adet}."""
    if not bot.izin.get('skylab', True):
        return {}
    st = ilerlet(bot, now)
    hak = min(en_cok, (now - st.get('tasima', now)) / TASIMA_SN)
    st['tasima'] = now
    out = {}
    for ore in sorted(st['depo'], key=lambda o: DEGER.get(o, 9)):
        n = int(min(hak, st['depo'][ore]))
        if n <= 0:
            continue
        st['depo'][ore] -= n
        hak -= n
        kargo = ORES[ore][2]
        out[kargo] = out.get(kargo, 0) + n
    for t, n in out.items():
        bot.k['kargo'][str(t)] = bot.k['kargo'].get(str(t), 0) + n
    if out:
        bot.ist('skylab_tasima', sum(out.values()))
    return out
