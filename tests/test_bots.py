"""Bots: roster generation, progression maths, the decision engine (simulated clock) and bot ships inside a real World."""
import os
import random
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
os.environ.setdefault('DO_KAYIT_KLASORU', tempfile.mkdtemp())        # yollar.SAVE: the bot name log (ad_kaydi) is not the real one
import dunya
from profil import Profil
from bot import katalog as K
from bot import kisilik as KS
from bot import soyut as S
from bot import yonetici as YN
from bot import govde as BG
from bot.durum import Bot
from bot.hedefler import alisveris as ALIS
from bot.hedefler import gorev as GV

T0 = 1_800_000_000.0


def paket(adet=30, tohum=3, **ayar):
    return dict(ad='t', kip='normal', gelisim=ayar.pop('gelisim', 'progressive'), ayarlar=dict(dict(telafi_saat=0, kayit_sn=0), **ayar),
                kadro=KS.kadro_uret(tohum, adet))


class Roster(unittest.TestCase):
    def test_same_seed_same_roster_and_unique_valid_names(self):
        a, b = KS.kadro_uret(11, 120), KS.kadro_uret(11, 120)
        self.assertEqual(a, b)
        names = [x['ad'].lower() for x in a]
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(KS.AD_DESEN.match(x['ad']) for x in a))

    def test_faction_split_follows_weights(self):
        r = KS.kadro_uret(5, 100, firma_dagilimi=(2, 1, 1))
        counts = [sum(1 for x in r if x['firma'] == f) for f in (1, 2, 3)]
        self.assertEqual(counts, [50, 25, 25])

    def test_used_names_are_avoided(self):
        first = KS.kadro_uret(8, 1)[0]['ad']
        self.assertNotEqual(KS.kadro_uret(8, 1, mevcut=[first.upper()])[0]['ad'].lower(), first.lower())

    def test_traits_in_range_and_archetype_shapes_them(self):
        r = random.Random(1)
        hunters = [KS.kisilik_uret(r, 'avci')['ozellik']['saldirganlik'] for _ in range(60)]
        casual = [KS.kisilik_uret(r, 'rahat')['ozellik']['saldirganlik'] for _ in range(60)]
        self.assertGreater(sum(hunters) / 60, sum(casual) / 60 + 0.3)
        self.assertTrue(all(0 < v < 1 for v in hunters + casual))

    def test_mood_decays_back_to_balance(self):
        m = KS.RuhHali(t=T0)
        m.it(ofke=0.8)
        m.guncelle(T0 + KS.DUYGU_SONUM_SN['ofke'])
        self.assertAlmostEqual(m['ofke'], 0.4, places=2)

    def test_memory_holds_grudges_and_forgets(self):
        h = KS.Hafiza()
        h.olay('Nova', 'oldurdu_beni', T0)
        self.assertIn('Nova', h.kinliler(now=T0))
        self.assertGreater(h.iliski('nova', T0 + 3 * KS.Hafiza.UNUTMA_SN), -0.1)


class Catalog(unittest.TestCase):
    def test_power_grows_with_gear(self):
        phoenix = K.degerler(K.yeni_ekip())
        goliath = K.degerler({'gemi': 'ship_goliath', 'lazer': {'equipment_weapon_laser_lf-3': 23},
                              'kalkan': {'equipment_generator_shield_sg3n-b02': 15}, 'hiz': {}, 'dron': {'drone_iris': 8},
                              'cephane': 'ammunition_laser_lcb-10'})
        self.assertLess(phoenix['guc'], 10)
        self.assertGreater(goliath['guc'], 15 * phoenix['guc'])
        self.assertEqual(goliath['lazer_yuva'], 15 + 16)

    def test_weak_ship_avoids_deadly_maps_and_x1_pays(self):
        d = K.degerler(K.yeni_ekip())
        self.assertGreater(K.harita_degerlendir(1, d['dps'], d['ehp'])['saat_ep'], 5000)
        hard = K.harita_degerlendir(29, d['dps'], d['ehp'])
        self.assertFalse({'98', '99'} & set(hard['hedefler']))

    def test_portal_path_respects_levels(self):
        self.assertEqual(K.yol(1, 3, 1, 5)[0], 1)
        self.assertEqual(K.yol(1, 3, 1, 5)[-1], 3)
        self.assertIsNone(K.yol(1, 29, 1, 1))


class Decisions(unittest.TestCase):
    def run_hours(self, y, hours, step=5.0):
        now = T0
        for _ in range(int(hours * 3600 / step)):
            now += step
            y.tick(now)
        return now

    def test_cargo_fills_and_is_sold_at_own_station(self):
        y = YN.Yonetici(paket(20), None, log=lambda *_: None, now=T0)
        self.run_hours(y, 4)
        sold = [b for b in y.botlar if b.k['istat'].get('cevher_kredi')]
        self.assertGreater(len(sold), 5)
        self.assertTrue(all(b.kargo_dolu() <= 1.0 + 1e-9 for b in y.botlar))
        from bot.hedefler import satis as SA
        b = Bot(dict(no=99, ad='satici', firma=3, kisilik=KS.kisilik_uret(random.Random(12), 'kasici')))
        b.izin, b.saat = y.botlar[0].izin, (lambda: y.now)
        b.k['harita'] = 11                                       # 3-3, far from home (a fresh bot: the 4 h above is random)
        b.kargo_ekle({2: 10 ** 4})
        self.assertTrue(SA.Satis().uygun(b, None))
        b.yolda = None
        g = SA.Satis()
        ctx = NS(y=y, now=T0)
        g.basla(b, ctx)
        self.assertIn(b.plan['harita'], K.satis_haritalari(3))
        kredi = b.k['kredi']
        now = T0
        for _ in range(200):
            now += 30
            y.now = now
            g.soyut(b, 30, y)
            if g.bitti(b, None):
                break
        self.assertIn(b.harita, K.satis_haritalari(3))
        self.assertEqual(b.kargo_dolu(), 0)
        self.assertGreater(b.k['kredi'], kredi)

    def test_cargo_permission_off_collects_nothing(self):
        y = YN.Yonetici(paket(10, izinler={'kargo': False}), None, log=lambda *_: None, now=T0)
        self.run_hours(y, 2)
        self.assertFalse(any(b.k['istat'].get('kargo_kutusu') or b.k['istat'].get('cevher_kredi') for b in y.botlar))

    def test_bots_progress_realistically_in_a_day(self):
        y = YN.Yonetici(paket(30), None, log=lambda *_: None, now=T0)
        self.run_hours(y, 24)
        levels = [b.seviye for b in y.botlar]
        self.assertGreater(sum(levels) / len(levels), 3)
        self.assertLess(max(levels), 14)                      # nobody rockets to the top in a day
        self.assertTrue(any(b.k['ekip']['gemi'] != 'ship_phoenix' for b in y.botlar))
        self.assertTrue(any(b.k['istat'].get('gorev') for b in y.botlar))

    def test_disabled_access_is_never_chosen(self):
        y = YN.Yonetici(paket(15, izinler={'magaza': False, 'gorev': False, 'pvp': False}), None, log=lambda *_: None, now=T0)
        self.run_hours(y, 4)
        self.assertTrue(all(b.k['ekip']['gemi'] == 'ship_phoenix' for b in y.botlar))
        self.assertFalse(any(b.k['istat'].get('gorev') or b.k['istat'].get('oyuncu') for b in y.botlar))

    def test_jumpstart_spreads_levels_and_spends_money(self):
        y = YN.Yonetici(paket(40, gelisim='jumpstart', jumpstart_saat=40), None, log=lambda *_: None, now=T0)
        levels = sorted(b.seviye for b in y.botlar)
        self.assertGreater(levels[-1] - levels[0], 4)
        rich_phoenix = [b for b in y.botlar if b.k['ekip']['gemi'] == 'ship_phoenix' and b.k['kredi'] - b.klan_birikimi() > 300000]   # (leaders save for a clan)
        self.assertFalse(rich_phoenix)

    def test_progressive_pilots_register_one_by_one(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, 'p', 'durum.json')
        pk = paket(90, kayit_sn=15)
        y = YN.Yonetici(pk, path, log=lambda *_: None, now=T0)
        self.assertFalse(any(b.kayitli or b.cevrimici for b in y.botlar))       # nobody exists yet
        firmalar = len({b.firma for b in y.botlar})
        now = T0
        for _ in range(60):                                     # 60 s
            now += 1
            y.tick(now)
        n = sum(b.kayitli for b in y.botlar)
        self.assertGreaterEqual(n, 3 * firmalar - firmalar)     # one per company every 10-20 s
        self.assertLessEqual(n, 6 * firmalar)
        for b in y.botlar:
            if b.kayitli:
                self.assertTrue(b.cevrimici)                    # a new pilot plays right away, from scratch, at home
                self.assertEqual((b.seviye, b.harita), (1, K.ev(b.firma)))
        y.kaydet(now)
        y2 = YN.Yonetici(pk, path, log=lambda *_: None, now=now)
        self.assertEqual(sum(b.kayitli for b in y2.botlar), n)  # the queue continues where it stopped
        self.assertTrue(all(b.kayitli for b in YN.Yonetici(paket(20, gelisim='jumpstart', kayit_sn=15), None,
                                                           log=lambda *_: None, now=T0).botlar))

    def test_state_survives_save_and_reload(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, 'p', 'durum.json')
        pk = paket(10)
        y = YN.Yonetici(pk, path, log=lambda *_: None, now=T0)
        self.run_hours(y, 2)
        y.kaydet(T0 + 7200)
        before = {b.ad: (b.seviye, b.k['ep'], b.k['ekip']['gemi']) for b in y.botlar}
        y2 = YN.Yonetici(pk, path, log=lambda *_: None, now=T0 + 7200)
        self.assertEqual({b.ad: (b.seviye, b.k['ep'], b.k['ekip']['gemi']) for b in y2.botlar}, before)

    def test_quest_kill_progress_completes_and_pays(self):
        b = Bot(dict(no=1, ad='q', firma=1, kisilik=KS.kisilik_uret(random.Random(2), 'gorevci')))
        qid, q = next((i, q) for i, q in GV.gorevler().items() if q['seviye'] == 0 and not q['onceki']
                      and all(c['tur'] == GV.KILL_NPC for c in q['kosullar']))
        b.k['gorev'] = dict(id=qid, kosullar={})
        ep = b.k['ep']
        for c in q['kosullar']:
            maps = [m for h in c['haritalar'] for m in GV.haritalar(h, 1)] or [1]
            b.k['harita'] = maps[0]
            GV.ilerlet(b, GV.KILL_NPC, n=c['hedef'], npc_kimlik=c['eslesme'][0], harita=maps[0])
        self.assertIn(qid, b.k['tamam'])
        self.assertGreater(b.k['ep'], ep)

    def test_shopping_prefers_filling_slots_and_saves_for_big_goals(self):
        b = Bot(dict(no=1, ad='s', firma=1, kisilik=KS.kisilik_uret(random.Random(4), 'kasici')))
        b.k['kredi'] = 15000
        self.assertEqual(ALIS.aday(b)[0][3], 'equipment_extra_repbot_rep-1')     # a repair bot is worth it early
        b.izin = {'ekstra': False}
        b._adaylar = None
        now, goal = ALIS.aday(b)
        self.assertIsNone(now)                                  # saves for the upgrade in reach instead of buying cheap filler
        self.assertEqual(goal[3], 'equipment_weapon_laser_sll-01')
        b.k['kredi'] = 80000
        self.assertEqual(ALIS.aday(b)[0][3], 'equipment_weapon_laser_sll-01')
        b.k['kredi'] = 0
        self.assertIsNone(ALIS.aday(b)[0])
        self.assertIsNotNone(ALIS.aday(b)[1])

    def test_death_sends_bot_home_and_remembers_killer(self):
        y = YN.Yonetici(paket(2), None, log=lambda *_: None, now=T0)
        b = y.botlar[0]
        b.k['harita'] = 3
        S.olum(b, y, neden='oyuncu', katil='Nova', now=T0)
        self.assertEqual(b.harita, K.ev(b.firma))
        self.assertGreater(b.olu_bitis, T0)
        self.assertIn('Nova', b.hafiza.kinliler(now=T0))


