"""Basit kip: botlar haritalara seviyelerine göre dağıtılır, harita değiştirmez, büyük karar vermez; bulundukları haritada uzaylı
keser, düşman olan oyuncuyu görünce gücüne göre saldırır ya da kaçar (govde.py'nin taktiği), ölünce aynı haritada yeniden doğar.

Paket ayarları:
  basit_haritalar  {harita sınıfı: bot sayısı} (X-1, X-2, X-3, X-4, 4-X, X-5, X-6, X-7, X-8, 4-5): her firmanın haritasına ayrı ayrı
  basit_guc        güç oranı (0,5 zayıf .. 2 güçlü): haritanın tipik donanımının çarpanı
  basit_dost       düşman / dost oranı: haritanın firmasından olanların payı (0-1)
Kadro paket oluşturulurken bu sayılara göre üretilir (panel/botlar.py); harita ataması ve donanım burada, tohumla belirlenimci.
"""
import random

import harita as H
from .beyin import Hedef, hedef
from . import katalog as K

VARSAYILAN_HARITALAR = {'X-1': 2, 'X-2': 2, 'X-3': 2, 'X-4': 2, '4-X': 3, 'X-5': 1, 'X-6': 1, 'X-7': 1, 'X-8': 1, '4-5': 2}

# harita sınıfı -> (gemi, lazer, lazer adedi payı, kalkan jeneratörü, dron sayısı, dron): o haritada oynayan tipik oyuncu
SINIF_DONANIM = {
    'X-1': ('ship_phoenix', 'equipment_weapon_laser_lf-1', 1.0, 'equipment_generator_shield_sg3n-a01', 0, None),
    'X-2': ('ship_piranha', 'equipment_weapon_laser_mp-1', 0.8, 'equipment_generator_shield_sg3n-a02', 0, None),
    'X-3': ('ship_nostromo', 'equipment_weapon_laser_mp-1', 1.0, 'equipment_generator_shield_sg3n-a02', 2, 'drone_flax'),
    'X-4': ('ship_bigboy', 'equipment_weapon_laser_sll-01', 1.0, 'equipment_generator_shield_sg3n-a03', 3, 'drone_flax'),
    '4-X': ('ship_vengeance', 'equipment_weapon_laser_lf-2', 1.0, 'equipment_generator_shield_sg3n-a03', 4, 'drone_flax'),
    'X-5': ('ship_goliath', 'equipment_weapon_laser_lf-2', 0.9, 'equipment_generator_shield_sg3n-b02', 6, 'drone_iris'),
    'X-6': ('ship_goliath', 'equipment_weapon_laser_lf-3', 0.9, 'equipment_generator_shield_sg3n-b02', 7, 'drone_iris'),
    'X-7': ('ship_goliath', 'equipment_weapon_laser_lf-3', 1.0, 'equipment_generator_shield_sg3n-b02', 8, 'drone_iris'),
    'X-8': ('ship_goliath', 'equipment_weapon_laser_lf-3', 1.0, 'equipment_generator_shield_sg3n-b02', 8, 'drone_iris'),
    '4-5': ('ship_goliath', 'equipment_weapon_laser_lf-3', 1.0, 'equipment_generator_shield_sg3n-b02', 8, 'drone_iris'),
}
SINIF_SEVIYE = {'X-1': 3, 'X-2': 5, 'X-3': 7, 'X-4': 9, '4-X': 11, 'X-5': 13, 'X-6': 14, 'X-7': 15, 'X-8': 16, '4-5': 17}


def sinif(map_id):
    c = H.map_class(map_id)
    return '4-X' if c in ('4-1', '4-2', '4-3', '4-4') else c


def haritalar(sinif_adi):
    return [m for m in K.HARITALAR if sinif(m) == sinif_adi]


def yer_sayisi(sayilar):
    """Kadronun olması gereken büyüklüğü (panel kadroyu buna göre üretir)."""
    return len(dagit(sayilar))


