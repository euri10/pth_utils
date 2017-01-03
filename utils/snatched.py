import time
import threading
import logging

import click
from lxml import html
import re

logger = logging.getLogger(__name__)
logging.basicConfig()
logging.root.setLevel(level=logging.DEBUG)


def rate_limited(max_per_second):
    """
    Decorator that make functions not be called faster than
    """
    lock = threading.Lock()
    minInterval = 1.0 / float(max_per_second)

    def decorate(func):
        lastTimeCalled = [0.0]

        def rateLimitedFunction(args, *kargs):
            lock.acquire()
            elapsed = time.clock() - lastTimeCalled[0]
            leftToWait = minInterval - elapsed
            if leftToWait > 0:
                time.sleep(leftToWait)
            lock.release()
            ret = func(args, *kargs)
            lastTimeCalled[0] = time.clock()
            return ret

        return rateLimitedFunction

    return decorate


# API use is limited to 5 requests within any 10-second window
@rate_limited(0.5)
def get_formats(torrent_group_id, session):
    """Get formats for a given torrent group, uses the API because it can !"""
    url = 'https://passtheheadphones.me/ajax.php'
    params = {'action': 'torrentgroup', 'id': torrent_group_id}
    logger.info('getting formats of {}'.format(torrent_group_id))
    # rate limit hit if too fast, awful hard-coding
    # TODO : better handling of rate limit, this one sucks but works
    r = session.get(url, params=params)
    if r.json()['status'] == 'failure':
        logger.debug(r.json())
    else:
        return [r.json()['response']['torrents'][i]['format'] for i in
                range(len(r.json()['response']['torrents']))]


@rate_limited(0.5)
def get_display_infos(torrent_id, session):
    """Get formats for a given torrent id, uses the API because it can !"""
    # ajax.php?action=torrent&id=<Torrent Id>
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

@rate_limited(0.5)
def send_request(authkey, session, torrent_group_id, my_id):

    #checking torrent page to see if there's a request already
    url_torrent = 'https://passtheheadphones.me/torrents.php'
    params_torrent = {'id': torrent_group_id}
    rt = session.get(url=url_torrent, params=params_torrent)
    torrent_page = html.fromstring(rt.content)
    if len(torrent_page.xpath('//div[@class="box"]/div[@class="head"]/span/text()')):
        if 'Requests' in torrent_page.xpath('//div[@class="box"]/div[@class="head"]/span/text()')[0]:
            existing_requests = torrent_page.xpath('//table[@id="requests"]/tr[contains(@class,"requestrows")]/td[1]/a/@href')
            for er in existing_requests:
                rid = re.match('requests\.php\?action=view&id=(\d+)', er).group(1)
                url = 'https://passtheheadphones.me/ajax.php'
                params_req = {'action':'request', 'id': rid}
                rreq = session.get(url, params=params_req)
                if rreq.json()['status'] == 'failure':
                    logger.debug(rreq.json())
                else:
                    if rreq.json()['response']['requestorId'] == int(my_id):
                        logger.debug('Request already done on {}'.format(torrent_group_id))
                        return None
    logger.debug('Request make on {}'.format(torrent_group_id))
    url = 'https://passtheheadphones.me/requests.php'
    params = {'action': 'new', 'groupid': torrent_group_id}
    r = session.get(url=url, params=params)
    req_page = html.fromstring(r.content)

    logger.debug(req_page.xpath('//div[@class="box"]/div[@class="head"]/span/text()'))

    data = [(s.attrib['name'], s.attrib['value']) for s in
            req_page.xpath('//form[@id="request_form"]//input') if
            ('value' in s.attrib.keys() and 'name' in s.attrib.keys())]

    #remove formats, media, bitrates and amount then replace with what we want, FLAC, all medias, all release type, 100MB request
    data2 = [(i, v) for i, v in data if i not in ['formats[]', 'media[]', 'bitrates[]', 'amount']]
    data2.append(('formats[]', 1))
    data2.append(('all_bitrates', 'on'))
    data2.append(('all_media', 'on'))
    data2.append(('amount', 104857600))

    data2.append(('description', 'requested with pth_utils checker @ https://github.com/euri10/pth_utils'))
    data2.append(('unit', 'mb'))
    data2.append(('type', 'Music'))
    data2.append(('releasetype', (req_page.cssselect('#releasetype > option:checked')[0].attrib['value'])))
    for s in req_page.cssselect('#importance > option:checked'):
        data2.append(('importance[]', s.attrib['value']))

    if click.confirm('Do you want to continue request on {}?'.format(torrent_group_id)):
        r2 = session.post(url=url, data=data2)
        preq_page = html.fromstring(r2.content)
        if len(preq_page.xpath('//div[@class="box pad"]/p/text()')):
            logger.debug('we hit a request error')
            logger.debug(preq_page.xpath('//div[@class="box pad"]/p/text()')[0])
        else:
            logger.info('request done on {}'.format(torrent_group_id))
    else:
        logger.debug('no request made on {}'.format(torrent_group_id))
        return None



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

    torrents = snatchedpage.xpath(
        '//tr[@class="torrent torrent_row"]/td[@class="big_info"]/div/a[re:match(@href, "torrents\.php\?id=(\d+)&torrentid=(\d+)")]/@href',
        namespaces={"re": "http://exslt.org/regular-expressions"})
    logger.debug('{} items: {}'.format(len(torrents), torrents))
    if not len(torrents):
        logger.debug(
            anonymize(html.tostring(snatchedpage), auth, passkey, authkey))
    levels = snatchedpage.xpath(
        '//tr[@class="torrent torrent_row"]/td[@class="big_info"]/div/a[re:match(@href, "torrents\.php\?id=(\d+)&torrentid=(\d+)")]/following-sibling::text()[1]',
        namespaces={"re": "http://exslt.org/regular-expressions"})
    logger.debug('{} items: {}'.format(len(levels), levels))
    artists_id = snatchedpage.xpath(
        '//tr[@class="torrent torrent_row"]/td[@class="big_info"]/div/a[1]/@href')
    logger.debug('{} items: {}'.format(len(artists_id), artists_id))
    artists_name = snatchedpage.xpath(
        '//tr[@class="torrent torrent_row"]/td[@class="big_info"]/div/a[1]/text()')
    logger.debug('{} items: {}'.format(len(artists_name), artists_name))

    if not (len(torrents) == len(levels) == len(artists_id) == len(
            artists_name)):
        logging.error('mmmmmm shit')
        logging.debug(
            anonymize(html.tostring(snatchedpage), auth, passkey, authkey))
    return torrents, levels, artists_id, artists_name
