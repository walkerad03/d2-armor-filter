import os
from configparser import ConfigParser
import numpy as np
import polars as pl
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFontMetrics, QIcon, QPixmap, QPainter
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QGroupBox,
    QScrollArea,
)

from src.destiny_api import ManifestBrowser


class HoverImage(QLabel):
    def __init__(
        self, base_pixmap_path, overlay_pixmap_path=None, image_size=64, tooltip_title="", tooltip_body="", parent=None
    ):
        super().__init__(parent)
        self.base_pixmap = QPixmap(base_pixmap_path).scaled(image_size, image_size, Qt.KeepAspectRatio)
        self.overlay_pixmap = QPixmap(overlay_pixmap_path).scaled(image_size, image_size, Qt.KeepAspectRatio) if overlay_pixmap_path else None
        
        self.setMouseTracking(True)
        self.setToolTip(f"""
                        <b>{tooltip_title}</b><br>{tooltip_body}
                        """)
        self.setStyleSheet("border: 2px solid transparent;")

        self.create_combined_pixmap()

    def create_combined_pixmap(self):
        combined = QPixmap(self.base_pixmap.size())
        combined.fill(Qt.transparent)

        painter = QPainter(combined)
        painter.drawPixmap(0, 0, self.base_pixmap)

        if self.overlay_pixmap:
            painter.drawPixmap(0, 0, self.overlay_pixmap)

        painter.end()
        self.setPixmap(combined)

    def enterEvent(self, event):
        self.setStyleSheet("border: 2px solid #00aaff;")
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet("border: 2px solid transparent;")
        super().leaveEvent(event)


