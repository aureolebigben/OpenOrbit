"""Botun eylemleri (araçlar): karar motoru, sohbet ve LLM (Gelişmiş kip) bota yalnız bu araçlarla iş yaptırır.

Her araç: ad, açıklama, parametreler (JSON şema; LLM'e verilir), izin (paketin erişim ayarı) ve işlev (yonetici, bot, **arg) ->
{'ok': bool, 'mesaj': str}. Hedef değiştiren araçlar botun niyetini kurar (beyin.zorla): bot işi kendi aklıyla sürdürür, yarıda
kalırsa karar motoru devralır. Yeni bir eylem için buraya @arac ile bir işlev eklemek yeter; şema LLM'e kendiliğinden gider.
"""
import harita as H
from . import beyin as B
from . import katalog as K

ARACLAR = {}


def arac(ad, aciklama, parametreler=None, izin=None):
    def kaydet(fn):
        ARACLAR[ad] = dict(ad=ad, aciklama=aciklama, parametreler=parametreler or {}, izin=izin, fn=fn)
        return fn
    return kaydet


def sema(y=None, adlar=None):
    """LLM için araç listesi: [{ad, aciklama, parametreler}] (izni kapalı olanlar hariç)."""
    out = []
    for a in ARACLAR.values():
        if adlar is not None and a['ad'] not in adlar:
            continue
        if a['izin'] and y is not None and not y.izin(a['izin']):
            continue
        out.append({'ad': a['ad'], 'aciklama': a['aciklama'], 'parametreler': a['parametreler']})
    return out


def cagir(y, bot, ad, arg=None):
    """Aracı çalıştır -> {'ok', 'mesaj'}. Bilinmeyen araç, kapalı izin ya da hatalı argüman hata döner (bot bir şey yapmaz)."""
    a = ARACLAR.get(str(ad or ''))
    if a is None:
        return {'ok': False, 'mesaj': 'bilinmeyen araç'}
    if a['izin'] and y is not None and not y.izin(a['izin']):
        return {'ok': False, 'mesaj': 'izin kapalı'}
    try:
        r = a['fn'](y, bot, **{k: v for k, v in (arg or {}).items() if k in a['parametreler']})
    except (TypeError, ValueError, KeyError) as e:
        return {'ok': False, 'mesaj': 'hatalı argüman: %s' % e}
    bot.olay('arac', y.now if y is not None else None, ad=ad, sonuc=r.get('ok'))
    return r


def _harita(ad):
    from .konusma import HARITA
    ids = {v.lower(): k for k, v in H.NAMES.items()}
    s = str(ad or '').strip().lower()
    r = HARITA.search(s)
    m = ids.get(s) or (ids.get('%s-%s' % (r.group(1), r.group(2))) if r else None)
    return int(m) if m is not None and int(m) in K.HARITALAR else None


def _ok(m=''):
    return {'ok': True, 'mesaj': m}


def _hata(m):
    return {'ok': False, 'mesaj': m}


# ------------------------------------------------------------------------------------------------------------ hedefler
@arac('npc_avla', 'Uzaylı kas (harita verilirse oraya gidip orada).', {'harita': 'string, ör. "1-3" (isteğe bağlı)'})
def npc_avla(y, bot, harita=None):
    m = _harita(harita) if harita else None
    if harita and (m is None or not K.girebilir(m, bot.firma, bot.seviye)):
        return _hata('haritaya girilemez')
    B.zorla(bot, 'kasilma', plan={'harita': m} if m else {}, pay=0.8, now=y.now if y else None)
    return _ok()


@arac('pvp_avla', 'Düşman firmadan oyuncu avına çık.', {}, izin='pvp')
def pvp_avla(y, bot):
    B.zorla(bot, 'pvp', pay=0.8, now=y.now if y else None)
    return _ok()


@arac('gorev_yap', 'Görev zincirine devam et.', {}, izin='gorev')
def gorev_yap(y, bot):
    B.zorla(bot, 'gorev', pay=0.8, now=y.now if y else None)
    return _ok()


