"""Düello: sohbette meydan okuyan oyuncuya (başka firmadan) karşılık: buluşma haritasına gidip onu bulur ve saldırır. Kararı
etkilesim._duello verir (saldırganlık, rekabet, öfke, seviye farkı), bu hedef niyetle (beyin.zorla) seçilir. Biri ölünce
(govde.oyuncu_oldu / olduruldu) ya da oyuncu buluşmaya gelmeyince (niyetin süresi) biter. Oyuncu haritayı değiştirirse peşinden
gider (girebildiği ve yolu olan bir haritaysa)."""
import math

from ..beyin import Hedef, hedef
from .. import katalog as K
from .. import soyut as S


def rakip(bot):
    import topluluk as TP
    ad = bot.plan.get('ad')
    return TP.bul(ad=ad) if ad else None


@hedef
class Duello(Hedef):
    ad = 'duello'
    izin = 'pvp'
    en_az_sn = 300

    def uygun(self, bot, b):
        n = bot.k.get('niyet') or {}
        return n.get('hedef') == self.ad and bool((n.get('plan') or {}).get('ad'))

    def puan(self, bot, b):
        return 0.5 + 0.4 * bot.o('rekabet')

    def basla(self, bot, b):
        bot.plan.update((bot.k.get('niyet') or {}).get('plan') or {})
        if not S.git(bot, bot.plan['harita'], b.y, b.now):
            bot.plan['bitti'] = True

    def soyut(self, bot, dt, y):
        if S.yolculuk(bot, y):
            return
        o = rakip(bot)
        if o is None or o.oturum is None:
            bot.plan['bitti'] = True                     # oyuncu çıktı
            return
        m = int(o.profil.d['konum'].get('mapId', 0))
        if m != bot.harita and m in K.HARITALAR and K.girebilir(m, bot.firma, bot.seviye) and K.yol(bot.harita, m, bot.firma,
                                                                                                     bot.seviye):
            bot.plan['harita'] = m
            S.git(bot, m, y)                             # haritayı değiştirdi: peşinden
        elif K.harita_npcleri(bot.harita) and bot.r.random() < 0.3:
            S.kas(bot, dt * 0.3, y)                      # beklerken biraz uzaylı keser

    def somut(self, bot, g, w, now):
        """Rakip bu dünyanın kahramanıysa ona doğru uçar; görüşe girince govde.pvp_hedefi onu seçer (düello hedefi önce)."""
        if g.hedef is not None or str(bot.plan.get('ad', '')).lower() != str(w.p.d['pilot'].get('userName', '')).lower():
            return False
        if w.hero_dead:
            return False
        hx, hy = w.hero_pos(now)
        nx, ny = g.mover.pos(now)
        if math.hypot(hx - nx, hy - ny) > 500:
            from .. import govde as G
            G._git(w, g, hx + bot.r.uniform(-200, 200), hy + bot.r.uniform(-200, 200), now)
            return True
        return False

    def bitti(self, bot, b):
        n = bot.k.get('niyet') or {}
        return bot.plan.get('bitti', False) or n.get('hedef') != self.ad
