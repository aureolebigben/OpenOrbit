"""Rehber (istemcinin Kişiler penceresi, ContactsComponentSystem; posta penceresinin kişiler sekmesi): arkadaşlık isteği, kabul,
ret, isteği geri alma, arkadaşı silme, engelleme ve "davetleri engelle".

Arkadaş sunucusunda istekler öteki oyuncunun kaydına da yazılır (bağlı değilse kaydı sunucuda durdukça); tek oyunculuda yalnız
oyuncunun kendisi var. Rehber profilde ada göre tutulur (misafirin sunucudaki kimliği her katılmada başka): arkadas, gelen (bekleyen
istek), giden (gönderilen istek), reddeden (isteği reddedilen), engelli. Pencerenin satırı (ContactListEntryModule) oyuncunun
kimliğiyle; sunucuda olmayan kişiye addan türetilen sabit kimlik verilir (sahte_kimlik). Bir kişi birden çok türde olabilir
(ContactListEntryTypeCommand.contactEntryTypes).
İstemci her istekten sonra pencereyi kilitler, ContactUiUnblockCommand gelince açar. Listedeki değişiklik: kaldırılanlar
ContactListRemoveContactsCommand, eklenen ve değişenler ContactListUpdateContactsCommand (gelen istekte istemci bildirim gösterir);
çevrimiçi, harita ve seviye GUNCELLEME_SN'de bir yoklanır. Günlük metinleri istemcinin (log_msg_contact_*).
"""
import threading, time, zlib
import topluluk as TP
from cbs import stm

GUNCELLEME_SN = 2.0
REQUESTS = {'ContactRequest', 'ContactListRequest', 'ContactListSettingsModule', 'ContactListBlockInvitationsModule'}
# ContactRequest.contactRequestType
OLUSTUR, KABUL, RET, ISTEK_SIL, ARKADAS_SIL, ENGELLE, ENGEL_KALDIR = range(7)
# ContactListEntryTypeModule.entryType
ARKADAS, KLAN, GELEN, GIDEN, REDDEDILDI, ENGELLI = range(6)
LISTELER = (('arkadas', ARKADAS), ('gelen', GELEN), ('giden', GIDEN), ('reddeden', REDDEDILDI), ('engelli', ENGELLI))
SUZGEC = {'showClanMembers': True, 'showRequests': True, 'showFriends': True, 'showBlacklistPlayers': False}

LOCK = threading.RLock()
SON = {}                      # oyuncu kimliği -> {satır kimliği: (ad, ContactListEntryModule)}: istemcinin son gördüğü liste
_is = None


def mod(_cls, **f):
    return dict(_=_cls, **f)


def kayit(p):
    import ad_kaydi as AK
    AK.profil_uygula(p)                                  # panelde adı değişen ya da silinen botlar (ad_kaydi.py)
    with p.lock:
        return _kayit(p)


def _kayit(p):
    """Profilin rehberi (p.lock altında)."""
    r = p.d.setdefault('rehber', {})
    for ad, _ in LISTELER:
        r.setdefault(ad, [])
    r.setdefault('davet_engeli', False)
    r.setdefault('suzgec', dict(SUZGEC))
    return r


def _var(lst, ad):
    return any(x.lower() == ad.lower() for x in lst)


def _ekle(p, liste, ad):
    with p.lock:
        lst = _kayit(p)[liste]
        if not _var(lst, ad):
            lst.append(ad)
            p.dirty = True


def _sil(p, liste, ad):
    with p.lock:
        lst = _kayit(p)[liste]
        kalan = [x for x in lst if x.lower() != ad.lower()]
        if len(kalan) != len(lst):
            lst[:] = kalan
            p.dirty = True


def sahte_kimlik(ad):
    """Sunucuda olmayan kişinin satır kimliği (addan; misafirlerin 2,0-2,1 milyar aralığının ve gerçek kimliklerin dışında)."""
    return 2150000000 + zlib.crc32(ad.lower().encode('utf8')) % 100000000


