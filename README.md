# Marketplace Watcher

Runs Facebook® Marketplace searches on a schedule, filters the results against
your keywords, and pushes new matches to Telegram (photo + tap-to-open link).

Point it at anything — furniture, bikes, a specific tool, free stuff — by editing
`config.yml`: list the search terms, then whitelist/blacklist words in the title.
You only get pinged for **new** listings, once each.

> ⚠️ Facebook has no public Marketplace API, so this drives a logged-in browser.
> Automated access is against Facebook's Terms of Service and can get the account
> restricted — **use an account you don't mind losing, never your main one.**
> Polling every 30 min is gentle; don't crank it faster. For personal, educational
> use only. Not affiliated with or endorsed by Meta.

> 🍎 **macOS: keep this project OUT of `~/Downloads`, `~/Documents`, and
> `~/Desktop`.** Those folders are privacy-protected, and a `launchd` background
> job gets "Operation not permitted" trying to read them. A home-folder path like
> `~/marketplace-watcher` is fine.

## Pipeline

```
launchd (every 30 min) → Playwright + saved login
   → open each search URL (newest first) → scrape listing cards
   → filter (whole-word include / exclude, price) → dedup (SQLite)
   → Telegram alert for each NEW match
```

---

## Setup

Requires **macOS** (for the scheduler) and **Python 3.9+**.

### 1. Get the code + your config
```bash
git clone <YOUR-REPO-URL> ~/marketplace-watcher
cd ~/marketplace-watcher
cp config.example.yml config.yml      # your searches        (git-ignored)
cp .env.example .env                  # your Telegram secrets (git-ignored)
```

### 2. Install dependencies
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
```

### 3. Log in once (saves the session)
```bash
.venv/bin/python login.py
```
A browser opens → log in to the account the bot will use → press Enter in the terminal.

### 4. Set the Marketplace location + radius
```bash
.venv/bin/python set_location.py
```
Set the location control to your city + preferred radius, Apply, then press Enter.
Facebook ties the feed to the account's saved location — it can't be set via URL.

### 5. Telegram alerts
1. In Telegram, message **@BotFather** → `/newbot` → copy the **bot token**.
2. Paste the token into `.env` as `TELEGRAM_BOT_TOKEN`.
3. Send your new bot any message (so it's allowed to reply to you).
4. Auto-fill your chat id, then test:
   ```bash
   .venv/bin/python get_chat_id.py
   .venv/bin/python bot.py --test-telegram
   ```

### 6. Tune your searches, then dry-run
Edit `config.yml`, then test **without sending alerts**:
```bash
.venv/bin/python bot.py --dry-run
```

### 7. Baseline + schedule
```bash
.venv/bin/python bot.py        # first run baselines current listings silently
./install_launchd.sh           # generate + load the every-30-min launchd job
```
`install_launchd.sh` writes the launchd plist for *your* install path (no
hard-coded usernames) and starts it. Logs go to `bot.log`.

> launchd only fires while the Mac is awake (missed runs are skipped, not queued).
> For true 24/7, run it on a small always-on Linux VPS instead (cron/systemd).

---

## `config.yml` options

| Key | Meaning |
|---|---|
| `marketplace_urls` | One `…/search?query=…` URL per term; results combined + de-duped. |
| `include_keywords` | Keep a listing only if its title has one of these (whole-word + plurals). Empty = keep everything. |
| `exclude_keywords` | Drop the listing if its title has any of these. |
| `require_free` | `true` = only "Free" listings; `false` = any price. |
| `exclude_spanish` | `true` = drop titles that look like Spanish. |
| `headless` | `false` shows the browser; `true` runs it in the background. |
| `scroll_passes` | How many times to scroll each results page. |

Edits apply on the next scheduled run — no restart needed.

---

## Everyday operations

```bash
tail -f ~/marketplace-watcher/bot.log                        # watch it run
.venv/bin/python bot.py                                     # run one scan now
./uninstall_launchd.sh                                      # stop + disable schedule
./install_launchd.sh                                        # (re)start schedule
launchctl kickstart -k gui/$(id -u)/com.marketplacewatcher.bot   # force a run now
rm seen.db && .venv/bin/python bot.py                       # reset: re-baseline
```

`bot.py` flags: `--dry-run` (scan + print, no alerts/writes), `--loop` (run forever
in the terminal instead of launchd), `--backfill` (alert on ALL current matches
instead of baselining), `--test-telegram` (send a test message).

---

## Helper scripts

| Script | What it does |
|---|---|
| `login.py` | One-time login; persists the session to `user-data/`. |
| `set_location.py` | Set the account's Marketplace location + radius. |
| `get_chat_id.py` | Reads your bot token from `.env`, writes your Telegram chat id. |
| `install_launchd.sh` / `uninstall_launchd.sh` | Load / stop the 30-min scheduler. |

---

## Troubleshooting

- **"bounced to login page"** → `.venv/bin/python login.py` again (session expired).
- **The scheduled job hangs / never finishes (macOS)** → the Chromium launch args in
  `scraper.py` include `--password-store=basic`. Without it, Chromium hangs under
  launchd waiting on an un-answerable Keychain prompt when it loads the logged-in
  cookie jar. Keep that flag.
- **`launchctl load` says "Input/output error"** → that command is deprecated on
  current macOS; use `./install_launchd.sh` (it uses `launchctl bootstrap`).
- **"Operation not permitted" reading the venv** → the project is inside a
  protected folder (`~/Downloads` etc.). Move it to e.g. `~/marketplace-watcher`.
- **0 cards scraped** → set `headless: false` and watch; Facebook may be showing a
  checkpoint, or a search URL needs adjusting.
- **No Telegram photo, just text** → normal; Facebook's image CDN sometimes blocks
  Telegram's fetcher, so it falls back to a text + link message.
- **Don't run `login.py` / `set_location.py` and the bot at the same time** — they
  share one browser profile and will collide.

---

## License

MIT — see [LICENSE](LICENSE). Provided as-is, for personal and educational use.
Respect Facebook's Terms of Service and your local laws.
