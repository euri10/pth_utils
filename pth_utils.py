import json
import os
import re

import click
import logging
import requests
from lxml import html

from utils.get_torrent import get_torrent
from utils.hidden_password import HiddenPassword
from utils.login import headers, BASE_URL, logout
from utils.login import login
from utils.master import RELEASE_TYPE, FORMAT, MEDIA, COLLAGE_CATEGORY, \
    LFM_PERIODS
from utils.size import sizeof_fmt
from utils.snatched import get_upgradables_from_page, notify_artist, \
    subscribe_collage, get_formats, get_display_infos

logger = logging.getLogger(__name__)
logging.basicConfig()
logging.root.setLevel(level=logging.INFO)


class PTH(object):
    def __init__(self, pth_user=None, pth_password=None):
        self.pth_user = pth_user
        self.pth_password = pth_password

pass_pth = click.make_pass_decorator(PTH)

@click.group()
@click.option('--pth_user',
              # prompt=True,
              default=lambda: os.environ.get('PTH_USER', ''),
              help='Defaults to PTH_USER environment variable')
@click.option('--pth_password',
              # prompt=True,
              default=lambda: HiddenPassword(
                  os.environ.get('PTH_PASSWORD', '')),
              help='Defaults to PTH_PASSWORD environment variable',
              hide_input=True)
@click.pass_context
def cli(ctx, pth_user, pth_password):
    ctx.obj = PTH(pth_user, pth_password)


@click.command(
    short_help='Builds a list of snatched MP3s that have a FLAC. You can set up notifications for artists where there is NO FLAC and you snatched the MP3')
@pass_pth
@click.option('--notify/--no-notify',
              prompt=True,
              default=False,
              help='Set to True to set up a notification for new FLAC for the '
                   'artists where you got an MP3 and no FLAC is available yet, '
                   'would be amazing to be able to do that per torrent group !')
def checker(ctx, notify):
    """
    Builds a list of snatched MP3s that have a FLAC.
    You can set up notifications for artists where there is NO FLAC and you snatched the MP3
    """
    # log into pth, gets the id
    session = requests.Session()
    session.headers = headers
    if isinstance(ctx.pth_password, HiddenPassword):
        pth_password = ctx.pth_password.password
    my_id, _, _, authkey = login(ctx.pth_user, pth_password, session)
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
            torrents, levels, artists_id, artists_name = get_upgradables_from_page(page, my_id, session)

            #test
            upgradable = []
            notifiable = []
            snatched = []
            for t in zip(torrents, levels, artists_id, artists_name):
                snatched.append(t)
            for snatch in snatched:
                if re.match('.*MP3.*', snatch[1]):
                    torrent_group_id = re.match('torrents\.php\?id=(\d+)&torrentid=(\d+)', snatch[0]).group(1)
                    if 'FLAC' in get_formats(torrent_group_id, session):
                        # TODO handle false positive
                        upgradable.append(snatch[0])
                    else:
                        if notify:
                            notifiable.append(snatch[3])

            ##
            for u in upgradable:
                upgradables.append(u)
            for n in set(notifiable):
                notifiables.append(n)

    for upgradable in upgradables:
        logger.info(
            'You can get a better version on: {}'.format(BASE_URL + upgradable))

    notify_artist(authkey=authkey, session=session, artists_list=notifiables, notification_label='no flac but got mp3')
    logout(authkey=authkey, session=session)


@click.command(
    short_help='Grabs an entire artist discography or a collage given filters')
@pass_pth
@click.option('--artists', '-a', multiple=True, help='Artists id')
@click.option('--collages', '-c', multiple=True, help='Collages id')
@click.option('--releases', '-r', type=click.Choice(RELEASE_TYPE.keys()),
              multiple=True)
@click.option('--formats', '-f', type=click.Choice(FORMAT), multiple=True)
@click.option('--medias', '-m', type=click.Choice(MEDIA), multiple=True,
              help='If nothing is specified, all medias are taken')
@click.option('--output', '-o', prompt=True, type=click.Path(exists=True, file_okay=False),
              default=os.path.join(os.environ.get('HOME', ''), 'Downloads'),
              help='Defaults to HOME/Downloads environment variable')
def grabber(ctx, artists, collages, releases, formats,
            medias, output):
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
    if isinstance(ctx.pth_password, HiddenPassword):
        pth_password = ctx.pth_password.password
    my_id, auth, passkey, authkey = login(ctx.pth_user, pth_password, session)

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
    logout(authkey=authkey, session=session)


