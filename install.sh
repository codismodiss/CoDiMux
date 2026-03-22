#!/bin/bash
# CoDiMux installer
set -e

echo "=== CoDiMux Installer ==="
echo ""

echo "Checking dependencies..."

if ! command -v ffmpeg &>/dev/null; then
    echo "  ✗ ffmpeg not found"
    echo "    Install with: sudo pacman -S ffmpeg  (or apt install ffmpeg)"
    exit 1
fi
echo "  ✓ ffmpeg"

if ! python3 -c "import gi" &>/dev/null; then
    echo "  ✗ PyGObject not found"
    echo "    Install with: sudo pacman -S python-gobject  (or apt install python3-gi)"
    exit 1
fi
echo "  ✓ PyGObject"

if ! python3 -c "import gi; gi.require_version('Adw','1'); from gi.repository import Adw" &>/dev/null 2>&1; then
    echo "  ✗ libadwaita not found"
    echo "    Install with: sudo pacman -S libadwaita  (or apt install gir1.2-adw-1)"
    exit 1
fi
echo "  ✓ libadwaita"

echo ""
echo "Installing CoDiMux..."

INSTALL_DIR="$HOME/.local/share/codimux"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"

mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"
mkdir -p "$DESKTOP_DIR"

# Copy app files
cp -r codimux/ "$INSTALL_DIR/"
cp codimux.py "$INSTALL_DIR/"

# Install icon if present
ICON_DIR="$HOME/.local/share/icons/hicolor"
if [[ -f "codimux.png" ]]; then
    for size in 16 32 48 64 128 256; do
        mkdir -p "$ICON_DIR/${size}x${size}/apps"
        cp codimux.png "$ICON_DIR/${size}x${size}/apps/codimux.png"
        # also install under the app ID so Wayland picks it up
        cp codimux.png "$ICON_DIR/${size}x${size}/apps/com.codismodiss.codimux.png"
    done
    gtk-update-icon-cache -f -t "$ICON_DIR/" 2>/dev/null || true
    echo "  ✓ Icon installed"
else
    echo "  ⚠ No codimux.png found — using system placeholder icon"
fi

# Create launcher using printf to avoid heredoc issues
printf '#!/bin/bash\nexec python3 "%s/.local/share/codimux/codimux.py" "$@"\n' "$HOME" > "$BIN_DIR/codimux"
chmod +x "$BIN_DIR/codimux"

# Create .desktop entry
printf '[Desktop Entry]\nName=CoDiMux\nComment=ffmpeg GUI\nExec=%s/.local/bin/codimux\nIcon=codimux\nTerminal=false\nType=Application\nCategories=AudioVideo;Video;\n' "$HOME" > "$DESKTOP_DIR/codimux.desktop"

echo "  ✓ Installed to $INSTALL_DIR"
echo "  ✓ Launcher at $BIN_DIR/codimux"
echo "  ✓ Desktop entry created"
echo ""

if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo "  ⚠ $HOME/.local/bin is not in your PATH."
    echo "  Add this to your ~/.bashrc or ~/.zshrc:"
    echo '    export PATH="$HOME/.local/bin:$PATH"'
    echo ""
fi


echo "Install complete. Open CoDiMux in your app launcher or run:"
echo "  python3 ~/.local/share/codimux/codimux.py"