class ArmorCleanerUI(QMainWindow):
    def __init__(self, config_parser: ConfigParser, do_calculations):
        super().__init__()

        self.configur = config_parser

        # NOTE: Temporary
        self.do_calculations = do_calculations

        self.setWindowTitle("Walker's Destiny Armor Tool")
        self.setWindowIcon(QIcon("src/assets/icon.png"))
        self.setGeometry(100, 100, 800, 400)

        central_widget = QWidget()
        central_widget.setLayout(self.initUI())
        self.setCentralWidget(central_widget)

    def initUI(self):
        # Get default values from config file
        default_min_quality = self.configur.getfloat(
            "values", "DEFAULT_MINIMUM_QUALITY"
        )
        default_disc_target = self.configur.getint(
            "values", "DEFAULT_BOTTOM_STAT_TARGET"
        )

        main_layout = QVBoxLayout()
        top_layout = QHBoxLayout()
        bottom_layout = QHBoxLayout()

        # Setup left layout and upload button
        left_layout = QVBoxLayout()

        upload_section = QGroupBox()
        upload_layout = QVBoxLayout()
        self.upload_button = QPushButton("Upload DIM Armor CSV", self)

        upload_layout.addWidget(self.upload_button)

        upload_section.setLayout(upload_layout)
        upload_section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        left_layout.addWidget(upload_section)

        # Create minimum quality option
        min_quality_section = QGroupBox()
        min_quality_layout = QVBoxLayout()

        min_quality_label = QLabel("Minimum Quality")
        self.min_quality_input = QLineEdit()
        self.min_quality_input.setText(str(default_min_quality))

        min_quality_layout.addWidget(min_quality_label)
        min_quality_layout.addWidget(self.min_quality_input)

        min_quality_section.setLayout(min_quality_layout)
        min_quality_section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        left_layout.addWidget(min_quality_section)

        # Create slider and label for discipline target values
        disc_stat_section = QGroupBox()
        disc_stat_layout = QVBoxLayout()

        self.disc_stat_label = QLabel(f"Discipline Target: {default_disc_target}")
        self.disc_stat_slider = QSlider(Qt.Horizontal)
        self.disc_stat_slider.setRange(2, 30)
        self.disc_stat_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.disc_stat_slider.setValue(default_disc_target)

        disc_stat_layout.addWidget(self.disc_stat_label)
        disc_stat_layout.addWidget(self.disc_stat_slider)

        disc_stat_section.setLayout(disc_stat_layout)
        disc_stat_section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        left_layout.addWidget(disc_stat_section)

        # Generate Checkbox Grid
        checkbox_section = QGroupBox()
        checkbox_layout = QGridLayout()

        classes = ["Hunter", "Warlock", "Titan"]
        for col, label in enumerate(classes):
            checkbox_layout.addWidget(QLabel(label), 0, col + 1)

        font_metrics = QFontMetrics(QLabel().font())
        text_height = font_metrics.height()

        icon_paths = [
            "src/assets/svg/mobility.svg",
            "src/assets/svg/resilience.svg",
            "src/assets/svg/recovery.svg",
        ]

        stat_pairs = [(0, 1), (0, 2), (1, 2)]
        for row, (i, j) in enumerate(stat_pairs, start=1):
            checkbox_layout.addLayout(
                self.make_double_svg_container(
                    icon_paths[i], icon_paths[j], text_height
                ),
                row,
                0,
            )

        self.checkboxes = [[None for _ in range(3)] for _ in range(3)]

        for x in range(3):
            for y in range(3):
                checkbox = QCheckBox()
                checkbox_layout.addWidget(checkbox, x + 1, y + 1)
                self.checkboxes[x][y] = checkbox

                checkbox.stateChanged.connect(
                    lambda state, r=x, c=y: self.update_config_from_checkbox(r, c)
                )

        self.config_keys = ["mob_res", "mob_rec", "res_rec"]
        self.class_keys = [
            "hunter distributions",
            "warlock distributions",
            "titan distributions",
        ]

        for col, class_key in enumerate(self.class_keys):
            for row, stat_key in enumerate(self.config_keys):
                value = self.configur.getboolean(class_key, stat_key)
                self.checkboxes[row][col].setChecked(value)

        checkbox_section.setLayout(checkbox_layout)
        checkbox_section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        left_layout.addWidget(checkbox_section)

        # Set layout options for left layout
        left_widget = QWidget()
        left_widget.setLayout(left_layout)
        left_widget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

        # Create right layout and add widgets
        right_layout = QVBoxLayout()

        image_container = QWidget()
        self.image_box = QGridLayout()
        image_container.setLayout(self.image_box)

        scroll_area = QScrollArea()
        scroll_area.setWidget(image_container)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        run_button = QPushButton("Clean Armor")
        right_layout.addWidget(scroll_area)
        right_layout.addWidget(run_button)

        # Set right layout options
        right_widget = QWidget()
        right_widget.setLayout(right_layout)
        right_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        # combine everything
        top_layout.addWidget(left_widget)
        top_layout.addWidget(right_widget)

        top_widget = QWidget()
        top_widget.setLayout(top_layout)
        top_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        main_layout.addWidget(top_widget)

        self.output_box = QTextEdit()
        self.output_box.setFixedHeight(text_height * 2)
        self.output_box.setReadOnly(True)

        bottom_layout.addWidget(self.output_box)

        bottom_widget = QWidget()
        bottom_widget.setLayout(bottom_layout)
        bottom_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        main_layout.addWidget(bottom_widget)

        # set connections
        self.min_quality_input.editingFinished.connect(self.update_min_quality_config)
        self.disc_stat_slider.valueChanged.connect(self.update_disc_slider)
        self.upload_button.clicked.connect(self.upload_file)
        run_button.clicked.connect(self.process_file)

        return main_layout

    def make_double_svg_container(self, path_1, path_2, size):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        icon_1 = QSvgWidget(path_1)
        icon_2 = QSvgWidget(path_2)

        icon_1.setFixedSize(size, size)
        icon_2.setFixedSize(size, size)
        layout.addWidget(icon_1)
        layout.addWidget(icon_2)

        return layout

    def update_min_quality_config(self):
        value = self.min_quality_input.text()

        try:
            float_value = float(value)  # validate input
            self.configur.set("values", "DEFAULT_MINIMUM_QUALITY", str(float_value))
            with open("config.ini", "w") as configfile:
                self.configur.write(configfile)
        except ValueError:
            # Optionally show a warning dialog or reset the field
            print("Invalid input: must be a number")

    def update_config_from_checkbox(self, row, col):
        section = self.class_keys[col]
        key = self.config_keys[row]
        value = self.checkboxes[row][col].isChecked()

        self.configur.set(section, key, str(value))
        with open("config.ini", "w") as configfile:
            self.configur.write(configfile)

    def extract_grid_values(self):
        grid_values = {
            "hunter distributions": {},
            "warlock distributions": {},
            "titan distributions": {},
        }

        for col, class_key in enumerate(self.class_keys):
            for row, stat_key in enumerate(self.config_keys):
                checkbox = self.checkboxes[row][col]
                grid_values[class_key][stat_key] = checkbox.isChecked()

        return grid_values

    def update_disc_slider(self, value):
        self.disc_stat_label.setText(f"Discipline Target: {value}")
        self.configur.set("values", "DEFAULT_BOTTOM_STAT_TARGET", str(value))
        with open("config.ini", "w") as configfile:
            self.configur.write(configfile)

    def upload_file(self):
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
            self.output_box.setText(f"File selected: {self.fileName}")

    def process_file(self):
        if not hasattr(self, "fileName") or not self.fileName:
            # Display an error message to the user
            QMessageBox.warning(self, "Error", "No file selected.")
            return

        self.output_box.setText("Checking armor")

        for i in reversed(range(self.image_box.count())):
            self.image_box.itemAt(i).widget().setParent(None)

        # Read the CSV file
        df = pl.read_csv(self.fileName)

        min_quality = self.min_quality_input.text()
        bottom_stat_target = self.disc_stat_slider.value()

        distributions = self.extract_grid_values()

        text_result, hash_list = self.do_calculations(
            df,
            min_quality,
            bottom_stat_target,
            distributions,
        )

        # NOTE: THIS IS TEMPORARY
        self.output_box.setText("Downloading Armor Details")

        manifest_browser = ManifestBrowser()

        if not os.path.exists("data/icons"):
            os.makedirs("data/icons")


        image_window_width = self.image_box.parentWidget().width()
        image_window_spacing = self.image_box.spacing()
        num_cols = int(np.floor(image_window_width / (64 + image_window_spacing)))

        for idx, hash_value in enumerate(hash_list):
            manifest_browser.get_item_icon_from_hash(
                hash_value, f"data/icons/{hash_value}"
            )
            item_data = manifest_browser.get_item_details_from_hash(hash_value)

            row = idx // num_cols
            col = idx % num_cols

            label = HoverImage(
                base_pixmap_path=f"data/icons/{hash_value}.png",
                overlay_pixmap_path=f"data/icons/{hash_value}_overlay.png",
                image_size=64,
                tooltip_title=item_data["name"],
                tooltip_body=item_data["flavorText"],
            )
            self.image_box.addWidget(label, row, col)

        self.output_box.setText(
            f"Found {len(hash_list)} Armor Pieces. DIM query copied to clipboard."
        )
        QApplication.clipboard().setText(text_result)
