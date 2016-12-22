Set of utilities for PTH.

Launch the script, enter username, password.

Alternatively you can set them in environment variables PTH_USER and PTH_PASSWORD

```
export PTH_USER=toto
export PTH_PASSWORD=1234
python snatched.py
```

**snatched**


```
➜  pth_utils git:(master) ✗ python snatched.py --help          
Usage: snatched.py [OPTIONS]

  Builds a list of snatched MP3s that have a FLAC. You can set up
  notifications for artists where there is NO FLAC and you snatched the MP3

Options:
  --pth_user TEXT         Defaults to PTH_USER environment variable
  --pth_password TEXT     Defaults to PTH_PASSWORD environment variable
  --notify / --no-notify  Set to True to set up a notification for new FLAC
                          for the artists where you got an MP3 and no FLAC is
                          available yet, would be amazing to be able to do
                          that per torrent group !
  --help                  Show this message and exit.

```


**grab_discography**

```
 ➜  pth_utils git:(master) ✗ python grab_discography.py --help
Usage: grab_discography.py [OPTIONS]

Options:
  --pth_user TEXT                 Defaults to PTH_USER environment variable
  --pth_password TEXT             Defaults to PTH_PASSWORD environment
                                  variable
  -a, --artists TEXT              Artists id
  -c, --collages TEXT             Collages id
  -r, --releases [DJ Mix|Live|Remix|Mixtape|Bootleg|EP|Unknown|Single|Demo|Compilation|Anthology|Interview|Album|Soundtrack|Concert Recording]
  -f, --formats [MP3|FLAC|AAC|AC3|DTS]
  -m, --medias [CD|DVD|Vinyl|Soundboard|SACD|DAT|Cassette|WEB|Blu-Ray]
                                  If nothing is specified, all medias are
                                  taken
  -o, --output TEXT
  --help                          Show this message and exit.

```

**ideas**

_a script to populate the 'similar artists' field of an artist's page._
https://passtheheadphones.me/forums.php?action=viewthread&threadid=1744


**done**

_A script that lets you download the whole discography of one artist (letting you decide the quality and etc.)_
https://passtheheadphones.me/forums.php?action=viewthread&threadid=1744&page=1

_Option to download entire collages in a given format?_ 
https://passtheheadphones.me/forums.php?page=3&action=viewthread&threadid=1744
