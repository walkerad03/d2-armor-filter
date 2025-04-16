import os

import polars as pl
from PyQt5.QtCore import QThreadPool
from PyQt5.QtGui import QPixmap

from src.destiny_api import ManifestBrowser
from src.ui import AppUI, HoverImage
from src.workers import IconLoaderRunnable


class AppController:
    def __init__(self, ui: AppUI, api: ManifestBrowser, armor_cleaner, configur):
        self.ui = ui
        self.api = api
        self.armor_cleaner = armor_cleaner
        self.configur = configur
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(1)

        self.df = None
        self.filepath = None
        self.text_result = None
        self.image_placeholders = {}

        self.connect_signals()

    def connect_signals(self):
        self.ui.upload_triggered.connect(self.handle_upload)
        self.ui.process_triggered.connect(self.handle_process)
        self.ui.copy_query_triggered.connect(self.handle_copy_query)

    def handle_copy_query(self):
        if not self.text_result:
            self.ui.show_warning(title="Error", body="Run the filter first")
        self.ui.set_clipboard_contents(self.text_result)
        self.ui.output_box.setText(
            "DIM query copied to clipboard."
        )



    def handle_upload(self, filepath):
        self.ui.output_box.setText(f"File selected: {filepath}")
        self.filepath = filepath

    def handle_process(self, min_quality, bottom_stat_target, distributions):
        if not self.filepath:
            self.ui.show_warning(title="Error", body="No file selected.")
            return
        
        self.ui.set_process_enabled_state(False)
        
        self.ui.clear_photo_grid()
        self.image_placeholders = {}
        
        self.df = pl.read_csv(self.filepath)
        self.text_result, trash_armor_df = self.do_calculations(self.df, min_quality, bottom_stat_target, distributions)
        self.ui.set_clipboard_contents(self.text_result)

        hash_list = trash_armor_df["Hash"].to_list()

        os.makedirs("data/icons", exist_ok=True)

        self.hash_list = hash_list
        unique_hashes = list(set(hash_list))
        self.remaining_downloads = len(unique_hashes)

        skeleton_path = "src/assets/placeholder.png"

        idx = 0
        for row in trash_armor_df.iter_rows(named=True):
            armor_id = row["Id"]
            hash_value = row["Hash"]
            row = idx // 7
            col = idx % 7

            placeholder = HoverImage(
                base_pixmap_path=skeleton_path,
                overlay_pixmap_path=None,
                image_size=64,
                tooltip_title="Loading...",
                tooltip_body="Fetching item details..."
            )

            self.ui.image_box.addWidget(placeholder, row, col)
            self.image_placeholders[(hash_value, armor_id, row, col)] = placeholder

            idx += 1

        for hash_value in unique_hashes:
            task = IconLoaderRunnable(hash_value, self.api)
            task.signals.finished.connect(self._on_runner_finished)
            self.thread_pool.start(task)
        

    def do_calculations(self, armor_file, min_quality, bottom_stat_target, distributions):
        DEFAULT_MINIMUM_QUALITY = float(min_quality)
        DEFAULT_BOTTOM_STAT_TARGET = int(bottom_stat_target)
        IGNORE_TAGS = self.configur.getboolean("values", "IGNORE_TAGS")
        ALWAYS_KEEP_HIGHEST_POWER = self.configur.getboolean(
            "values", "ALWAYS_KEEP_HIGHEST_POWER"
        )

        HUNTER_DIST = distributions["hunter distributions"]
        TITAN_DIST = distributions["titan distributions"]
        WARLOCK_DIST = distributions["warlock distributions"]

        # Load csv and tier armor
        scored_armor = self.armor_cleaner.calculate_decays(
            armor_file,
            DEFAULT_BOTTOM_STAT_TARGET,
            HUNTER_DIST,
            TITAN_DIST,
            WARLOCK_DIST,
            IGNORE_TAGS,
            ALWAYS_KEEP_HIGHEST_POWER,
        )

        raid_armor = self.armor_cleaner.find_raid_armor(scored_armor, DEFAULT_MINIMUM_QUALITY)

        low_quality_armor = self.armor_cleaner.find_low_quality_armor(scored_armor, DEFAULT_MINIMUM_QUALITY)

        artifice_armor = self.armor_cleaner.find_artifice_armor(
            armor_file,
            DEFAULT_MINIMUM_QUALITY,
            DEFAULT_BOTTOM_STAT_TARGET,
            HUNTER_DIST,
            TITAN_DIST,
            WARLOCK_DIST,
            IGNORE_TAGS,
            ALWAYS_KEEP_HIGHEST_POWER,
        )

        exotic_armor = self.armor_cleaner.find_exotics(scored_armor, DEFAULT_MINIMUM_QUALITY)

        class_items = self.armor_cleaner.find_class_items(armor_file)

        armor_to_delete = pl.concat(
            [low_quality_armor, raid_armor, artifice_armor, exotic_armor, class_items]
        )

        armor_list = " or ".join([f"id:{item}" for item in armor_to_delete["Id"].to_list()])

        return armor_list, armor_to_delete["Id", "Hash"]
    
    def get_armor_stats(self, armor_id: str) -> str:
        row = self.df.filter(pl.col("Id") == armor_id)

        if row.is_empty():
            return "Stats not found."

        stats = row.select([
            pl.col("Mobility"),
            pl.col("Resilience"),
            pl.col("Recovery"),
            pl.col("Discipline"),
            pl.col("Intellect"),
            pl.col("Strength"),
            pl.col("Total")
        ]).to_dicts()[0]

        return (
            "<table style='font-family: sans-serif; font-size: 10pt;'>"
            f"<tr><td>Mobility</td><td>{self.number_to_bar(stats['Mobility'])}</td></tr>"
            f"<tr><td>Resilience</td><td>{self.number_to_bar(stats['Resilience'])}</td></tr>"
            f"<tr><td>Recovery</td><td>{self.number_to_bar(stats['Recovery'])}</td></tr>"
            f"<tr><td>Discipline</td><td>{self.number_to_bar(stats['Discipline'])}</td></tr>"
            f"<tr><td>Intellect</td><td>{self.number_to_bar(stats['Intellect'])}</td></tr>"
            f"<tr><td>Strength</td><td>{self.number_to_bar(stats['Strength'])}</td></tr>"
            f"<tr><td><b>Total</b></td><td><b>{stats['Total']}</b></td></tr>"
            "</table>"
        )

    def number_to_bar(self, value, max_val=44, bar_length=22):
        filled_blocks = int((value / max_val) * bar_length)
        empty_blocks = bar_length - filled_blocks

        return (
            f"<span style='font-family: monospace;'>"
            f"<span style='color: #4caf50;'>{'█' * filled_blocks}</span>"
            f"<span style='color: #ccc;'>{'█' * empty_blocks}</span> {value}</span>"
        )

    def _handle_item_loaded(self, image_path, overlay_path, item_data):
        self.ui.add_to_photo_grid(
            image_path=image_path,
            overlay_path=overlay_path,
            item_data=item_data
        )

    def _on_runner_finished(self, hash_value):
        self.remaining_downloads -= 1

        if self.remaining_downloads == 0:
            self.ui.set_process_enabled_state(True)

        image_path = f"data/icons/{hash_value}.png"
        overlay_path = f"data/icons/{hash_value}_overlay.png"
        item_data = self.api.get_item_details_from_hash(hash_value)

        for key, label in list(self.image_placeholders.items()):
            key_hash, armor_id, _, _ = key
            if str(key_hash) == hash_value:
                stats_block = self.get_armor_stats(armor_id)

                new_label = HoverImage(
                    base_pixmap_path=image_path,
                    overlay_pixmap_path=overlay_path,
                    image_size=64,
                    tooltip_title=item_data["name"],
                    tooltip_body=item_data["flavorText"],
                    tooltip_stats=stats_block,
                    armor_id=armor_id
                )
                self.ui.image_box.replaceWidget(label, new_label)
                label.deleteLater()
                self.ui.output_box.setText(
                    f"Found {self.ui.image_box.count()} Armor Pieces. DIM query copied to clipboard."
                )
