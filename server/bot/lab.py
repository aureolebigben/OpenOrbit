"""Arıtma ve laboratuvar: kargodaki ham cevherden Prometid, Duranium, Promerium arıtıp lazere, rokete ve kalkana yüklemek
(oyuncu gibi: magaza.upgrade, esyalar.json laboratuvar).

Tarifler (birim başına): Prometid 20 Prometium + 10 Endurium, Duranium 10 Endurium + 20 Terbium, Promerium 10 Prometid + 10
Duranium + 1 Xenomit. Yükleme: lazer (0) ve roket (1) Prometid +%15, Promerium +%30, Seprom +%60; kalkan (2) Duranium +%10,
Promerium +%20. Bir birim cevher lazerde 10 mermi, rokette 10 roket, kalkanda 1 dakika yeter.
bot.k['lab'] {parça: [cevher, kalan]}: kalan mermi / roket / saniye. Aynı cevher eklenir, başka cevher öncekini siler (oyundaki gibi).

Kim yükseltir: hırslı, rekabetçi ya da tutumsuz botlar (izin 'lab', 4. seviyeden); tutumlu bot cevherini satar. Arıtılmış cevher
satışta ham hâlinden ucuz olduğu için yalnız yükleyeceği kadar arıtılır.
"""
from . import katalog as K

LAB = K.ESYA['laboratuvar']
TARIF = {int(u): {int(t): n for t, n in g.items()} for u, g in LAB['tarifler'].items()}      # 4, 5, 6
BONUS = {int(p): {int(c): v for c, v in g.items()} for p, g in LAB['bonuslar'].items()}
BIRIM = {int(p): v for p, v in LAB['birim'].items()}
LAZER, ROKET, KALKAN = 0, 1, 2
PROMETID, DURANIUM, PROMERIUM = 4, 5, 6


def yuklu(bot):
    return bot.k.setdefault('lab', {})


def bonus(bot, parca):
    """Parçanın şimdiki laboratuvar bonusu (0: yüklü değil ya da bitti)."""
    v = yuklu(bot).get(str(parca))
    return BONUS[parca].get(int(v[0]), 0.0) if v and v[1] > 0 else 0.0


def harca(bot, parca, n):
    """Yükten n birim (mermi, roket ya da saniye) harcar; biterse yük kalkar."""
    y = yuklu(bot)
    v = y.get(str(parca))
    if not v:
        return
    v[1] -= n
    if v[1] <= 0:
        del y[str(parca)]


def _kargo(bot):
    return bot.k.setdefault('kargo', {})


def aritir(bot, urun, adet):
    """Kargodaki girdilerden en çok adet birim arıtır -> arıtılan."""
    kargo = _kargo(bot)
    tarif = TARIF[urun]
    n = min([adet] + [kargo.get(str(t), 0) // g for t, g in tarif.items()])
    if n <= 0:
        return 0
    for t, g in tarif.items():
        kargo[str(t)] -= g * n
        if kargo[str(t)] <= 0:
            del kargo[str(t)]
    kargo[str(urun)] = kargo.get(str(urun), 0) + n
    bot.ist('aritma', n)
    return n


def yukle(bot, parca, cevher, adet):
    """Kargodan parçaya adet birim cevher yükler (aynı cevher eklenir, başkası öncekini siler) -> yüklenen."""
    kargo = _kargo(bot)
    adet = min(adet, kargo.get(str(cevher), 0))
    if adet <= 0:
        return 0
    kargo[str(cevher)] -= adet
    if kargo[str(cevher)] <= 0:
        del kargo[str(cevher)]
    y = yuklu(bot)
    sure = adet * BIRIM[parca] * (LAB.get('dakika_sn', 60) if parca >= 2 else 1)
    v = y.get(str(parca))
    y[str(parca)] = [cevher, (v[1] if v and int(v[0]) == cevher else 0) + sure]
    bot.ist('lab_yukleme', adet)
    return adet


def yukseltir_mi(bot):
    if not bot.izin.get('lab', True) or bot.seviye < 4:
        return False
    return bot.o('hirs') * 0.5 + bot.o('rekabet') * 0.3 + (1 - bot.o('tutumluluk')) * 0.4 > 0.55


def _promerium_iyi_mi(bot, ihtiyac):
    """Kargoyla Promerium yolu (+%30) Prometid yolundan (+%15) çok mu kazandırır (bonus x mermi): kargonun kopyasında dener."""
    asil, sayac = dict(_kargo(bot)), bot.k['istat'].get('aritma', 0)
    try:
        aritir(bot, PROMETID, ihtiyac * 10)
        aritir(bot, DURANIUM, ihtiyac * 10)
        prom = aritir(bot, PROMERIUM, ihtiyac)
        bot.k['kargo'] = dict(asil)
        prometid = aritir(bot, PROMETID, ihtiyac)
    finally:
        bot.k['kargo'] = asil
        bot.k['istat']['aritma'] = sayac
    return BONUS[LAZER][PROMERIUM] * prom > BONUS[LAZER][PROMETID] * prometid


def karar(bot, saatlik_mermi):
    """Kargodaki cevherle laboratuvar: yükü azaldıysa arıtıp yükler (lazer önce, sonra kalkan ve roket). Satıştan önce çağrılır:
    kalan cevher satılır."""
    if not yukseltir_mi(bot):
        return
    kargo = _kargo(bot)
    hedef = saatlik_mermi * (1 + bot.o('hirs'))                     # yaklaşık bir-iki saatlik mermi
    v = yuklu(bot).get(str(LAZER))
    if not v or v[1] < hedef * 0.3:
        ihtiyac = int(hedef / BIRIM[LAZER]) + 1
        if kargo.get('3', 0) > 0 and _promerium_iyi_mi(bot, ihtiyac):     # Xenomit varsa ve daha çok kazandırıyorsa Promerium (+%30)
            aritir(bot, PROMETID, ihtiyac * 10)
            aritir(bot, DURANIUM, ihtiyac * 10)
            if aritir(bot, PROMERIUM, ihtiyac):
                yukle(bot, LAZER, PROMERIUM, ihtiyac)
        else:
            aritir(bot, PROMETID, ihtiyac)
            yukle(bot, LAZER, PROMETID, ihtiyac)
    v = yuklu(bot).get(str(KALKAN))
    if bot.o('risk') < 0.6 and (not v or v[1] < 1800):
        aritir(bot, DURANIUM, 60)
        yukle(bot, KALKAN, DURANIUM, 60)                           # bir saatlik kalkan
    v = yuklu(bot).get(str(ROKET))
    if bot.izin.get('roket', True) and (not v or v[1] < 50):
        aritir(bot, PROMETID, 10)
        yukle(bot, ROKET, PROMETID, 10)
