import json
import os
import re
from difflib import SequenceMatcher

import click
import logging
import requests
from lxml import html
from apiclient.discovery import build

from utils.get_torrent import get_torrent
from utils.hidden_password import HiddenPassword
from utils.login import headers, BASE_URL, logout
from utils.login import login
from utils.master import RELEASE_TYPE, FORMAT, MEDIA, COLLAGE_CATEGORY, \
    LFM_PERIODS
from utils.size import sizeof_fmt
from utils.snatched import get_upgradables_from_page, notify_artist, \
    subscribe_collage, get_formats, get_display_infos, send_request, catlookup, \
    artistlookup, filelookup

logger = logging.getLogger(__name__)
logging.basicConfig()


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
@click.option('--debug/--no_debug', default=False,
              help='Set to true to see debug logs on top of info')
@click.pass_context
def cli(ctx, pth_user, pth_password, debug):
    ctx.obj = PTH(pth_user, pth_password)
    if debug:
        logging.root.setLevel(level=logging.DEBUG)
    else:
        logging.root.setLevel(level=logging.INFO)


@click.command(
    short_help='Builds a list of snatched MP3s that have a FLAC. You can set up notifications for artists where there is NO FLAC and you snatched the MP3')
@pass_pth
@click.option('--notify/--no-notify',
              prompt=True,
              default=False,
              help='Set to True to set up a notification for new FLAC for the '
                   'artists where you got an MP3 and no FLAC is available yet, '
                   'would be amazing to be able to do that per torrent group !')
@click.option('--make_request/--no_make_request', prompt=True, default=False,
              help='Set to True to request a FLAC')