# ------------------------------------------------------------ liste
def satirlar(p, kisiler):
    """Rehberin satırları: kimlik -> (ad, ContactListEntryModule)."""
    import klan as KL
    r = kayit(p)
    adlar = {}
    for liste, tur in LISTELER:
        for ad in r[liste]:
            adlar.setdefault(ad.lower(), [ad, []])[1].append(tur)
    c = KL.klani(p)                                    # klan üyeleri (istemcinin "Clan members" süzgeci)
    for low, u in (c or {}).get('uyeler', {}).items():
        if low != KL.ad(p):
            adlar.setdefault(low, [u.get('ad', low), []])[1].append(KLAN)
    by_ad = {k.ad.lower(): k for k in kisiler.values()}
    out = {}
    for low, (ad, turler) in adlar.items():
        k = by_ad.get(low)
        uid = k.uid if k is not None else sahte_kimlik(ad)
        attrs = [mod('ContactListEntryAttributeNameModule', userName=k.ad if k is not None else ad),
                 mod('ContactListEntryAttributeOnlineModule', online=k is not None and k.oturum is not None)]
        if k is not None:
            pl = k.profil.d['pilot']
            attrs += [mod('ContactListEntryAttributeMapModule', currentMap=int(k.profil.d['konum'].get('mapId', 0))),
                      mod('ContactListEntryAttributeLevelModule', level=int(pl.get('level', 1))),
                      mod('ContactListEntryAttributeClanTagModule', clanTag=str(pl.get('clanTag', ''))),
                      mod('ContactListEntryAttributeClanModule', clanId=int(pl.get('clanId', 0) or 0)),
                      mod('ContactListEntryAttributeClanRelationModule', clanRelation=mod('ClanRelationModule', type=KL.iliski(p, k.profil)))]
        out[uid] = (ad, mod('ContactListEntryModule',
                            typeCommand=mod('ContactListEntryTypeCommand', userId=uid,
                                            contactEntryTypes=[mod('ContactListEntryTypeModule', entryType=t) for t in sorted(turler)]),
                            attributeCommand=mod('ContactListEntryAttributeCommand', userId=uid, attributes=attrs)))
    return out


def giris_cmd(p):
    """Girişteki ContactListInitializationCommand (kayıttaki boş listenin yerine)."""
    r = kayit(p)
    with LOCK:
        cur = satirlar(p, TP.hepsi())
        SON[p.user_id] = cur
    baslat()
    return ('ContactListInitializationCommand', {
        'blockInvitations': mod('ContactListBlockInvitationsModule', blockAllInvitations=bool(r['davet_engeli'])),
        'filterSettings': mod('ContactListSettingsModule', **dict(SUZGEC, **r['suzgec'])),
        'contactsCommand': mod('ContactListUpdateContactsCommand', contacts=[e for _, e in cur.values()])})


def yenile(k, kisiler=None):
    """Oyuncunun istemcisindeki listeyi profildekine getiren mesajlar (değişen yoksa boş)."""
    with LOCK:
        cur = satirlar(k.profil, kisiler if kisiler is not None else TP.hepsi())
        old = SON.get(k.uid)
        if old is None:                  # liste henüz gönderilmedi (giriş demeti gitmeden)
            return []
        SON[k.uid] = cur
    msgs = []
    gone = sorted(set(old) - set(cur))
    if gone:
        msgs.append(('ContactListRemoveContactsCommand', {'contactUserIds': gone}))
    changed = [e for uid, (_, e) in cur.items() if old.get(uid, (None, None))[1] != e]
    if changed:
        msgs.append(('ContactListUpdateContactsCommand', {'contacts': changed}))
    return msgs


def unut(uid):
    """Oyuncunun bağlantısı kapandı: sonraki girişte liste baştan gider."""
    with LOCK:
        SON.pop(uid, None)