@click.command(short_help='Fetch similar artists from Last.fm and fills pth')
@pass_pth
@click.option('--lastfm_api_key',
              prompt=True,
              default=lambda: os.environ.get('LASTFM_API_KEY', ''),
              help='Defaults to LASTFM_API_KEY environment variable')
@click.option('--artists', '-a', multiple=True, help='Artists id')
@click.option('--trigger', '-t', multiple=True,
              help='Match level required to add to similar list')
def similar(ctx, lastfm_api_key, artists,
            trigger):
    """Fetch similar artists from Last.fm and fills pth"""

    # log into pth, gets the id
    session = requests.Session()
    session.headers = headers
    if isinstance(ctx.pth_password, HiddenPassword):
        pth_password = ctx.pth_password.password
    my_id, auth, passkey, authkey = login(ctx.pth_user, pth_password, session)

    url = 'https://passtheheadphones.me/ajax.php'
    for artist in artists:
        params = {'action': 'artist', 'id': artist}
        r = session.get(url, params=params)
        pth_artist_name = r.json()['response']['name']
        pth_similars = [s['name'] for s in
                        r.json()['response']['similarArtists']]

        lfm_url = 'http://ws.audioscrobbler.com/2.0/?'
        lfm_params = {'method': 'artist.getsimilar', 'artist': pth_artist_name,
                      'api_key': lastfm_api_key, 'format': 'json'}
        lfm_r = requests.get(lfm_url, params=lfm_params, )
        if lfm_r.status_code == 200:
            similars = [sa['name'] for sa in
                        lfm_r.json()['similarartists']['artist'] if
                        sa['match'] > trigger[0]]
        logger.info('found {} similar artists with a match > {}: {}'.format(
            len(similars), trigger[0], similars))

        for sim in similars:
            if sim not in pth_similars:
                if click.confirm('Do you want to add {}?'.format(sim)):
                    # params_sim = {'action': 'artist', 'artistname': sim}
                    # rsim = session.get(url, params=params_sim)
                    # pth_artist_id = rsim.json()['response']['id']
                    datasim = {'action': 'add_similar', 'auth': authkey,
                               'artistid': artist, 'artistname': sim}
                    createsim = session.post(
                        'https://passtheheadphones.me/artist.php', data=datasim)
                    if createsim.status_code == 200 and sim.encode() not in createsim.content:
                        logger.info('not added')
                    else:
                        pass
            else:
                logger.info('Artist {} is already in pth similars'.format(sim))
    logout(authkey=authkey, session=session)


@click.command(short_help='Filter collages and subscribe to them')
@pass_pth
@click.option('--search', '-s', help='Search term')
@click.option('--tags', '-t', multiple=True, help='Tags')
@click.option('--tags_type', '-tt', default='all',
              type=click.Choice(['any', 'all']))
@click.option('--categories', '-c', multiple=True,
              type=click.Choice(COLLAGE_CATEGORY))
@click.option('--search_in', '-si', type=click.Choice(['name', 'desc']))
def collage_notify(ctx, search, tags, tags_type, categories,
                   search_in):
    # log into pth, gets the id
    session = requests.Session()
    session.headers = headers
    if isinstance(ctx.pth_password, HiddenPassword):
        pth_password = ctx.pth_password.password
    my_id, auth, passkey, authkey = login(ctx.pth_user, pth_password, session)

    cats_filter = [1 if cat in categories else 0 for cat in COLLAGE_CATEGORY]
    if search_in is 'desc':
        search_in = 'description'
    else:
        search_in = 'c.name'

    if tags_type is 'all':
        tags_type = 1
    else:
        tags_type = 0
    url = 'https://passtheheadphones.me/collages.php'
    params = {'action': 'search', 'search': search, 'tags': ','.join(tags),
              'tags_type': tags_type, 'cats[0]': cats_filter[0],
              'cats[1]': cats_filter[1], 'cats[2]': cats_filter[2],
              'cats[3]': cats_filter[3], 'cats[4]': cats_filter[4],
              'cats[5]': cats_filter[5], 'cats[6]': cats_filter[6],
              'cats[7]': cats_filter[7], 'type': search_in, 'order_by': 'Time',
              'order_way': 'Descending'}

    r = session.get(url, params=params)
    logger.info(r.url)
    collage_page = html.fromstring(r.content)
    # loop through pages
    pages = set(re.match('collages\.php\?page=(\d+).*', collage_page.xpath(
        '//div[@class="linkbox"][2]/a/@href')[i]).group(1) for i in range(
        len(collage_page.xpath('//div[@class="linkbox"][2]/a/@href'))))
    pages.add('1')
    collages_tonotify = []
    # yeah I know I could get page 1 info right away...
    for page in pages:
        params = {'page': page, 'action': 'search', 'search': search,
                  'tags': ','.join(tags),
                  'tags_type': tags_type, 'cats[0]': cats_filter[0],
                  'cats[1]': cats_filter[1], 'cats[2]': cats_filter[2],
                  'cats[3]': cats_filter[3], 'cats[4]': cats_filter[4],
                  'cats[5]': cats_filter[5], 'cats[6]': cats_filter[6],
                  'cats[7]': cats_filter[7], 'type': search_in,
                  'order_by': 'Time',
                  'order_way': 'Descending'}
        r = session.get(url, params=params)
        logger.info(r.url)
        collage_page = html.fromstring(r.content)
        collages = [re.match('collages\.php\?id=(\d+)', collage_page.xpath(
            '//table[@class="collage_table"]/tr/td[2]/a/@href')[i]).group(1) for
                    i in range(len(collage_page.xpath(
                '//table[@class="collage_table"]/tr/td[2]/a/@href')))]
        for col in collages:
            collages_tonotify.append(col)
        logger.info('Found {} collages'.format(len(collages_tonotify)))
        click.confirm(
            'Are you sure you want to subscribe to those {} collages?'.format(
                len(collages_tonotify)), abort=True)
        for ctn in collages_tonotify:
            subscribe_collage(authkey, session, ctn)
        logout(authkey=authkey, session=session)