def checker(ctx, notify, make_request):
    """
    Builds a list of snatched MP3s that have a FLAC.
    You can set up notifications for artists where there is NO FLAC and you snatched the MP3
    """
    # log into pth, gets the id
    session = requests.Session()
    session.headers = headers
    if isinstance(ctx.pth_password, HiddenPassword):
        pth_password = ctx.pth_password.password
    my_id, auth, passkey, authkey = login(ctx.pth_user, pth_password, session)
    # get the #  of pages, loops them to build upgradables list
    upgradables = []
    notifiables = []
    requests_list = []
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
        snatched = []
        for page in pages:
            logger.info('getting page number {}'.format(page))
            torrents, levels, artists_id, artists_name = get_upgradables_from_page(
                page, my_id, session, auth, passkey, authkey)
            for t in zip(torrents, levels, artists_id, artists_name):
                snatched.append(t)
        # making lists of snatched torrents by format, handling already upgraded stuff, more efficient than previous
        logger.info('You snatched {} torrents'.format(len(snatched)))
        snatched_mp3 = [s for s in snatched if re.match('.*MP3.*', s[1])]
        logger.info('You snatched {} MP3s'.format(len(snatched_mp3)))
        snatched_flac = [s for s in snatched if re.match('.*FLAC.*', s[1])]
        logger.info('You snatched {} FLACs'.format(len(snatched_flac)))
        tgid_mp3 = [
            re.match('torrents\.php\?id=(\d+)&torrentid=(\d+)', u[0]).group(1)
            for u in snatched_mp3]
        tgid_flac = [
            re.match('torrents\.php\?id=(\d+)&torrentid=(\d+)', u[0]).group(1)
            for u in snatched_flac]
        already_upgraded = list(set(tgid_mp3) & set(tgid_flac))
        logger.info(
            'Among your MP3s snatched, you got already {} upgraded'.format(
                len(already_upgraded)))
        snatched_mp3_upgradable = [mp3 for mp3 in snatched_mp3 if re.match(
            'torrents\.php\?id=(\d+)&torrentid=(\d+)', mp3[0]).group(
            1) not in already_upgraded]
        logger.info(
            'Getting info on the {} upgradable MP3s you snatched'.format(
                len(snatched_mp3_upgradable)))
        for snatch in snatched_mp3_upgradable:
            logger.debug(snatch)
            torrent_group_id = re.match(
                'torrents\.php\?id=(\d+)&torrentid=(\d+)', snatch[0]).group(1)
            if 'FLAC' in get_formats(torrent_group_id, session):
                upgradables.append(snatch[0])
            else:
                if notify:
                    notifiables.append(snatch[3])
                if make_request:
                    # https://passtheheadphones.me/requests.php?action=new&groupid=269034
                    send_request(authkey, session, torrent_group_id, my_id)
    for upgradable in upgradables:
        logger.info(
            'You can get a better version on: {}'.format(BASE_URL + upgradable))
    notify_artist(authkey=authkey, session=session, artists_list=notifiables,
                  notification_label='no flac but got mp3')
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
@click.option('--output', '-o', prompt=True,
              type=click.Path(exists=True, file_okay=False),
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
    lfm_params = {'method': 'user.gettopartists', 'user': lfm_user,
                  'period': period,
                  'api_key': lastfm_api_key, 'format': 'json'}
    lfm_r = requests.get(lfm_url, params=lfm_params, )
    if lfm_r.status_code == 200:
        lfm_top_artists = [lfm_r.json()['topartists']['artist'][i]['name'] for i
                           in range(len(lfm_r.json()['topartists']['artist']))]
        notify_artist(authkey=authkey, session=session,
                      artists_list=lfm_top_artists,
                      notification_label='top lastfm artists')


@click.command(short_help='Displays info of your snatched torrents')
@click.option('--outfile', '-o', type=click.Path(),
              default='snatched_info.json')
@pass_pth
def displayer(ctx, outfile):
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
        displayables = []
        for page in pages:
            logger.info('getting page number {}'.format(page))
            torrents, levels, artists_id, artists_name = get_upgradables_from_page(
                page, my_id, session, auth, passkey, authkey)
            logger.debug('after get_upgradables_from_page')
            snatched = []
            for t in zip(torrents, levels, artists_id, artists_name):
                snatched.append(t)
            for snatch in snatched:
                logger.info(snatch)
                torrent_id = re.match('torrents\.php\?id=(\d+)&torrentid=(\d+)',
                                      snatch[0]).group(2)
                info = get_display_infos(torrent_id, session)
                displayables.append(info)
        logger.info('Here\'s an attempt at giving you your snatched info')
        extract = ['id', 'recordLabel', 'catalogueNumber']
        data = [{extract[i]: dis[v]} for i, v in enumerate(extract) for dis in
                displayables]
        with open(outfile, 'w') as output:
            json.dump(data, output)
        logout(authkey=authkey, session=session)


@click.command()
@pass_pth
@click.option('--mix_url', '-m', help='Beatport mix url')
def mixer(ctx, mix_url):
    headers_beatport = {'Host': 'mixes.beatport.com',
                        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:51.0) Gecko/20100101 Firefox/51.0',
                        'Referer': 'http://mixes.beatport.com/'}
    session_bp = requests.session()
    session_bp.headers = headers_beatport

    r = session_bp.get(mix_url)
    mixpage = html.fromstring(r.content)
    titles = mixpage.xpath('//table[@id="tracks"]/tbody/tr/td[5]/a/text()')
    artists_td = mixpage.xpath('//table[@id="tracks"]/tbody/tr/td[6]')
    artists = [art.xpath('a/text()') for art in artists_td]
    titles_links = mixpage.xpath('//table[@id="tracks"]/tbody/tr/td[5]/a/@href')
    labels_links = mixpage.xpath('//table[@id="tracks"]/tbody/tr/td[7]/a/@href')
    logger.info(r)

    session = requests.Session()
    session.headers = headers
    if isinstance(ctx.pth_password, HiddenPassword):
        pth_password = ctx.pth_password.password
    my_id, auth, passkey, authkey = login(ctx.pth_user, pth_password, session)

    for (at, s) in zip(artists, titles):
        logger.info('>>>Looking for {} by {}'.format(s, at))
        for a in at:
            found = artistalgo(a, s, session)
            for p, ttt in found:
                if ttt == 1:
                    logger.info('  |{}|{}|https://passtheheadphones.me/torrents.php?id={}'.format(p['artists'][0]['name'], p['groupName'], p['groupId']))
                elif ttt == 2:
                    logger.info('  |{}|{}|https://passtheheadphones.me/torrents.php?id={}'.format(p['artist'], p['groupName'], p['groupId']))
    logout(authkey=authkey, session=session)


