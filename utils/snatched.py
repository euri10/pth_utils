import time
import logging
from lxml import html
import re

logger = logging.getLogger(__name__)
logging.basicConfig()
logging.root.setLevel(level=logging.DEBUG)


def get_formats(torrent_group_id, session):
    """Get formats for a given torrent group, uses the API because it can !"""
    url = 'https://passtheheadphones.me/ajax.php'
    params = {'action': 'torrentgroup', 'id': torrent_group_id}
    logger.info('getting formats of {}'.format(torrent_group_id))
    # rate limit hit if too fast, awful hard-coding
    # TODO : better handling of rate limit, this one sucks but works
    time.sleep(2)
    r = session.get(url, params=params)
    return [r.json()['response']['torrents'][i]['format'] for i in
            range(len(r.json()['response']['torrents']))]

def get_display_infos(torrent_id, session):
    """Get formats for a given torrent id, uses the API because it can !"""
    #ajax.php?action=torrent&id=<Torrent Id>
    url = 'https://passtheheadphones.me/ajax.php'
    params = {'action': 'torrent', 'id': torrent_id}
    logger.info('getting info for {}'.format(torrent_id))
    # rate limit hit if too fast, awful hard-coding
    # TODO : better handling of rate limit, this one sucks but works
    time.sleep(2)
    r = session.get(url, params=params)
    return r.json()['response']['group']


def notify_artist(authkey, session, artists_list, notification_label):
    """Set notification for all artists"""
    url = 'https://passtheheadphones.me/user.php'
    data = {'formid': 1, 'action': 'notify_handle', 'auth': authkey,
            'label1': notification_label,
            'artists1': ','.join(artists_list), 'formats1[]': 'FLAC', }
    r = session.post(url, data=data)
    if r.status_code == 200 and b'Error' not in r.content:
        logger.info('Notification set for artists {}'.format(artists_list))
    else:
        logger.error('notify failed ? artists {}'.format(artists_list))


def subscribe_collage(my_auth, session, collage_id):
    """Subscribe a collage"""
    url = 'https://passtheheadphones.me/userhistory.php'
    params = {'action': 'collage_subscribe', 'collageid': collage_id,
              'auth': my_auth}
    r = session.get(url, params=params)
    if r.status_code == 200:
        logger.info('Subscription set for collage {}'.format(collage_id))
    else:
        logger.info('Subscription failed for collage {}'.format(collage_id))


def anonymize(page, auth, passkey, authkey):

    # pattern_auth = b'(auth=)(.*;)'
    # pattern_passkey = b'(passkey=)(.*;)'
    # pattern_authkey = b'(authkey=)(.*["|;])'
    # pattern_upvote = b'onclick="UpVoteGroup\((.*)\)'
    # pattern_downvote = b'onclick="DownVoteGroup\((.*)\)'
    # pattern_unvote_group = b'onclick="UnvoteGroup\((.*)\)'
    # ANON = {pattern_auth: b'\1AUTH', pattern_passkey: b'\1PASSKEY;', pattern_authkey:b'AUTHKEY;', pattern_upvote:b'AUTH', pattern_downvote:b'AUTH', pattern_unvote_group:b'AUTH'}

    # for pattern, repl in ANON.items():
    #     page = re.sub(pattern=pattern, repl=repl, string=page)
    page = re.sub(auth.encode('utf-8'), b'AUTH', page)
    page = re.sub(passkey.encode('utf-8'), b'PASSKEY', page)
    page = re.sub(authkey.encode('utf-8'), b'AUTHKEY', page)
    return page



def get_upgradables_from_page(page, my_id, session, auth, passkey, authkey):
    """On a snatched list page retrieve the torrents that could be upgraded
    from MP3 to FLAC """
    logger.debug('entering get_upgradables_from_page')
    snatched_url = 'https://passtheheadphones.me/torrents.php'
    params = {'page': page, 'type': 'snatched', 'userid': my_id}
    r = session.get(snatched_url, params=params)
    if r.status_code != 200:
        logger.info('error while getting snatched')
    else:
        logger.info('getting page number')
        snatchedpage = html.fromstring(r.content)

    torrents = snatchedpage.xpath('//tr[@class="torrent torrent_row"]/td[@class="big_info"]/div/a[re:match(@href, "torrents\.php\?id=(\d+)&torrentid=(\d+)")]/@href', namespaces={"re": "http://exslt.org/regular-expressions"})
    logger.debug('{} items: {}'.format(len(torrents), torrents))
    if not len(torrents):
        logger.debug(anonymize(html.tostring(snatchedpage), auth, passkey, authkey))
    levels = snatchedpage.xpath(
        '//tr[@class="torrent torrent_row"]/td[@class="big_info"]/div/a[re:match(@href, "torrents\.php\?id=(\d+)&torrentid=(\d+)")]/following-sibling::text()[1]', namespaces={"re": "http://exslt.org/regular-expressions"})
    logger.debug('{} items: {}'.format(len(levels), levels))
    artists_id = snatchedpage.xpath(
        '//tr[@class="torrent torrent_row"]/td[@class="big_info"]/div/a[1]/@href')
    logger.debug('{} items: {}'.format(len(artists_id), artists_id))
    artists_name = snatchedpage.xpath(
        '//tr[@class="torrent torrent_row"]/td[@class="big_info"]/div/a[1]/text()')
    logger.debug('{} items: {}'.format(len(artists_name), artists_name))

    if not (len(torrents) == len(levels) == len(artists_id) == len(artists_name)):
        logging.error('mmmmmm shit')
        logging.debug(anonymize(html.tostring(snatchedpage), auth, passkey, authkey))
    return torrents, levels, artists_id, artists_name