class SimpleMode(unittest.TestCase):
    def test_bots_stay_on_their_map_and_respawn_there(self):
        from bot import basit
        y = YN.Yonetici(dict(kip='basit', ayarlar=dict(basit_haritalar={'X-1': 1, 'X-3': 1, '4-5': 1}),
                             kadro=KS.kadro_uret(6, 7)), None, log=lambda *_: None, now=T0)
        self.assertTrue(all(b.cevrimici for b in y.botlar))
        maps = {b.uid: b.harita for b in y.botlar}
        self.assertEqual(sorted(K.H.name(m) for m in maps.values()), ['1-1', '1-3', '2-1', '2-3', '3-1', '3-3', '4-5'])
        x1 = next(b for b in y.botlar if K.H.name(b.harita) == '1-1')
        top = next(b for b in y.botlar if K.H.name(b.harita) == '4-5')
        self.assertGreater(top.deger()['guc'], 5 * x1.deger()['guc'])
        S.olum(top, y, neden='npc', now=T0)
        now = T0
        for _ in range(720):
            now += 5
            y.tick(now)
        self.assertEqual({b.uid: b.harita for b in y.botlar}, maps)
        self.assertTrue(all(b.hedef is None or b.hedef.ad == 'basit' for b in y.botlar))


class FakeChat:
    def __init__(self):
        self.rooms, self.whispers = [], []

    def broadcast(self, path, msg, ep, user):
        self.rooms.append((path, msg, user['userId']))
        return 1

    def bot_fisildar(self, to, msg, ep, user):
        self.whispers.append((to, msg, user['userId']))
        return True


class FakeSession:
    def __init__(self, p):
        self.profil, self.world, self.sosyal, self.got = p, None, None, []

    def send(self, msgs, note=None):
        self.got.extend(msgs)


def toplum_profil(b):
    from bot import toplum
    return toplum.profil(b)