@click.command(short_help='Subscribe to top artists of you lastfm user')
@pass_pth
@click.option('--lastfm_api_key',
              prompt=True,
              default=lambda: os.environ.get('LASTFM_API_KEY', ''),
              help='Defaults to LASTFM_API_KEY environment variable')
@click.option('--lfm_user', '-l', help='Last.fm user')
@click.option('--period', '-p', type=click.Choice(LFM_PERIODS),
              help='The time period over which to retrieve top artists for')
def lfm_subscriber(ctx, lastfm_api_key, lfm_user, period):
    """Subscribe to top artists of you lastfm user"""

    # log into pth, gets the id
    session = requests.Session()
    session.headers = headers
    if isinstance(ctx.pth_password, HiddenPassword):
        pth_password = ctx.pth_password.password
    my_id, auth, passkey, authkey = login(ctx.pth_user, pth_password, session)
    lfm_url = 'http://ws.audioscrobbler.com/2.0/?'
    lfm_params = {'method': 'user.gettopartists', 'user': lfm_user, 'period': period,
                  'api_key': lastfm_api_key, 'format': 'json'}
    lfm_r = requests.get(lfm_url, params=lfm_params, )
    if lfm_r.status_code == 200:
        lfm_top_artists= [lfm_r.json()['topartists']['artist'][i]['name'] for i in range(len(lfm_r.json()['topartists']['artist']))]
        notify_artist(authkey=authkey, session=session, artists_list=lfm_top_artists, notification_label='top lastfm artists')


@click.command(short_help='Displays info of your snatched torrents')
@pass_pth
def displayer(ctx):
    """Displays info of your snatched torrents"""

    # log into pth, gets the id
    session = requests.Session()
    session.headers = headers
    if isinstance(ctx.pth_password, HiddenPassword):
        pth_password = ctx.pth_password.password
    my_id, auth, passkey, authkey = login(ctx.pth_user, pth_password, session)
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
        pages = {5}
        displayables = []
        for page in pages:
            logger.info('getting page number {}'.format(page))
            torrents, levels, artists_id, artists_name = get_upgradables_from_page(page, my_id, session)
            snatched = []
            for t in zip(torrents, levels, artists_id, artists_name):
                snatched.append(t)
            for snatch in snatched[0:1]:
                logger.info(snatch)
                torrent_id = re.match('torrents\.php\?id=(\d+)&torrentid=(\d+)', snatch[0]).group(2)
                info = get_display_infos(torrent_id, session)
                displayables.append(info)
        logger.info('Here\'s an attempt at giving you your snatched info')
        extract = ['id', 'recordLabel', 'catalogueNumber']
        data = [{extract[i]: dis[v]} for i,v in enumerate(extract) for dis in displayables]
        with open('snatched_info.txt', 'w') as outfile:
            json.dump(data, outfile)

cli.add_command(checker)
cli.add_command(grabber)
cli.add_command(similar)
cli.add_command(collage_notify)
cli.add_command(lfm_subscriber)
cli.add_command(displayer)

if __name__ == '__main__':
    cli()
