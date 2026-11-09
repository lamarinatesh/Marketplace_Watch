#!/usr/bin/env bash
# Generate + load the launchd agent for THIS checkout — no hard-coded usernames.
# The plist is written for wherever you cloned the repo and whoever you are.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$DIR/.venv/bin/python"
LABEL="com.marketplacewatcher.bot"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
UID_NUM="$(id -u)"

if [ ! -x "$PY" ]; then
  echo "No virtualenv found at $PY" >&2
  echo "Run the install steps in the README first (python3 -m venv .venv ...)." >&2
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PY</string>
        <string>$DIR/bot.py</string>
    </array>
    <key>WorkingDirectory</key><string>$DIR</string>
    <key>StartInterval</key><integer>1800</integer>
    <key>RunAtLoad</key><true/>
    <key>StandardOutPath</key><string>$DIR/bot.log</string>
    <key>StandardErrorPath</key><string>$DIR/bot.log</string>
</dict>
</plist>
PLIST_EOF

# Reload cleanly (and clear any previous "disabled" override).
launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null || true
launchctl enable "gui/$UID_NUM/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$UID_NUM" "$PLIST"

echo "Loaded $LABEL — scans every 30 min. Logs: $DIR/bot.log"
