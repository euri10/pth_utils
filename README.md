Set of utilities for PTH.

Launch the script, enter username, password.

Alternatively you can set them in environment variables PTH_USER and PTH_PASSWORD

**Installation**
```python setup.py install```

**Usage**
```
➜  pth_utils git:(master) ✗ pth_utils                                           
Usage: pth_utils [OPTIONS] COMMAND [ARGS]...

Options:
  --pth_user TEXT      Defaults to PTH_USER environment variable
  --pth_password TEXT  Defaults to PTH_PASSWORD environment variable
  --help               Show this message and exit.

Commands:
  checker         Builds a list of snatched MP3s that have a FLAC. You can set
                  up notifications for artists where there is NO FLAC and you
                  snatched the MP3
  collage_notify  Filter collages and subscribe to them
  displayer       Displays info of your snatched torrents
  grabber         Grabs an entire artist discography or a collage given
                  filters
  lfm_subscriber  Subscribe to top artists of you lastfm user
  similar         Fetch similar artists from Last.fm and fills pth


```

**Ideas**


**Implemented**

_A script that lets you download the whole discography of one artist (letting you decide the quality and etc.)_
https://passtheheadphones.me/forums.php?action=viewthread&threadid=1744&postid=19122#post19122

_Option to download entire collages in a given format?_ 
https://passtheheadphones.me/forums.php?action=viewthread&threadid=1744&postid=37334#post37334

_a script to populate the 'similar artists' field of an artist's page._
https://passtheheadphones.me/forums.php?action=viewthread&threadid=1744&postid=20172#post20172

_I would love to subscribe to collages, notification-style. Would this be possible?_
https://passtheheadphones.me/forums.php?action=viewthread&threadid=1744&postid=52608#post52608

_Notifications for your top last.fm artists_

_Is there a script that let you view the release info (label/#cat etc) in your snatched torrents? Or possibly making a list of that info. Good information to backup or use when tagging the personal library_
https://passtheheadphones.me/forums.php?action=viewthread&threadid=1744&postid=88270#post88270

