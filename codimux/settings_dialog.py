"""
CoDiMux settings dialog.
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk, GObject
from pathlib import Path
from codimux.config import DEFAULT_CONFIG_DIR, POINTER_FILE


class SettingsDialog(Adw.PreferencesWindow):
    __gsignals__ = {
        "theme-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, parent, config, **kwargs):
        super().__init__(**kwargs)
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_title("Settings")
        self.set_default_size(500, 500)
        self.config = config
        self._build_ui()

    def _build_ui(self):
        # ── Appearance page ───────────────────────────────────────────────────
        appearance_page = Adw.PreferencesPage()
        appearance_page.set_title("Appearance")
        appearance_page.set_icon_name("preferences-desktop-appearance-symbolic")
        self.add(appearance_page)

        theme_group = Adw.PreferencesGroup()
        theme_group.set_title("Theme")
        appearance_page.add(theme_group)

        theme_row = Adw.ActionRow()
        theme_row.set_title("Color Scheme")
        themes = ["Follow System", "Dark", "Light"]
        self._theme_combo = Gtk.DropDown.new_from_strings(themes)
        cur = self.config.get("theme", "system")
        mapping = {"system": 0, "dark": 1, "light": 2}
        self._theme_combo.set_selected(mapping.get(cur, 0))
        self._theme_combo.set_valign(Gtk.Align.CENTER)
        self._theme_combo.connect("notify::selected", self._on_theme_changed)
        theme_row.add_suffix(self._theme_combo)
        theme_group.add(theme_row)

        # ── Storage page ──────────────────────────────────────────────────────
        storage_page = Adw.PreferencesPage()
        storage_page.set_title("Storage")
        storage_page.set_icon_name("drive-harddisk-symbolic")
        self.add(storage_page)

        dir_group = Adw.PreferencesGroup()
        dir_group.set_title("Paths")
        storage_page.add(dir_group)

        config_row = Adw.ActionRow()
        config_row.set_title("Config Directory")
        config_row.set_subtitle(str(self.config.config_dir))
        self._config_row = config_row

        change_config_btn = Gtk.Button(label="Change")
        change_config_btn.set_valign(Gtk.Align.CENTER)
        change_config_btn.set_css_classes(["flat"])
        change_config_btn.connect("clicked", self._on_change_config_dir)
        config_row.add_suffix(change_config_btn)
        dir_group.add(config_row)

        output_row = Adw.ActionRow()
        output_row.set_title("Output Subfolder Name")
        output_row.set_subtitle("Created inside each input folder")
        self._output_entry = Gtk.Entry()
        self._output_entry.set_text(self.config.get("output_dir_name", "encode_output"))
        self._output_entry.set_valign(Gtk.Align.CENTER)
        self._output_entry.set_max_width_chars(20)
        self._output_entry.connect("changed", self._on_output_name_changed)
        output_row.add_suffix(self._output_entry)
        dir_group.add(output_row)

        reset_group = Adw.PreferencesGroup()
        storage_page.add(reset_group)

        reset_row = Adw.ActionRow()
        reset_row.set_title("Reset Config Location")
        reset_row.set_subtitle(f"Move back to default: {DEFAULT_CONFIG_DIR}")
        reset_btn = Gtk.Button(label="Reset")
        reset_btn.set_valign(Gtk.Align.CENTER)
        reset_btn.set_css_classes(["flat"])
        reset_btn.connect("clicked", self._on_reset_config_dir)
        reset_row.add_suffix(reset_btn)
        reset_group.add(reset_row)

    def _on_theme_changed(self, combo, _):
        scheme_map = {
            0: ("system",  Adw.ColorScheme.DEFAULT),
            1: ("dark",    Adw.ColorScheme.FORCE_DARK),
            2: ("light",   Adw.ColorScheme.FORCE_LIGHT),
        }
        theme, scheme = scheme_map[combo.get_selected()]
        self.config.set("theme", theme)
        # Apply instantly — StyleManager is global so this affects the whole app
        Adw.StyleManager.get_default().set_color_scheme(scheme)
        self.emit("theme-changed")

    def _on_change_config_dir(self, btn):
        dialog = Gtk.FileDialog()
        dialog.set_title("Choose New Config Directory")
        dialog.select_folder(self, None, self._on_config_dir_chosen)

    def _on_config_dir_chosen(self, dialog, result):
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                import shutil
                new_path = Path(folder.get_path()) / "codimux"
                new_path.mkdir(parents=True, exist_ok=True)
                for f in self.config.config_dir.iterdir():
                    shutil.copy2(f, new_path / f.name)
                POINTER_FILE.write_text(str(new_path))
                self.config.config_dir = new_path
                self.config.settings_path = new_path / "settings.json"
                self.config.presets_path = new_path / "presets.json"
                self.config.set("config_dir", str(new_path))
                self._config_row.set_subtitle(str(new_path))
        except Exception as e:
            print(f"Error moving config: {e}")

    def _on_output_name_changed(self, entry):
        name = entry.get_text().strip()
        if name:
            self.config.set("output_dir_name", name)

    def _on_reset_config_dir(self, btn):
        POINTER_FILE.unlink(missing_ok=True)
        self._config_row.set_subtitle(str(DEFAULT_CONFIG_DIR))