@click.command()
@pass_pth
@click.option('--youtube_playlist_id', '-y', help='youtube playlist url')
@click.option('--youtube_api_key',
              default=lambda: os.environ.get('YOUTUBE_API_KEY', ''),
              help='Defaults to PTH_PASSWORD environment variable',
              hide_input=True)
def yt_playlist(ctx, youtube_playlist_id, youtube_api_key):
    # log into pth, gets the id
    session = requests.Session()
    session.headers = headers
    if isinstance(ctx.pth_password, HiddenPassword):
        pth_password = ctx.pth_password.password
    my_id, auth, passkey, authkey = login(ctx.pth_user, pth_password, session)

    # youtube get items of playlist
    youtube_playlist_id = 'PLMC9KNkIncKtGvr2kFRuXBVmBev6cAJ2u'
    youtube = build('youtube', 'v3', developerKey=youtube_api_key)
    playlist = youtube.playlistItems().list(
        part='contentDetails,id,snippet,status',
        playlistId='PLMC9KNkIncKtGvr2kFRuXBVmBev6cAJ2u'
    ).execute()
    titles = [playlist['items'][p]['snippet']['title'] for p in
              range(len(playlist['items']))]
    # remove stuff inside parenthesis
    ctitles = []
    for t in titles:
        ctitles.append(re.sub('\s*\([^\)]*\)\s*', '', t))

    url = 'https://passtheheadphones.me/ajax.php'
    for ct in ctitles:
        params = {'action': 'browse', 'searchstr': ct}
        r = session.get(url, params=params)
        logger.debug(r.json())
        logger.debug(len(r.json()['response']['results']))


def by_artist(a, s, session):
    pm = artistlookup(a, s, session)
    if len(pm):
        return pm, 1
    else:
        bfn = filelookup(a, s, session)
        if len(bfn):
            return bfn, 2
        else:
            return [], 0


def catalgo(a, s, c, session):
    found = []
    pattern_variations = ['([a-zA-Z]+)([0-9]+)', '([a-zA-Z]+) ([0-9]+)']
    cat_variations = [c]
    for i, pat in enumerate(pattern_variations):
        can = re.match(pat, c)
        if can is not None:
            if i == 0:
                cat_variations.append(can.group(1) + ' ' + can.group(2))
            elif i == 1:
                cat_variations.append(can.group(1) + can.group(2))
    for cat in cat_variations:
        match = catlookup(cat, session)
        if len(match):
            for m in match:
                try:
                    dist = SequenceMatcher(None, a, m['artist']).ratio()
                    if dist > 0.9:
                        found.append((m, 2))
                except KeyError as e:
                    logging.debug('key error in {}'.format(m))
    return found


def artistalgo(a, s, session):
    found = []
    pattern_variations = ['(.*) (\(.*\))']
    song_variations = [s]
    for i, pat in enumerate(pattern_variations):
        song_match = re.match(pat, s)
        if song_match is not None:
            if i == 0:
                song_variations.append(song_match.group(1))
    for song in song_variations:
        ba, ttt = by_artist(a, song, session)
        for p in ba:
            found.append((p, ttt))
    return found


