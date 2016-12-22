Set of utilities for PTH.

**snatched**

Launch the script, enter username, password.

Alternatively you can set them in env variables PTH_USER and PTH_PASSWORD

```
export PTH_USER=toto
export PTH_PASSWOD=1234
python snatched.py
```
```
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


