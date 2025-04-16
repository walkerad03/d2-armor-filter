from PyQt5.QtCore import QObject, pyqtSignal, QRunnable, pyqtSlot
import os

class IconLoaderSignals(QObject):
    item_loaded = pyqtSignal(str, str, dict)
    finished = pyqtSignal(str)

class IconLoaderRunnable(QRunnable):
    def __init__(self, hash_value, api):
        super().__init__()
        self.hash_value = hash_value
        self.api = api
        self.signals = IconLoaderSignals()

    @pyqtSlot()
    def run(self):
        base_path = f"data/icons/{self.hash_value}.png"

        if not os.path.isfile(base_path):
            self.api.get_item_icon_from_hash(self.hash_value, base_path)

        self.signals.finished.emit(str(self.hash_value))