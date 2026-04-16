#!/bin/bash
# Install village systemd timers
set -e

VILLAGE_DIR="${VILLAGE_DIR:-$HOME/source/village}"
SYSTEMD_DIR="$HOME/.config/systemd/user"

mkdir -p "$SYSTEMD_DIR"

UNITS=(
    "village-analyze"
    "village-scribe-curate"
)

for unit in "${UNITS[@]}"; do
    if [ -f "$VILLAGE_DIR/contrib/systemd/${unit}.service" ]; then
        cp "$VILLAGE_DIR/contrib/systemd/${unit}.service" "$SYSTEMD_DIR/"
        cp "$VILLAGE_DIR/contrib/systemd/${unit}.timer" "$SYSTEMD_DIR/"
        sed -i "s|%h|$HOME|g" "$SYSTEMD_DIR/${unit}.service"
        sed -i "s|WorkingDirectory=.*|WorkingDirectory=$VILLAGE_DIR|g" "$SYSTEMD_DIR/${unit}.service"
        systemctl --user enable "${unit}.timer"
        echo "Installed: ${unit}"
    else
        echo "Skipping: ${unit} (files not found)"
    fi
done

systemctl --user daemon-reload

echo ""
echo "Village timers installed. Start with:"
echo "  systemctl --user start village-analyze.timer"
echo "  systemctl --user start village-scribe-curate.timer"
echo ""
echo "Check status with: systemctl --user list-timers"
