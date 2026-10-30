"""Görev: oyunun görev zincirinden (gorevler.json) uzaylı öldürme / oyuncu öldürme / harita ziyareti görevlerini almak ve bitirmek.

Bot görev vericiden seviyesine uygun, ön koşulları tamam, bitirmediği görevi alır; koşulların haritasına gidip istenen uzaylıyı
kovalar. Ödüller görevin kendi ödülleri (currency_credits, currency_experience, currency_uridium, currency_honour ve eşyalar).
Görev verisi değişince (Dünya Editörü) botlar yenisini kendiliğinden kullanır.
"""
from ..beyin import Hedef, hedef
from .. import katalog as K
from .. import soyut as S

KILL_NPC, KILL_PLAYERS, VISIT_MAP, ON_MAP, HOME = 6, 28, 34, 77, 62
DESTEKLI = {KILL_NPC, KILL_PLAYERS, VISIT_MAP, HOME}
_gorevler = None
_kimlik_tip = None


def gorevler():
    """id -> {seviye, onceki, kosullar [{id, tur, hedef, eslesme, haritalar (belirteçler)}], oduller}: yalnız botun yapabildikleri."""
    global _gorevler, _kimlik_tip
    if _gorevler is None:
        import gorev as GV
        _kimlik_tip = {}
        for tip, t in K.NPC['tipler'].items():
            _kimlik_tip.setdefault(str(t.get('npc_kimlik', '')), []).append(tip)
        out = {}
        for qid, q in GV.QUESTS.items():
            if q.get('turler') != [2] or q.get('sure_sn'):
                continue
            kos = []
            ok = True
            for el in q['kok'].get('modifier', []):
                c = el.get('condition')
                if not c or c['type'] not in DESTEKLI:
                    ok = False
                    break
                har = [m for s in c.get('subConditions', []) if s.get('type') == ON_MAP for m in s.get('matches', [])]
                if any(s.get('type') not in (ON_MAP,) for s in c.get('subConditions', [])):
                    ok = False
                    break
                kos.append(dict(id=c['id'], tur=c['type'], hedef=int(c.get('targetValue', 1)), eslesme=list(c.get('matches', [])),
                                haritalar=har))
            paket = any(str(l).startswith('ship_') or (l == 'currency_uridium' and n >= 10000) for l, n in q.get('oduller', []))
            if ok and kos and not paket:            # hoş geldin paketi (gemi, binlerce uridyum): botlar herkes gibi sıfırdan
                out[int(qid)] = dict(seviye=int(q.get('seviye', 0)), onceki=[int(x) for x in q.get('onceki', [])], kosullar=kos,
                                     oduller=q.get('oduller', []), ad=q.get('ad', ''), sirali=q['kok'].get('ordered', False))
        _gorevler = out
    return _gorevler


def haritalar(belirtec, firma):
    import gorev as GV
    try:
        return [int(m) for m in GV.maps_for(str(belirtec).lstrip('@'), firma) if int(m) in K.HARITALAR]
    except (KeyError, ValueError, TypeError):
        return []


def npc_tipleri(kimlik):
    gorevler()
    return _kimlik_tip.get(str(kimlik), [])


def uygunlar(bot):
    """Botun şimdi alabileceği görevler (seviyeye yakın olanlar önce)."""
    tamam = set(bot.k['tamam'])
    ertele = bot.k.get('ertelenen') or {}
    out = []
    for qid, q in gorevler().items():
        if qid in tamam or ertele.get(str(qid), 0) >= bot.seviye or q['seviye'] > bot.seviye or any(x not in tamam and x in gorevler() for x in q['onceki']):
            continue
        out.append((qid, q))
    out.sort(key=lambda x: (-x[1]['seviye'], x[0]))
    return out


def siradaki(bot):
    """Süren görevin sıradaki bitmemiş koşulu -> (koşul, haritalar) ya da None."""
    g = bot.k.get('gorev')
    if not g:
        return None
    q = gorevler().get(g['id'])
    if not q:
        bot.k['gorev'] = None
        return None
    for c in q['kosullar']:
        if g['kosullar'].get(str(c['id']), 0) < c['hedef']:
            maps = [m for h in c['haritalar'] for m in haritalar(h, bot.firma)]
            if c['tur'] == VISIT_MAP:
                maps = [m for h in c['eslesme'] for m in haritalar(h, bot.firma)]
            elif c['tur'] == HOME:
                maps = [K.ev(bot.firma)]
            elif c['tur'] == KILL_NPC and not maps:
                # haritası verilmemiş: o uzaylının çıktığı, girebildiği en yakın harita
                tipler = {t for k in c['eslesme'] for t in npc_tipleri(k)}
                maps = [m for m in K.HARITALAR if K.girebilir(m, bot.firma, bot.seviye)
                        and any(v['tip'] in tipler for v, _ in K.harita_npcleri(m))]
            maps = [m for m in maps if K.girebilir(m, bot.firma, bot.seviye)]
            return c, maps
        if q['sirali']:
            continue
    return None


