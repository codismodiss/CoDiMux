# CoDiMux
ffmpeg GUI I made because I got tired of writing bash scripts every time I wanted to encode something.
Built with Python + GTK4/libadwaita. Made by codismodiss.
## What it does
- Pick which audio and subtitle tracks to keep
- Soft subs by default, burn in hardsubs if you want
- Smart stream copy - if the video is already x265 and within your target resolution it just copies it instead of re-encoding (saves a ton of time)
- Batch mode - set it up once and let it run through a whole folder unattended
- Presets for PC, PS Vita, PSP, 3DS, Steam Deck, Android (pre-configured for what those platforms need to play video)
- Preset editor with CRF slider, resolution, codec, bitrate, container
- In-app ffmpeg log so you can see what's actually happening
- First run setup for theme and config path
## Platforms & defaults
| Platform      | Video  | Audio   | Resolution | Container |
|--------------|--------|---------|------------|-----------|
| PC           | x265   | Opus    | 1920×1080  | MKV       |
| PS Vita      | x264   | AAC     | 960×544    | MP4       |
| PSP          | x264   | AAC     | 480×272    | MP4       |
| Nintendo 3DS | x264   | AAC     | 400×240    | MP4       |
| Steam Deck   | x265   | Opus    | 1280×800   | MKV       |
| iOS          | x264   | AAC     | 1920×1080  | MP4       |
| Android      | x264   | AAC     | 1920×1080  | MP4       |

Vita, PSP, and 3DS auto-select hardsubs since those platforms can't render soft subs.
## Requirements
**Arch/Manjaro:**
```bash
sudo pacman -S ffmpeg python-gobject libadwaita
```
**Debian/Ubuntu:**
```bash
sudo apt install ffmpeg python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1
```
## Install
**AUR:**
```bash
yay -S codimux
```
(Or any AUR helper)

**Manual:**
```bash
chmod +x install.sh
./install.sh
```
Find it in your app launcher as CoDiMux, or run:
```bash
python3 ~/.local/share/codimux/codimux.py
```
## Config
Stored at `~/.config/codimux/` by default, changeable on first launch or in settings.
- `settings.json` - theme, paths, preferences
- `presets.json` - all your presets including custom ones
If you move the config folder, a pointer file at `~/.codimux_path` keeps track of where it went.
## Uninstall
```bash
rm -rf ~/.local/share/codimux
rm ~/.local/bin/codimux
rm ~/.local/share/applications/codimux.desktop
rm -rf ~/.config/codimux
rm -f ~/.codimux_path
```
## Stack
Python, GTK4, libadwaita, PyGObject. Calls ffmpeg and ffprobe as subprocesses
---
## Planned (v0.2)
- .deb + apt repo
- Flatpak
- DE-aware theming - detects KDE/GNOME/Hyprland and adapts. KDE will nudge you to install breeze-gtk if it's not already there, with a button that opens the page for it
- Guided UI tour on first launch
