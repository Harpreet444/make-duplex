# main.py — make-duplex
#
# Copyright (C) 2024  Harpreet444 <https://github.com/Harpreet444/make-duplex>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
main.py
~~~~~~~

Application entry point for make-duplex.
"""

from __future__ import annotations

import os
import sys

from PyQt6.QtWidgets import QApplication

from make_duplex.ui.main_window import MainWindow, get_app_icon


def main() -> None:
    """Launch the make-duplex GUI application."""
    # On Windows, set explicit AppUserModelID so Windows Taskbar uses the app icon
    # instead of grouping under python.exe or showing the generic fallback icon.
    if sys.platform == "win32":
        try:
            import ctypes
            app_id = "Harpreet444.make-duplex.DesktopApp.1.0"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("make-duplex")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("Harpreet444")

    # Set application-wide icon
    app_icon = get_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    window = MainWindow()
    if not app_icon.isNull():
        window.setWindowIcon(app_icon)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
