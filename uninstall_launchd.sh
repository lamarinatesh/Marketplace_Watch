#!/usr/bin/env bash
# Stop the scheduler and keep it stopped across logins/reboots.
set -euo pipefail

LABEL="com.marketplacewatcher.bot"
UID_NUM="$(id -u)"

launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null || true
launchctl disable "gui/$UID_NUM/$LABEL" 2>/dev/null || true

echo "Stopped and disabled $LABEL. Re-enable with ./install_launchd.sh"