class Society(unittest.TestCase):
    """Bots inside the game's social systems: community registry, groups, whispers, help calls, clans."""

    def setUp(self):
        import game
        import klan as KL
        import topluluk as TP
        from unittest.mock import patch
        from bot import toplum
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Profil(path=str(Path(self.tmp.name) / 'pilot.json'))
        self.p.d['pilot'].update(factionId=1, userName='Nova', level=10)
        self.s = FakeSession(self.p)
        patches = [patch.object(game, 'PROFIL', self.p), patch.object(game, 'CURRENT', self.s), patch.object(KL, 'DOSYA', None),
                   patch.dict(KL.KLANLAR, {}, clear=True), patch.object(TP, 'BOTLAR', None)]
        for x in patches:
            x.start()
            self.addCleanup(x.stop)
        kadro = KS.kadro_uret(31, 12, firma_dagilimi=(1, 0, 0))
        self.y = YN.Yonetici(dict(kip='normal', ayarlar=dict(telafi_saat=0, kayit_sn=0), kadro=kadro), None, log=lambda *_: None)
        self.chat = FakeChat()
        toplum.kaydol(self.y, self.chat)
        self.y.toplum = True
        self.now = time.time()
        for b in self.y.botlar:
            self.y.giris(b, self.now)
            b.oturum_bitis = self.now + 1e6
        self.y.giden = []
        toplum._KISILER['t'] = 0

    def advance(self, seconds, step=5):
        for _ in range(int(seconds / step)):
            self.now += step
            self.y.tick(self.now)

    def test_bots_are_in_the_community(self):
        import topluluk as TP
        everyone = TP.hepsi()
        b = self.y.botlar[0]
        self.assertIn(b.uid, everyone)
        self.assertEqual(TP.bul(ad=b.ad.upper()).uid, b.uid)
        self.assertIsNotNone(everyone[b.uid].oturum)

    def test_group_invite_is_answered_after_a_human_delay(self):
        import grup as GR
        import topluluk as TP
        b = max(self.y.botlar, key=lambda x: x.o('sosyallik'))
        b.hafiza.olay('Nova', 'yardim_etti', self.now)
        b.hafiza.olay('Nova', 'yardim_etti', self.now)
        GR.handle(TP.bul(uid=self.p.user_id), 'InvitationCreationRequest', {'name': b.ad})
        self.assertTrue(b.bekleyen)
        self.advance(60)
        self.assertFalse(b.bekleyen)
        g = GR.grubu(b.uid)
        if g is not None:
            self.addCleanup(GR.handle, TP.bul(uid=self.p.user_id), 'LeaveGroupRequest', {})
            self.assertIn(self.p.user_id, g.uyeler)
            self.assertEqual((b.k.get('niyet') or {}).get('hedef'), 'grup')

    def test_whisper_to_bot_gets_a_reply(self):
        b = self.y.botlar[0]
        self.assertTrue(self.y.fisilti_gelen(b.ad.lower(), 'selam', {'userId': 'Nova', 'id': str(self.p.user_id), 'factionId': '1'}))
        self.assertFalse(self.y.fisilti_gelen('kimseyok', 'selam', {'userId': 'Nova'}))
        self.advance(60)
        self.assertTrue(any(w[0] == 'Nova' and w[2] == b.ad for w in self.chat.whispers))

    def test_help_call_sends_some_bots_to_the_map(self):
        for b in self.y.botlar:
            b.k['seviye'] = 6
            b.k['kisilik']['ozellik']['yardimseverlik'] = 0.95
        self.y.sohbet_gelen('/room/faction/1/', '1-3 yardim edin vru var', {'userId': 'Nova', 'id': '1', 'factionId': '1'})
        self.advance(10)
        helpers = [b for b in self.y.botlar if (b.k.get('niyet') or {}).get('hedef') == 'yardim']
        self.assertTrue(1 <= len(helpers) <= 3)
        self.assertEqual(helpers[0].k['niyet']['plan']['harita'], 3)
        self.advance(60)
        self.assertTrue(any(r[0] == '/room/faction/1/' for r in self.chat.rooms))

    def test_leader_bot_founds_clan_and_judges_applications(self):
        import klan as KL
        from bot import toplum
        b = self.y.botlar[0]
        b.k['kisilik']['arketip'] = 'lider'
        b.k['seviye'], b.k['kredi'] = 12, 2_000_000
        for _ in range(40):
            if b.k.get('klan'):
                break
            b.sonraki_sosyal = 0
            toplum.klan_isleri(self.y, b, self.now)
        self.assertTrue(b.k.get('klan'))
        k = KL.KLANLAR[b.k['klan']]
        self.assertEqual(k['lider'], b.ad.lower())
        self.assertLess(b.k['kredi'], 2_000_000)
        self.p.d['pilot']['credits'] = 100000
        KL.Klan(self.p).handle('ApplyClanRequest', {'clanId': k['id'], 'message': 'hi'})
        self.assertTrue(k['basvurular'])
        toplum.klan_isleri(self.y, b, self.now)
        self.now += 400
        toplum.klan_isleri(self.y, b, self.now)
        self.assertFalse(k['basvurular'])


    def test_aggressive_clan_leader_declares_war_on_another_company_and_the_other_accepts_peace(self):
        import klan as KL
        from bot import toplum
        leaders = self.y.botlar[0], self.y.botlar[1]
        self.y.ayarlar['klan_basina'] = 1                                # room for two bot clans in a small pack
        for b, firma in zip(leaders, (1, 2)):
            b.k['firma'], b.k['seviye'], b.k['kredi'] = firma, 12, 5_000_000
            b.k['kisilik']['arketip'] = 'lider'
            for _ in range(40):
                if b.k.get('klan'):
                    break
                toplum.klan_isleri(self.y, b, self.now)
            self.assertTrue(b.k.get('klan'))
        a, c = leaders
        a.k['kisilik']['ozellik']['saldirganlik'] = 1.0
        kredi = a.k['kredi']
        with patch.object(a.r, 'random', return_value=0.0):
            toplum.diplomasi(self.y, a, KL.KLANLAR[a.k['klan']], KL.Klan(toplum.profil(a)), self.now)
        self.assertEqual(toplum.klan_iliskisi(a, c), 3)
        self.assertEqual(a.k['kredi'], kredi - KL.SAVAS_BEDELI)          # the leader paid the war into the clan bank
        self.assertEqual(a.olaylar[-1]['tur'], 'diplomasi')
        c.k['kisilik']['ozellik']['saldirganlik'] = 0.0                   # the peaceful side asks for peace ...
        with patch.object(c.r, 'random', return_value=0.0):
            toplum.diplomasi(self.y, c, KL.KLANLAR[c.k['klan']], KL.Klan(toplum.profil(c)), self.now)
        self.assertTrue(KL.KLANLAR[a.k['klan']]['diplo_istek'])
        a.k['kisilik']['ozellik']['saldirganlik'] = 0.0                   # ... and the other leader accepts it
        with patch.object(a.r, 'random', return_value=0.0):
            toplum.diplomasi(self.y, a, KL.KLANLAR[a.k['klan']], KL.Klan(toplum.profil(a)), self.now)
        self.assertEqual(toplum.klan_iliskisi(a, c), 0)


    # ------------------------------------------------------------ requests through chat and mail (etkilesim)
    def nova(self):
        import topluluk as TP
        return TP.bul(uid=self.p.user_id)

    def leave_groups(self):
        import grup as GR
        for b in self.y.botlar:
            if GR.grubu(b.uid) is not None:
                from bot import toplum
                GR.handle(toplum.kisi(b), 'LeaveGroupRequest', {})
        if GR.grubu(self.p.user_id) is not None:
            GR.handle(self.nova(), 'LeaveGroupRequest', {})
        GR.DAVETLER.clear()

    def test_open_group_call_gets_one_bot_to_invite_and_it_then_joins_the_player(self):
        import grup as GR
        self.addCleanup(self.leave_groups)
        for b in self.y.botlar:
            b.k['kisilik']['ozellik']['sosyallik'] = 1.0
            b.hafiza.olay('Nova', 'yardim_etti', self.now)
        self.y.sohbet_gelen('/room/faction/1/', 'who wants to group up with me? lets do quests', {'userId': 'Nova', 'id': str(self.p.user_id),
                                                                                                 'factionId': '1'})
        self.advance(5)
        self.assertFalse([d for d in GR.DAVETLER if d[1] == self.p.user_id])     # first he types his answer ...
        self.advance(40)
        invites = [d for d in GR.DAVETLER if d[1] == self.p.user_id]
        self.assertEqual(len(invites), 1)                              # ... then one pilot invites, like in a real chat
        b = next(x for x in self.y.botlar if x.uid == invites[0][0])
        self.assertTrue(any(r[2] == b.ad for r in self.chat.rooms))     # ("sent inv")
        GR.handle(self.nova(), 'InvitationAcceptRequest', {'inviterId': b.uid})
        self.advance(10)
        self.assertIn(self.p.user_id, GR.grubu(b.uid).uyeler)
        self.assertEqual((b.k.get('niyet') or {}).get('hedef'), 'grup')  # the bot now flies with the player

    def test_bot_says_inv_me_when_the_player_already_leads_a_group_and_accepts_his_invite(self):
        import grup as GR
        from bot import etkilesim as ET
        self.addCleanup(self.leave_groups)
        a, b = self.y.botlar[0], self.y.botlar[1]
        a.r.random = lambda: 0.0
        GR.handle(self.nova(), 'InvitationCreationRequest', {'name': a.ad})
        self.advance(60)
        self.assertIsNotNone(GR.grubu(self.p.user_id))                  # Nova leads a group with a
        b.r.random = lambda: 0.0
        k = ET.karar(self.y, b, 'grup', 'Nova', {'userId': 'Nova', 'id': str(self.p.user_id), 'factionId': '1'}, None, 'group?', self.now)
        self.assertEqual((k['kabul'], k['eylem'], k['kalip'][0]), (True, None, 'inv_me'))
        b.r.random = lambda: 0.99                                        # in a bad mood later: the promise still holds
        GR.handle(self.nova(), 'InvitationCreationRequest', {'name': b.ad})
        self.advance(60)
        self.assertIn(b.uid, GR.grubu(self.p.user_id).uyeler)

    def test_friend_bot_greets_the_player_and_a_group_offer_answered_yes_becomes_an_invite(self):
        import grup as GR
        from bot import etkilesim as ET
        self.addCleanup(self.leave_groups)
        b = self.y.botlar[0]
        for _ in range(3):
            b.hafiza.olay('Nova', 'yardim_etti', self.now)
        self.advance(60)
        self.assertTrue(any(w[0] == 'Nova' and w[2] == b.ad for w in self.chat.whispers))    # "yo Nova, wb"
        ET.teklif_ver(b, 'grup', 'Nova', self.now)                                       # later: "wanna group up?"
        b.r.random = lambda: 0.99                                                        # (would refuse on a whim)
        self.y.fisilti_gelen(b.ad, 'sure', {'userId': 'Nova', 'id': str(self.p.user_id), 'factionId': '1'})
        self.advance(30)
        self.assertIn((b.uid, self.p.user_id), GR.DAVETLER)

    def test_pm_me_in_a_channel_gets_a_real_whisper(self):
        for b in self.y.botlar:
            b.k['kisilik']['ozellik'].update(sosyallik=1.0, yardimseverlik=1.0)
        self.y.sohbet_gelen('/room/faction/1/', 'can someone send private message to me', {'userId': 'Nova', 'id': str(self.p.user_id),
                                                                                         'factionId': '1'})
        self.advance(40)
        self.assertEqual(len([w for w in self.chat.whispers if w[0] == 'Nova']), 1)

    def test_grouped_bot_talks_in_group_chat_now_and_then(self):
        import grup as GR
        self.addCleanup(self.leave_groups)
        a = self.y.botlar[0]
        a.r.random = lambda: 0.0
        GR.handle(self.nova(), 'InvitationCreationRequest', {'name': a.ad})
        self.advance(60)
        self.assertIn(a.uid, GR.grubu(self.p.user_id).uyeler)
        self.advance(1100)
        self.assertTrue(any('/room/group/' in r[0] and r[2] == a.ad for r in self.chat.rooms))

    def test_group_members_follow_the_player_when_asked_in_group_chat(self):
        import grup as GR
        self.addCleanup(self.leave_groups)
        a = self.y.botlar[0]
        a.k['seviye'] = 10
        a.r.random = lambda: 0.0
        GR.handle(self.nova(), 'InvitationCreationRequest', {'name': a.ad})
        self.advance(60)
        self.assertIn(a.uid, GR.grubu(self.p.user_id).uyeler)
        self.y.sohbet_gelen('/room/group/%d/' % GR.grubu(self.p.user_id).id, 'come to 1-3 guys',
                            {'userId': 'Nova', 'id': str(self.p.user_id), 'factionId': '1'})
        self.advance(30)
        self.assertEqual(a.k['niyet']['plan']['harita'], 3)

    def test_quest_help_is_a_group_request_not_a_pvp_help_call(self):
        import grup as GR
        from bot import konusma as KN
        self.assertEqual(KN.niyet('can someone help me with a quest?')[0], 'gorev')
        self.assertEqual(KN.niyet('help, vru attacking me on 1-3')[0], 'yardim')
        self.addCleanup(self.leave_groups)
        for b in self.y.botlar:
            b.k['kisilik']['ozellik']['sosyallik'] = 1.0
            b.hafiza.olay('Nova', 'yardim_etti', self.now)
        self.y.sohbet_gelen('/room/faction/1/', 'can someone help me with a quest?', {'userId': 'Nova', 'id': str(self.p.user_id),
                                                                                    'factionId': '1'})
        self.advance(45)
        self.assertEqual(len([d for d in GR.DAVETLER if d[1] == self.p.user_id]), 1)       # a group invite ...
        self.assertFalse([b for b in self.y.botlar if (b.k.get('niyet') or {}).get('hedef') == 'yardim'])   # ... not a PvP rescue

    def test_duel_challenge_is_taken_by_an_enemy_bot_and_declined_by_teammates(self):
        from bot import etkilesim as ET
        kim = {'userId': 'Nova', 'id': str(self.p.user_id), 'factionId': '1'}
        mate = self.y.botlar[0]
        k = ET.karar(self.y, mate, 'duello', 'Nova', kim, None, 'who wants to duel me', self.now)
        self.assertEqual((k['kabul'], k['kalip'][0]), (False, 'duello_ayni'))           # same company: no fight
        foe = self.y.botlar[1]
        foe.k['firma'], foe.k['seviye'] = 2, 20
        foe.k['kisilik']['ozellik'].update(saldirganlik=1.0, rekabet=1.0)
        foe.r.random = lambda: 0.0
        k = ET.karar(self.y, foe, 'duello', 'Nova', kim, '4-4', '1v1 me on 4-4', self.now)
        self.assertTrue(k['kabul'])
        ET.uygula(self.y, foe, k)
        self.assertEqual(foe.k['niyet']['hedef'], 'duello')
        self.assertEqual(foe.k['niyet']['plan'], {'harita': 16, 'ad': 'Nova'})

    def test_where_are_you_and_come_here_are_answered_truthfully(self):
        from bot import etkilesim as ET
        b = self.y.botlar[0]
        b.k['seviye'] = 10
        kim = {'userId': 'Nova', 'id': str(self.p.user_id), 'factionId': '1'}
        k = ET.karar(self.y, b, 'takip', 'Nova', kim, None, 'where are you?', self.now)
        import harita as H
        self.assertEqual(k['kalip'], ('nerede', {'harita': H.name(b.harita)}))
        b.r.random = lambda: 0.0
        k = ET.karar(self.y, b, 'takip', 'Nova', kim, '1-3', 'come to 1-3', self.now)
        ET.uygula(self.y, b, k)
        self.assertEqual(b.k['niyet']['plan']['harita'], 3)
        b.k['seviye'] = 1
        k = ET.karar(self.y, b, 'takip', 'Nova', kim, '1-5', 'come to 1-5', self.now)
        self.assertEqual((k['kabul'], k['kalip'][0]), (False, 'gelemem'))   # level too low: says so instead of promising

    # ------------------------------------------------------------ renamed and deleted bots everywhere (ad_kaydi)
    def nova_clan_with(self, *bots):
        import klan as KL
        self.p.d['pilot']['credits'] = 1_000_000
        out = KL.Klan(self.p).handle('FoundClanRequest', {'clanTag': 'NOVA', 'clanName': 'Novas', 'clanDescription': 'x'})
        self.assertTrue(out[0][1]['success'])
        k = KL.klani(self.p)
        for b in bots:
            k['uyeler'][b.ad.lower()] = {'ad': b.ad, 'uid': b.uid, 'firma': b.firma, 'seviye': 1, 'rutbe': 0}
        KL.degisti(k)
        return k

    def befriend(self, b):
        import rehber as RH
        RH.kayit(self.p)['arkadas'].append(b.ad)
        RH.kayit(toplum_profil(b))['arkadas'].append('Nova')

    def test_a_renamed_bot_is_renamed_in_clans_contacts_and_other_bots_memory_while_playing(self):
        import ad_kaydi as AK
        import klan as KL
        import rehber as RH
        b, o = self.y.botlar[0], self.y.botlar[1]
        k = self.nova_clan_with(b)
        self.befriend(b)
        o.hafiza.olay(b.ad, 'grup', self.now)
        eski = b.ad
        AK.ekle([{'tur': 'ad', 'eski': eski, 'yeni': 'NewName77'}])
        self.assertEqual(self.y.ad_kaydi_uygula(), 1)                  # the panel's channel call while the game runs
        self.assertEqual(b.ad, 'NewName77')
        self.assertIs(self.y.ada['newname77'], b)
        self.assertIn('newname77', k['uyeler'])
        self.assertNotIn(eski.lower(), k['uyeler'])
        self.assertIn('newname77', self.p.d['klan']['uyeler'])          # the player's copy of his clan too
        self.assertIn('NewName77', RH.kayit(self.p)['arkadas'])
        self.assertNotIn(eski, RH.kayit(self.p)['arkadas'])
        self.assertGreater(o.hafiza.iliski('NewName77'), 0)
        self.assertEqual(toplum_profil(b).d['pilot']['userName'], 'NewName77')

    def test_a_deleted_bot_leaves_every_clan_and_contact_list_and_a_bot_led_clan_passes_to_the_player(self):
        import ad_kaydi as AK
        import klan as KL
        import rehber as RH
        from bot import toplum
        lider, uye = self.y.botlar[0], self.y.botlar[1]
        lider.k['kisilik']['arketip'] = 'lider'
        lider.k['seviye'], lider.k['kredi'] = 12, 3_000_000
        for _ in range(40):
            if lider.k.get('klan'):
                break
            toplum.klan_isleri(self.y, lider, self.now)
        k = KL.KLANLAR[lider.k['klan']]
        k['uyeler']['nova'] = {'ad': 'Nova', 'uid': self.p.user_id, 'firma': 1, 'seviye': 10, 'rutbe': 0}
        k['uyeler'][uye.ad.lower()] = {'ad': uye.ad, 'uid': uye.uid, 'firma': 1, 'seviye': 1, 'rutbe': 0}
        self.befriend(uye)
        AK.ekle([{'tur': 'sil', 'ad': lider.ad}, {'tur': 'sil', 'ad': uye.ad}])
        AK.klanlar_uygula(KL)
        self.assertEqual(set(k['uyeler']), {'nova'})
        self.assertEqual(k['lider'], 'nova')                            # the clan is the player's now, not gone
        self.assertNotIn(uye.ad, RH.kayit(self.p)['arkadas'])

    def test_offline_changes_reach_the_players_clan_copy_at_login(self):
        import ad_kaydi as AK
        import klan as KL
        b, c = self.y.botlar[0], self.y.botlar[1]
        k = self.nova_clan_with(b, c)
        cid = k['id']
        KL.KLANLAR.clear()                                              # another session: only the player's copy remains
        AK.ekle([{'tur': 'ad', 'eski': b.ad, 'yeni': 'Renamed01'}, {'tur': 'sil', 'ad': c.ad}])
        m = KL.bagla(self.p, log=lambda *_: None)
        self.assertEqual(m['id'], cid)
        self.assertEqual(set(m['uyeler']), {'nova', 'renamed01'})

    def test_the_panel_logs_renames_shrinking_and_deletion(self):
        import ad_kaydi as AK
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server" / "panel"))
        import botlar as BTP
        pid = BTP.olustur('Ad Kaydi Deneme', adet=12)
        d = BTP.oku(pid)
        n = AK.son()
        BTP.bot_adi(pid, d['kadro'][0]['no'], 'Renamed02')
        BTP.kadro(pid, adet=10)
        BTP.sil(pid)
        ev = AK.yeniler(n)
        self.assertEqual(ev[0], dict(ev[0], tur='ad', eski=d['kadro'][0]['ad'], yeni='Renamed02'))
        self.assertEqual([e['ad'] for e in ev[1:3]], [x['ad'] for x in d['kadro'][10:12]])
        self.assertEqual(len([e for e in ev if e['tur'] == 'sil']), 2 + 10)

    def test_clan_leader_tells_the_player_to_apply_and_accepts_him(self):
        import klan as KL
        from bot import toplum
        b = self.y.botlar[0]
        b.k['kisilik']['arketip'] = 'lider'
        b.k['seviye'], b.k['kredi'] = 12, 3_000_000
        for _ in range(40):
            if b.k.get('klan'):
                break
            toplum.klan_isleri(self.y, b, self.now)
        k = KL.KLANLAR[b.k['klan']]
        self.y.fisilti_gelen(b.ad, 'is your clan recruiting?', {'userId': 'Nova', 'id': str(self.p.user_id), 'factionId': '1'})
        self.advance(30)
        self.assertTrue(any(w[0] == 'Nova' and k['etiket'] in w[1] for w in self.chat.whispers))
        self.p.d['pilot']['credits'] = 100000
        KL.Klan(self.p).handle('ApplyClanRequest', {'clanId': k['id'], 'message': 'hi'})
        b.r.random = lambda: 0.99                                         # would normally refuse; the promise holds
        for _ in range(3):
            toplum.klan_isleri(self.y, b, self.now)
            self.now += 400
        self.assertIn('nova', k['uyeler'])

    def test_bot_reads_a_mail_and_answers_it_by_mail(self):
        import posta as PS
        b = self.y.botlar[0]
        out = PS.Posta(self.p, log=lambda *_: None).handle('UserMessageSendRequest', {
            'recipients': [b.ad], 'subject': 'hey', 'body': 'wanna group up later?', 'recipientType': 'user'})
        self.assertTrue(out[0][1]['success'])
        self.assertTrue(b.k['posta']['gelen'])                           # the bot's mailbox is part of its save
        self.advance(900)
        self.assertEqual(b.k['posta']['gelen'][0]['durum'], PS.OKUNDU)
        got = [r for r in self.p.d['posta']['gelen'] if r.get('gonderen') == b.ad]
        self.assertTrue(got and got[0]['konu'].startswith('Re: '))

    def test_new_bots_bid_on_cheap_useful_auction_lots(self):
        import muzayede as MZ
        from bot import toplum
        b = self.y.botlar[0]
        toplum.profil(b)
        b.k['kredi'] = 60000
        b.r.random = lambda: 0.0
        b.r.choice = lambda seq: next(l for l in seq if l['loot'] == 'ammunition_laser_mcb-25') if seq and isinstance(seq[0], dict) \
            else seq[0]
        toplum.muzayede(self.y, b, self.now)
        self.assertTrue(any(k.endswith('ammunition_laser_mcb-25') for k in b.k['muzayede']['teklifler']))
        self.assertLess(b.k['kredi'], 60000)


