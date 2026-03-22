"""
CoDiMux config manager.
Handles first-run detection, settings persistence, and preset storage.

Pointer file: ~/.codimux_path  (stores custom config dir if not default)
Config dir:   ~/.config/codimux/ (default)
Settings:     <config_dir>/settings.json
Presets:      <config_dir>/presets.json
"""

import os
import json
from pathlib import Path

POINTER_FILE = Path.home() / ".codimux_path"
DEFAULT_CONFIG_DIR = Path.home() / ".config" / "codimux"

DEFAULT_SETTINGS = {
    "theme": "system",          # "dark" | "light" | "system"
    "config_dir": str(DEFAULT_CONFIG_DIR),
    "output_dir_name": "encode_output",
    "last_input_dir": str(Path.home()),
}

DEFAULT_PRESETS = {
    "PC": {
        "label": "PC (x265 / Opus)",
        "crf": 22,
        "max_bitrate": "8M",
        "bufsize": "16M",
        "audio_bitrate": "160k",
        "audio_samplerate": 48000,
        "video_codec": "libx265",
        "audio_codec": "libopus",
        "width": 1920,
        "height": 1080,
        "preset": "medium",
        "container": "mkv",
        "smart_copy": True,
    },
    "PS Vita": {
        "label": "PS Vita (x264 / AAC)",
        "requires_hardsub": True,
        "crf": 25,
        "max_bitrate": "4M",
        "bufsize": "8M",
        "audio_bitrate": "128k",
        "audio_samplerate": 48000,
        "video_codec": "libx264",
        "audio_codec": "aac",
        "width": 960,
        "height": 544,
        "preset": "medium",
        "h264_profile": "main",
        "h264_level": "4.1",
        "container": "mp4",
        "smart_copy": False,
        "force_fps": 24,
    },
    "PSP": {
        "label": "PSP (x264 / AAC)",
        "requires_hardsub": True,
        "crf": 26,
        "max_bitrate": "1.5M",
        "bufsize": "3M",
        "audio_bitrate": "128k",
        "audio_samplerate": 44100,
        "video_codec": "libx264",
        "audio_codec": "aac",
        "width": 480,
        "height": 272,
        "preset": "medium",
        "h264_profile": "main",
        "h264_level": "3.0",
        "container": "mp4",
        "smart_copy": False,
        "force_fps": 29.97,
    },
    "Nintendo 3DS": {
        "label": "Nintendo 3DS (x264 / AAC)",
        "requires_hardsub": True,
        "crf": 28,
        "max_bitrate": "1M",
        "bufsize": "2M",
        "audio_bitrate": "128k",
        "audio_samplerate": 32000,
        "video_codec": "libx264",
        "audio_codec": "aac",
        "width": 400,
        "height": 240,
        "preset": "medium",
        "h264_profile": "baseline",
        "h264_level": "3.1",
        "container": "mp4",
        "smart_copy": False,
        "force_fps": 30,
    },
    "Steam Deck": {
        "label": "Steam Deck (x265 / Opus)",
        "crf": 20,
        "max_bitrate": "12M",
        "bufsize": "24M",
        "audio_bitrate": "192k",
        "audio_samplerate": 48000,
        "video_codec": "libx265",
        "audio_codec": "libopus",
        "width": 1280,
        "height": 800,
        "preset": "medium",
        "container": "mkv",
        "smart_copy": True,
    },
    "iOS": {
        "label": "iOS (x264 / AAC)",
        "requires_hardsub": False,
        "crf": 23,
        "max_bitrate": "6M",
        "bufsize": "12M",
        "audio_bitrate": "160k",
        "audio_samplerate": 48000,
        "video_codec": "libx264",
        "audio_codec": "aac",
        "width": 1920,
        "height": 1080,
        "preset": "medium",
        "h264_profile": "high",
        "h264_level": "4.1",
        "container": "mp4",
        "smart_copy": False,
    },
    "Android": {
        "label": "Android (x264 / AAC)",
        "crf": 23,
        "max_bitrate": "6M",
        "bufsize": "12M",
        "audio_bitrate": "160k",
        "audio_samplerate": 48000,
        "video_codec": "libx264",
        "audio_codec": "aac",
        "width": 1920,
        "height": 1080,
        "preset": "medium",
        "h264_profile": "high",
        "h264_level": "4.1",
        "container": "mp4",
        "smart_copy": False,
    },
}


class Config:
    def __init__(self):
        self.config_dir = self._resolve_config_dir()
        self.settings_path = self.config_dir / "settings.json"
        self.presets_path = self.config_dir / "presets.json"
        self.settings = {}
        self.presets = {}

        if self.settings_path.exists():
            self._load()

    def _resolve_config_dir(self) -> Path:
        if POINTER_FILE.exists():
            custom = Path(POINTER_FILE.read_text().strip())
            if custom.exists():
                return custom
        return DEFAULT_CONFIG_DIR

    def is_configured(self) -> bool:
        return self.settings_path.exists()

    def setup(self, theme: str, config_dir: str):
        """Called by the setup wizard to initialise config for the first time."""
        self.config_dir = Path(config_dir)
        self.settings_path = self.config_dir / "settings.json"
        self.presets_path = self.config_dir / "presets.json"

        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Write pointer file if non-default path chosen
        if self.config_dir != DEFAULT_CONFIG_DIR:
            POINTER_FILE.write_text(str(self.config_dir))
        else:
            POINTER_FILE.unlink(missing_ok=True)

        self.settings = {**DEFAULT_SETTINGS, "theme": theme, "config_dir": str(self.config_dir)}
        self.presets = dict(DEFAULT_PRESETS)

        self._save()

    def _load(self):
        try:
            self.settings = json.loads(self.settings_path.read_text())
        except Exception:
            self.settings = dict(DEFAULT_SETTINGS)

        if self.presets_path.exists():
            try:
                loaded = json.loads(self.presets_path.read_text())
                # Merge default keys into loaded presets so new flags (e.g.
                # requires_hardsub) are always present even on old installs
                self.presets = {}
                for name, defaults in DEFAULT_PRESETS.items():
                    if name in loaded:
                        merged = dict(defaults)
                        merged.update(loaded[name])
                        self.presets[name] = merged
                    else:
                        self.presets[name] = dict(defaults)
                # Keep any custom presets the user added
                for name, preset in loaded.items():
                    if name not in self.presets:
                        self.presets[name] = preset
            except Exception:
                self.presets = dict(DEFAULT_PRESETS)
        else:
            self.presets = dict(DEFAULT_PRESETS)
            self._save_presets()

    def _save(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(json.dumps(self.settings, indent=2))
        self._save_presets()

    def _save_presets(self):
        self.presets_path.write_text(json.dumps(self.presets, indent=2))

    def save_settings(self):
        self.settings_path.write_text(json.dumps(self.settings, indent=2))

    def save_preset(self, name: str, preset: dict):
        self.presets[name] = preset
        self._save_presets()

    def delete_preset(self, name: str):
        self.presets.pop(name, None)
        self._save_presets()

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value
        self.save_settings()
