from configparser import ConfigParser

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFontMetrics, QIcon, QPainter, QPixmap
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class HoverImage(QLabel):
    def __init__(
        self,
        base_pixmap_path,
        overlay_pixmap_path=None,
        image_size=64,
        tooltip_title="",
        tooltip_body="",
        tooltip_stats="",
        armor_id: str = None,
        parent=None,
    ):
        super().__init__(parent)
        self.base_pixmap_path = base_pixmap_path
        self.armor_id = armor_id

        self.tooltip_title = tooltip_title
        self.tooltip_body = tooltip_body
        self.tooltip_stats = tooltip_stats

        self.image_size = image_size
        self.base_pixmap = QPixmap(base_pixmap_path).scaled(
            image_size, image_size, Qt.KeepAspectRatio
        )
        self.overlay_pixmap = (
            QPixmap(overlay_pixmap_path).scaled(
                image_size, image_size, Qt.KeepAspectRatio
            )
            if overlay_pixmap_path
            else None
        )

        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"""
                        <b>{tooltip_title}</b><br>{tooltip_body}<br>{tooltip_stats}
                        """)
        self.setStyleSheet("border: 2px solid transparent;")

        self.create_combined_pixmap()

    def create_combined_pixmap(self):
        if self.base_pixmap.isNull():
            print("Error: base pixmap failed to load")
            print(f"Pixmap Path: {self.base_pixmap_path}")
            return

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
        self.setToolTip(f"""
                        <b>{self.tooltip_title}</b><br>{self.tooltip_body}<br>{self.tooltip_stats}
                        """)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet("border: 2px solid transparent;")
        super().leaveEvent(event)

    def resizeEvent(self, event):
        size = self.image_size
        self.setFixedSize(size, size)
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.armor_id:
            QApplication.clipboard().setText("id:" + self.armor_id)
            self.setToolTip(f"Copied ID: <b>{self.armor_id}</b>")
            self.setStyleSheet("border: 2px solid #00ffaa;")
        super().mousePressEvent(event)


