import os
import re
import time
from lxml import html
import click as click
import logging
import requests

BASE_URL = "https://passtheheadphones.me/"
headers = {
    'Content-type': 'application/x-www-form-urlencoded',
    'Accept-Charset': 'utf-8',
    'User-Agent': 'pth_utils @ https://github.com/euri10/pth_utils]'
}

# log stuff
logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s')
logging.root.setLevel(level=logging.INFO)


def login(username, password, session):
    """Logs in user"""
    loginpage = 'https://passtheheadphones.me/login.php'
    data = {'username': username,
            'password': password,
            'keeplogged': 1,
            'login': 'Login'
            }
    r = session.post(loginpage, data=data)
    if r.status_code == 200 and b'You entered an invalid password' in r.content:
        logger.error('error while attempting to log')
    else:
        logger.info('successful logging')
    mainpage = html.fromstring(r.content)
    user_id = re.match('user\.php\?id=(\d+)', mainpage.xpath('//li[@id="nav_userinfo"]/a/@href')[0]).group(1)
    return user_id


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


def notify_artist(artist_id):
    """Set notification for an artist"""
    pass


def get_upgradables_from_page(page, my_id, session, notify):
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
    snatched = []
    torrents = snatchedpage.xpath(
        '//tr[@class="torrent torrent_row"]/td[@class="big_info"]/div/a[2]/@href')
    levels = snatchedpage.xpath(
        '//tr[@class="torrent torrent_row"]/td[@class="big_info"]/div/a[2]/following-sibling::text()[1]')
    artists = snatchedpage.xpath(
        '//tr[@class="torrent torrent_row"]/td[@class="big_info"]/div/a[1]/@href')
    for t in zip(torrents, levels, artists):
        snatched.append(t)
    for snatch in snatched:
        if re.match('.*MP3.*', snatch[1]):
            torrent_group_id = re.match('torrents\.php\?id=(\d+)&torrentid=(\d+)', snatch[0]).group(1)
            torrent_id = re.match('torrents\.php\?id=(\d+)&torrentid=(\d+)', snatch[0]).group(2)
            # https://passtheheadphones.me/artist.php?id=61125
            artist_id = re.match('artist\.php\?id=(\d+)', snatch[2]).group(1)
            if 'FLAC' in get_formats(torrent_group_id, session):
                #TODO handle false positive
                upgradable.append(snatch[0])
            else:
                if notify:
                    notify_artist(artist_id)
    return upgradable


class HiddenPassword(object):
    def __init__(self, password=''):
        self.password = password

    def __str__(self):
        return '*' * 4


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
    my_id = login(pth_user, pth_password, session)
    # get the #  of pages, loops them to build upgradables list
    upgradables = []
    snatched_url = 'https://passtheheadphones.me/torrents.php'
    params = {'page': 1, 'type': 'snatched', 'userid': my_id}
    r = session.get(snatched_url, params=params)
    if r.status_code != 200:
        logger.info('error while getting snatched')
    else:
        snatchedpage = html.fromstring(r.content)
        pages = set(re.match('torrents\.php\?page=(\d+).*', snatchedpage.xpath('//div[@class="linkbox"][1]/a/@href')[i]).group(1) for i in range(len(snatchedpage.xpath('//div[@class="linkbox"][1]/a/@href'))))
        pages.add('1')
        # yeah I know I could get page 1 info right away...
        for page in pages:
            logger.info('getting page number {}'.format(page))
            for up in get_upgradables_from_page(page, my_id, session, notify):
                upgradables.append(up)

    for upgradable in upgradables:
        logger.info('You can get a better version on: {}'.format(BASE_URL+upgradable))


if __name__ == '__main__':
    get_snatched_list()