def ilerlet(bot, tur, n=1, npc_kimlik=None, harita=None, y=None):
    """Olay görevi ilerletir (kasılmada öldürülen uzaylı, PvP, harita girişi) -> görev bitti mi."""
    g = bot.k.get('gorev')
    if not g:
        return False
    q = gorevler().get(g['id'])
    if not q:
        return False
    for c in q['kosullar']:
        key = str(c['id'])
        if g['kosullar'].get(key, 0) >= c['hedef']:
            continue
        if c['tur'] != tur:
            if q['sirali']:
                break
            continue
        if tur == KILL_NPC and npc_kimlik is not None and str(npc_kimlik) not in c['eslesme']:
            continue
        maps = [m for h in c['haritalar'] for m in haritalar(h, bot.firma)]
        if tur == VISIT_MAP:
            maps = [m for h in c['eslesme'] for m in haritalar(h, bot.firma)]
        elif tur == HOME:
            maps = [K.ev(bot.firma)]
        if maps and harita not in maps:
            continue
        g['kosullar'][key] = min(c['hedef'], g['kosullar'].get(key, 0) + n)
        if q['sirali']:
            break
    if all(g['kosullar'].get(str(c['id']), 0) >= c['hedef'] for c in q['kosullar']):
        bitir(bot, q, y)
        return True
    return False


def bitir(bot, q, y):
    hiz = y.hiz(bot) if y is not None else 1.0
    para = dict(currency_credits='kredi', currency_experience='ep', currency_uridium='uridyum', currency_honour='onur')
    kaz = {}
    for loot, n in q['oduller']:
        if loot in para:
            kaz[para[loot]] = kaz.get(para[loot], 0) + n
        else:
            bot.ekle(loot, n)
    bot.odul('gorev', hiz, **kaz)
    bot.k['tamam'].append(bot.k['gorev']['id'])
    bot.k['gorev'] = None
    bot.ist('gorev')
    bot.ruh.it(moral=0.15, sikilma=-0.2)
    bot.olay('gorev_bitti', ad=q['ad'])


def ertele(bot):
    """Görev şimdilik yapılamıyor (istenen uzaylıya gücü yetmiyor): bırakılır, bir seviye atlayınca yeniden denenir (gerçek
    oyuncu da görevi iptal edip sonra döner)."""
    g = bot.k.get('gorev')
    if g:
        bot.k.setdefault('ertelenen', {})[str(g['id'])] = bot.seviye
        bot.k['gorev'] = None
    bot.plan['bitti'] = True


@hedef
class Gorev(Hedef):
    ad = 'gorev'
    izin = 'gorev'
    en_az_sn = 240

    def uygun(self, bot, b):
        if bot.k.get('gorev'):
            s = siradaki(bot)
            return bool(s and s[1])
        return bool(uygunlar(bot))

    def puan(self, bot, b):
        o = bot.ozellik
        p = 0.45 + 0.35 * o['hirs'] * o['sabir'] + (0.35 if bot.arketip == 'gorevci' else 0)
        if bot.k.get('gorev'):
            p += 0.15                     # yarım görev çeker
        return p * (1 - 0.3 * bot.ruh['sikilma'])

    def basla(self, bot, b):
        if not bot.k.get('gorev'):
            for qid, q in uygunlar(bot)[:6]:
                bot.k['gorev'] = dict(id=qid, kosullar={})
                s = siradaki(bot)
                if s and s[1]:
                    break
                bot.k['gorev'] = None
            if not bot.k.get('gorev'):
                bot.plan['bitti'] = True
                return
            bot.olay('gorev_aldi', ad=gorevler()[bot.k['gorev']['id']]['ad'])
        self._yonel(bot, b.y, b.now)

    def _yonel(self, bot, y, now=None):
        s = siradaki(bot)
        if not s or not s[1]:
            bot.plan['bitti'] = True
            return
        c, maps = s
        tipler = [t for k in c['eslesme'] for t in npc_tipleri(k)] if c['tur'] == KILL_NPC else []
        if tipler:
            # gücünün yettiği (öldürmeye cesaret ettiği) haritalar; hiçbiri yoksa görev güçlenene dek bekler
            d = bot.deger()
            maps = [m for m in maps if set(tipler) & set(K.harita_degerlendir(m, d['dps'], d['ehp'], 0.8)['hedefler'])]
            if not maps:
                ertele(bot)
                return
        hedef_map = min(maps, key=lambda m: len(K.yol(bot.harita, m, bot.firma, bot.seviye) or range(99)))
        bot.plan['kosul'] = c['id']
        bot.plan['harita'] = hedef_map
        bot.plan['tip'] = next((v['tip'] for v, _ in K.harita_npcleri(hedef_map) if v['tip'] in tipler), None)
        S.git(bot, hedef_map, y, now)

    def soyut(self, bot, dt, y):
        if S.yolculuk(bot, y):
            return
        s = siradaki(bot)
        if not s:
            bot.plan['bitti'] = True
            return
        c, maps = s
        if c['id'] != bot.plan.get('kosul') or bot.harita not in maps:
            self._yonel(bot, y)
            return
        if c['tur'] in (VISIT_MAP, HOME):
            if bot.plan.get('ziyaret') != (c['id'], bot.harita):        # varışta bir kez (her soyut adımda sayılıyordu)
                bot.plan['ziyaret'] = (c['id'], bot.harita)
                ilerlet(bot, c['tur'], harita=bot.harita, y=y)
        elif c['tur'] == KILL_PLAYERS:
            S.kas(bot, dt, y)             # PvP koşulu: haritada dolaşırken karşılaşmalar (yonetici.pvp_tick) sayar
        else:
            S.kas(bot, dt, y, hedef_tip=bot.plan.get('tip'))

    def bitti(self, bot, b):
        return bot.plan.get('bitti', False) or (not bot.k.get('gorev') and 'kosul' in bot.plan)
