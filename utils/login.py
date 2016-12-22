import logging

# log stuff
import re

from lxml import html

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s')
logging.root.setLevel(level=logging.INFO)

BASE_URL = "https://passtheheadphones.me/"
headers = {
    'Content-type': 'application/x-www-form-urlencoded',
    'Accept-Charset': 'utf-8',
    'User-Agent': 'pth_utils @ https://github.com/euri10/pth_utils]'
}

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
    # user_id = re.match('user\.php\?id=(\d+)',
    #                    mainpage.xpath('//li[@id="nav_userinfo"]/a/@href')[
    #                        0]).group(1)
    user_id, auth, passkey, authkey = re.match(
        'feeds\.php\?feed=feed_news&user=(.*)&auth=(.*)&passkey=(.*)&authkey=(.*)',
        mainpage.xpath(
            '//head//link[@type="application/rss+xml"][@title="PassTheHeadphones - News"]/@href')[
            0]).groups()
    return user_id, auth, passkey, authkey
