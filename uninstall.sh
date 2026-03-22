#!/bin/bash
# CoDiMux uninstaller

echo "=== CoDiMux Uninstaller ==="
echo ""

read -rp "This will remove CoDiMux and all its files. Continue? [y/N]: " confirm
if [[ ! "$confirm" =~ ^[Yy] ]]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo "Removing CoDiMux..."

rm -rf "$HOME/.local/share/codimux"
echo "  ✓ App files removed"

rm -f "$HOME/.local/bin/codimux"
echo "  ✓ Launcher removed"

rm -f "$HOME/.local/share/applications/codimux.desktop"
echo "  ✓ Desktop entry removed"

# Remove icons
ICON_DIR="$HOME/.local/share/icons/hicolor"
for size in 16 32 48 64 128 256; do
    rm -f "$ICON_DIR/${size}x${size}/apps/codimux.png"
    rm -f "$ICON_DIR/${size}x${size}/apps/com.codismodiss.codimux.png"
done
gtk-update-icon-cache -f -t "$ICON_DIR/" 2>/dev/null || true
echo "  ✓ Icons removed"

# Config — ask before deleting
echo ""
read -rp "Remove config and presets (~/.config/codimux/)? [y/N]: " rmconfig
if [[ "$rmconfig" =~ ^[Yy] ]]; then
    rm -rf "$HOME/.config/codimux"
    rm -f "$HOME/.codimux_path"
    echo "  ✓ Config removed"
else
    echo "  — Config kept at ~/.config/codimux/"
fi

# Refresh KDE if running
if command -v kbuildsycoca6 &>/dev/null; then
    kbuildsycoca6 --noincremental 2>/dev/null || true
fi

echo ""
echo "Done. CoDiMux has been uninstalled."
