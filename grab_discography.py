import os

import click
import logging
import requests


from utils.get_torrent import get_torrent
from utils.hidden_password import HiddenPassword
from utils.login import headers, login
from utils.size import sizeof_fmt

RELEASE_TYPE = {'Album': 1, 'Soundtrack': 3, 'EP': 5, 'Anthology': 6,
                'Compilation': 7,
                'Single': 9, 'Live': 11, 'Remix': 13, 'Bootleg': 14,
                'Interview': 15, 'Mixtape': 16,
                'Demo': 17, 'Concert Recording': 18, 'DJ Mix': 19,
                'Unknown': 21}
FORMAT = ['MP3', 'FLAC', 'AAC', 'AC3', 'DTS']
MEDIA = ['CD', 'DVD', 'Vinyl', 'Soundboard', 'SACD', 'DAT', 'Cassette', 'WEB',
         'Blu-Ray']

# log stuff
logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s')
logging.root.setLevel(level=logging.INFO)


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
@click.option('--artists', '-a', multiple=True, help='Artists id')
@click.option('--collages', '-c', multiple=True, help='Collages id')
@click.option('--releases', '-r', type=click.Choice(RELEASE_TYPE.keys()),
              multiple=True)
@click.option('--formats', '-f', type=click.Choice(FORMAT), multiple=True)
@click.option('--medias', '-m', type=click.Choice(MEDIA), multiple=True,
              help='If nothing is specified, all medias are taken')
@click.option('--output', '-o', prompt=True, default=os.path.join(os.environ.get('HOME', ''), 'Downloads'))
def dl_artist(pth_user, pth_password, artists, collages, releases, formats, medias, output):


    if releases == ():
        releases = RELEASE_TYPE
    if formats == ():
        formats = FORMAT
    if medias == ():
        medias = MEDIA

    logger.info('Downloading artist ids: {}'.format(artists))
    logger.info('Downloading collage ids: {}'.format(collages))
    logger.info('Downloading releases: {}'.format(releases))
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
        allowed_releases = [v for k, v in RELEASE_TYPE.items() if k in releases]
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
        allowed_releases = [v for k, v in RELEASE_TYPE.items() if k in releases]
        for tg in r.json()['response']['torrentgroups']:
            if tg['releaseType'] in allowed_releases:
                for t in tg['torrent']:
                    if t['format'] in formats and t['media'] in medias:
                        dl_list.append(t)
        total_size = 0
        for d in dl_list:
            total_size += d['size']
    logger.warning('You\'re about to dl {} in total from {} torrents'.format(sizeof_fmt(total_size), len(dl_list)))
    click.confirm('Do you want to continue?', abort=True)
    for d in dl_list:
        get_torrent(d['id'], authkey, passkey, session, output)
if __name__ == '__main__':
    dl_artist()
