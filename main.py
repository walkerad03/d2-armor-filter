import os
import sys
from configparser import ConfigParser

from PyQt5.QtWidgets import QApplication

from src.armor_cleaner import ArmorFilter
from src.auth import BungieOAuth
from src.controller import AppController
from src.destiny_api import ManifestBrowser
from src.ui import AppUI


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, "config.ini")
    configur = ConfigParser()
    configur.read(config_path)

    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

    app = QApplication(sys.argv)

    cert_filepath = os.path.join("src", "ssl", "localhost.crt")
    key_filepath = os.path.join("src", "ssl", "localhost.key")

    ui = AppUI(config_parser=configur)
    auth = BungieOAuth(cert_filepath=cert_filepath, key_filepath=key_filepath)
    manifest_browser = ManifestBrowser()
    armor_filter = ArmorFilter()

    controller = AppController(
        ui=ui,
        api=manifest_browser,
        armor_cleaner=armor_filter,
        auth=auth,
        configur=configur,
    )

    controller.start_app()

    stylesheet_path = os.path.join(base_dir, "src", "style.qss")
    with open(stylesheet_path, "r") as f:
        _style = f.read()
        app.setStyleSheet(_style)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
