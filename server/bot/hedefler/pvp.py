"""PvP avı: düşman firmanın oyuncularını aramak (4-X, başka firmanın haritaları). Karşılaşmaları yonetici.pvp_tick çözer; avdaki bot
saldırgan sayılır. Öfke (az önce öldürüldü) ve kin (hafızada onu öldüren) avı çeker: intikam."""
from ..beyin import Hedef, hedef
from .. import katalog as K
from .. import soyut as S


@hedef
class PvpAvi(Hedef):
    ad = 'pvp'
    izin = 'pvp'
    en_az_sn = 240

    def uygun(self, bot, b):
        return bot.seviye >= (b.ayar('pvp_seviye', 6) or 1) and bot.deger()['guc'] >= 8

    def puan(self, bot, b):
        o = bot.ozellik
        p = 0.1 + 0.55 * o['saldirganlik'] * o['rekabet'] + (0.35 if bot.arketip == 'avci' else 0)
        p += 0.45 * bot.ruh['ofke'] * o['saldirganlik']
        p *= 0.6 + 0.6 * bot.ruh['ozguven']
        if b.y is not None and bot.hafiza.kinliler() and b.y.cevrimici_ad(bot.hafiza.kinliler()):
            p += 0.25 * o['saldirganlik']
        return p

    def basla(self, bot, b):
        y = b.y
        hedef_map = None
        kin = y.cevrimici_ad(bot.hafiza.kinliler()) if y is not None else None
        if kin is not None and K.yol(bot.harita, kin.harita, bot.firma, bot.seviye):
            hedef_map = kin.harita                        # intikam: onu öldüreni bulmaya gider
            bot.plan['av'] = kin.ad
        elif y is not None:
            # düşmanların olduğu, gidilebilen ve çok güçlü düşmanı olmayan harita
            guc = bot.deger()['guc']
            adaylar = []
            for m, dusman in y.dusman_nufusu(bot).items():
                if not dusman or not K.girebilir(m, bot.firma, bot.seviye) or not K.yol(bot.harita, m, bot.firma, bot.seviye):
                    continue
                tehdit = max(d.deger()['guc'] for d in dusman) / max(1.0, guc)
                adaylar.append((len(dusman) - 2.5 * max(0.0, tehdit - 1.0 - bot.o('risk')), m))
            if adaylar:
                hedef_map = max(adaylar)[1]
        if hedef_map is None:
            hedef_map = next((m for m in (13 + bot.firma - 1, 16, 29) if K.girebilir(m, bot.firma, bot.seviye)), bot.harita)
        bot.plan['harita'] = int(hedef_map)
        S.git(bot, hedef_map, y, b.now)

    def soyut(self, bot, dt, y):
        if S.yolculuk(bot, y):
            return
        if K.harita_npcleri(bot.harita) and bot.r.random() < 0.5:
            S.kas(bot, dt * 0.5, y)        # beklerken uzaylı da keser (yarı verim)
