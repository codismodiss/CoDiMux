#!/usr/bin/env python3
"""
CoDiMux — Multi-platform video encoder GUI by codismodiss
"""

import sys
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, Gio, GLib
from codimux.config import Config
from codimux.window import CoDiMuxWindow
from codimux.setup_wizard import SetupWizard


class CoDiMuxApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="com.codismodiss.codimux",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self.config = None

    def do_activate(self):
        self.config = Config()

        if not self.config.is_configured():
            wizard = SetupWizard(application=self, config=self.config)
            wizard.connect("setup-complete", self._on_setup_complete)
            wizard.present()
        else:
            self._open_main_window()

    def _on_setup_complete(self, wizard):
        wizard.close()
        self._open_main_window()

    def _open_main_window(self):
        win = CoDiMuxWindow(application=self, config=self.config)
        win.present()


def main():
    app = CoDiMuxApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
