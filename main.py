import os
import sys
from configparser import ConfigParser

from PyQt5.QtWidgets import QApplication

from src.armor_cleaner import ArmorFilter
from src.controller import AppController
from src.destiny_api import ManifestBrowser
from src.ui import AppUI


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, "config.ini")
    configur = ConfigParser()
    configur.read(config_path)

    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

    app = QApplication(sys.argv)

    ui = AppUI(config_parser=configur)
    manifest_browser = ManifestBrowser()
    armor_filter = ArmorFilter()
    controller = AppController(
        ui=ui,
        api=manifest_browser,
        armor_cleaner=armor_filter,
        configur=configur,
    )

    ui.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
