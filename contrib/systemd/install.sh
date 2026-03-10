#!/bin/bash
# Install village systemd timers
set -e

VILLAGE_DIR="${VILLAGE_DIR:-$HOME/source/village}"
SYSTEMD_DIR="$HOME/.config/systemd/user"

# Ensure systemd directory exists
mkdir -p "$SYSTEMD_DIR"

# Copy unit files
cp "$VILLAGE_DIR/contrib/systemd/village-analyze.timer" "$SYSTEMD_DIR/"
cp "$VILLAGE_DIR/contrib/systemd/village-analyze.service" "$SYSTEMD_DIR/"

# Replace placeholder paths
sed -i "s|%h|$HOME|g" "$SYSTEMD_DIR/village-analyze.service"
sed -i "s|WorkingDirectory=.*|WorkingDirectory=$VILLAGE_DIR|g" "$SYSTEMD_DIR/village-analyze.service"

# Enable and start
systemctl --user daemon-reload
systemctl --user enable village-analyze.timer

echo "Village timer installed. Start with: systemctl --user start village-analyze.timer"
echo "Check status with: systemctl --user list-timers"