@arac('alisveris_yap', 'Parası yetiyorsa en iyi yükseltmeyi al.', {}, izin='magaza')
def alisveris_yap(y, bot):
    from .hedefler import alisveris as ALIS
    c = ALIS.aday(bot)[0]
    if c is None:
        return _hata('alınacak bir şey yok ya da para yetmiyor')
    if bot.ode(c[1], c[2]):
        bot.ekle(c[3])
        bot.olay('alim', y.now if y else None, esya=c[3], fiyat=c[2], para=c[1])
        if c[3].startswith('ship_'):
            bot.olay('yeni_gemi', y.now if y else None, esya=c[3])
        return _ok(c[3])
    return _hata('para yetmedi')


@arac('dinlen', 'Üste dön ve bir süre dinlen / sohbet et.', {})
def dinlen(y, bot):
    B.zorla(bot, 'dinlenme', pay=0.8, sure=900, now=y.now if y else None)
    return _ok()


@arac('yardima_git', 'Yardım isteyen oyuncunun haritasına gidip düşmanlarla savaş.', {'harita': 'string, ör. "2-4"', 'ad': 'string: yardım isteyen'},
      izin='yardim')
def yardima_git(y, bot, harita=None, ad=''):
    m = _harita(harita) if harita else None
    if m is None and ad:
        import topluluk as TP
        k = TP.bul(ad=ad)
        m = int(k.profil.d['konum'].get('mapId', 0)) if k is not None else None
    if m is None or m not in K.HARITALAR or not K.girebilir(m, bot.firma, bot.seviye) or not K.yol(bot.harita, m, bot.firma, bot.seviye):
        return _hata('oraya gidemez')
    B.zorla(bot, 'yardim', plan={'harita': m, 'ad': ad}, pay=1.2, sure=900, now=y.now if y else None)
    if ad:
        bot.hafiza.olay(ad, 'yardim_ettim', y.now if y else None)
    return _ok(H.name(m))


@arac('duello', 'Meydan okuyan oyuncuyu buluşma haritasında bulup savaş.', {'ad': 'string', 'harita': 'string, ör. "4-4"'},
      izin='pvp')
def duello(y, bot, ad='', harita=None):
    m = _harita(harita) if harita else None
    if not ad or m is None or not K.girebilir(m, bot.firma, bot.seviye) or not K.yol(bot.harita, m, bot.firma, bot.seviye):
        return _hata('oraya gidemez')
    B.zorla(bot, 'duello', plan={'harita': m, 'ad': ad}, pay=1.5, sure=900, now=y.now if y else None)
    bot.hafiza.olay(ad, 'meydan', y.now if y else None)
    return _ok(H.name(m))


@arac('cevrimdisi_ol', 'Oyundan çık (oturumu bitir).', {})
def cevrimdisi_ol(y, bot):
    bot.oturum_bitis = y.now if y else 0
    return _ok()


# ------------------------------------------------------------------------------------------------------------ sosyal
@arac('sohbet_yaz', 'Bir kanala yaz.', {'kanal': 'global | firma | klan | grup', 'metin': 'string'}, izin='sohbet')
def sohbet_yaz(y, bot, kanal='firma', metin=''):
    if kanal not in ('global', 'firma', 'klan', 'grup') or not str(metin).strip():
        return _hata('kanal ya da metin geçersiz')
    y.konus(bot, kanal, str(metin).strip()[:200])
    return _ok()


@arac('fisilda', 'Birine özel mesaj yaz.', {'ad': 'string', 'metin': 'string'}, izin='sohbet')
def fisilda(y, bot, ad='', metin=''):
    if not ad or not str(metin).strip():
        return _hata('ad ya da metin yok')
    y.konus(bot, 'fisilti', str(metin).strip()[:200], alici=ad)
    return _ok()