class AppUI(QMainWindow):
    reload_triggered = pyqtSignal()
    process_triggered = pyqtSignal()
    copy_query_triggered = pyqtSignal()
    
    disc_slider_changed = pyqtSignal(int)
    quality_updated = pyqtSignal(float)

    def __init__(self, config_parser: ConfigParser):
        super().__init__()

        self.configur = config_parser

        self.setWindowTitle("Walker's Destiny Armor Tool")
        self.setWindowIcon(QIcon("src/assets/icon.png"))
        self.setGeometry(100, 100, 800, 400)

        self.setMinimumWidth(800)

        central_widget = QWidget()
        central_widget.setLayout(self.initUI())
        self.setCentralWidget(central_widget)

    def initUI(self):
        # Get default values from config file
        default_quality = self.configur.getfloat(
            "values", "DEFAULT_MAX_QUALITY"
        )
        default_disc_target = self.configur.getint(
            "values", "DEFAULT_DISC_TARGET"
        )
        default_ignore_tags_value = self.configur.getboolean("values", "IGNORE_TAGS")

        main_layout = QVBoxLayout()
        top_layout = QHBoxLayout()
        bottom_layout = QHBoxLayout()

        # Setup left layout and upload button
        left_layout = QVBoxLayout()

        reload_section = QGroupBox()
        reload_layout = QVBoxLayout()
        self.reload_button = QPushButton("Reload Armor List", self)
        self.reload_button.setToolTip(
            "Get new armor stats from Bungie"
        )

        reload_layout.addWidget(self.reload_button)

        reload_section.setLayout(reload_layout)
        reload_section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        left_layout.addWidget(reload_section)

        # Create maximum quality option
        quality_section = QGroupBox()
        quality_layout = QVBoxLayout()

        quality_label = QLabel("Maximum Quality")
        self.quality_input = QLineEdit()
        self.quality_input.setText(str(default_quality))
        quality_section.setToolTip(
            "Most sensitive option. Lower quality will be more restrictive.\n<5=very relaxed\n<2=somewhat strict\n<1=extremely strict"
        )

        quality_layout.addWidget(quality_label)
        quality_layout.addWidget(self.quality_input)

        quality_section.setLayout(quality_layout)
        quality_section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        left_layout.addWidget(quality_section)

        # Create slider and label for discipline target values
        disc_stat_section = QGroupBox()
        disc_stat_layout = QVBoxLayout()

        self.disc_stat_label = QLabel(f"Discipline Target: {default_disc_target}")
        self.disc_stat_slider = QSlider(Qt.Horizontal)
        self.disc_stat_slider.setRange(2, 30)
        self.disc_stat_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.disc_stat_slider.setValue(default_disc_target)
        disc_stat_section.setToolTip(
            "Base discipline above this level will not be penalized by the filter"
        )

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
                    lambda _, r=x, c=y: self.update_config_from_checkbox(r, c)
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
        checkbox_section.setToolTip(
            "Check any bottom bucket stat combos you wish to keep"
        )

        left_layout.addWidget(checkbox_section)

        # Ignore Tags button
        ignore_tags_section = QGroupBox()
        ignore_tags_layout = QHBoxLayout()

        ignore_tags_label = QLabel("Ignore Tags")
        self.ignore_tags_toggle = QCheckBox()
        self.ignore_tags_toggle.setChecked(default_ignore_tags_value)

        ignore_tags_section.setToolTip("Filter items tagged as Archive or Infuse")

        ignore_tags_layout.addWidget(ignore_tags_label)
        ignore_tags_layout.addWidget(self.ignore_tags_toggle)

        ignore_tags_section.setLayout(ignore_tags_layout)
        ignore_tags_section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        left_layout.addWidget(ignore_tags_section)

        copy_all_section = QGroupBox()
        copy_all_layout = QHBoxLayout()

        self.copy_all_button = QPushButton("Copy to Clipboard")

        copy_all_section.setToolTip(
            "Create a DIM query to highlight everything at once.\nClick on the tiles to copy individual IDs."
        )
        copy_all_layout.addWidget(self.copy_all_button)

        copy_all_section.setLayout(copy_all_layout)
        copy_all_section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        left_layout.addWidget(copy_all_section)

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

        self.run_button = QPushButton("Clean Armor")
        self.run_button.setToolTip("Press after setting all other settings")
        right_layout.addWidget(scroll_area)
        right_layout.addWidget(self.run_button)

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

        self.output_box.setText(
            "Welcome to Walker's Armor Cleaner! Select a DIM Armor CSV to begin."
        )

        bottom_layout.addWidget(self.output_box)

        bottom_widget = QWidget()
        bottom_widget.setLayout(bottom_layout)
        bottom_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        main_layout.addWidget(bottom_widget)

        # set connections
        self.quality_input.editingFinished.connect(self.update_quality_config)
        self.disc_stat_slider.valueChanged.connect(self.update_disc_slider)
        self.ignore_tags_toggle.clicked.connect(self.update_ignore_tags)

        self.reload_button.clicked.connect(self.trigger_armor_refresh)
        self.run_button.clicked.connect(self.trigger_process)
        self.copy_all_button.clicked.connect(self.copy_query_to_clipboard)

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

    def copy_query_to_clipboard(self):
        self.copy_query_triggered.emit()

    def update_quality_config(self):
        value = float(self.quality_input.text())
        self.quality_updated.emit(value)

    def update_config_from_checkbox(self, row, col):
        section = self.class_keys[col]
        key = self.config_keys[row]
        value = self.checkboxes[row][col].isChecked()

        self.configur.set(section, key, str(value))
        with open("config.ini", "w") as configfile:
            self.configur.write(configfile)

    def update_ignore_tags(self):
        value = self.ignore_tags_toggle.isChecked()

        self.configur.set("values", "ignore_tags", str(value))
        with open("config.ini", "w") as configfile:
            self.configur.write(configfile)

    def extract_grid_values(self):
        grid_values = {
            "Hunter": {},
            "Warlock": {},
            "Titan": {},
        }

        for col, class_key in enumerate(self.class_keys):
            for row, stat_key in enumerate(self.config_keys):
                checkbox = self.checkboxes[row][col]
                grid_values[class_key][stat_key] = checkbox.isChecked()

        return grid_values

    def update_disc_slider(self, value):
        self.disc_stat_label.setText(f"Discipline Target: {value}")
        self.disc_slider_changed.emit(value)

    def trigger_armor_refresh(self):
        self.reload_triggered.emit()

    def trigger_process(self):
        self.process_triggered.emit()

    def show_warning(self, title: str = "", body: str = ""):
        QMessageBox.warning(self, title, body)

    def add_to_photo_grid(self, image_path: str, overlay_path: str, item_data: dict):
        NUM_COLS = 7

        idx = self.image_box.count()
        row = idx // NUM_COLS
        col = idx % NUM_COLS

        label = HoverImage(
            base_pixmap_path=image_path,
            overlay_pixmap_path=overlay_path,
            image_size=64,
            tooltip_title=item_data["name"],
            tooltip_body=item_data["flavorText"],
        )
        self.image_box.addWidget(label, row, col)

        self.output_box.setText(
            f"Found {idx} Armor Pieces. DIM query copied to clipboard."
        )

    def set_process_enabled_state(self, enabled: bool):
        self.run_button.setEnabled(enabled)

    def set_clipboard_contents(self, to_copy: str):
        QApplication.clipboard().setText(to_copy)

    def clear_photo_grid(self):
        for i in reversed(range(self.image_box.count())):
            self.image_box.itemAt(i).widget().setParent(None)