@click.command()
@pass_pth
@click.option('--month_number', '-m')
@click.option('--year_number', '-y')
@click.option('--collage_id', '-c')
def ra(ctx, month_number, year_number, collage_id):
    # log into pth, gets the id
    session = requests.Session()
    session.headers = headers
    if isinstance(ctx.pth_password, HiddenPassword):
        pth_password = ctx.pth_password.password
    my_id, auth, passkey, authkey = login(ctx.pth_user, pth_password, session)

    url_ra = 'https://www.residentadvisor.net/dj-charts.aspx'
    if month_number is None:
        params_ra = {'top': 100, 'yr': year_number}
        top = 100
    else:
        params_ra = {'top': 50, 'mn': month_number, 'yr': year_number}
        top = 50

    req_ra = requests.get(url=url_ra, params=params_ra)
    if not req_ra.status_code == 200:
        logger.debug('RA request failed')
    else:
        chartpage = html.fromstring(req_ra.content)
        artist_links = chartpage.xpath('//table[@id="tracks"]/tr/td[3]')
        if len(artist_links) != top:
            logger.debug('error not 50 found')
        song_links = chartpage.xpath('//table[@id="tracks"]/tr/td[4]')
        if len(song_links) != top:
            logger.debug('error not 50 found')
        catalogs = chartpage.xpath('//table[@id="tracks"]/tr/td[5]')
        ra_items = []
        for i in zip(artist_links, song_links, catalogs):
            artist = i[0].xpath('a/text()')[0]
            song = ' '.join(i[1].xpath('a/text() | text()'))
            if len(i[2].xpath('div/text()')):
                cat_number = i[2].xpath('div/text()')[0]
            else:
                cat_number = None
            ra_items.append((artist, song, cat_number))
        if len(ra_items) != top:
            logger.debug('error not 50 found')

        dl_list = []
        # loop through songs
        # ra_items = [('Floorplan','Never Grow Old (Re-Plant)', None)]
        # ra_items = [('Ten Walls','Walking With Elephants','BOSO 001')]
        # ra_items = [('Recondite','Caldera','HFT035')]
        for i, (a, s, c) in enumerate(ra_items):
            found = []
            ttt = 0
            logger.info('{:2d}(\'{}\',\'{}\',\'{}\')'.format(i + 1, a, s, c))
            # look by catalog number 1st
            if c is not None:
                found = catalgo(a, s, c, session)
                if not len(found):
                    found = artistalgo(a, s, session)
            else:
                found = artistalgo(a, s, session)

            for p, ttt in found:
                if ttt == 1:
                    logger.info(
                        '  |{}|{}|https://passtheheadphones.me/torrents.php?id={}'.format(
                            p['artists'][0]['name'], p['groupName'],
                            p['groupId']))
                elif ttt == 2:
                    logger.info(
                        '  |{}|{}|https://passtheheadphones.me/torrents.php?id={}'.format(
                            p['artist'], p['groupName'], p['groupId']))

    logout(authkey=authkey, session=session)


@click.command()
@pass_pth
def reqfiller(ctx):
    # log into pth, gets the id
    session = requests.Session()
    session.headers = headers
    if isinstance(ctx.pth_password, HiddenPassword):
        pth_password = ctx.pth_password.password
    my_id, auth, passkey, authkey = login(ctx.pth_user, pth_password, session)

    url_ajax = 'https://passtheheadphones.me/ajax.php'
    params = {'action': 'requests', 'page': 88}
    r = session.get(url_ajax, params=params)
    if r.status_code == 200 and r.json()['status'] == 'success':
        for rr in r.json()['response']['results']:
            if not rr['isFilled'] and rr['categoryId'] == 1:
                # logger.info('Request: https://passtheheadphones.me/requests.php?action=view&id={}'.format(rr['requestId']))
                (a, s, c) = (
                rr['artists'][0][0]['name'], rr['title'], rr['catalogueNumber'])
                if c is not None:
                    found = catalgo(a, s, c, session)
                    if not len(found):
                        found = artistalgo(a, s, session)
                else:
                    found = artistalgo(a, s, session)
                for p, ttt in found:
                    logger.info(
                        'Request: https://passtheheadphones.me/requests.php?action=view&id={}'.format(
                            rr['requestId']))
                    if ttt == 1:
                        logger.info(
                            '  |{}|{}|https://passtheheadphones.me/torrents.php?id={}'.format(
                                p['artists'][0]['name'], p['groupName'],
                                p['groupId']))
                    elif ttt == 2:
                        logger.info(
                            '  |{}|{}|https://passtheheadphones.me/torrents.php?id={}'.format(
                                p['artist'], p['groupName'], p['groupId']))

    logout(authkey=authkey, session=session)


cli.add_command(checker)
cli.add_command(grabber)
cli.add_command(similar)
cli.add_command(collage_notify)
cli.add_command(lfm_subscriber)
cli.add_command(displayer)
cli.add_command(mixer)
cli.add_command(yt_playlist)
cli.add_command(ra)
cli.add_command(reqfiller)

if __name__ == '__main__':
    cli()
