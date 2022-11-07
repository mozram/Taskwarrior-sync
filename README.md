# Taskwarrior-sync

Alternative to Taskd by Taskwarrior. Using simpler method than Taskd, but as secure (if not more secure) via PGP encryption.

# Features
[+] Secure sync via PGP<br>
[+] Store data in Git Gist<br>
[+] Very easy to setup<br>
[+] Daemon mode to auto sync<br>
[+] Desktop notification support for daemon mode<br>
[-] Only support desktop<br>

# Usage
Export the following environment variable:
```bash
export TASK_SYNC_TOKEN="Your Gist access token"
export TASK_GIST_ID="Your Gist ID"
export TASK_USER_ID="Email address associated with your PGP key"
```

To push to Gist: `./taskwarrior-sync.py --push`

To pull from Gist: `./taskwarrior-sync.py --pull`
