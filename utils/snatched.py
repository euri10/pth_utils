import re
import time
import logging
from lxml import html

logger = logging.getLogger(__name__)
logging.basicConfig()
logging.root.setLevel(level=logging.INFO)

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


def get_upgradables_from_page(page, my_id, session, notify, my_auth):
    """On a snatched list page retrieve the torrents that could be upgraded
    from MP3 to FLAC """
    snatched_url = 'https://passtheheadphones.me/torrents.php'
    params = {'page': page, 'type': 'snatched', 'userid': my_id}
    r = session.get(snatched_url, params=params)
    if r.status_code != 200:
        logger.info('error while getting snatched')
    else:
        logger.info('getting page number')
        snatchedpage = html.fromstring(r.content)
    upgradable = []
    notifiable = []
    snatched = []
    torrents = snatchedpage.xpath(
        '//tr[@class="torrent torrent_row"]/td[@class="big_info"]/div/a[2]/@href')
    levels = snatchedpage.xpath(
        '//tr[@class="torrent torrent_row"]/td[@class="big_info"]/div/a[2]/following-sibling::text()[1]')
    artists_id = snatchedpage.xpath(
        '//tr[@class="torrent torrent_row"]/td[@class="big_info"]/div/a[1]/@href')
    artists_name = snatchedpage.xpath(
        '//tr[@class="torrent torrent_row"]/td[@class="big_info"]/div/a[1]/text()')
    for t in zip(torrents, levels, artists_id, artists_name):
        snatched.append(t)
    for snatch in snatched:
        if re.match('.*MP3.*', snatch[1]):
            torrent_group_id = re.match(
                'torrents\.php\?id=(\d+)&torrentid=(\d+)', snatch[0]).group(1)
            # torrent_id = re.match('torrents\.php\?id=(\d+)&torrentid=(\d+)',
            #                       snatch[0]).group(2)
            # https://passtheheadphones.me/artist.php?id=61125
            # artist_id = re.match('artist\.php\?id=(\d+)', snatch[2]).group(1)
            if 'FLAC' in get_formats(torrent_group_id, session):
                # TODO handle false positive
                upgradable.append(snatch[0])
            else:
                if notify:
                    notifiable.append(snatch[3])
    return upgradable, notifiable
