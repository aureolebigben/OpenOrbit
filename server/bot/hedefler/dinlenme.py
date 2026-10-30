"""Dinlenme: üste ya da güvenli yerde durmak, sohbet etmek, "afk". Yorgun, hırsı az ya da sosyal botlar seçer; yorgunluk azalmaz
(oturum süresiyle artar), sıkılma ve öfke söner."""
from ..beyin import Hedef, hedef
from .. import katalog as K
from .. import soyut as S


@hedef
class Dinlenme(Hedef):
    ad = 'dinlenme'
    en_az_sn = 120

    def puan(self, bot, b):
        o = bot.ozellik
        return 0.06 + 0.5 * bot.ruh['yorgunluk'] + 0.15 * (1 - o['hirs']) + 0.1 * o['sosyallik'] * bot.ruh['sikilma'] \
            + 0.2 * max(0.0, 0.4 - bot.ruh['moral'])

    def basla(self, bot, b):
        if bot.r.random() < 0.6:
            S.git(bot, K.ev(bot.firma), b.y, b.now)

    def soyut(self, bot, dt, y):
        if S.yolculuk(bot, y):
            return
        bot.ruh.it(sikilma=-dt / 900.0, ofke=-dt / 1200.0, moral=dt / 3600.0 * 0.2)