class BotShips(unittest.TestCase):
    def test_tough_aliens_get_double_ammo_from_stock(self):
        from types import SimpleNamespace as NS
        from bot import silah as SL
        b = Bot(dict(no=1, ad='a', firma=1, kisilik=KS.kisilik_uret(random.Random(5), 'kasici')))
        b.k['kisilik']['ozellik']['tutumluluk'] = 0.0
        b.k['stok'] = {SL.LCB: 100, SL.MCB25: 10}
        n = NS(bot=b)
        saimon, lordakia = NS(bot=None, d=K.NPC['tipler']['75']), NS(bot=None, d=K.NPC['tipler']['71'])
        self.assertEqual(BG._cephane(n, 1, saimon, None), SL.MCB25)
        for _ in range(9):
            BG._cephane(n, 1, saimon, None)
        self.assertNotIn(SL.MCB25, b.k['stok'])                       # one round per laser per shot
        self.assertEqual(BG._cephane(n, 1, saimon, None), SL.LCB)     # x2 ran out: back to x1
        self.assertEqual(BG._cephane(n, 2, lordakia, None), SL.LCB)
        b.k['stok'] = {}
        self.assertIsNone(BG._cephane(n, 3, lordakia, None))          # no ammo, no shot
        self.assertGreater(BG._atis(b, cephane=SL.MCB25), BG._atis(b) * 1.2)

    def test_abstract_hunting_spends_ammo_and_restocks(self):
        from bot import silah as SL
        b = Bot(dict(no=1, ad='a', firma=1, kisilik=KS.kisilik_uret(random.Random(5), 'kasici')))
        for _ in range(60):
            S.kas(b, 30, None)
        self.assertLess(b.k['stok'].get(SL.LCB, 0), 1000)
        self.assertLess(b.k['stok'].get(SL.ROKETLER[0], 0), 20)       # rockets were fired too
        b.k['stok'] = {}
        b.k['kredi'] = 50000
        kills = b.k['istat'].get('npc', 0)
        S.kas(b, 600, None)
        self.assertEqual(b.k['istat'].get('npc', 0), kills)           # nothing to shoot with
        self.assertGreater(SL.ikmal(b).get(SL.LCB, 0), 0)
        self.assertLess(b.k['kredi'], 50000)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Profil(path=str(Path(self.tmp.name) / 'pilot.json'))
        self.p.d['pilot'].update(factionId=1, userName='Nova')
        self.sent = []
        self.y = YN.Yonetici(paket(3, tohum=21), None, log=lambda *_: None)
        YN.AKTIF = self.y
        self.addCleanup(setattr, YN, 'AKTIF', None)

    def world(self, map_id, x=10000, y=6000):
        self.p.d['konum'].update(mapId=map_id, x=x, y=y)
        w = dunya.World(self.p, self.sent.extend, lambda t: None, map_id)
        w.hero = dunya.Mover(x, y)
        return w

    def embody(self, w, b, x, y):
        now = time.time()
        b.k['harita'] = int(w.map_id)
        b.k['x'], b.k['y'] = x, y
        self.y.giris(b, now)
        b.oturum_bitis = now + 1e6
        w._bot_t = 0
        BG.tick(w, now)
        return b.govde

    def test_bot_appears_as_a_player_ship(self):
        w = self.world(3)
        b = self.y.botlar[0]
        n = self.embody(w, b, 10300, 6000)
        self.assertIs(w.npcs[b.uid], n)
        create = w.ship_create(n)[1]
        self.assertFalse(create['npc'])
        self.assertEqual((create['userName'], create['factionId'], create['typeId']), (b.ad, b.firma, 'ship_phoenix'))

    def test_player_kill_pays_pvp_reward_and_bot_goes_home(self):
        w = self.world(13)
        b = next(x for x in self.y.botlar if x.firma != 1) if any(x.firma != 1 for x in self.y.botlar) else self.y.botlar[0]
        b.k['firma'] = 2
        n = self.embody(w, b, 10300, 6000)
        w.view_tick(time.time())
        self.assertIn(n.id, w.visible)
        honour = self.p.d['pilot'].get('honourPoints', 0)
        with w.lock:
            w.hit_npc(n.id, 10 ** 8, 1)
        self.assertNotIn(n.id, w.npcs)
        self.assertGreater(self.p.d['pilot'].get('honourPoints', 0), honour)
        self.assertEqual(b.k['istat'].get('olum'), 1)
        self.assertIn('Nova', b.hafiza.kinliler())
        self.assertIn('ShipDestroyedCommand', [m[0] for m in self.sent])

    def test_own_faction_bot_is_protected_on_start_maps(self):
        w = self.world(1)
        b = self.y.botlar[0]
        b.k['firma'] = 1
        n = self.embody(w, b, 10300, 6000)
        self.assertTrue(BG.saldiri_hatasi(w, n))
        hp = n.hp
        with w.lock:
            w.hit_npc(n.id, 5000, 1)
        self.assertEqual(n.hp, hp)

    def test_bot_kill_rewards_bot_not_player(self):
        w = self.world(1, 5000, 5000)
        b = self.y.botlar[0]
        b.k['firma'] = 1
        n = self.embody(w, b, 12000, 6000)
        m = dunya.NPC(91001, '84', 12300, 6000)
        w.npcs[m.id] = m
        m.hp, m.shield = 1, 0
        n.hedef = m.id
        ep = self.p.d['pilot'].get('ep', 0)
        with w.lock:
            for k in range(20):
                if m.id not in w.npcs:
                    break
                n.next_shot = 0
                BG.ates(w, n, time.time())
        self.assertNotIn(m.id, w.npcs)
        self.assertEqual(self.p.d['pilot'].get('ep', 0), ep)
        self.assertGreater(b.k['ep'], 0)
        self.assertTrue(any(t[1] == 'npc' for t in w.pending))       # the alien respawns

    def test_world_stop_removes_bot_ships_before_caching(self):
        w = self.world(3)
        b = self.y.botlar[0]
        self.embody(w, b, 10300, 6000)
        w.stop()
        self.assertFalse(any(n.bot is not None for n in w.npcs.values()))
        self.assertIsNone(b.govde)


if __name__ == '__main__':
    unittest.main()


class Extras(unittest.TestCase):
    """CPUs and extras bought like a player and used where they matter."""

    def bot(self, seviye=10):
        b = Bot(dict(no=1, ad='e', firma=1, kisilik=KS.kisilik_uret(random.Random(6), 'kasici')))
        b.k['seviye'] = seviye
        b.k['ekip']['gemi'] = 'ship_goliath'
        return b

    def test_cargo_cpu_hm7_and_repair_bot_slot(self):
        from bot import ekstra as EK
        from bot.hedefler import satis as SA
        b = self.bot()
        cap = K.kargo_kapasitesi(b.k['ekip'])
        b.ekle(EK.KARGO)
        self.assertEqual(K.kargo_kapasitesi(b.k['ekip']), 2 * cap)
        b.ekle(EK.HM7)
        b.kargo_ekle({2: 100})
        g = SA.Satis()
        g.basla(b, NS(y=None, now=T0))
        self.assertTrue(g.bitti(b, None))
        self.assertEqual(b.kargo_dolu(), 0)                           # sold where it stood
        self.assertEqual(EK.takili(b)[EK.HM7], 99)
        b.ekle('equipment_extra_repbot_rep-1')
        b.ekle('equipment_extra_repbot_rep-3')
        self.assertEqual(EK.onarim_seviyesi(b), 4)
        self.assertNotIn('equipment_extra_repbot_rep-1', EK.takili(b))   # one repair bot at a time

    def test_jump_cpu_takes_the_bot_home_in_one_jump(self):
        from bot import ekstra as EK
        b = self.bot()
        b.ekle(EK.JP2)
        b.k['harita'] = 19                                              # 1-7: far from 1-1
        self.assertTrue(S.git(b, 1))
        self.assertEqual(b.harita, 1)
        self.assertIsNone(b.yolda)
        self.assertEqual(EK.takili(b)[EK.JP2], 19)

    def test_cloak_lets_a_weak_bot_slip_away(self):
        from bot import ekstra as EK
        guclu, zayif = self.bot(), self.bot()
        zayif.k['ekip']['gemi'] = 'ship_phoenix'
        zayif.k['kisilik']['ozellik']['risk'] = 0.0
        zayif.ekle(EK.GIZLE[1])
        sonuc = S.karsilasma(guclu, zayif, None, T0)
        self.assertEqual(sonuc[0], 'kacti')
        self.assertEqual(EK.takili(zayif)[EK.GIZLE[1]], 9)


