# CoDiMux
ffmpeg GUI I made because I got tired of writing bash scripts every time I wanted to encode something.
Built with Python + GTK4/libadwaita. Made by codismodiss.

## What it does
- Pick which audio and subtitle tracks to keep
- Soft subs by default, burn in hardsubs if you want
- Smart stream copy - if the video is already x265 and within your target resolution it just copies it instead of re-encoding (saves a ton of time)
- Batch mode - set it up once and let it run through a whole folder unattended
- Recursive folder scanning - point it at a parent folder and it finds all video files in subfolders, outputs each one into its own encode_output folder keeping the structure intact
- Remembers the last folder you opened
- Skip already encoded files toggle - skips files that already have an output in the encode_output folder, turn it off if you want to re-encode
- Presets for PC, PS Vita, PSP, 3DS, Steam Deck, iOS, Android (pre-configured for what those platforms need to play video)
- Preset editor with CRF slider, resolution, codec, bitrate, container
- In-app ffmpeg log so you can see what's actually happening
- First run setup for theme and config path

## Platforms & defaults
| Platform      | Video  | Audio   | Resolution | Container |
|--------------|--------|---------|------------|-----------|
| PC           | x265   | Opus    | 1920x1080  | MKV       |
| PS Vita      | x264   | AAC     | 960x544    | MP4       |
| PSP          | x264   | AAC     | 480x272    | MP4       |
| Nintendo 3DS | x264   | AAC     | 400x240    | MP4       |
| Steam Deck   | x265   | Opus    | 1280x800   | MKV       |
| iOS          | x264   | AAC     | 1920x1080  | MP4       |
| Android      | x264   | AAC     | 1920x1080  | MP4       |

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
Or just run `./uninstall.sh` from the original zip.

## Stack
Python, GTK4, libadwaita, PyGObject. Calls ffmpeg and ffprobe as subprocesses.

## Planned (v0.3)
- Hardware encoding - NVENC (Nvidia), VAAPI (Intel/AMD), AMF (AMD) as options in the preset editor
- Selective recursive scanning - pick which subfolders to include instead of all or none
- Language filter - filter the file list to only show files that have tracks in specific languages (useful for anime libraries with mixed JP/EN releases)
- .deb package + apt repo
- Flatpak
- DE-specific themes
- Guided UI tour on first launch

## Changelog
**v0.2.0**
- Recursive folder scanning
- Remembers last opened folder (toggle in settings)
- Skip already encoded files toggle
- iOS preset
- Fixed Opus encoding with 5.1 surround source audio
- File checkboxes in the sidebar for encoding specific files
- In-app ffmpeg log panel
- Smart Copy vs Always Re-encode option in preset editor
- Softsubs/Hardsubs dropdown per track replacing the burn-in checkbox
- Hardsub auto-select for platforms that require it (Vita, PSP, 3DS)
- Settings window redesigned with clear sections
- uninstall.sh included in the zip

**v0.1.0**
- Initial release
