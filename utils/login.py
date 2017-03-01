import logging
import re
from lxml import html

logger = logging.getLogger(__name__)
logging.basicConfig()
logging.root.setLevel(level=logging.INFO)

BASE_URL = "https://redacted.ch/"
headers = {
    'Content-type': 'application/x-www-form-urlencoded',
    'Accept-Charset': 'utf-8',
    'User-Agent': 'pth_utils @ https://github.com/euri10/pth_utils'
}


def login(username, password, session):
    """Logs in user"""
    loginpage = 'https://redacted.ch/login.php'
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
    user_id, auth, passkey, authkey = re.match(
        'feeds\.php\?feed=feed_news&user=(.*)&auth=(.*)&passkey=(.*)&authkey=(.*)',
        mainpage.xpath(
            '//head//link[@type="application/rss+xml"][@title="PassTheHeadphones - News"]/@href')[
            0]).groups()
    return user_id, auth, passkey, authkey


def logout(authkey, session):
    """Logs out user"""
    logoutpage = 'https://redacted.ch/logout.php'
    params = {'auth': authkey}
    session.get(logoutpage, params=params, allow_redirects=False)
    logger.info('logged out')