class LabSkylabTech(unittest.TestCase):
    """Refining and lab upgrades, the bot's own Skylab, Assembly tech items and the rocket launcher."""

    def bot(self, seviye=10, **oz):
        b = Bot(dict(no=1, ad='l', firma=1, kisilik=KS.kisilik_uret(random.Random(7), 'kasici')))
        b.k['seviye'] = seviye
        b.k['kisilik']['ozellik'].update(oz)
        return b

    def test_lab_refines_cargo_and_boosts_lasers_until_used_up(self):
        from bot import lab as LB, silah as SL
        b = self.bot(hirs=0.9, rekabet=0.8, tutumluluk=0.1)
        b.k['kargo'] = {'0': 400, '1': 300, '2': 300}
        dps0 = SL.kasma_plani(b, 5000)[3]
        b.kargo_sat()
        self.assertEqual(LB.bonus(b, LB.LAZER), 0.15)                   # Prometid on the lasers
        self.assertGreater(SL.kasma_plani(b, 5000)[3], dps0 * 1.1)
        kalan = b.k['lab']['0'][1]
        LB.harca(b, LB.LAZER, kalan)
        self.assertEqual(LB.bonus(b, LB.LAZER), 0.0)
        frugal = self.bot(hirs=0.1, rekabet=0.1, tutumluluk=0.95)
        frugal.k['kargo'] = {'0': 400, '1': 300}
        frugal.kargo_sat()
        self.assertFalse(frugal.k.get('lab'))                          # sells instead

    def test_skylab_produces_upgrades_and_ships_ore(self):
        from bot import skylab as SK
        b = self.bot()
        b.k['kredi'] = 10 ** 7
        st = SK.durum(b, T0)
        now = T0
        for _ in range(24):
            now += 3600
            SK.yatirim(b, now)
        self.assertGreater(sum(SK.seviye(st, m) for m in st['mod']), 10)
        self.assertLess(b.k['kredi'], 10 ** 7)
        b.saat = lambda: now
        SK.tasi(b, now, 10 ** 6)                                       # earlier quota used up
        got = SK.tasi(b, now + 3600, 10 ** 6)
        self.assertAlmostEqual(sum(got.values()), 3600 / SK.TASIMA_SN, delta=2)       # 500 per hour
        b.izin = {'skylab': False}
        self.assertIsNone(SK.yatirim(b, now + 7200))

    def test_assembly_tech_items_and_launcher(self):
        from bot import teknoloji as TK, silah as SL
        b = self.bot(seviye=12, saldirganlik=0.9, risk=0.5, tutumluluk=0.1)
        b.k['uridyum'] = 100000
        made = TK.uret(b)
        self.assertIn('tech_backup-shields', made)
        self.assertLess(b.k['uridyum'], 100000)
        self.assertGreater(TK.pvp_carpani(b), 1.1)
        b.ekle(TK.HST[1])
        b.k['stok'][TK.FROKET[1]] = 50
        b.k['ekip']['gemi'] = 'ship_phoenix'
        with_l = SL.kasma_plani(b, 10 ** 6)[2]
        self.assertGreater(with_l, TK.fircatici_dps(b, TK.FROKET[1]) * 0.99)
        SL.tuket(b, 10 ** 6, *SL.kasma_plani(b, 10 ** 6))
        self.assertLess(b.k['stok'].get(TK.FROKET[1], 0), 50)


class LootGatesPasses(unittest.TestCase):
    """Booty boxes and keys, the Assembly, Galaxy Gates, Battle Pass, Season Pass and event boxes."""

    def bot(self, **oz):
        b = Bot(dict(no=1, ad='g', firma=1, kisilik=KS.kisilik_uret(random.Random(8), 'kasici')))
        b.k['kisilik']['ozellik'].update(oz)
        return b

    def test_green_key_bought_only_when_worth_it_and_box_pays_out(self):
        from bot import ganimet as GB
        b = self.bot(tutumluluk=0.1)
        b.k['uridyum'] = 20000
        self.assertTrue(GB.acar_mi(b, 'PIRATE_BOOTY'))
        self.assertEqual(b.k['uridyum'], 18500)                     # one green key, 1.500 U
        self.assertTrue(GB.ac(b, 'PIRATE_BOOTY', random.Random(3)))
        self.assertNotIn('resource_booty-key', b.k['stok'])
        poor = self.bot(tutumluluk=0.9)
        poor.k['uridyum'] = 3000
        self.assertFalse(GB.acar_mi(poor, 'PIRATE_BOOTY'))          # a frugal pilot keeps his uridium
        self.assertFalse(GB.acar_mi(poor, 'PIRATE_BOOTY_RED'))      # red keys are never sold
        poor.k['stok']['resource_booty-key-red'] = 1
        self.assertTrue(GB.acar_mi(poor, 'PIRATE_BOOTY_RED'))

    def test_assembly_turns_alien_resources_into_a_key(self):
        from bot import ganimet as GB
        b = self.bot()
        b.saat = lambda: T0
        b.k['stok'].update({'resource_collectable_scrapium': 40, 'resource_collectable_aurus': 20,
                            'resource_collectable_schism': 10})
        self.assertTrue(GB.assembly(b))
        self.assertTrue(any(k.startswith('resource_booty-key') for k in b.k['stok']))
        self.assertIsNone(GB.assembly(b))                           # looks again 10 minutes later

    def test_gate_generator_build_and_run(self):
        from bot import kapi as KP
        b = self.bot(hirs=0.9, rekabet=0.9, tutumluluk=0.0)
        b.k['seviye'] = 15
        b.k['ekip'].update(gemi='ship_goliath', lazer={'equipment_weapon_laser_lf-3': 15},
                           kalkan={'equipment_generator_shield_sg3n-b02': 15})
        b.k['stok']['ammunition_laser_mcb-50'] = 100000
        b.ekip_degisti()
        b.k['stok'][KP.ENERJI] = 3000
        while KP.durum(b)['kurulu'] == [] and b.k['stok'].get(KP.ENERJI):
            KP.cekilis(b, 'alpha', 50)
        self.assertTrue(KP.durum(b)['kurulu'])
        k = KP.durum(b)['kurulu'][0]
        ep = b.k['ep']
        KP.odullendir(b, k)
        self.assertGreater(b.k['ep'], ep + 1000000)
        self.assertEqual(KP.durum(b)['kronos'], 1)

    def test_battle_pass_season_pass_and_event_boxes(self):
        from bot import etkinlik as ET
        b = self.bot(hirs=0.9)
        with patch.object(ET, 'aktif_pass', return_value='halloween'):
            ET.battle_pass(b, ET.PASS_GOREV_SN * 3)
        self.assertEqual(b.k['pass']['tamam'], 3)
        b.k['stok']['resource_battle-pass-key'] = 30
        ET.degistir(b, b.k['pass'])
        self.assertLess(b.k['stok'].get('resource_battle-pass-key', 0), 30)
        ET.season_pass(b, 3600 * 10)
        self.assertGreater(b.k['sezon']['seviye'], 1)
        spec = {'mod': 'biri', 'icerik': [['resource_collectable_candy-corn', [20, 60], 100]]}
        ET.kutu_ac(b, spec)
        self.assertGreaterEqual(b.k['stok']['resource_collectable_candy-corn'], 20)


class EventModes(unittest.TestCase):
    """Event-specific and PvE modes: entry rules, a run on the mode's own map, rewards by progress; Dispatch."""

    def bot(self, gemi='ship_goliath', lazer=15, seviye=20):
        b = Bot(dict(no=1, ad='m', firma=1, kisilik=KS.kisilik_uret(random.Random(9), 'kasici')))
        b.k['seviye'] = seviye
        b.k['ekip'].update(gemi=gemi, lazer={'equipment_weapon_laser_lf-3': lazer},
                           kalkan={'equipment_generator_shield_sg3n-b02': lazer})
        b.k['stok']['ammunition_laser_mcb-50'] = 100000
        b.ekip_degisti()
        return b

    def test_every_mode_builds_its_waves(self):
        from bot import modlar as MD
        b = self.bot()
        for m in MD.modlar():
            ul, top, sure, odul = MD.tahmin(b, m)
            self.assertGreater(top, 0, m.ad)
            self.assertLessEqual(ul, top, m.ad)
        weak = self.bot('ship_phoenix', 1, 8)
        self.assertLess(MD.tahmin(weak, MD.Voyagers())[0], MD.tahmin(b, MD.Voyagers())[0])

    def test_voyagers_run_hides_the_bot_and_pays_by_stars(self):
        from bot import modlar as MD
        from bot.hedefler import mod_kosusu as MK
        y = YN.Yonetici(paket(2), None, log=lambda *_: None, now=T0)
        b = y.botlar[0]
        b.k.update(seviye=20)
        b.k['ekip'].update(self.bot().k['ekip'])
        b.k['stok']['ammunition_laser_mcb-50'] = 100000
        b.ekip_degisti()
        b.cevrimici = True
        g = MK.ModKosusu()
        b._mod_aday, b._mod_bak = MD.Voyagers(), T0 + 999
        ctx = NS(y=y, now=T0)
        g.basla(b, ctx)
        self.assertEqual(b.harita, MD.Voyagers.harita)                   # off your map during the run
        self.assertEqual(MD.durum(b, 'voyagers')['ucretsiz'], MD.gun())   # the free daily entry was used
        y.now = b.plan['bitis'] + 1
        stok0 = dict(b.k['stok'])
        g.soyut(b, 5, y)
        self.assertTrue(g.bitti(b, None))
        self.assertIn(b.harita, K.HARITALAR)
        self.assertEqual(b.k['istat'].get('mod_kosu'), 1)
        if b.plan['ul'] == b.plan['top']:
            self.assertNotEqual(b.k['stok'], stok0)

    def test_event_gate_rules_daily_and_cpu(self):
        from bot import modlar as MD
        b = self.bot()
        plutus = next(m for m in MD.modlar() if m.kimlik == 'ekapi_plutus_kolay')
        self.assertTrue(plutus.girebilir(b, T0))
        plutus.kaydet(b, 44, 44)
        self.assertFalse(plutus.girebilir(b, T0))                       # once a day (Easy and Normal share it)
        normal = next(m for m in MD.modlar() if m.kimlik == 'ekapi_plutus')
        self.assertFalse(normal.girebilir(b, T0))
        karantina = next(m for m in MD.modlar() if m.kimlik == 'ekapi_karantina')
        b.k['uridyum'] = 0
        self.assertFalse(karantina.bedel(b))                           # needs its CPU
        b.k['stok'][karantina.kural['cpu']] = 1
        self.assertTrue(karantina.bedel(b))

    def test_dispatch_sends_a_retriever_and_brings_rewards(self):
        from bot import modlar as MD
        b = self.bot()
        b.k['kredi'] = 10 ** 8
        MD.dispatch(b, T0)
        st = MD.durum(b, 'dispatch')
        self.assertIn('bitis', st)
        MD.dispatch(b, st['bitis'] + 1)
        self.assertEqual(b.k['istat'].get('dispatch'), 1)


