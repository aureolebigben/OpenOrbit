"""Botların oyun ayarı profili: oyuncunun oyun ayarlarından (ayar.py) ayrı. Oyuncu kendine kolay ayar seçse de botlar paketin
profiliyle ilerler (kullanıcı isteği 2026-10-29).

Profil (paketin 'oyun_ayari' ayarı): {'profil': 'standart' | 'oyuncu' | <ayar.HAZIR'daki hazır ayar> | 'ozel', 'degerler': {...}}
  standart  oyunun kendi değerleri (varsayılan)
  oyuncu    oyuncunun o anki oyun ayarları (eski davranış gibi değil: önceden botlar hiç çarpan kullanmıyordu)
  rahat, hizli, zorlu ...  ayar.HAZIR'ın değerleri
  ozel      paneldeki değerler (ALANLAR)
carpan(key, kaynak) ayar.carpan gibi: üst çarpan x kaynağın alt çarpanı (ep x ep_npc).
"""
import ayar as AY

ALANLAR = ('ep', 'kredi', 'uridyum', 'onur', 'npc_can', 'npc_hasar', 'magaza_fiyat', 'tamir_ucreti')   # Özel profilin düzenlenenleri
PROFILLER = ('standart', 'oyuncu', 'rahat', 'hizli', 'zorlu', 'ozel')


class Profil:
    def __init__(self, ayar=None):
        ayar = ayar if isinstance(ayar, dict) else {}
        self.ad = ayar.get('profil') if ayar.get('profil') in PROFILLER else 'standart'
        if self.ad == 'ozel':
            self.d = {k: float(v) for k, v in (ayar.get('degerler') or {}).items() if k in AY.DEFAULTS}
        elif self.ad in AY.HAZIR:
            self.d = dict(AY.HAZIR[self.ad]['degerler'])
        else:
            self.d = {}

    def get(self, key):
        if self.ad == 'oyuncu':
            return AY.get(key)
        return self.d.get(key, AY.DEFAULTS.get(key, 1.0))

    def carpan(self, key, kaynak=None):
        alt = AY.ALT.get((key, kaynak))
        try:
            return float(self.get(key)) * (float(self.get(alt)) if alt else 1.0)
        except (TypeError, ValueError):
            return 1.0


STANDART = Profil()
