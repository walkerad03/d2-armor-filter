import sys
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QTextEdit,
    QCheckBox,
    QHBoxLayout,
    QSpacerItem,
    QSizePolicy,
    QLineEdit,
    QGridLayout,
    QSlider,
    QMessageBox,
)

from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtGui import QIcon, QFontMetrics
from PyQt5.QtCore import Qt
import polars as pl
from src.main import do_calculations
from configparser import ConfigParser
import os

from src.destiny_api import ManifestBrowser

configur = ConfigParser()
configur.read("config.ini")


class SimpleCSVProcessor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Walker's Destiny Armor Tool")
        self.setWindowIcon(QIcon("src/assets/icon.png"))
        self.setGeometry(100, 100, 800, 400)

        self.centralWidget = QWidget()
        self.setCentralWidget(self.centralWidget)

        mainLayout = QHBoxLayout(self.centralWidget)
        leftLayout = QVBoxLayout()
        leftLayout.setSpacing(0)

        self.uploadButton = QPushButton("Upload Armor CSV", self)
        leftLayout.addWidget(self.uploadButton)

        leftLayout.addSpacerItem(
            QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        )

        self.minQualityLabel = QLabel("Minimum Quality", self)
        leftLayout.addWidget(self.minQualityLabel)

        self.minQualityInput = QLineEdit(self)
        self.minQualityInput.setText(
            str(configur.getfloat("values", "DEFAULT_MINIMUM_QUALITY"))
        )
        leftLayout.addWidget(self.minQualityInput)

        bottomStatDefault = configur.getint("values", "DEFAULT_BOTTOM_STAT_TARGET")

        self.bottomStatTargetLabel = QLabel(
            f"Bottom Stat Target: {bottomStatDefault}", self
        )
        leftLayout.addWidget(self.bottomStatTargetLabel)

        self.bottomStatTargetInput = QSlider(Qt.Horizontal, self)
        self.bottomStatTargetInput.setRange(2, 30)
        self.bottomStatTargetInput.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.bottomStatTargetInput.setValue(bottomStatDefault)
        self.bottomStatTargetInput.valueChanged.connect(self.updateSlider)
        leftLayout.addWidget(self.bottomStatTargetInput)

        HUNTER_DIST = dict(configur.items("hunter distributions"))
        TITAN_DIST = dict(configur.items("titan distributions"))
        WARLOCK_DIST = dict(configur.items("warlock distributions"))

        gridLayout = QGridLayout()

        hunter_label = QLabel("Hunter")
        warlock_label = QLabel("Warlock")
        titan_label = QLabel("Titan")

        gridLayout.addWidget(hunter_label, 0, 1)
        gridLayout.addWidget(warlock_label, 0, 2)
        gridLayout.addWidget(titan_label, 0, 3)

        font_metrics = QFontMetrics(hunter_label.font())
        text_height = font_metrics.height()

        mobil_path = "src/assets/svg/mobility.svg"
        recov_path = "src/assets/svg/recovery.svg"
        resil_path = "src/assets/svg/resilience.svg"

        gridLayout.addLayout(
            self.make_double_svg_container(mobil_path, resil_path, text_height), 1, 0
        )

        gridLayout.addLayout(
            self.make_double_svg_container(mobil_path, recov_path, text_height), 2, 0
        )

        gridLayout.addLayout(
            self.make_double_svg_container(resil_path, recov_path, text_height), 3, 0
        )

        for x in range(1, 4):
            for y in range(1, 4):
                gridLayout.addWidget(QCheckBox(), x, y)

        leftLayout.addLayout(gridLayout)
        mainLayout.addLayout(leftLayout)

        self.outputText = QTextEdit(self)
        mainLayout.addWidget(self.outputText)

        rightLayout = QVBoxLayout()
        rightLayout.setSpacing(0)

        self.processButton = QPushButton("Run Armor Analysis", self)
        rightLayout.addWidget(self.processButton)

        mainLayout.addLayout(rightLayout)

        self.uploadButton.clicked.connect(self.uploadFile)
        self.processButton.clicked.connect(self.processCSV)

    def make_double_svg_container(self, path_1, path_2, size):
        # TODO: Finish later.
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        icon_1 = QSvgWidget(path_1)
        icon_2 = QSvgWidget(path_2)

        icon_1.setFixedSize(size, size)
        icon_2.setFixedSize(size, size)
        layout.addWidget(icon_1)
        # layout.addWidget(QLabel(" + "))
        layout.addWidget(icon_2)

        return layout

    def extract_grid_values(self):
        hunter_dist = {}
        warlock_dist = {}
        titan_dist = {}

        for (cat1, cat2), checkbox in self.checkbox_dict.items():
            config_key = "_".join(cat2.lower().split(" + "))
            value = str(checkbox.isChecked())

            if cat1.lower() == "hunter":
                hunter_dist[config_key] = value
            elif cat1.lower() == "warlock":
                warlock_dist[config_key] = value
            elif cat1.lower() == "titan":
                titan_dist[config_key] = value

        return {
            "hunter distributions": hunter_dist,
            "warlock distributions": warlock_dist,
            "titan distributions": titan_dist,
        }

    def updateSlider(self, value):
        self.bottomStatTargetLabel.setText(f"Bottom Stat Target: {value}")

    def uploadFile(self):
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        self.fileName, _ = QFileDialog.getOpenFileName(
            self,
            "Open CSV File",
            "",
            "CSV Files (*.csv);;All Files (*)",
            options=options,
        )
        if self.fileName:
            self.outputText.setText(f"File selected: {self.fileName}")

    def processCSV(self):
        if not hasattr(self, "fileName") or not self.fileName:
            # Display an error message to the user
            QMessageBox.warning(self, "Error", "No file selected.")
            return
        # Read the CSV file
        df = pl.read_csv(self.fileName)

        min_quality = self.minQualityInput.text()
        bottom_stat_target = self.bottomStatTargetInput.value()

        distributions = self.extract_grid_values()

        text_result, hash_list = do_calculations(
            df,
            min_quality,
            bottom_stat_target,
            distributions,
        )

        # THIS IS TEMPORARY
        manifest_browser = ManifestBrowser()

        for idx, hash_value in enumerate(hash_list):
            manifest_browser.get_item_icon_from_hash(hash_value, f"icons/{idx}.png")

        # Set the output string to the text edit
        self.outputText.setText(text_result)


if __name__ == "__main__":
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

    app = QApplication(sys.argv)
    mainWindow = SimpleCSVProcessor()
    mainWindow.show()
    sys.exit(app.exec_())