class ReviewRegressions(unittest.TestCase):
    """Bugs found in the 2026-10-30 review."""

    def test_death_repair_is_chosen_like_a_player_and_costs_no_credits(self):
        y = YN.Yonetici(paket(5), None, log=lambda *_: None, now=T0)
        b = y.botlar[0]
        b.k['firma'], b.k['harita'], b.k['x'], b.k['y'] = 1, 3, 9000, 6000      # 1-3: two jumps from home
        b.k['kisilik']['ozellik'].update(sabir=0.0, tutumluluk=0.0)
        b.ruh.d['ofke'] = 1.0
        b.k['uridyum'], b.k['kredi'], kredi = 100000, 50000, 50000
        with patch.object(b.r, 'random', return_value=0.0):
            S.olum(b, y, neden='oyuncu', katil='X', now=T0)
        self.assertEqual(b.olaylar[-1]['tamir'], 'yerinde')
        self.assertEqual((b.harita, b.k['kredi'], b.k['uridyum']), (3, kredi, 99000))
        self.assertTrue(b.yerinde_tamir and b.olu_bitis <= T0 + 15)
        b.k['uridyum'] = 0                                           # can't afford: free station repair at home
        S.olum(b, y, neden='npc', now=T0)
        self.assertEqual(b.olaylar[-1]['tamir'], 'istasyon')
        self.assertEqual((b.harita, b.k['kredi']), (K.ev(1), kredi))
        self.assertFalse(b.k['x'])                                   # spawns around the station, not where it died

    def test_event_drops_with_a_chance_are_read_like_the_game_reads_them(self):
        from bot import etkinlik as ET
        b = Bot(dict(no=1, ad='a', firma=1, kisilik=KS.kisilik_uret(random.Random(1))))
        tablo = {'dusme': {'84': {'resource_logfile': {'adet': 2, 'olasilik': 1.0}, 'resource_collectable_agate-splinter': [3, 3]}}}
        with patch.object(ET, 'bolumler', return_value=[('agatus', tablo)]):       # Agatus: {adet, olasilik} broke the bots
            ET.dusme(b, 1, '84')
        self.assertEqual(b.k['istat'].get('etkinlik_dusme'), 5)

    def test_a_broken_bot_does_not_stop_the_manager_or_saving(self):
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, 'p', 'durum.json')
        y = YN.Yonetici(paket(20), path, log=lambda *_: None, now=T0)
        bad = next(b for b in y.botlar if b.cevrimici) if any(b.cevrimici for b in y.botlar) else y.botlar[0]
        bad.cevrimici = True
        del bad.k['kisilik']['ozellik']['hirs']
        now = T0
        for _ in range(120):
            now += 1
            y.tick(now)
        self.assertTrue(os.path.exists(path))
        self.assertTrue(any(b.k['istat'].get('sure_sn') for b in y.botlar if b is not bad))

    def test_unsellable_palladium_does_not_trap_the_bot_in_selling(self):
        from bot.hedefler import satis as SA
        b = Bot(dict(no=1, ad='p', firma=1, kisilik=KS.kisilik_uret(random.Random(1), 'kasici')))
        b.k['kargo'] = {'8': 100}
        self.assertTrue(SA.Satis().uygun(b, None))
        b.kargo_sat()
        self.assertFalse(SA.Satis().uygun(b, None))
        self.assertEqual(b.k['stok'].get('resource_ore_palladium'), 100)

    def test_mode_run_postpones_logout_and_dead_ship_is_cleared(self):
        y = YN.Yonetici(paket(2), None, log=lambda *_: None, now=T0)
        b = y.botlar[0]
        y.giris(b, T0)
        b.hedef = NS(ad='mod', soyut=lambda *a: None, somut=lambda *a: False, bitti=lambda *a: False)
        b.plan = {'mod': 'x'}
        b.oturum_bitis = T0 - 1
        y.bot_tick(b, T0 + 5)
        self.assertTrue(b.cevrimici)                                     # stays until the run is over
        b.plan['bitti'] = True
        y.bot_tick(b, T0 + 10)
        self.assertFalse(b.cevrimici)
        self.assertIsNone(b.govde)


class ActiveItems(unittest.TestCase):
    """An on-screen bot uses tech items and active CPUs with the same client messages a player's ship sends."""
    world, embody = BotShips.world, BotShips.embody

    def setUp(self):
        BotShips.setUp(self)
        self.w = self.world(13, 5000, 5000)                               # 4-1: PvP allowed
        self.b = self.y.botlar[1]
        self.b.k['firma'] = 2
        self.n = self.embody(self.w, self.b, 5300, 5000)
        self.w.tanir = lambda uid: True

    def legacy(self, kod):
        return any(kod in str(m) for m in self.sent)

    def test_insta_shield_backup_shields_and_cloak(self):
        from bot import aktif as AK, ekstra as EK, silah as SL
        b, n, w = self.b, self.n, self.w
        b.ekle(EK.ISH)
        b.k['stok'].update({SL.MAYINLAR[0]: 10, 'tech_backup-shields': 1})
        now = time.time()
        n.saldiran[w.hid] = now
        d = b.deger()
        with w.lock:
            AK.savas(w, n, now, d, 0.2, [w.hid])
        self.assertTrue(self.legacy('0|n|ISH|%d' % n.id))
        self.assertTrue(self.legacy('0|n|A|S|SBU|%d' % n.id))
        self.assertTrue(AK.korumali(n, now + 1))
        self.assertFalse(BG.vuruldu(w, n))                                 # invulnerable for 3 s
        self.assertFalse(AK.korumali(n, now + 5))
        b.ekle(EK.GIZLE[1])
        w.target = n.id
        with w.lock:
            self.assertTrue(AK.gizlen(w, n, now))
        self.assertTrue(self.legacy('0|n|INV|%d|1' % n.id))
        self.assertIsNone(w.target)
        AK.gorun(w, n)
        self.assertTrue(self.legacy('0|n|INV|%d|0' % n.id))

    def test_emp_aim_and_chain_impulse(self):
        from bot import aktif as AK, ekstra as EK, silah as SL
        b, n, w = self.b, self.n, self.w
        b.k['stok'][AK.EMP] = 1
        w.target = n.id
        now = time.time()
        with w.lock:
            self.assertTrue(AK.emp(w, n, now))
        self.assertIsNone(w.target)
        b.ekle(EK.AIM2)
        b.k['kargo']['3'] = 100
        self.assertGreater(AK.nisan(n, 0.8, True), 0.85)
        self.assertEqual(b.k['kargo']['3'], 90)                           # 10 Xenomit per shot
        self.assertEqual(AK.nisan(n, 0.8, False), 0.8)                   # not wasted on easy targets
        ms = []
        for i in range(3):
            m = dunya.NPC(92000 + i, '71', 5400 + i * 50, 5000)
            m.hp, m.shield = 50000, 3000
            w.npcs[m.id] = m
            ms.append(m)
        b.k['stok']['tech_chain-impulse'] = 1
        with w.lock:
            AK.chain_impulse(w, n, now)
        self.assertTrue(self.legacy('0|n|ECI|1|%d|' % n.id))
        self.assertTrue(all(m.shield == 0 and m.hp == 50000 for m in ms))   # shield damage only


