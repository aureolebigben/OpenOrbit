"""Uzaylı kasma: gücüne ve kişiliğine en uygun haritaya gidip orada uzaylı öldürmek (oyunun ana döngüsü)."""
from ..beyin import Hedef, hedef
from .. import kisilik as KS
from .. import soyut as S


@hedef
class Kasilma(Hedef):
    ad = 'kasilma'
    en_az_sn = 300

    def uygun(self, bot, b):
        return bool(b.harita)

    def puan(self, bot, b):
        o = bot.ozellik
        p = 0.35 + 0.35 * o['hirs'] + 0.25 * o['sabir'] + (0.2 if bot.arketip == 'kasici' else 0)
        from .. import silah as SL
        if not SL.lazer_var(bot):
            p *= 0.3                                      # cephanesiz: yalnız bonus kutusu toplayabilir (önce kargo satar, dinlenir)
        return p * (1 - 0.5 * bot.ruh['yorgunluk']) * (1 - 0.3 * bot.ruh['sikilma'])

    def basla(self, bot, b):
        plan = (bot.k.get('niyet') or {}).get('plan') or {}
        m = plan.get('harita')
        if not m:
            # ilk üç aday arasından faydaya göre: herkes aynı "en iyi" haritaya yığılmasın
            ilk = b.harita[:3]
            enb = ilk[0][0] or 1
            m = KS.softmax_sec([(x[1], x[0] / enb) for x in ilk], 0.15, bot.r)
        bot.plan['harita'] = int(m)
        S.git(bot, m, b.y, b.now)

    def soyut(self, bot, dt, y):
        if S.yolculuk(bot, y):
            return
        S.kas(bot, dt, y)

    def bitti(self, bot, b):
        # haritası artık uygun değil (güç arttı ya da azaldı): ilk beşte değilse yeniden düşünsün
        m = bot.plan.get('harita')
        return bool(b.harita) and m is not None and not bot.yolda and m not in [x[1] for x in b.harita[:5]]
