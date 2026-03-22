"""
CoDiMux preset editor dialog.
Lets you tweak all encoding settings and save as a named preset.
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GObject


class PresetEditorDialog(Adw.Window):
    __gsignals__ = {
        "preset-saved": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self, parent, preset_name: str, preset: dict, config, is_new=False, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_title("Edit Preset" if not is_new else "New Preset")
        self.set_default_size(520, 680)
        self.config = config
        self.preset = dict(preset)
        self.original_name = preset_name
        self.is_new = is_new

        self._build_ui()

    def _build_ui(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(outer)

        header = Adw.HeaderBar()
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda b: self.close())
        header.pack_start(cancel_btn)

        save_btn = Gtk.Button(label="Save")
        save_btn.set_css_classes(["suggested-action"])
        save_btn.connect("clicked", self._on_save)
        header.pack_end(save_btn)
        outer.append(header)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        outer.append(scroll)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        content.set_margin_top(20)
        content.set_margin_bottom(20)
        content.set_margin_start(20)
        content.set_margin_end(20)
        scroll.set_child(content)

        # ── Name ──────────────────────────────────────────────────────────────
        name_group = Adw.PreferencesGroup()
        name_group.set_title("Preset Name")
        content.append(name_group)

        name_row = Adw.ActionRow()
        name_row.set_title("Name")
        self._name_entry = Gtk.Entry()
        self._name_entry.set_text(self.original_name)
        self._name_entry.set_valign(Gtk.Align.CENTER)
        self._name_entry.set_hexpand(True)
        name_row.add_suffix(self._name_entry)
        name_group.add(name_row)

        # ── Video ─────────────────────────────────────────────────────────────
        video_group = Adw.PreferencesGroup()
        video_group.set_title("Video")
        video_group.set_description("CRF dictates quality vs file size (lower = bigger file, higher quality)")
        content.append(video_group)

        # Video codec
        vcodec_row = Adw.ActionRow()
        vcodec_row.set_title("Video Codec")
        self._vcodec_combo = Gtk.DropDown.new_from_strings(["libx265", "libx264", "libvpx-vp9"])
        codecs = ["libx265", "libx264", "libvpx-vp9"]
        cur_codec = self.preset.get("video_codec", "libx265")
        if cur_codec in codecs:
            self._vcodec_combo.set_selected(codecs.index(cur_codec))
        self._vcodec_combo.set_valign(Gtk.Align.CENTER)
        vcodec_row.add_suffix(self._vcodec_combo)
        video_group.add(vcodec_row)

        # CRF slider
        crf_row = Adw.ActionRow()
        crf_row.set_title("CRF")
        crf_row.set_subtitle("Lower = better quality, larger file")
        crf_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        crf_box.set_valign(Gtk.Align.CENTER)
        self._crf_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 51, 1)
        self._crf_scale.set_value(self.preset.get("crf", 22))
        self._crf_scale.set_size_request(180, -1)
        self._crf_scale.set_draw_value(True)
        self._crf_scale.set_value_pos(Gtk.PositionType.RIGHT)
        crf_box.append(self._crf_scale)
        crf_row.add_suffix(crf_box)
        video_group.add(crf_row)

        # Resolution
        res_row = Adw.ActionRow()
        res_row.set_title("Max Resolution")
        res_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        res_box.set_valign(Gtk.Align.CENTER)
        self._width_spin = Gtk.SpinButton.new_with_range(64, 7680, 2)
        self._width_spin.set_value(self.preset.get("width", 1920))
        self._width_spin.set_size_request(90, -1)
        x_label = Gtk.Label(label="×")
        self._height_spin = Gtk.SpinButton.new_with_range(64, 4320, 2)
        self._height_spin.set_value(self.preset.get("height", 1080))
        self._height_spin.set_size_request(90, -1)
        res_box.append(self._width_spin)
        res_box.append(x_label)
        res_box.append(self._height_spin)
        res_row.add_suffix(res_box)
        video_group.add(res_row)

        # Preset speed
        speed_row = Adw.ActionRow()
        speed_row.set_title("Encode Speed")
        speed_row.set_subtitle("Slower = better compression")
        speeds = ["ultrafast", "superfast", "veryfast", "faster", "fast",
                  "medium", "slow", "slower", "veryslow"]
        self._speed_combo = Gtk.DropDown.new_from_strings(speeds)
        cur_speed = self.preset.get("preset", "medium")
        if cur_speed in speeds:
            self._speed_combo.set_selected(speeds.index(cur_speed))
        self._speed_combo.set_valign(Gtk.Align.CENTER)
        speed_row.add_suffix(self._speed_combo)
        video_group.add(speed_row)

        # Max bitrate
        bitrate_row = Adw.ActionRow()
        bitrate_row.set_title("Max Bitrate")
        self._bitrate_entry = Gtk.Entry()
        self._bitrate_entry.set_text(self.preset.get("max_bitrate", "8M"))
        self._bitrate_entry.set_valign(Gtk.Align.CENTER)
        self._bitrate_entry.set_max_width_chars(8)
        bitrate_row.add_suffix(self._bitrate_entry)
        video_group.add(bitrate_row)

        # Container
        container_row = Adw.ActionRow()
        container_row.set_title("Container")
        containers = ["mkv", "mp4"]
        self._container_combo = Gtk.DropDown.new_from_strings(containers)
        cur_container = self.preset.get("container", "mkv")
        if cur_container in containers:
            self._container_combo.set_selected(containers.index(cur_container))
        self._container_combo.set_valign(Gtk.Align.CENTER)
        container_row.add_suffix(self._container_combo)
        video_group.add(container_row)

        # Video mode
        mode_row = Adw.ActionRow()
        mode_row.set_title("Video Mode")
        mode_row.set_subtitle(
            "Smart Copy skips re-encoding if the source codec already matches the output. "
            "Always Re-encode uses CRF to encode the video regardless of current codec "
            "(e.g x265 CRF 18 source \u2192 x265 CRF 22 output)"
        )
        video_modes = ["Smart Copy", "Always Re-encode"]
        self._video_mode_combo = Gtk.DropDown.new_from_strings(video_modes)
        cur_mode = 0 if self.preset.get("smart_copy", False) else 1
        self._video_mode_combo.set_selected(cur_mode)
        self._video_mode_combo.set_valign(Gtk.Align.CENTER)
        mode_row.add_suffix(self._video_mode_combo)
        video_group.add(mode_row)

        # ── Audio ─────────────────────────────────────────────────────────────
        audio_group = Adw.PreferencesGroup()
        audio_group.set_title("Audio")
        content.append(audio_group)

        acodec_row = Adw.ActionRow()
        acodec_row.set_title("Audio Codec")
        acodecs = ["libopus", "aac", "libvorbis", "mp3"]
        self._acodec_combo = Gtk.DropDown.new_from_strings(acodecs)
        cur_acodec = self.preset.get("audio_codec", "libopus")
        if cur_acodec in acodecs:
            self._acodec_combo.set_selected(acodecs.index(cur_acodec))
        self._acodec_combo.set_valign(Gtk.Align.CENTER)
        acodec_row.add_suffix(self._acodec_combo)
        audio_group.add(acodec_row)

        abitrate_row = Adw.ActionRow()
        abitrate_row.set_title("Audio Bitrate")
        self._abitrate_entry = Gtk.Entry()
        self._abitrate_entry.set_text(self.preset.get("audio_bitrate", "160k"))
        self._abitrate_entry.set_valign(Gtk.Align.CENTER)
        self._abitrate_entry.set_max_width_chars(8)
        abitrate_row.add_suffix(self._abitrate_entry)
        audio_group.add(abitrate_row)

        samplerate_row = Adw.ActionRow()
        samplerate_row.set_title("Sample Rate")
        samplerates = ["22050", "32000", "44100", "48000"]
        self._samplerate_combo = Gtk.DropDown.new_from_strings(samplerates)
        cur_sr = str(self.preset.get("audio_samplerate", 48000))
        if cur_sr in samplerates:
            self._samplerate_combo.set_selected(samplerates.index(cur_sr))
        self._samplerate_combo.set_valign(Gtk.Align.CENTER)
        samplerate_row.add_suffix(self._samplerate_combo)
        audio_group.add(samplerate_row)

        # ── Delete preset ─────────────────────────────────────────────────────
        if not self.is_new:
            danger_group = Adw.PreferencesGroup()
            content.append(danger_group)
            del_btn = Gtk.Button(label="Delete Preset")
            del_btn.set_css_classes(["destructive-action"])
            del_btn.connect("clicked", self._on_delete)
            danger_group.add(del_btn)

    def _on_save(self, btn):
        name = self._name_entry.get_text().strip()
        if not name:
            return

        codecs = ["libx265", "libx264", "libvpx-vp9"]
        acodecs = ["libopus", "aac", "libvorbis", "mp3"]
        containers = ["mkv", "mp4"]
        speeds = ["ultrafast", "superfast", "veryfast", "faster", "fast",
                  "medium", "slow", "slower", "veryslow"]
        samplerates = [22050, 32000, 44100, 48000]

        self.preset.update({
            "label": name,
            "video_codec": codecs[self._vcodec_combo.get_selected()],
            "crf": int(self._crf_scale.get_value()),
            "width": int(self._width_spin.get_value()),
            "height": int(self._height_spin.get_value()),
            "preset": speeds[self._speed_combo.get_selected()],
            "max_bitrate": self._bitrate_entry.get_text().strip(),
            "bufsize": self._bitrate_entry.get_text().strip().replace("M", "") + "M",
            "container": containers[self._container_combo.get_selected()],
            "smart_copy": self._video_mode_combo.get_selected() == 0,
            "audio_codec": acodecs[self._acodec_combo.get_selected()],
            "audio_bitrate": self._abitrate_entry.get_text().strip(),
            "audio_samplerate": samplerates[self._samplerate_combo.get_selected()],
        })

        # If renamed, delete old key
        if not self.is_new and self.original_name != name:
            self.config.delete_preset(self.original_name)

        self.config.save_preset(name, self.preset)
        self.emit("preset-saved", name)
        self.close()

    def _on_delete(self, btn):
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Delete Preset?",
            body=f'"{self.original_name}" will be permanently deleted.',
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self._on_delete_confirmed)
        dialog.present()

    def _on_delete_confirmed(self, dialog, response):
        if response == "delete":
            self.config.delete_preset(self.original_name)
            self.emit("preset-saved", "")
            self.close()
