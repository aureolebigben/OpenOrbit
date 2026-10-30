"""Yardım: sohbette yardım çağrısı (ya da fısıltıyla rica) üzerine o haritaya gidip düşmanlara saldırmak. Kim gideceğine
yonetici karar verir (yardımseverlik, firma, güç, ilişki; Gelişmiş kipte LLM); bu hedef niyetle (beyin.zorla) seçilir."""
import math

from ..beyin import Hedef, hedef
from .. import katalog as K
from .. import soyut as S


@hedef
class Yardim(Hedef):
    ad = 'yardim'
    izin = 'yardim'
    en_az_sn = 240

    def uygun(self, bot, b):
        n = bot.k.get('niyet') or {}
        return n.get('hedef') == self.ad and bool((n.get('plan') or {}).get('harita'))

    def puan(self, bot, b):
        return 0.3 + 0.5 * bot.o('yardimseverlik')

    def basla(self, bot, b):
        plan = (bot.k.get('niyet') or {}).get('plan') or {}
        bot.plan.update(plan)
        if not S.git(bot, plan['harita'], b.y, b.now):
            bot.plan['bitti'] = True

    def soyut(self, bot, dt, y):
        if S.yolculuk(bot, y):
            return
        if K.harita_npcleri(bot.harita):
            S.kas(bot, dt * 0.5, y)

    def somut(self, bot, g, w, now):
        """Yardım isteyen bu dünyanın kahramanıysa yanına git (düşmanla savaş govde'nin PvP aklında: avdaymış gibi)."""
        if g.hedef is not None or bot.plan.get('ad', '').lower() != str(w.p.d['pilot'].get('userName', '')).lower():
            return False
        hx, hy = w.hero_pos(now)
        nx, ny = g.mover.pos(now)
        if math.hypot(hx - nx, hy - ny) > 600:
            from .. import govde as G
            G._git(w, g, hx + bot.r.uniform(-250, 250), hy + bot.r.uniform(-250, 250), now)
            return True
        return False

    def bitti(self, bot, b):
        return bot.plan.get('bitti', False)
