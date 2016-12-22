import os
import re
import time
from lxml import html
import click as click
import requests

from utils.hidden_password import HiddenPassword
from utils.login import logger, headers, login, BASE_URL


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


def notify_artist(my_auth, session, artists_list):
    """Set notification for all artists"""
    url = 'https://passtheheadphones.me/user.php'
    data = {'formid': 1, 'action': 'notify_handle', 'auth': my_auth,
            'label1': 'pth_utils filter',
            'artists1': ','.join(artists_list), 'formats1[]': 'FLAC', }
    r = session.post(url, data=data)
    if r.status_code == 200 and b'Error' not in r.content:
        logger.info('Notification set for artists {}'.format(artists_list))
    else:
        logger.error('notify failed ? artists {}'.format(artists_list))


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
            torrent_id = re.match('torrents\.php\?id=(\d+)&torrentid=(\d+)',
                                  snatch[0]).group(2)
            # https://passtheheadphones.me/artist.php?id=61125
            artist_id = re.match('artist\.php\?id=(\d+)', snatch[2]).group(1)
            if 'FLAC' in get_formats(torrent_group_id, session):
                # TODO handle false positive
                upgradable.append(snatch[0])
            else:
                if notify:
                    notifiable.append(snatch[3])
    return upgradable, notifiable




@click.command()
@click.option('--pth_user',
              prompt=True,
              default=lambda: os.environ.get('PTH_USER', ''),
              help='Defaults to PTH_USER environment variable')
@click.option('--pth_password',
              prompt=True,
              default=lambda: HiddenPassword(
                  os.environ.get('PTH_PASSWORD', '')),
              help='Defaults to PTH_PASSWORD environment variable',
              hide_input=True)
@click.option('--notify/--no-notify',
              prompt=True,
              default=False,
              help='Set to True to set up a notification for new FLAC for the '
                   'artists where you got an MP3 and no FLAC is available yet, '
                   'would be amazing to be able to do that per torrent group !')
def get_snatched_list(pth_user, pth_password, notify):
    """
    Builds a list of snatched MP3s that have a FLAC.
    You can set up notifications for artists where there is NO FLAC and you snatched the MP3
    """
    # log into pth, gets the id
    session = requests.Session()
    session.headers = headers
    if isinstance(pth_password, HiddenPassword):
        pth_password = pth_password.password
    my_id, _, _, my_auth = login(pth_user, pth_password, session)
    # get the #  of pages, loops them to build upgradables list
    upgradables = []
    notifiables = []
    snatched_url = 'https://passtheheadphones.me/torrents.php'
    params = {'page': 1, 'type': 'snatched', 'userid': my_id}
    r = session.get(snatched_url, params=params)
    if r.status_code != 200:
        logger.info('error while getting snatched')
    else:
        snatchedpage = html.fromstring(r.content)
        pages = set(re.match('torrents\.php\?page=(\d+).*', snatchedpage.xpath(
            '//div[@class="linkbox"][1]/a/@href')[i]).group(1) for i in range(
            len(snatchedpage.xpath('//div[@class="linkbox"][1]/a/@href'))))
        pages.add('1')
        # yeah I know I could get page 1 info right away...
        for page in pages:
            logger.info('getting page number {}'.format(page))
            up, notif = get_upgradables_from_page(page, my_id, session, notify,
                                                  my_auth)
            for u in up:
                upgradables.append(u)
            for n in set(notif):
                notifiables.append(n)

    for upgradable in upgradables:
        logger.info(
            'You can get a better version on: {}'.format(BASE_URL + upgradable))

    notify_artist(my_auth, session, notifiables)


if __name__ == '__main__':
    get_snatched_list()