def dagit(sayilar):
    """{sınıf: sayı} -> [(harita, firma, sıra)]: sınıfın her haritasına sayı kadar yer (firma haritalarında her firmanınkine ayrı;
    ortak haritalarda (4-X, 4-5) firma None: bot kendi firmasıyla gelir)."""
    out = []
    for s, n in sayilar.items():
        for m in haritalar(s):
            sahip = H.company(m)
            for k in range(int(n)):
                out.append((m, sahip, k))
    return out


def ekip(map_id, guc=1.0, r=random):
    """Haritanın tipik donanımı x güç oranı: lazer ve jeneratörlerin doluluğu, dron sayısı; güçlüde bir üst lazer."""
    gemi, lazer, pay, kalkan, dron_n, dron = SINIF_DONANIM.get(sinif(map_id), SINIF_DONANIM['X-1'])
    g = K.ESYA['gemiler'][gemi]
    sira = ['equipment_weapon_laser_lf-1', 'equipment_weapon_laser_mp-1', 'equipment_weapon_laser_sll-01',
            'equipment_weapon_laser_lf-2', 'equipment_weapon_laser_lf-3']
    i = sira.index(lazer) if lazer in sira else 0
    if guc >= 1.5 and i + 1 < len(sira):
        lazer = sira[i + 1]
    elif guc <= 0.6 and i > 0:
        lazer = sira[i - 1]
    dolu = max(0.25, min(1.0, pay * guc * r.uniform(0.8, 1.1)))
    dron_n = max(0, min(8, int(round(dron_n * min(guc, 1.3) * r.uniform(0.7, 1.2))))) if dron else 0
    yuva = g['laser'] + dron_n * (2 if dron == 'drone_iris' else 1)
    return {'gemi': gemi, 'lazer': {lazer: max(1, int(round(yuva * dolu)))},
            'kalkan': {kalkan: max(1, int(round(g['generators'] * dolu * 0.8)))}, 'hiz': {}, 'dron': {dron: dron_n} if dron_n else {},
            'cephane': 'ammunition_laser_mcb-25' if guc >= 1.4 else K.CEPHANE[0]}


def hazirla(y, now):
    """Basit kip yükleme: kadroyu haritalara dağıtır (kadronun basit_harita'sı varsa o), donanımı ve seviyeyi kurar; hepsi
    çevrimiçi."""
    guc = float(y.ayar('basit_guc', 1.0))
    yerler = dagit(y.ayar('basit_haritalar') or VARSAYILAN_HARITALAR)
    dost = float(y.ayar('basit_dost', 0.5))
    for i, b in enumerate(y.botlar):
        r = random.Random('basit|%s|%d' % (b.ad, b.k['no']))
        m = b.k.get('basit_harita')
        if not m:
            if not yerler:
                break
            m, sahip, _ = yerler[i % len(yerler)]
            b.k['basit_harita'] = m
            if sahip and r.random() < dost:
                b.k['firma'] = sahip
            elif sahip:
                b.k['firma'] = r.choice([f for f in (1, 2, 3) if f != sahip])
        b.k['harita'] = m
        b.k['ekip'] = ekip(m, guc * r.uniform(0.85, 1.15), r)
        lv = SINIF_SEVIYE.get(sinif(m), 5) + r.randint(-1, 2)
        b.k['seviye'] = max(1, lv)
        b.ekip_degisti()
        y.giris(b, now)
        b.oturum_bitis = float('inf')


@hedef
class Basit(Hedef):
    """Basit kipin tek hedefi: kendi haritasında uzaylı kesmek (soyutta da)."""
    ad = 'basit'
    kipler = ('basit',)
    en_az_sn = 1e9

    def puan(self, bot, b):
        return 1.0

    def soyut(self, bot, dt, y):
        from . import soyut as S
        S.kas(bot, dt, y)
