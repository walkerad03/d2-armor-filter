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
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt
import pandas as pd
from src.main import do_calculations
from configparser import ConfigParser
import os

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

        bottomStatDefault = configur.getint(
            "values", "DEFAULT_BOTTOM_STAT_TARGET"
        )

        self.bottomStatTargetLabel = QLabel(
            f"Bottom Stat Target: {bottomStatDefault}", self
        )
        leftLayout.addWidget(self.bottomStatTargetLabel)

        self.bottomStatTargetInput = QSlider(Qt.Horizontal, self)
        self.bottomStatTargetInput.setRange(2, 30)
        self.bottomStatTargetInput.setTickPosition(
            QSlider.TickPosition.TicksBelow
        )
        self.bottomStatTargetInput.setValue(bottomStatDefault)
        self.bottomStatTargetInput.valueChanged.connect(self.updateSlider)
        leftLayout.addWidget(self.bottomStatTargetInput)

        HUNTER_DIST = dict(configur.items("hunter distributions"))
        TITAN_DIST = dict(configur.items("titan distributions"))
        WARLOCK_DIST = dict(configur.items("warlock distributions"))

        gridLayout = QGridLayout()
        categories1 = ["Hunter", "Warlock", "Titan"]
        categories2 = ["Mob + Rec", "Mob + Res", "Res + Rec"]
        self.checkbox_dict = {}

        self.checkboxes = {}

        for i, cat1 in enumerate(categories1):
            for j, cat2 in enumerate(categories2):
                checkbox = QCheckBox(f"{cat1}-{cat2}")
                gridLayout.addWidget(checkbox, i, j)

                config_key = "_".join(cat2.lower().split(" + "))

                # Set the checkbox state based on the config value
                if cat1.lower() == "hunter":
                    checkbox.setChecked(
                        HUNTER_DIST.get(config_key, "False").lower() == "true"
                    )
                elif cat1.lower() == "warlock":
                    checkbox.setChecked(
                        WARLOCK_DIST.get(config_key, "False").lower() == "true"
                    )
                elif cat1.lower() == "titan":
                    checkbox.setChecked(
                        TITAN_DIST.get(config_key, "False").lower() == "true"
                    )

                # Store the checkbox in a dictionary for easy access later
                self.checkbox_dict[(cat1, cat2)] = checkbox

        leftLayout.addLayout(gridLayout)

        mainLayout.addLayout(leftLayout)

        self.outputText = QTextEdit(self)
        mainLayout.addWidget(self.outputText)

        self.processButton = QPushButton("Run Armor Analysis", self)
        mainLayout.addWidget(self.processButton)

        self.uploadButton.clicked.connect(self.uploadFile)
        self.processButton.clicked.connect(self.processCSV)

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
        if hasattr(self, "fileName") and self.fileName:
            # Read the CSV file
            df = pd.read_csv(self.fileName)

            min_quality = self.minQualityInput.text()
            bottom_stat_target = self.bottomStatTargetInput.value()

            distributions = self.extract_grid_values()

            result = do_calculations(
                df,
                min_quality,
                bottom_stat_target,
                distributions,
            )

            # Set the output string to the text edit
            self.outputText.setText(result)
        else:
            self.outputText.setText("No file selected.")


if __name__ == "__main__":
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_EnableHighDpiScaling)
    mainWindow = SimpleCSVProcessor()
    mainWindow.show()
    sys.exit(app.exec_())
