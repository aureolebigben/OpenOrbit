"""Keşif: seviyesi yeni bir haritanın kapısını açınca oraya bir göz atmak (merak; sabırsız ve hırslı botlar daha çok)."""
from ..beyin import Hedef, hedef
from .. import katalog as K
from .. import soyut as S


def yeni_haritalar(bot):
    gorulen = set(bot.k.get('gorulen', [])) | {bot.harita}
    return [m for m in K.HARITALAR if m not in gorulen and K.girebilir(m, bot.firma, bot.seviye)
            and (K.H.company(m) in (None, bot.firma) or bot.o('risk') > 0.6)]


@hedef
class Kesif(Hedef):
    ad = 'kesif'
    en_az_sn = 60

    def uygun(self, bot, b):
        return bool(yeni_haritalar(bot))

    def puan(self, bot, b):
        return 0.12 + 0.25 * (1 - bot.o('sabir')) + 0.15 * bot.o('hirs')

    def basla(self, bot, b):
        maps = yeni_haritalar(bot)
        maps.sort(key=lambda m: len(K.yol(bot.harita, m, bot.firma, bot.seviye) or range(99)))
        bot.plan['harita'] = maps[0]
        if not S.git(bot, maps[0], b.y, b.now):
            bot.k.setdefault('gorulen', []).append(maps[0])
            bot.plan['bitti'] = True

    def soyut(self, bot, dt, y):
        if S.yolculuk(bot, y):
            return
        S.kas(bot, dt, y)
        if bot.harita == bot.plan.get('harita'):
            bot.plan.setdefault('vardi', 0)
            bot.plan['vardi'] += dt
            if bot.plan['vardi'] > 120:
                bot.plan['bitti'] = True

    def bitti(self, bot, b):
        return bot.plan.get('bitti', False)
