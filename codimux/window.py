"""
CoDiMux main window.
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk, GLib, Gio, Pango
from pathlib import Path

from codimux.config import Config
from codimux.probe import probe, ProbeResult, AudioStream, SubtitleStream
from codimux.encoder import EncodeJob
from codimux.preset_editor import PresetEditorDialog


class CoDiMuxWindow(Adw.ApplicationWindow):
    def __init__(self, config: Config, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.set_title("CoDiMux")
        self.set_default_size(960, 780)

        # CSS provider reference — kept so we can replace it on theme change
        self._css_provider = None

        self._apply_theme()

        # State
        self._input_dir: str = config.get("last_input_dir", str(Path.home()))
        self._video_files: list[str] = []
        self._probe_cache: dict[str, ProbeResult] = {}
        self._selected_preset_key: str = list(config.presets.keys())[0] if config.presets else "PC"
        self._audio_indices: list[int] = []
        self._sub_indices: list[int] = []
        self._hardsub_index: int | None = None
        self._current_job: EncodeJob | None = None
        self._queue: list[str] = []
        self._queue_index = 0
        self._batch_mode = False
        self._log_lines: list[str] = []

        self._build_ui()

    # ── Theme ─────────────────────────────────────────────────────────────────
    def _apply_theme(self):
        theme = self.config.get("theme", "system")
        manager = Adw.StyleManager.get_default()
        scheme_map = {
            "dark":   Adw.ColorScheme.FORCE_DARK,
            "light":  Adw.ColorScheme.FORCE_LIGHT,
            "system": Adw.ColorScheme.DEFAULT,
        }
        manager.set_color_scheme(scheme_map.get(theme, Adw.ColorScheme.DEFAULT))
        self._apply_custom_css(theme)

    def _apply_custom_css(self, theme: str):
        display = Gdk.Display.get_default()
        if display is None:
            return

        # Remove old provider first to avoid stacking
        if self._css_provider is not None:
            Gtk.StyleContext.remove_provider_for_display(display, self._css_provider)
            self._css_provider = None

        if theme == "light":
            css = b"""
            window, .view, scrolledwindow > viewport {
                background-color: #f0eeec;
            }
            .navigation-sidebar {
                background-color: #e8e6e4;
            }
            headerbar {
                background-color: #e4e2e0;
            }
            """
        else:
            return  # dark/system look fine as-is, no custom CSS needed

        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_display(
            display,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        self._css_provider = provider

    # ── UI build ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(outer)

        # Header bar
        header = Adw.HeaderBar()
        header.set_centering_policy(Adw.CenteringPolicy.STRICT)
        title = Adw.WindowTitle()
        title.set_title("CoDiMux")

        header.set_title_widget(title)

        settings_btn = Gtk.Button()
        settings_btn.set_icon_name("preferences-system-symbolic")
        settings_btn.set_tooltip_text("Settings")
        settings_btn.connect("clicked", self._on_settings)
        header.pack_end(settings_btn)
        outer.append(header)

        # Main paned
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_vexpand(True)
        outer.append(paned)

        # ── LEFT: file list ───────────────────────────────────────────────────
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        left.set_size_request(280, -1)

        left_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        left_header.set_margin_top(12)
        left_header.set_margin_bottom(8)
        left_header.set_margin_start(12)
        left_header.set_margin_end(12)

        folder_label = Gtk.Label(label="<b>Input Files</b>")
        folder_label.set_use_markup(True)
        folder_label.set_hexpand(True)
        folder_label.set_halign(Gtk.Align.START)
        left_header.append(folder_label)

        open_btn = Gtk.Button()
        open_btn.set_icon_name("folder-open-symbolic")
        open_btn.set_tooltip_text("Open Folder")
        open_btn.set_css_classes(["flat"])
        open_btn.connect("clicked", self._on_open_folder)
        left_header.append(open_btn)
        left.append(left_header)
        left.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        self._file_store = Gtk.StringList()
        self._file_selection = Gtk.SingleSelection(model=self._file_store)
        self._file_selection.connect("notify::selected", self._on_file_selected)
        self._file_checked: list[bool] = []  # tracks checkbox state per file

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._file_item_setup)
        factory.connect("bind", self._file_item_bind)

        file_list = Gtk.ListView(model=self._file_selection, factory=factory)
        file_list.set_css_classes(["navigation-sidebar"])

        list_scroll = Gtk.ScrolledWindow()
        list_scroll.set_vexpand(True)
        list_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        list_scroll.set_child(file_list)
        left.append(list_scroll)

        # Select all / none buttons
        sel_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        sel_box.set_margin_start(8)
        sel_box.set_margin_end(8)
        sel_box.set_margin_top(6)
        sel_box.set_margin_bottom(6)
        sel_all_btn = Gtk.Button(label="All")
        sel_all_btn.set_css_classes(["flat", "caption"])
        sel_all_btn.set_hexpand(True)
        sel_all_btn.connect("clicked", self._on_select_all)
        sel_none_btn = Gtk.Button(label="None")
        sel_none_btn.set_css_classes(["flat", "caption"])
        sel_none_btn.set_hexpand(True)
        sel_none_btn.connect("clicked", self._on_select_none)
        sel_box.append(sel_all_btn)
        sel_box.append(sel_none_btn)
        left.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        left.append(sel_box)
        paned.set_start_child(left)
        paned.set_shrink_start_child(False)

        # ── RIGHT: controls ───────────────────────────────────────────────────
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        right.set_hexpand(True)
        paned.set_end_child(right)
        paned.set_shrink_end_child(False)

        right_scroll = Gtk.ScrolledWindow()
        right_scroll.set_vexpand(True)
        right_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        right.append(right_scroll)

        right_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        right_content.set_margin_top(20)
        right_content.set_margin_bottom(20)
        right_content.set_margin_start(20)
        right_content.set_margin_end(20)
        right_scroll.set_child(right_content)

        # Preset
        preset_group = Adw.PreferencesGroup()
        preset_group.set_title("Encoding Preset")
        right_content.append(preset_group)

        preset_row = Adw.ActionRow()
        preset_row.set_title("Target Platform")
        self._preset_combo = Gtk.DropDown()
        self._refresh_preset_combo()
        self._preset_combo.set_valign(Gtk.Align.CENTER)
        self._preset_combo.connect("notify::selected", self._on_preset_changed)
        preset_row.add_suffix(self._preset_combo)

        edit_preset_btn = Gtk.Button(label="Edit")
        edit_preset_btn.set_valign(Gtk.Align.CENTER)
        edit_preset_btn.set_css_classes(["flat"])
        edit_preset_btn.connect("clicked", self._on_edit_preset)
        preset_row.add_suffix(edit_preset_btn)

        new_preset_btn = Gtk.Button()
        new_preset_btn.set_icon_name("list-add-symbolic")
        new_preset_btn.set_tooltip_text("New Preset")
        new_preset_btn.set_valign(Gtk.Align.CENTER)
        new_preset_btn.set_css_classes(["flat"])
        new_preset_btn.connect("clicked", self._on_new_preset)
        preset_row.add_suffix(new_preset_btn)
        preset_group.add(preset_row)

        self._preset_summary = Adw.ActionRow()
        self._preset_summary.set_title("Settings")
        self._preset_summary.set_subtitle(self._format_preset_summary())
        preset_group.add(self._preset_summary)

        # Stream info
        self._stream_group = Adw.PreferencesGroup()
        self._stream_group.set_title("Stream Info")
        self._stream_group.set_description("Select a file to see its streams")
        right_content.append(self._stream_group)

        self._video_row = Adw.ActionRow()
        self._video_row.set_title("Video")
        self._video_row.set_subtitle("—")
        self._stream_group.add(self._video_row)

        # Audio tracks
        self._audio_group = Adw.PreferencesGroup()
        self._audio_group.set_title("Audio Tracks")
        self._audio_group.set_description("Select tracks to keep")
        right_content.append(self._audio_group)
        self._audio_rows: list[tuple] = []

        # Subtitle tracks
        self._sub_group = Adw.PreferencesGroup()
        self._sub_group.set_title("Subtitle Tracks")
        self._sub_group.set_description(
            "Select tracks to keep. Use the dropdown to copy over softsubs or burn hardsubs."
        )
        right_content.append(self._sub_group)

        # Warning row — shown above track list for platforms needing hardsubs
        self._hardsub_warning_row = Adw.ActionRow()
        self._hardsub_warning_row.set_title(
            "⚠ Selected platform requires hardsubs to display subtitles"
        )
        self._hardsub_warning_row.set_css_classes(["error"])
        self._hardsub_warning_row.set_visible(False)
        self._sub_group.add(self._hardsub_warning_row)

        self._sub_rows: list[tuple] = []  # (row, keep_check, mode_dropdown)

        # Output options
        output_group = Adw.PreferencesGroup()
        output_group.set_title("Output")
        right_content.append(output_group)

        self._output_dir_row = Adw.ActionRow()
        self._output_dir_row.set_title("Output Folder")
        self._output_dir_row.set_subtitle(
            self.config.get("output_dir_name", "encode_output") + "/ (next to input)"
        )
        change_out_btn = Gtk.Button(label="Change")
        change_out_btn.set_valign(Gtk.Align.CENTER)
        change_out_btn.set_css_classes(["flat"])
        change_out_btn.connect("clicked", self._on_change_output_dir)
        self._output_dir_row.add_suffix(change_out_btn)
        output_group.add(self._output_dir_row)

        batch_row = Adw.ActionRow()
        batch_row.set_title("Batch Mode")
        batch_row.set_subtitle("Apply current track choices to all files without prompting")
        self._batch_switch = Gtk.Switch()
        self._batch_switch.set_valign(Gtk.Align.CENTER)
        self._batch_switch.connect("notify::active", self._on_batch_toggled)
        batch_row.add_suffix(self._batch_switch)
        output_group.add(batch_row)

        # Progress
        self._progress_group = Adw.PreferencesGroup()
        self._progress_group.set_title("Progress")
        right_content.append(self._progress_group)

        self._progress_bar = Gtk.ProgressBar()
        self._progress_bar.set_show_text(True)
        self._progress_bar.set_text("Idle")
        self._progress_bar.set_margin_top(4)
        self._progress_bar.set_margin_bottom(4)
        self._progress_group.add(self._progress_bar)

        self._status_label = Gtk.Label(label="")
        self._status_label.set_css_classes(["dim-label", "caption"])
        self._status_label.set_halign(Gtk.Align.START)
        self._progress_group.add(self._status_label)

        # Log toggle row
        log_toggle_row = Adw.ActionRow()
        log_toggle_row.set_title("ffmpeg Log")
        log_toggle_row.set_subtitle("Raw encoder output")

        log_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        log_btn_box.set_valign(Gtk.Align.CENTER)

        self._log_toggle_btn = Gtk.ToggleButton(label="Show Log")
        self._log_toggle_btn.set_css_classes(["flat"])
        self._log_toggle_btn.connect("toggled", self._on_log_toggled)
        log_btn_box.append(self._log_toggle_btn)

        self._copy_log_btn = Gtk.Button(label="Copy")
        self._copy_log_btn.set_css_classes(["flat"])
        self._copy_log_btn.set_tooltip_text("Copy log to clipboard")
        self._copy_log_btn.connect("clicked", self._on_copy_log)
        log_btn_box.append(self._copy_log_btn)

        log_toggle_row.add_suffix(log_btn_box)
        self._progress_group.add(log_toggle_row)

        # Log panel — hidden by default
        self._log_revealer = Gtk.Revealer()
        self._log_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self._log_revealer.set_transition_duration(200)
        self._log_revealer.set_reveal_child(False)

        log_frame = Gtk.Frame()
        log_frame.set_margin_top(4)
        log_frame.set_margin_bottom(4)

        log_scroll = Gtk.ScrolledWindow()
        log_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        log_scroll.set_min_content_height(180)
        log_scroll.set_max_content_height(300)

        self._log_view = Gtk.TextView()
        self._log_view.set_editable(False)
        self._log_view.set_cursor_visible(False)
        self._log_view.set_monospace(True)
        self._log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._log_view.set_margin_start(8)
        self._log_view.set_margin_end(8)
        self._log_view.set_margin_top(6)
        self._log_view.set_margin_bottom(6)
        self._log_buffer = self._log_view.get_buffer()

        log_scroll.set_child(self._log_view)
        log_frame.set_child(log_scroll)
        self._log_revealer.set_child(log_frame)
        self._progress_group.add(self._log_revealer)

        # Bottom encode bar
        bottom_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        bottom_bar.set_margin_top(12)
        bottom_bar.set_margin_bottom(12)
        bottom_bar.set_margin_start(20)
        bottom_bar.set_margin_end(20)

        self._encode_all_btn = Gtk.Button(label="Encode All")
        self._encode_all_btn.set_css_classes(["suggested-action", "pill"])
        self._encode_all_btn.set_hexpand(True)
        self._encode_all_btn.set_sensitive(False)
        self._encode_all_btn.connect("clicked", self._on_encode_all)
        bottom_bar.append(self._encode_all_btn)

        self._encode_selected_btn = Gtk.Button(label="Encode Selected")
        self._encode_selected_btn.set_css_classes(["pill"])
        self._encode_selected_btn.set_sensitive(False)
        self._encode_selected_btn.connect("clicked", self._on_encode_selected)
        bottom_bar.append(self._encode_selected_btn)

        self._cancel_btn = Gtk.Button(label="Cancel")
        self._cancel_btn.set_css_classes(["destructive-action", "pill"])
        self._cancel_btn.set_sensitive(False)
        self._cancel_btn.connect("clicked", self._on_cancel)
        bottom_bar.append(self._cancel_btn)

        right.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        right.append(bottom_bar)

    # ── File list factory ─────────────────────────────────────────────────────
    def _file_item_setup(self, factory, item):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row.set_margin_top(6)
        row.set_margin_bottom(6)
        row.set_margin_start(8)
        row.set_margin_end(8)
        check = Gtk.CheckButton()
        check.set_valign(Gtk.Align.CENTER)
        label = Gtk.Label()
        label.set_halign(Gtk.Align.START)
        label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        label.set_max_width_chars(24)
        label.set_hexpand(True)
        row.append(check)
        row.append(label)
        item.set_child(row)

    def _file_item_bind(self, factory, item):
        row = item.get_child()
        check = row.get_first_child()
        label = check.get_next_sibling()
        idx = item.get_position()
        label.set_text(item.get_item().get_string())
        # Set checkbox state from our tracked list
        if idx < len(self._file_checked):
            check.set_active(self._file_checked[idx])
        else:
            check.set_active(True)
        # Reconnect signal — unbind old one first if any
        try:
            check.disconnect_by_func(self._on_file_check_toggled)
        except Exception:
            pass
        check.connect("toggled", self._on_file_check_toggled, idx)

    # ── Folder open ───────────────────────────────────────────────────────────
    def _on_open_folder(self, btn):
        dialog = Gtk.FileDialog()
        dialog.set_title("Open Video Folder")
        dialog.select_folder(self, None, self._on_folder_chosen)

    def _on_folder_chosen(self, dialog, result):
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                self._input_dir = folder.get_path()
                self.config.set("last_input_dir", self._input_dir)
                self._scan_folder()
        except Exception:
            pass

    def _scan_folder(self):
        exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv",
                ".webm", ".m4v", ".ts", ".mpg", ".mpeg", ".3gp"}
        self._video_files = []
        self._file_checked = []
        new_store = Gtk.StringList()
        for f in sorted(Path(self._input_dir).iterdir()):
            if f.is_file() and f.suffix.lower() in exts:
                self._video_files.append(str(f))
                self._file_checked.append(False)
                new_store.append(f.name)
        self._file_store = new_store
        self._file_selection.set_model(new_store)
        has_files = len(self._video_files) > 0
        self._encode_all_btn.set_sensitive(has_files)
        if has_files:
            self._file_selection.set_selected(0)

    # ── File selection ────────────────────────────────────────────────────────
    def _on_file_selected(self, selection, *args):
        idx = selection.get_selected()
        if idx >= len(self._video_files):
            return
        self._encode_selected_btn.set_sensitive(True)
        self._probe_file(self._video_files[idx])

    def _on_file_check_toggled(self, check, idx):
        if idx < len(self._file_checked):
            self._file_checked[idx] = check.get_active()

    def _on_select_all(self, btn):
        self._file_checked = [True] * len(self._video_files)
        self._file_selection.set_model(self._file_store)  # force rebind

    def _on_select_none(self, btn):
        self._file_checked = [False] * len(self._video_files)
        self._file_selection.set_model(self._file_store)  # force rebind

    def _probe_file(self, filepath: str):
        if filepath in self._probe_cache:
            self._update_stream_ui(self._probe_cache[filepath])
            return
        self._video_row.set_subtitle("Probing…")
        self._status_label.set_text(f"Probing {Path(filepath).name}…")
        import threading
        def _do():
            result = probe(filepath)
            self._probe_cache[filepath] = result
            GLib.idle_add(self._update_stream_ui, result)
        threading.Thread(target=_do, daemon=True).start()

    def _update_stream_ui(self, result: ProbeResult):
        self._status_label.set_text("")
        preset = self.config.presets.get(self._selected_preset_key, {})

        # Video row
        if result.video:
            v = result.video
            will_copy = (
                preset.get("smart_copy") and v.codec == "hevc" and
                v.width <= preset.get("width", 1920) and
                v.height <= preset.get("height", 1080)
            )
            action = "stream copy" if will_copy else f"→ {preset.get('video_codec', 'encode')}"
            self._video_row.set_subtitle(
                f"{v.codec.upper()} {v.width}×{v.height} @ {v.fps}fps  [{action}]"
            )
        else:
            self._video_row.set_subtitle("No video stream found")

        # Clear audio rows
        for row, _ in self._audio_rows:
            self._audio_group.remove(row)
        self._audio_rows.clear()
        self._audio_indices = []

        for track in result.audio:
            row = Adw.ActionRow()
            row.set_title(track.display())
            will_copy = preset.get("smart_copy") and track.codec == "opus"
            action_label = Gtk.Label(
                label="copy" if will_copy else f"→ {preset.get('audio_codec', 'encode')}"
            )
            action_label.set_css_classes(["dim-label", "caption"])
            action_label.set_valign(Gtk.Align.CENTER)
            row.add_suffix(action_label)
            check = Gtk.CheckButton()
            check.set_active(True)
            check.set_valign(Gtk.Align.CENTER)
            row.add_prefix(check)
            row.set_activatable_widget(check)
            self._audio_group.add(row)
            self._audio_rows.append((row, check))
            self._audio_indices.append(track.index)

        # Clear subtitle rows
        for row, _, _ in self._sub_rows:
            self._sub_group.remove(row)
        self._sub_rows.clear()
        self._sub_indices = []
        self._hardsub_index = None

        for track in result.subtitles:
            row = Adw.ActionRow()
            row.set_title(track.display())

            keep_check = Gtk.CheckButton()
            keep_check.set_active(True)
            keep_check.set_valign(Gtk.Align.CENTER)
            row.add_prefix(keep_check)
            row.set_activatable_widget(keep_check)

            # Softsubs / Hardsubs dropdown — all sub types can be burned in
            # Text subs use subtitles filter, PGS uses overlay filter
            mode_combo = Gtk.DropDown.new_from_strings(["Softsubs", "Hardsubs"])
            mode_combo.set_valign(Gtk.Align.CENTER)
            mode_combo.connect("notify::selected", self._on_sub_mode_changed, track.index)
            row.add_suffix(mode_combo)

            keep_check.connect("toggled", self._on_keep_sub_toggled, mode_combo)

            self._sub_group.add(row)
            self._sub_rows.append((row, keep_check, mode_combo))
            self._sub_indices.append(track.index)

        # Apply hardsub warning/auto-select after rows are built
        self._update_hardsub_warning()

    # ── Hardsub warning + mode handling ──────────────────────────────────────
    def _update_hardsub_warning(self):
        preset = self.config.presets.get(self._selected_preset_key, {})
        requires = preset.get("requires_hardsub", False)

        if requires and self._sub_rows:
            self._hardsub_warning_row.set_visible(True)
            # Auto-select "Hardsubs" on the first checked sub track
            first_set = False
            for i, (_, keep_check, mode_combo) in enumerate(self._sub_rows):
                if keep_check.get_active():
                    if not first_set:
                        mode_combo.handler_block_by_func(self._on_sub_mode_changed)
                        mode_combo.set_selected(1)  # Hardsubs
                        mode_combo.handler_unblock_by_func(self._on_sub_mode_changed)
                        self._hardsub_index = self._sub_indices[i]
                        first_set = True
                    # Leave subsequent subs on Softsubs
        else:
            self._hardsub_warning_row.set_visible(False)
            self._hardsub_index = None

    def _on_sub_mode_changed(self, combo, _, track_index):
        selected = combo.get_selected()
        if selected == 1:  # Burn In
            # Only one track can be burned in — reset others to Soft
            for i, (_, _, mc) in enumerate(self._sub_rows):
                if mc is not combo:
                    mc.set_selected(0)
            self._hardsub_index = track_index
        else:
            if self._hardsub_index == track_index:
                self._hardsub_index = None

    def _on_keep_sub_toggled(self, check, mode_combo):
        if not check.get_active():
            # Deselecting track — if it was the hardsub, clear that
            idx = next(
                (self._sub_indices[i] for i, (_, kc, mc) in enumerate(self._sub_rows)
                 if mc is mode_combo),
                None
            )
            if idx == self._hardsub_index:
                self._hardsub_index = None
                mode_combo.set_selected(0)
            mode_combo.set_sensitive(False)
        else:
            mode_combo.set_sensitive(True)

    # ── Preset ────────────────────────────────────────────────────────────────
    def _refresh_preset_combo(self):
        keys = list(self.config.presets.keys())
        self._preset_combo.set_model(Gtk.StringList.new(keys))
        if self._selected_preset_key in keys:
            self._preset_combo.set_selected(keys.index(self._selected_preset_key))

    def _on_preset_changed(self, combo, _):
        keys = list(self.config.presets.keys())
        idx = combo.get_selected()
        if idx < len(keys):
            self._selected_preset_key = keys[idx]
            self._preset_summary.set_subtitle(self._format_preset_summary())
            self._update_hardsub_warning()
            sel = self._file_selection.get_selected()
            if sel < len(self._video_files):
                self._probe_file(self._video_files[sel])

    def _format_preset_summary(self) -> str:
        p = self.config.presets.get(self._selected_preset_key, {})
        if not p:
            return "—"
        parts = [
            f"CRF {p.get('crf', '?')}",
            f"{p.get('video_codec', '?')}",
            f"{p.get('audio_codec', '?')} {p.get('audio_bitrate', '?')}",
            f"{p.get('width', '?')}×{p.get('height', '?')}",
            f".{p.get('container', '?')}",
        ]
        if p.get("smart_copy"):
            parts.append("smart copy ✓")
        return "  |  ".join(parts)

    def _on_edit_preset(self, btn):
        preset = self.config.presets.get(self._selected_preset_key, {})
        dialog = PresetEditorDialog(
            parent=self,
            preset_name=self._selected_preset_key,
            preset=dict(preset),
            config=self.config,
        )
        dialog.connect("preset-saved", self._on_preset_saved)
        dialog.present()

    def _on_new_preset(self, btn):
        from codimux.config import DEFAULT_PRESETS
        dialog = PresetEditorDialog(
            parent=self,
            preset_name="",
            preset=dict(list(DEFAULT_PRESETS.values())[0]),
            config=self.config,
            is_new=True,
        )
        dialog.connect("preset-saved", self._on_preset_saved)
        dialog.present()

    def _on_preset_saved(self, dialog, name):
        self._selected_preset_key = name
        self._refresh_preset_combo()
        self._preset_summary.set_subtitle(self._format_preset_summary())

    # ── Output dir ────────────────────────────────────────────────────────────
    def _on_change_output_dir(self, btn):
        dialog = Gtk.FileDialog()
        dialog.set_title("Choose Output Subfolder Name")
        dialog.select_folder(self, None, self._on_output_dir_chosen)

    def _on_output_dir_chosen(self, dialog, result):
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                name = Path(folder.get_path()).name
                self.config.set("output_dir_name", name)
                self._output_dir_row.set_subtitle(f"{name}/ (next to input)")
        except Exception:
            pass

    # ── Batch mode ────────────────────────────────────────────────────────────
    def _on_batch_toggled(self, switch, _):
        self._batch_mode = switch.get_active()

    # ── Encoding ─────────────────────────────────────────────────────────────
    def _get_selected_audio_indices(self) -> list[int]:
        return [
            self._audio_indices[i]
            for i, (_, check) in enumerate(self._audio_rows)
            if check.get_active() and i < len(self._audio_indices)
        ]

    def _get_selected_sub_indices(self) -> list[int]:
        return [
            self._sub_indices[i]
            for i, (_, check, _) in enumerate(self._sub_rows)
            if check.get_active() and i < len(self._sub_indices)
        ]

    def _get_hardsub_index(self):
        for i, (_, check, mode_combo) in enumerate(self._sub_rows):
            if check.get_active() and mode_combo.get_selected() == 1:
                return self._sub_indices[i]
        return None

    def _on_encode_selected(self, btn):
        # Encode only checked files
        checked = [f for i, f in enumerate(self._video_files)
                   if i < len(self._file_checked) and self._file_checked[i]]
        if checked:
            self._start_queue(checked)

    def _on_encode_all(self, btn):
        # Always encodes every file regardless of checkbox state
        self._start_queue(list(self._video_files))

    def _start_queue(self, files: list[str]):
        self._queue = files
        self._queue_index = 0
        self._clear_log()
        self._encode_all_btn.set_sensitive(False)
        self._encode_selected_btn.set_sensitive(False)
        self._cancel_btn.set_sensitive(True)
        self._encode_next()

    def _encode_next(self):
        if self._queue_index >= len(self._queue):
            self._on_queue_complete()
            return

        filepath = self._queue[self._queue_index]
        filename = Path(filepath).name
        self._status_label.set_text(f"[{self._queue_index+1}/{len(self._queue)}] {filename}")
        self._progress_bar.set_text(f"Encoding {filename}…")
        self._progress_bar.set_fraction(0)

        if filepath not in self._probe_cache:
            self._probe_cache[filepath] = probe(filepath)
        probe_result = self._probe_cache[filepath]

        preset = self.config.presets.get(self._selected_preset_key, {})
        output_dir_name = self.config.get("output_dir_name", "encode_output")
        output_dir = Path(filepath).parent / output_dir_name
        output_dir.mkdir(parents=True, exist_ok=True)

        container = preset.get("container", "mkv")
        output_path = str(output_dir / f"{Path(filepath).stem}.{container}")

        if Path(output_path).exists():
            self._status_label.set_text(f"Skipping (exists): {filename}")
            self._queue_index += 1
            GLib.timeout_add(300, self._encode_next)
            return

        if self._batch_mode and self._queue_index > 0:
            audio_indices = self._audio_indices
            sub_indices = self._sub_indices
        else:
            audio_indices = self._get_selected_audio_indices()
            sub_indices = self._get_selected_sub_indices()
            if self._batch_mode and self._queue_index == 0:
                self._audio_indices = audio_indices
                self._sub_indices = sub_indices

        # Fallback: if no audio tracks were selected (e.g. file wasn't probed
        # in the UI before encoding), map all audio tracks from probe result
        if not audio_indices:
            audio_indices = [a.index for a in probe_result.audio]
            print(f"[CoDiMux] No audio selection found, falling back to all tracks: {audio_indices}")

        hardsub_index = self._get_hardsub_index() if self._sub_rows else None
        print(f"[CoDiMux] Encoding: {filename}")
        print(f"[CoDiMux] Audio indices: {audio_indices}")
        print(f"[CoDiMux] Sub indices: {sub_indices}")
        print(f"[CoDiMux] Hardsub: {hardsub_index}")
        print(f"[CoDiMux] Preset: {self._selected_preset_key}")


        v = probe_result.video
        smart_copy = preset.get("smart_copy", False)
        video_action = "copy" if (
            smart_copy and v and v.codec == "hevc" and
            v.width <= preset.get("width", 1920) and
            v.height <= preset.get("height", 1080)
        ) else "encode"

        audio_actions = []
        for idx in audio_indices:
            track = next((a for a in probe_result.audio if a.index == idx), None)
            audio_actions.append(
                "copy" if (track and smart_copy and track.codec == "opus") else "encode"
            )

        job = EncodeJob(
            input_path=filepath,
            output_path=output_path,
            preset=preset,
            audio_indices=audio_indices,
            sub_indices=sub_indices,
            hardsub_index=hardsub_index,
            video_action=video_action,
            audio_actions=audio_actions,
            probe_result=probe_result,
        )
        self._current_job = job
        print(f"[CoDiMux] Starting job for {filepath}")
        job.run(
            on_progress=lambda f, t, s, e: GLib.idle_add(self._on_progress, f, t, s, e),
            on_done=lambda ok, msg: GLib.idle_add(self._on_job_done, ok, msg),
            on_log=lambda line: GLib.idle_add(self._append_log, line),
        )

    def _on_progress(self, frame, total, speed, eta):
        if total > 0:
            frac = min(frame / total, 1.0)
            self._progress_bar.set_fraction(frac)
            eta_str = f"  ETA {int(eta//60)}m{int(eta%60):02d}s" if eta > 0 else ""
            self._progress_bar.set_text(f"{int(frac*100)}%  {speed:.1f}x{eta_str}")
        else:
            self._progress_bar.pulse()
            self._progress_bar.set_text(f"Frame {frame}  {speed:.1f}x")

    def _on_job_done(self, success, message):
        filename = Path(self._queue[self._queue_index]).name
        self._status_label.set_text(
            f"✓ {filename}" if success else f"✗ {filename}: {message}"
        )
        self._queue_index += 1
        self._encode_next()

    def _on_queue_complete(self):
        self._progress_bar.set_fraction(1.0)
        self._progress_bar.set_text("All done!")
        self._status_label.set_text(f"Finished {len(self._queue)} file(s)")
        self._encode_all_btn.set_sensitive(True)
        self._encode_selected_btn.set_sensitive(True)
        self._cancel_btn.set_sensitive(False)
        self._current_job = None

    def _on_cancel(self, btn):
        if self._current_job:
            self._current_job.cancel()
        self._queue = []
        self._queue_index = 0
        self._progress_bar.set_fraction(0)
        self._progress_bar.set_text("Cancelled")
        self._encode_all_btn.set_sensitive(True)
        self._encode_selected_btn.set_sensitive(True)
        self._cancel_btn.set_sensitive(False)

    # ── Log panel ─────────────────────────────────────────────────────────────
    def _on_log_toggled(self, btn):
        revealed = btn.get_active()
        self._log_revealer.set_reveal_child(revealed)
        btn.set_label("Hide Log" if revealed else "Show Log")

    def _on_copy_log(self, btn):
        start = self._log_buffer.get_start_iter()
        end = self._log_buffer.get_end_iter()
        text = self._log_buffer.get_text(start, end, False)
        clipboard = self.get_clipboard()
        clipboard.set(text)

    def _append_log(self, line: str):
        end = self._log_buffer.get_end_iter()
        self._log_buffer.insert(end, line + "\n")
        # Auto-scroll to bottom
        adj = self._log_view.get_parent().get_vadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())

    def _clear_log(self):
        self._log_buffer.set_text("")
        self._log_lines.clear()

    # ── Settings ──────────────────────────────────────────────────────────────
    def _on_settings(self, btn):
        from codimux.settings_dialog import SettingsDialog
        dialog = SettingsDialog(parent=self, config=self.config)
        dialog.connect("theme-changed", self._on_theme_changed)
        dialog.present()

    def _on_theme_changed(self, dialog):
        self._apply_theme()