# ------------------------------------------------------------ istekler
def handle(k, name, f):
    """İsteği yapan oyuncu (topluluk.Kisi) -> kendisine giden yanıt; karşı tarafın listesi doğrudan yenilenir."""
    p = k.profil
    if name == 'ContactListSettingsModule':
        with p.lock:
            _kayit(p)['suzgec'] = {x: bool(f.get(x, v)) for x, v in SUZGEC.items()}
            p.dirty = True
        return []
    if name == 'ContactListBlockInvitationsModule':
        with p.lock:
            _kayit(p)['davet_engeli'] = bool(f.get('blockAllInvitations'))
            p.dirty = True
        return [('ContactListBlockInvitationsModule', {'blockAllInvitations': kayit(p)['davet_engeli']})]
    if name == 'ContactListRequest':
        # posta penceresinin kişiler sekmesi: bekleyen istekler (type 1: Accept/Decline) ve arkadaşlar (type 0: sil, posta yaz;
        # istemcide denendi 2026-10-24)
        cur = SON.get(k.uid) or satirlar(p, TP.hepsi())
        turu = lambda e, t: any(x['entryType'] == t for x in e['typeCommand']['contactEntryTypes'])
        rows = sorted(cur.items(), key=lambda x: x[1][0].lower())
        lst = [mod('ContactInvitationInfoCommand', type=1, userId=uid, userName=ad, avatarURL='') for uid, (ad, e) in rows
               if turu(e, GELEN)] + \
              [mod('ContactFriendInfoCommand', type=0, userId=uid, userName=ad, avatarURL='') for uid, (ad, e) in rows if turu(e, ARKADAS)]
        start = max(0, int(f.get('startIndex') or 0))
        return [('ContactListCommand', {'contactList': lst[start:start + 15], 'total': len(lst), 'startIndex': start})]
    tur = int(f.get('contactRequestType', -1))
    ad = str(f.get('userName') or '').strip()
    if not ad:                                 # istemci satırdan kimliğiyle gönderiyor: son gönderilen listeden ada
        ad = (SON.get(k.uid) or {}).get(f.get('userId'), ('', None))[0]
    b = TP.bul(ad=ad) if ad else None
    if b is not None:
        ad = b.ad
    out, ona = [], []
    r = kayit(p)
    if tur == OLUSTUR:
        if b is None or b.uid == k.uid:
            out.append(stm('msg_grp_inv_err_candidate_nonexistant'))
        elif _var(r['arkadas'], ad):
            out.append(stm('log_msg_err_already_contact', NAME=ad))
        elif _var(r['giden'], ad):
            out.append(stm('log_msg_err_already_requested', NAME=ad))
        elif _var(r['gelen'], ad):             # o da istek göndermiş: kabul sayılır
            return handle(k, name, dict(f, contactRequestType=KABUL, userName=ad))
        else:
            _sil(p, 'reddeden', ad)
            _ekle(p, 'giden', ad)
            rb = kayit(b.profil)
            if not rb['davet_engeli'] and not _var(rb['engelli'], k.ad):    # engelleyen görmez
                _ekle(b.profil, 'gelen', k.ad)
            out.append(stm('log_msg_contact_invite_sent', NAME=ad))
    elif tur == KABUL and _var(r['gelen'], ad):
        _sil(p, 'gelen', ad)
        _ekle(p, 'arkadas', ad)
        out.append(stm('log_msg_contact_added', NAME=ad))
        if b is not None:
            _sil(b.profil, 'giden', k.ad)
            _sil(b.profil, 'reddeden', k.ad)
            _ekle(b.profil, 'arkadas', k.ad)
            ona.append(stm('log_msg_contact_added', NAME=k.ad))
    elif tur == RET and _var(r['gelen'], ad):
        _sil(p, 'gelen', ad)
        if b is not None and _var(kayit(b.profil)['giden'], k.ad):
            _sil(b.profil, 'giden', k.ad)
            _ekle(b.profil, 'reddeden', k.ad)
            ona.append(stm('log_msg_contact_declined', NAME=k.ad))
    elif tur == ISTEK_SIL:
        _sil(p, 'giden', ad)
        _sil(p, 'reddeden', ad)
        if b is not None:
            _sil(b.profil, 'gelen', k.ad)
    elif tur == ARKADAS_SIL and _var(r['arkadas'], ad):
        _sil(p, 'arkadas', ad)
        out.append(stm('log_msg_contact_removed', NAME=ad))
        if b is not None:
            _sil(b.profil, 'arkadas', k.ad)
    elif tur == ENGELLE and ad and ad.lower() != k.ad.lower():
        for liste in ('arkadas', 'gelen', 'giden', 'reddeden'):
            _sil(p, liste, ad)
        _ekle(p, 'engelli', ad)
        out.append(stm('log_msg_contact_blocked', NAME=ad))
        if b is not None:
            for liste in ('arkadas', 'gelen', 'giden'):
                _sil(b.profil, liste, k.ad)
    elif tur == ENGEL_KALDIR and _var(r['engelli'], ad):
        _sil(p, 'engelli', ad)
        out.append(stm('log_msg_contact_unblocked', NAME=ad))
    kisiler = TP.hepsi()
    if b is not None and b.uid != k.uid:
        b.gonder(ona + yenile(b, kisiler), 'rehber')
    return out + yenile(k, kisiler) + [('ContactUiUnblockCommand', {})]


# ------------------------------------------------------------ çevrimiçi, harita, seviye
def guncelle():
    kisiler = TP.hepsi()
    for k in kisiler.values():
        if k.oturum is not None and k.uid in SON:
            k.gonder(yenile(k, kisiler), 'rehber')


def _dongu():
    while True:
        time.sleep(GUNCELLEME_SN)
        try:
            guncelle()
        except Exception:
            import traceback
            traceback.print_exc()


def baslat():
    global _is
    if _is is None:
        _is = threading.Thread(target=_dongu, name='rehber', daemon=True)
        _is.start()
