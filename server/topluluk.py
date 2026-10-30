"""Sunucudaki oyuncular: grup (grup.py), rehber (rehber.py), sohbetin fısıltısı, posta ve pilot kartı başka oyuncuyu buradan bulur.

Tek oyunculuda yalnız oyuncunun kendisi; arkadaş sunucusunda (cok_oyunculu.py) sunucunun kendi oyuncusu ve misafirler, çoklu
istemcide ek oyuncular (bu bilgisayardaki öteki kayıtlar). Kaydı sunucuda
olan herkes bilinir (bağlı olmayan misafirin kaydı da bellekte durur: posta ve rehber isteği ona yazılır, son hâli paneline gider);
oyun bağlantısı olan çevrimiçidir. Misafirin sunucudaki kimliği her katılmada başka (cok_oyunculu._yeni_uid): kalıcı bağlar (rehber)
ada göre tutulur.
"""
import cok_oyunculu as CO

OYUN = None          # game modülü (game.py bağlar): PROFIL, CURRENT
BOTLAR = None        # () -> {kimlik: Kisi}: bot paketinin pilotları (bot/toplum.kaydol)


class Kisi:
    __slots__ = ('profil', 'oturum')

    def __init__(self, profil, oturum):
        self.profil, self.oturum = profil, oturum       # oturum: bağlı game.Session ya da None

    @property
    def uid(self):
        return self.profil.user_id

    @property
    def ad(self):
        return str(self.profil.d['pilot'].get('userName', ''))

    @property
    def world(self):
        w = self.oturum.world if self.oturum is not None else None
        return w if w is not None and w.running else None

    def gonder(self, msgs, note=None):
        """Bağlıysa istemcisine (bağlantı kapanmışsa sessizce düşer) -> gitti mi."""
        s = self.oturum
        if s is None or not msgs:
            return False
        try:
            s.send(msgs, note)
            return True
        except (OSError, ConnectionError):
            return False


def hepsi():
    """kimlik -> Kisi: sunucunun oyuncusu, bitmemiş misafir oturumları ve çoklu istemcinin ek oyuncuları."""
    g = OYUN
    if g is None:
        return {}
    host = g.PROFIL
    cur = g.CURRENT
    out = {host.user_id: Kisi(host, cur if cur is not None and cur.profil is host else None)}
    for m in CO.liste() + CO.yereller():
        if m.profil is not None:
            s = m.session
            out[m.profil.user_id] = Kisi(m.profil, s if s is not None and s.profil is m.profil else None)
    if BOTLAR is not None:
        for uid, k in BOTLAR().items():
            out.setdefault(uid, k)
    return out


def bul(ad=None, uid=None):
    """Kimliğe ya da ada (büyük/küçük harf ayrımsız) göre oyuncu ya da None."""
    kisiler = hepsi()
    if uid is not None:
        return kisiler.get(uid)
    ad = str(ad or '').strip().lower()
    return next((k for k in kisiler.values() if ad and k.ad.lower() == ad), None) if ad else None


def siralama(p, deger, en_cok=10):
    """Etkinlik sıralaması: sunucudaki oyuncular (değeri olanlar) değere göre -> ([(sıra, profil, değer)] ilk en_cok, oyuncunun
    (sıra, profil, değer) ya da değeri yoksa (0, p, 0)). Tek oyunculuda yalnız oyuncu."""
    lst = [k.profil for k in hepsi().values()]
    if all(x is not p for x in lst):                    # sunucuda olmayan profil tek başına
        lst = [p]
    vals = sorted(((x, deger(x)) for x in lst), key=lambda xv: (-xv[1], str(xv[0].d['pilot'].get('userName', '')).lower()))
    rows = [(i + 1, x, v) for i, (x, v) in enumerate(xv for xv in vals if xv[1])]
    me = next((r for r in rows if r[1] is p), (0, p, 0))
    return rows[:en_cok], me


def kisi(profil):
    """Profilin Kisi'si (oturumuyla) ya da yalnız profille (sunucudan düşmüş)."""
    return hepsi().get(profil.user_id) or Kisi(profil, None)