class AlienTags(unittest.TestCase):
    """First hit tags an alien: reward, quest and cargo box go to the tagger; others see the box blue and pay honor for it."""
    world, embody = BotShips.world, BotShips.embody

    def setUp(self):
        BotShips.setUp(self)
        self.p.d['pilot']['level'] = 1                                   # X-1 cargo cut does not apply
        self.w = self.world(1, 5000, 5000)
        self.b = self.y.botlar[0]
        self.b.k['firma'] = 1
        self.n = self.embody(self.w, self.b, 12000, 6000)
        self.m = dunya.NPC(91001, '84', 12300, 6000)
        self.w.npcs[self.m.id] = self.m

    def timers(self):
        while self.w.timers:
            t = list(self.w.timers)
            self.w.timers.clear()
            for _, fn in t:
                fn()

    def box(self):
        return next((h, k) for h, k in self.w.boxes.items() if k['tip'] in dunya.CARGO_BOXES)

    def test_bot_tagged_alien_pays_the_bot_and_its_box_is_blue_for_the_player(self):
        dunya.etiketle(self.m, ('b', self.n.id), time.time())
        ep, bep = self.p.d['pilot'].get('ep', 0), self.b.k['ep']
        with self.w.lock:
            self.w.hit_npc(self.m.id, 10 ** 8, 1)
            self.timers()
        self.assertEqual(self.p.d['pilot'].get('ep', 0), ep)
        self.assertGreater(self.b.k['ep'], bep)
        h, k = self.box()
        self.assertEqual(tuple(k['mal']), ('b', self.n.id))
        self.assertEqual(self.w.box_cmd(h, k)[1]['boxType'], 'FROM_SHIP_BLOCKED')

    def test_escort_bot_shooting_the_players_target_leaves_the_tag_to_the_player(self):
        now = time.time()
        self.w.target = self.m.id
        self.n.eslik = ('h', now + 300, 1.0)
        BG.npc_vur(self.w, self.n, self.m, 10, now, 1)
        self.assertEqual(dunya.etiket_sahibi(self.m, now), ('h', self.w.hid))
        other = dunya.NPC(91003, '84', 12350, 6000)
        self.w.npcs[other.id] = other
        BG.npc_vur(self.w, self.n, other, 10, now, 1)                   # its own target: its own tag
        self.assertEqual(dunya.etiket_sahibi(other, now), ('b', self.n.id))

    def test_others_cargo_boxes_follow_the_players_display_setting(self):
        h = self.w.drop_box('FROM_SHIP', 5000, 5000, {'1': 3}, 120, mal=('b', self.n.id))
        own = self.w.drop_box('FROM_SHIP', 5000, 5000, {'1': 3}, 120, mal=('h', self.w.hid))
        ayar = self.p.d.setdefault('ayarlar', {}).setdefault('displaySettingsModule', {})
        ayar['displayPenaltyCargoboxes'] = False
        self.assertFalse(self.w.item_in_view(h, 5000, 5000))           # hidden on the server, not left to the client
        self.assertTrue(self.w.item_in_view(own, 5000, 5000))
        ayar['displayPenaltyCargoboxes'] = True
        self.assertTrue(self.w.item_in_view(h, 5000, 5000))

    def test_player_tagged_alien_finished_by_a_bot_pays_the_player(self):
        dunya.etiketle(self.m, ('h', self.w.hid), time.time())
        ep, bep = self.p.d['pilot'].get('ep', 0), self.b.k['ep']
        with self.w.lock:
            BG.npc_oldur(self.w, self.m, self.n, time.time())
            self.timers()
        self.assertGreater(self.p.d['pilot'].get('ep', 0), ep)
        self.assertEqual(self.b.k['ep'], bep)
        h, k = self.box()
        self.assertEqual(self.w.box_cmd(h, k)[1]['boxType'], k['tip'])                # own box: normal look

    def test_stealing_a_same_company_box_costs_doubling_honor(self):
        self.p.d['pilot']['honourPoints'] = 1000
        for i in range(2):
            h = self.w.drop_box('FROM_SHIP', 5000, 5000, {'1': 3}, 120, mal=('b', self.n.id))
            with self.w.lock:
                self.w.take_box(h)
        self.assertEqual(self.p.d['pilot']['honourPoints'], 1000 - 10 - 20)
        self.assertLess(self.b.hafiza.iliski('Nova'), 0)                 # the bot remembers

    def test_tag_of_a_bot_that_left_the_map_falls_to_the_killer(self):
        dunya.etiketle(self.m, ('b', self.n.id), time.time())
        with self.w.lock:
            BG.kaldir(self.w, self.n)                                    # the tagging bot flew away
        ep = self.p.d['pilot'].get('ep', 0)
        with self.w.lock:
            self.w.hit_npc(self.m.id, 10 ** 8, 1)
            self.timers()
        self.assertGreater(self.p.d['pilot'].get('ep', 0), ep)

    def test_tag_expires_and_can_be_switched_off(self):
        now = time.time()
        dunya.etiketle(self.m, ('b', self.n.id), now)
        dunya.etiketle(self.m, ('h', self.w.hid), now + 1)              # someone else cannot take it over
        self.assertEqual(dunya.etiket_sahibi(self.m, now + 2), ('b', self.n.id))
        self.assertIsNone(dunya.etiket_sahibi(self.m, now + dunya.ETIKET_SN + 2))
        from unittest.mock import patch
        eski = dunya.AY.get
        with patch.object(dunya.AY, 'get', lambda k: False if k == 'etiket' else eski(k)):
            self.assertIsNone(dunya.etiket_sahibi(self.m, now + 2))

    def test_duel_bot_attacks_the_challenger_at_once_and_the_duel_ends_with_a_kill(self):
        from bot import beyin as B
        b, n = self.b, self.n
        b.k['firma'] = 2
        self.p.d['pilot']['userName'] = 'Nova'
        b.hedef = B.HEDEFLER['duello']
        b.plan = {'ad': 'Nova', 'harita': 1}
        b.k['niyet'] = dict(hedef='duello', pay=1.5, bitis=time.time() + 900, plan=dict(b.plan))
        b.k['kisilik']['ozellik'].update(saldirganlik=0.0, rekabet=0.0)       # would never pick a fight on its own
        self.w.running = True
        self.w.hero = dunya.Mover(12400, 6000)
        n.niyet_t = 0
        self.assertEqual(BG.pvp_hedefi(self.w, n, time.time()), self.w.hid)
        BG.oyuncu_oldu(self.w, n)
        self.assertTrue(b.plan['bitti'])
        self.assertTrue(b.hedef.bitti(b, None))

    def test_same_company_bot_escorts_the_player_and_shoots_the_players_target(self):
        now = time.time()
        self.w.hero = dunya.Mover(12200, 6000)
        self.b.k['kisilik']['ozellik'].update(sosyallik=1.0, yardimseverlik=1.0)
        with patch.object(random, 'random', return_value=0.0):
            BG.eslik_basla(self.w, self.n, now)
        self.assertEqual(self.n.eslik[0], 'h')
        self.w.target = self.m.id
        self.n.hedef = None
        self.assertFalse(BG.eslik(self.w, self.n, now))
        self.assertEqual(self.n.hedef, self.m.id)                         # joins the player's fight
        self.w.target, self.n.hedef = None, None
        self.w.hero = dunya.Mover(15000, 6000)
        self.assertTrue(BG.eslik(self.w, self.n, now))                    # no target: flies along
        self.assertGreater(self.n.mover.x1, 14000)
        self.w.hero_dead = True
        self.assertFalse(BG.eslik(self.w, self.n, now))                   # player gone: escort ends
        self.assertNotIn('eslik', self.n.__dict__)

    def test_nearby_bot_reacts_in_chat_to_a_boss_kill(self):
        boss = dunya.NPC(91002, '84', 12300, 6000)
        boss.d['ad'] = '-=[ Boss Streuner ]=-'
        self.assertTrue(BG.patron_mu(boss))
        self.b.k['kisilik']['ozellik']['konuskanlik'] = 1.0
        with patch.object(random, 'random', return_value=0.0):
            BG.tanik(self.w, 'patron', 12300, 6000, ad=boss.d['ad'], kim='Kahraman')
        o = self.b.olaylar[-1]
        self.assertEqual((o['tur'], o['alt'], o['kim']), ('tanik', 'patron', 'Kahraman'))
        self.b.cevrimici = True
        self.y.olay_sohbet(self.b, o, time.time())
        self.assertTrue(self.y.giden and self.y.giden[-1][2] == 'firma')

    def test_bot_ship_shows_design_title_drones_formation_and_gate_rings(self):
        from bot import gorunum as GR
        b = self.b
        b.k['ekip']['gemi'] = 'ship_goliath'
        b.k['ekip']['dron'] = {'drone_iris': 5, 'drone_flax': 1}
        b.k['kisilik']['ozellik'].update(tutumluluk=0.0, rekabet=1.0, sosyallik=1.0, saldirganlik=0.9)
        b.k['uridyum'], b.k['kredi'], b.k['onur'] = 10_000_000, 50_000_000, 500_000
        b.k['istat']['npc'] = 900
        b.k.setdefault('kapi', {})['tamam'] = ['alpha', 'gamma']
        with patch.object(b.r, 'random', return_value=0.0):
            GR.alisveris(b, time.time())
        self.assertTrue(b.k['ekip']['tasarim'].startswith('ship_goliath_design_'))
        self.assertEqual(b.k['formasyon'], 'drone_formation_f-05-pi')          # aggressive, 6 drones: Pincer
        create = BG.gorunum(self.w, self.n)[1]
        self.assertEqual((create['typeId'], create['galaxyGatesDone']), (b.k['ekip']['tasarim'], 5))
        msgs = [m[1] for m in BG.ek_gorunum(self.n)]
        txt = ' '.join(str(m) for m in msgs)
        self.assertIn('0|n|t|%d|' % self.n.id, txt)
        self.assertIn('title_achievement_honor-1', txt)
        self.assertIn('0|n|d|%d|5|1|3|0|0|2|3|0|0' % self.n.id, txt)      # Pincer; Flax then 5 Iris, level 3

    def test_embodied_bot_fires_rockets_from_stock(self):
        from bot import silah as SL
        self.b.k['stok'] = {SL.LCB: 1000, 'ammunition_rocket_plt-2021': 5}
        self.m.hp, self.m.shield = 10 ** 6, 0
        now = time.time()
        self.w.tanir = lambda uid: True                                # both ends in view
        with patch.object(random, 'random', return_value=0.0):       # always hits
            with self.w.lock:
                BG.roket(self.w, self.n, self.m.id, self.m, None, now)
                BG.roket(self.w, self.n, self.m.id, self.m, None, now + 1)   # still reloading
                self.timers()
        self.assertEqual(self.b.k['stok']['ammunition_rocket_plt-2021'], 4)
        self.assertLess(self.m.hp, 10 ** 6)
        self.assertTrue(any('|v|%d|%d|H|3|' % (self.n.id, self.m.id) in str(m) for m in self.sent))      # rocket visual

    def test_fleeing_bot_drops_a_mine_behind_it(self):
        from bot import silah as SL
        w = self.world(13, 5000, 5000)                                  # 4-1: PvP map, not a start map
        b = self.y.botlar[1]
        b.k['firma'] = 2
        n = self.embody(w, b, 9000, 6000)
        b.k['stok'] = {SL.LCB: 1000, SL.MAYINLAR[0]: 3}
        now = time.time()
        n.saldiran[w.hid] = now
        w.oyuncu = lambda uid: object() if uid == w.hid else None
        with w.lock:
            BG.kac(w, n, now)
            BG.kac(w, n, now + 1)                                         # cooldown
        self.assertEqual(b.k['stok'][SL.MAYINLAR[0]], 2)
        self.assertEqual(len([m for m in w.items.mines.values() if m['sahip'] == n.id]), 1)

    def test_embodied_bot_flies_to_its_station_to_sell(self):
        from bot.hedefler import satis as SA
        self.w.station = {'posX': 2000, 'posY': 2000, 'type': 1}
        self.b.kargo_ekle({1: 100})
        g = SA.Satis()
        self.b.plan = {'harita': 1}
        self.b.yolda = None
        now = time.time()
        self.assertTrue(g.somut(self.b, self.n, self.w, now))
        self.assertGreater(self.b.kargo_dolu(), 0)                     # still flying
        self.n.mover = dunya.Mover(2100, 2100)
        kredi = self.b.k['kredi']
        self.assertTrue(g.somut(self.b, self.n, self.w, now))
        self.assertEqual(self.b.kargo_dolu(), 0)
        self.assertEqual(self.b.k['kredi'] - kredi, 100 * K.cevher_fiyatlari(self.b.k['onur'])[1])

    def test_bot_skips_tagged_aliens_and_collects_its_own_cargo(self):
        now = time.time()
        dunya.etiketle(self.m, ('h', self.w.hid), now)
        self.n.hedef = None
        BG.avlan(self.w, self.n, now)
        self.assertNotEqual(self.n.hedef, self.m.id)
        h = self.w.drop_box('FROM_SHIP', 12000, 6000, {'1': 5}, 120, mal=('b', self.n.id))
        self.n.hedef = None
        self.assertTrue(BG.kutu_topla(self.w, self.n, now))
        self.assertNotIn(h, self.w.boxes)
        self.assertEqual(self.b.k['kargo'].get('1'), 5)


