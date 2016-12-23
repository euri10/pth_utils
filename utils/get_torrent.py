import os
import time


def get_torrent(torrent_id, authkey, passkey, session, save_directory):
    """Downloads the torrent at torrent_id using the authkey and passkey"""
    filename = os.path.join(save_directory, str(torrent_id)+'.torrent')
    torrentpage = 'https://passtheheadphones.me/torrents.php'
    params = {'action': 'download', 'id': torrent_id}
    if authkey:
        params['authkey'] = authkey
        params['torrent_pass'] = passkey
    r = session.get(torrentpage, params=params, allow_redirects=False, stream=True)
    time.sleep(2)
    if r.status_code == 200 and 'application/x-bittorrent' in r.headers['content-type']:
        with open(filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)