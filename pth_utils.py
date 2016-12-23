import os
import re

import click
import requests
from lxml import html

from utils.get_torrent import get_torrent
from utils.hidden_password import HiddenPassword
from utils.login import headers, logger, BASE_URL
from utils.login import login
from utils.master import RELEASE_TYPE, FORMAT, MEDIA
from utils.size import sizeof_fmt
from utils.snatched import get_upgradables_from_page, notify_artist


@click.group()
def cli():
    pass


@click.command(short_help='Builds a list of snatched MP3s that have a FLAC. You can set up notifications for artists where there is NO FLAC and you snatched the MP3')
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
def checker(pth_user, pth_password, notify):
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



@click.command(short_help='Grabs an entire artist discography or a collage given filters')
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
@click.option('--artists', '-a', multiple=True, help='Artists id')
@click.option('--collages', '-c', multiple=True, help='Collages id')
@click.option('--releases', '-r', type=click.Choice(RELEASE_TYPE.keys()),
              multiple=True)
@click.option('--formats', '-f', type=click.Choice(FORMAT), multiple=True)
@click.option('--medias', '-m', type=click.Choice(MEDIA), multiple=True,
              help='If nothing is specified, all medias are taken')
@click.option('--output', '-o', prompt=True,
              default=os.path.join(os.environ.get('HOME', ''), 'Downloads'),
              help='Defaults to HOME/Downloads environment variable')
def grabber(pth_user, pth_password, artists, collages, releases, formats, medias, output):
    """Grabs an entire artist discography or a collage given filters"""
    if releases == ():
        releases = RELEASE_TYPE
    if formats == ():
        formats = FORMAT
    if medias == ():
        medias = MEDIA

    logger.info('Downloading artist ids: {}'.format(artists))
    logger.info('Downloading collage ids: {}'.format(collages))
    logger.info('Downloading releases: {}'.format(releases.keys()))
    logger.info('Downloading formats: {}'.format(formats))
    logger.info('Downloading medias: {}'.format(medias))

    # log into pth, gets the id
    session = requests.Session()
    session.headers = headers
    if isinstance(pth_password, HiddenPassword):
        pth_password = pth_password.password
    my_id, auth, passkey, authkey = login(pth_user, pth_password, session)

    url = 'https://passtheheadphones.me/ajax.php'
    dl_list = []
    for artist in artists:
        params = {'action': 'artist', 'id': artist}
        r = session.get(url, params=params)
        allowed_releases = [v for k, v in RELEASE_TYPE.items() if
                            k in releases]
        for tg in r.json()['response']['torrentgroup']:
            if tg['releaseType'] in allowed_releases:
                for t in tg['torrent']:
                    if t['format'] in formats and t['media'] in medias:
                        dl_list.append(t)
        total_size = 0
        for d in dl_list:
            total_size += d['size']
    for collage in collages:
        params = {'action': 'collage', 'id': collage}
        r = session.get(url, params=params)
        allowed_releases = [v for k, v in RELEASE_TYPE.items() if
                            k in releases]
        for tg in r.json()['response']['torrentgroups']:
            if tg['releaseType'] in allowed_releases:
                for t in tg['torrent']:
                    if t['format'] in formats and t['media'] in medias:
                        dl_list.append(t)
        total_size = 0
        for d in dl_list:
            total_size += d['size']
    logger.warning(
        'You\'re about to dl {} in total from {} torrents'.format(
            sizeof_fmt(total_size), len(dl_list)))
    click.confirm('Do you want to continue?', abort=True)
    for d in dl_list:
        get_torrent(d['id'], authkey, passkey, session, output)


cli.add_command(checker)
cli.add_command(grabber)

if __name__ == '__main__':
    cli()