class Advanced(unittest.TestCase):
    """Gelişmiş kip: the LLM client against a fake llama-server, and LLM jobs applied to bots (tools, chat)."""

    def test_client_sends_no_think_and_parses_schema_reply(self):
        import json as J
        import threading as TH
        from http.server import BaseHTTPRequestHandler, HTTPServer
        from bot import llm_sunucu as LS
        seen = {}

        class Fake(BaseHTTPRequestHandler):
            def do_POST(self):
                seen['body'] = J.loads(self.rfile.read(int(self.headers['Content-Length'])))
                out = {'choices': [{'message': {'content': '<think>\n\n</think>\n{"metin": "selam", "arac": "hicbiri"}'}}]}
                data = J.dumps(out).encode()
                self.send_response(200); self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)

            def log_message(self, *a):
                pass
        srv = HTTPServer(('127.0.0.1', 0), Fake)
        TH.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        s = LS.Sunucu()
        s.port = srv.server_address[1]
        r, _ = s.sor('sys', 'hi', sema={'type': 'object'})
        self.assertEqual(r, {'metin': 'selam', 'arac': 'hicbiri'})
        self.assertFalse(seen['body']['chat_template_kwargs']['enable_thinking'])
        self.assertTrue(seen['body']['messages'][1]['content'].startswith('/no_think'))
        self.assertEqual(seen['body']['response_format']['type'], 'json_schema')

    def make(self, answers):
        from bot import llm
        y = YN.Yonetici(dict(kip='gelismis', ayarlar=dict(telafi_saat=0, kayit_sn=0), kadro=KS.kadro_uret(41, 6, firma_dagilimi=(1, 0, 0))), None,
                        log=lambda *_: None)
        for b in y.botlar:
            b.k['seviye'] = 8
            y.giris(b, time.time())
        y.giden = []
        br = llm.Beyin(y, log=lambda *_: None)
        br.hazir = True
        asked = []
        br.sor = lambda k, sema, **kw: (asked.append(k), answers.pop(0))[1]
        y.llm = br
        return y, br, asked

    def test_whisper_reply_and_tool_call(self):
        y, br, asked = self.make([{'metin': 'ok coming', 'arac': 'hicbiri', 'harita': ''}])
        b = y.botlar[0]
        b.k['kisilik']['ozellik']['yardimseverlik'] = 1.0
        b.r.random = lambda: 0.0                       # the decision engine says yes; the model only voices it
        self.assertTrue(br.sohbet(y, ('fisilti', b, 'yardim et 1-3 de', {'userId': 'Nova', 'id': '1', 'factionId': '1'}), y.now))
        _, _, job = br.kuyruk[0]
        job['fn'](job)
        self.assertIn('Nova', asked[0])
        self.assertIn(b.ad, asked[0])
        self.assertIn('HELP', asked[0])
        self.assertEqual(y.giden[-1][4], 'Nova')
        self.assertEqual(b.k['niyet']['hedef'], 'yardim')
        self.assertEqual(b.k['niyet']['plan']['harita'], 3)

    def test_channel_message_batches_listeners_in_one_request(self):
        y, br, asked = self.make([])
        names = [b.ad for b in y.botlar]
        br.sor = lambda k, sema, **kw: (asked.append(sema), {'yanitlar': [{'bot': names[0], 'metin': 'as', 'arac': 'hicbiri', 'harita': ''},
                                                                         {'bot': names[1], 'metin': 'selam', 'arac': 'hicbiri', 'harita': ''}]})[1]
        br.sohbet(y, ('oda', '/room/faction/1/', 'selam millet', {'userId': 'Nova', 'factionId': '1'}), y.now)
        _, _, job = br.kuyruk[0]
        job['fn'](job)
        self.assertEqual(len(asked), 1)
        self.assertLessEqual(len(asked[0]['properties']['yanitlar']['items']['properties']['bot']['enum']), 5)
        self.assertEqual({x[1].ad for x in y.giden}, set(names[:2]))

    def test_strategy_review_turns_into_intents(self):
        y, br, asked = self.make([])
        bots = y.botlar[:3]
        br.sor = lambda k, sema, **kw: {'kararlar': [{'bot': b.ad, 'hedef': 'dinlenme', 'harita': '', 'soz': ''} for b in bots]}
        br._karar({'botlar': bots})
        self.assertTrue(all(b.k['niyet']['hedef'] == 'dinlenme' for b in bots))

    def test_whisper_prompt_knows_the_shared_history(self):
        from bot import llm
        y, br, asked = self.make([{'metin': 'yo, again?'}])
        b = y.botlar[0]
        b.hafiza.olay('Nova', 'grup', y.now)
        b.hafiza.olay('Nova', 'oldurdu_beni', y.now)
        self.assertIn('grouped up 1 times', llm.ortak_gecmis(b, 'Nova'))
        br.sohbet(y, ('fisilti', b, 'hey', {'userId': 'Nova', 'id': '1', 'factionId': '1'}), y.now)
        _, _, job = br.kuyruk[0]
        job['fn'](job)
        self.assertIn('he killed you 1 times', asked[0])

    def test_group_request_in_a_channel_is_a_decision_not_a_map_tip(self):
        import grup as GR
        from bot import llm
        self.assertEqual(llm.mesaj_turu('who wants to group up with me?'), 'istek')
        self.assertEqual(llm.mesaj_turu('where can i find bosses?'), 'soru_oyun')
        y, br, asked = self.make([])
        for b in y.botlar:
            b.k['kisilik']['ozellik']['sosyallik'] = 1.0
            b.r.random = lambda: 0.0
        names = [b.ad for b in y.botlar]
        br.sor = lambda k, sema, **kw: (asked.append((k, sema)), {'yanitlar': [{'bot': sema['properties']['yanitlar']['items'][
            'properties']['bot']['enum'][0], 'metin': 'sure, sent inv'}]})[1]
        with patch.object(GR, 'handle', return_value=[]) as h:
            br.sohbet(y, ('oda', '/room/faction/1/', 'who wants to group up with me?', {'userId': 'Nova', 'id': '7', 'factionId': '1'}),
                      y.now)
            _, _, job = br.kuyruk[0]
            job['fn'](job)
        k, sema = asked[0]
        self.assertNotIn('GAME FACTS', k)                               # no map/alien list for a group call
        self.assertIn('ACCEPT', k)
        self.assertEqual(len(sema['properties']['yanitlar']['items']['properties']['bot']['enum']), 1)
        from bot import etkilesim as ET
        b = y.giden[-1][1]
        self.assertIn(b.ad, names)
        self.assertTrue(ET.soz_var(b, 'grup', 'Nova', y.now))              # Nova is offline here: "inv me", accepts his invite

    def test_queue_overflow_falls_back(self):
        y, br, asked = self.make([])
        b = y.botlar[0]
        for _ in range(br.yuva * 3):
            br.ekle(0, {'t': time.time(), 'fn': lambda j: None})
        self.assertFalse(br.ekle(3, {'t': time.time(), 'fn': lambda j: None}))


class GameSettingsProfile(unittest.TestCase):
    """Bots use their pack's own game-settings profile, not the player's."""

    def run_profile(self, profil):
        y = YN.Yonetici(paket(12, tohum=9, oyun_ayari={'profil': profil}), None, log=lambda *_: None, now=T0)
        now = T0
        for _ in range(int(6 * 3600 / 5)):
            now += 5
            y.tick(now)
        kredi = sum(b.k['kredi'] + b.k['istat'].get('harcama_kredi', 0) for b in y.botlar)      # kazanılan toplam kredi
        return sum(b.k['ep'] for b in y.botlar), kredi, sum(b.k['istat'].get('olum', 0) for b in y.botlar)

    def test_hard_profile_slows_bots_and_fast_profile_speeds_them(self):
        hard, std, fast = self.run_profile('zorlu'), self.run_profile('standart'), self.run_profile('hizli')
        self.assertLess(hard[1], std[1])                 # zorlu: kredi x0,75, uzaylılar sert
        self.assertGreater(fast[0], 2 * std[0])          # hızlı: ödüller x5

    def test_custom_profile_multiplies_rewards(self):
        from bot import oyun_ayari as OA
        b = Bot(dict(no=1, ad='p', firma=1, kisilik=KS.kisilik_uret(random.Random(1))))
        b.oa = OA.Profil({'profil': 'ozel', 'degerler': {'ep': 3.0}})
        b.odul('npc', ep=1000)
        self.assertEqual(b.k['ep'], 3000)


class Languages(unittest.TestCase):
    """Name and chat languages are separate; every panel language has names, chat lines and intent words."""

    def test_every_language_has_valid_names_and_all_chat_situations(self):
        from bot import dil_verisi as DV, konusma as KN
        self.assertEqual(DV.KODLAR, ('tr', 'en', 'de', 'es', 'fr', 'pl', 'pt', 'ru'))
        for kod in DV.KODLAR:
            r = random.Random(kod)
            for _ in range(200):
                self.assertTrue(KS.AD_DESEN.match(KS.ad_uret(r, kod)), kod)
            self.assertEqual(set(DV.DILLER[kod]['kaliplar']), set(KN.KALIPLAR), kod)
            b = Bot(dict(no=1, ad='x', firma=1, kisilik=KS.kisilik_uret(random.Random(1), dil=kod)))
            self.assertTrue(KN.kalip(b, 'yeni_gemi', gemi='goliath'))

    def test_mixed_names_chat_in_their_own_language_and_a_fixed_chat_language_wins(self):
        k = KS.kadro_uret(3, 120)
        self.assertTrue(all(x['kisilik']['dil'] == x['kisilik']['ad_dili'] for x in k))
        self.assertGreater(len({x['kisilik']['ad_dili'] for x in k}), 5)
        k = KS.kadro_uret(3, 40, dil='pl', ad_dili='karisik')
        self.assertEqual({x['kisilik']['dil'] for x in k}, {'pl'})

    def test_changing_the_chat_language_applies_to_existing_bots_without_renaming_them(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server" / "panel"))
        import botlar as BTP
        d = {'dil': 'karisik', 'kadro': KS.kadro_uret(4, 20, ad_dili='karisik')}
        adlar = [x['ad'] for x in d['kadro']]
        d['dil'] = 'fr'
        BTP.sohbet_dili_uygula(d)
        self.assertEqual({x['kisilik']['dil'] for x in d['kadro']}, {'fr'})
        d['dil'] = 'karisik'
        BTP.sohbet_dili_uygula(d)
        self.assertTrue(all(x['kisilik']['dil'] == x['kisilik']['ad_dili'] for x in d['kadro']))
        self.assertEqual([x['ad'] for x in d['kadro']], adlar)

    def test_intents_are_understood_in_other_languages(self):
        from bot import konusma as KN
        for m, n in (('wer will gruppe?', 'grup'), ('dodaj mnie', 'arkadas'), ('me chama no pv', 'ozel'), ('ты где', 'takip'),
                     ('hilfe bei der quest', 'gorev'), ('salut tout le monde', 'selam')):
            self.assertEqual(KN.niyet(m)[0], n, m)


class ChatFilters(unittest.TestCase):
    def setUp(self):
        from bot import llm
        self.y = YN.Yonetici(dict(kip='gelismis', ayarlar=dict(telafi_saat=0, kayit_sn=0), kadro=KS.kadro_uret(41, 4)), None, log=lambda *_: None)
        self.br = llm.Beyin(self.y, log=lambda *_: None)
        self.b = self.y.botlar[0]

    def test_lines_are_cleaned_or_silenced(self):
        m = lambda t, **kw: self.br._metin(self.b, t, **kw)
        self.assertEqual(m('check 2-1 for streuners 😎').strip(), m('check 2-1 for streuners').strip())
        self.assertEqual(m("gg wp'}"), m('gg wp'))
        for bad in ('Mood: relaxed, not very chatty', 'takip_et', 'how can i assist you today?', 'i have 43800 credits',
                    'selam nasılsın', 'u better shoot yourself', 'go die noob', 'kys'):
            self.assertEqual(m(bad), '', bad)
        self.assertEqual(m('this server is dead lol', yanki='this server is dead lol'), '')
        self.assertTrue(m("i'm 22, playing since 2015"))                    # yaş ve yıl serbest
        self.assertTrue(m('2-2, 2-3, 2-4', yanki='where can i find bosses?'))  # sözcüksüz yanıt yankı değil

    def test_player_talking_to_the_last_speaker_is_addressed(self):
        from bot import llm
        b = self.b
        b.cevrimici = True                                      # (ilk nüfus günün saatine bağlı)
        self.y.gecmis.append((self.y.now, b.ad, 'firma', 'level 5 finally'))
        self.assertEqual(llm.hitap_edilen(self.y, 'firma', 'how did you level so fast?', [b]), [b])
        self.assertEqual(llm.hitap_edilen(self.y, 'firma', 'where do i find streuners?', [b]), [])
        self.assertEqual(llm.hitap_edilen(self.y, 'firma', 'whats ur favorite ship guys', [b]), [])
        self.assertEqual(llm.hitap_edilen(self.y, 'firma', 'gz!', [b]), [b])

    def test_message_types_and_company_facts(self):
        from bot import llm
        self.assertEqual(llm.mesaj_turu('good to hear that dude, gz!'), 'kutlama')
        self.assertEqual(llm.mesaj_turu('how old are you guys lol'), 'soru_kisisel')
        self.assertEqual(llm.mesaj_turu('where can i find bosses?'), 'soru_oyun')
        self.assertEqual(llm.mesaj_turu('brb food'), 'ara')
        self.assertIn('EIC players start on 2-1', llm.oyun_bilgisi(2))
        self.assertIn('MMO', llm.harita_notu('dude im on EIC how can i start 1-1?', 2))