@arac('grup_davet', 'Oyuncuyu grubuna davet et.', {'ad': 'string'}, izin='grup')
def grup_davet(y, bot, ad=''):
    import grup as GR
    from . import toplum
    out = GR.handle(toplum.kisi(bot), 'InvitationCreationRequest', {'name': ad})
    hata = next((m[1].get('error') for m in out or () if m[0] == 'InvitationErrorCommand'), None)
    if hata is not None:                               # oyuncu başka grupta, çevrimdışı, davet sınırı ...: söz olarak kalır
        from . import etkilesim as ET
        ET.soz_ver(bot, 'grup', ad, y.now if y else 0)
        return _hata('davet gitmedi (%s)' % hata)
    return _ok()


@arac('gruptan_ayril', 'Gruptan ayrıl.', {}, izin='grup')
def gruptan_ayril(y, bot):
    import grup as GR
    from . import toplum
    if GR.grubu(bot.uid) is None:
        return _hata('grupta değil')
    GR.handle(toplum.kisi(bot), 'LeaveGroupRequest', {})
    return _ok()


@arac('arkadas_ekle', 'Arkadaşlık isteği gönder.', {'ad': 'string'}, izin='arkadas')
def arkadas_ekle(y, bot, ad=''):
    import rehber as RH
    from . import toplum
    RH.handle(toplum.kisi(bot), 'ContactRequest', {'contactRequestType': RH.OLUSTUR, 'userName': ad})
    bot.hafiza.olay(ad, 'arkadas', y.now if y else None)
    return _ok()


@arac('arkadas_kabul', 'Gelen arkadaşlık isteğini kabul et.', {'ad': 'string'}, izin='arkadas')
def arkadas_kabul(y, bot, ad=''):
    import rehber as RH
    from . import toplum
    RH.handle(toplum.kisi(bot), 'ContactRequest', {'contactRequestType': RH.KABUL, 'userName': ad})
    bot.hafiza.olay(ad, 'arkadas', y.now if y else None)
    return _ok()


@arac('posta_gonder', 'Birine oyun içi posta gönder.', {'ad': 'string', 'konu': 'string', 'metin': 'string'}, izin='sohbet')
def posta_gonder(y, bot, ad='', konu='', metin=''):
    import posta as PS
    from . import toplum
    konu, metin = str(konu).strip()[:50], str(metin).strip()[:1500]
    if not ad or len(konu) < 3 or len(metin) < 5:
        return _hata('ad, konu ya da metin eksik')
    out = PS.Posta(toplum.profil(bot), log=lambda *_: None).handle('UserMessageSendRequest', {
        'recipients': [ad], 'subject': konu, 'body': metin, 'recipientType': 'user'})
    return _ok() if out and out[0][1].get('success') else _hata('gönderilemedi')


@arac('takip_et', 'Oyuncunun bulunduğu haritaya git ve yanında avlan.', {'ad': 'string'})
def takip_et(y, bot, ad=''):
    import topluluk as TP
    k = TP.bul(ad=ad)
    if k is None:
        return _hata('böyle biri yok')
    return npc_avla(y, bot, harita=H.name(int(k.profil.d['konum'].get('mapId', bot.harita))))


@arac('klana_basvur', 'Bir klana başvur.', {'klan': 'string: klanın adı ya da etiketi'}, izin='klan')
def klana_basvur(y, bot, klan=''):
    import klan as KL
    from . import toplum
    c = next((c for c in KL.KLANLAR.values() if str(klan).lower() in (c['ad'].lower(), c['etiket'].lower())), None)
    if c is None:
        return _hata('klan yok')
    out = KL.Klan(toplum.profil(bot)).handle('ApplyClanRequest', {'clanId': c['id'], 'message': 'lvl %d' % bot.seviye})
    toplum.guncelle(bot)
    return _ok() if out and out[0][1].get('success') else _hata('başvurulamadı')


@arac('hicbiri', 'Bir şey yapma.', {})
def hicbiri(y, bot):
    return _ok()
