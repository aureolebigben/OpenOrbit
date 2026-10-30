"""Mod koşusu: etkinliğe özel ve PvE modları (bot/modlar.py). Bot açık, girebildiği ve geçebileceği modlardan beklenen değeri en
yükseğini seçer, bedelini öder (bilet, anahtar, CPU), modun haritasına geçer (senin haritandan kalkar); süre dolunca ulaştığı
yere göre ödül, sonra üsse döner."""
from ..beyin import Hedef, hedef
from .. import katalog as K
from .. import modlar as MD
from .. import soyut as S


@hedef
class ModKosusu(Hedef):
    ad = 'mod'
    izin = 'modlar'
    en_az_sn = 3600 * 2

    def uygun(self, bot, b):
        if bot.seviye < 8:
            return False
        if b.now < bot.__dict__.get('_mod_bak', 0):
            return bool(bot.__dict__.get('_mod_aday'))
        bot._mod_bak = b.now + 300                     # mod listesine 5 dakikada bir bakar
        a = MD.adaylar(bot, b.now)
        bot._mod_aday = max(a, key=lambda m: MD.deger(bot, m)) if a else None
        return bot._mod_aday is not None

    def puan(self, bot, b):
        return 0.7 + 0.5 * bot.o('hirs') + 0.3 * bot.o('rekabet') - 0.5 * bot.ruh['yorgunluk'] + 0.2 * bot.ruh['sikilma']

    def basla(self, bot, b):
        m = bot.__dict__.get('_mod_aday')
        if m is None or not m.bedel(bot):
            bot.plan['bitti'] = True
            bot._mod_aday, bot._mod_bak = None, b.now + 1800   # giremedi: yarım saat başka işlere bakar (boşta dönmesin)
            return
        ul, top, sure, odul = MD.kos(bot, m, bot.r)
        bot.plan.update(mod=m.kimlik, ul=ul, top=top, sure=sure, odul=odul, bitis=b.now + sure)
        bot._mod_aday = None
        bot._mod_bak = 0
        if m.harita:
            S.atla(bot, m.harita, b.y)                 # modun haritası: senin haritandan kalkar
        bot.olay('moda_girdi', mod=m.ad)

    def soyut(self, bot, dt, y):
        if bot.plan.get('bitti') or y.now < bot.plan.get('bitis', 0):
            return
        m = next((x for x in MD.modlar() if x.kimlik == bot.plan.get('mod')), None)
        if m is not None:
            o = bot.plan.get('odul') or {}
            bot.odul('npc', y.hiz(bot), ep=o.get('ep', 0), kredi=o.get('kredi', 0), uridyum=o.get('uridyum', 0), onur=o.get('onur', 0))
            m.bitir(bot, bot.plan['ul'], bot.plan['top'], bot.plan['sure'], bot.r)
            m.kaydet(bot, bot.plan['ul'], bot.plan['top'])
            bot.ist('mod_kosu')
            bot.olay('mod_bitti', mod=m.ad, ilerleme='%d/%d' % (bot.plan['ul'], bot.plan['top']))
        if bot.harita not in K.HARITALAR:
            S.atla(bot, K.ev(bot.firma), y)
        bot.plan['bitti'] = True

    def somut(self, bot, g, w, now):
        return False

    def bitti(self, bot, b):
        return bot.plan.get('bitti', False)
