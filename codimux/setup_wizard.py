"""
CoDiMux first-run setup wizard.
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GObject, GLib
from pathlib import Path
from codimux.config import DEFAULT_CONFIG_DIR


class SetupWizard(Adw.Window):
    __gsignals__ = {
        "setup-complete": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, config, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.set_title("CoDiMux Setup")
        self.set_default_size(520, 580)
        self.set_resizable(True)
        self.set_modal(True)

        self._selected_theme = "system"
        self._config_dir = str(DEFAULT_CONFIG_DIR)

        self._build_ui()

    def _build_ui(self):
        # Outer box
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(outer)

        # Header bar
        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(False)
        header.set_show_start_title_buttons(False)
        outer.append(header)

        # Scrollable content
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        outer.append(scroll)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        content.set_margin_top(32)
        content.set_margin_bottom(32)
        content.set_margin_start(48)
        content.set_margin_end(48)
        scroll.set_child(content)

        # Logo / title
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        title_box.set_halign(Gtk.Align.CENTER)

        title = Gtk.Label(label="CoDiMux")
        title.set_css_classes(["title-1"])
        title_box.append(title)



        content.append(title_box)

        # ── Theme selection ───────────────────────────────────────────────────
        theme_group = Adw.PreferencesGroup()
        theme_group.set_title("Appearance")
        theme_group.set_description("Choose how CoDiMux looks")
        content.append(theme_group)

        theme_row = Adw.ActionRow()
        theme_row.set_title("Theme")
        theme_row.set_subtitle("Controls the app's color scheme")

        self._theme_combo = Gtk.DropDown.new_from_strings(["Follow System", "Dark", "Light"])
        self._theme_combo.set_valign(Gtk.Align.CENTER)
        self._theme_combo.connect("notify::selected", self._on_theme_changed)
        theme_row.add_suffix(self._theme_combo)
        theme_group.add(theme_row)

        # ── Config directory ──────────────────────────────────────────────────
        dir_group = Adw.PreferencesGroup()
        dir_group.set_title("Storage")
        dir_group.set_description("Where CoDiMux stores settings and presets")
        content.append(dir_group)

        dir_row = Adw.ActionRow()
        dir_row.set_title("Config Directory")
        dir_row.set_subtitle(self._config_dir)
        self._dir_row = dir_row

        browse_btn = Gtk.Button(label="Change")
        browse_btn.set_valign(Gtk.Align.CENTER)
        browse_btn.set_css_classes(["flat"])
        browse_btn.connect("clicked", self._on_browse_config_dir)
        dir_row.add_suffix(browse_btn)
        dir_group.add(dir_row)

        # ── Bottom buttons ────────────────────────────────────────────────────
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_halign(Gtk.Align.END)
        btn_box.set_margin_top(8)
        content.append(btn_box)

        done_btn = Gtk.Button(label="Get Started")
        done_btn.set_css_classes(["suggested-action", "pill"])
        done_btn.connect("clicked", self._on_done)
        btn_box.append(done_btn)

    def _on_theme_changed(self, combo, _):
        idx = combo.get_selected()
        self._selected_theme = ["system", "dark", "light"][idx]
        # Apply instantly so the user sees the theme change in real time
        scheme_map = [
            Adw.ColorScheme.DEFAULT,
            Adw.ColorScheme.FORCE_DARK,
            Adw.ColorScheme.FORCE_LIGHT,
        ]
        Adw.StyleManager.get_default().set_color_scheme(scheme_map[idx])

    def _on_browse_config_dir(self, btn):
        dialog = Gtk.FileDialog()
        dialog.set_title("Choose Config Directory")
        dialog.set_initial_folder(
            Gio_File_new_for_path(str(Path.home() / ".config"))
        )
        dialog.select_folder(self, None, self._on_dir_chosen)

    def _on_dir_chosen(self, dialog, result):
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                self._config_dir = folder.get_path()
                self._dir_row.set_subtitle(self._config_dir)
        except Exception:
            pass

    def _on_done(self, btn):
        self.config.setup(
            theme=self._selected_theme,
            config_dir=self._config_dir,
        )
        self.emit("setup-complete")


# Helper since we can't import Gio at top without display
def Gio_File_new_for_path(path):
    from gi.repository import Gio
    return Gio.File.new_for_path(path)
