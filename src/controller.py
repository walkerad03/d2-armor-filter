import os
from typing import Optional

import polars as pl
from PyQt5.QtCore import QThreadPool, QTimer

from src.armor_cleaner import ArmorFilter, FilterParams
from src.auth import BungieOAuth
from src.destiny_api import ManifestBrowser
from src.ui import AppUI, HoverImage
from src.workers import IconLoaderRunnable


class AppController:
    item_stats_map = {
        "144602215": "Intellect",
        "392767087": "Resilience",
        "1735777505": "Discipline",
        "1943323491": "Recovery",
        "2996146975": "Mobility",
        "4244567218": "Strength",
    }

    source_map = {
        'Source: "Root of Nightmares" Raid': "nightmare",
        'Source: "Garden of Salvation" Raid': "gardenofsalvation",
        "Source: Complete activities in the Dreaming City.": "dreaming",
        "Source: Complete Iron Banner matches and earn rank-up packages from Lord Saladin.": "ironbanner",
        'Source: "Deep Stone Crypt" Raid': "deepstonecrypt",
        'Source: "Vow of the Disciple" Raid': "vowofthedisciple",
        'Source: "Vault of Glass" Raid': "vaultofglass",
        'Source: "Salvation\'s Edge" Raid': "salvationsedge",
        'Source: "Crota\'s End" Raid': "crotasend",
        'Source: "King\'s Fall" Raid': "kingsfall",
        "Source: Last Wish raid.": "lastwish",
        "Source: Guardian Games 2025": "guardiangames",
        "Source: Guardian Games": "guardiangames",
    }

    def __init__(
        self,
        ui: AppUI,
        api: ManifestBrowser,
        armor_cleaner: ArmorFilter,
        auth: BungieOAuth,
        configur,
    ):
        self.ui = ui
        self.api = api
        self.armor_cleaner = armor_cleaner
        self.auth = auth
        self.configur = configur
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(1)

        auth_token = self.auth.authenticate()
        self.api.set_auth_token(auth_token)

        self.mem_id, self.mem_type = self.api.get_membership_for_user()

        self.filepath: Optional[str] = None
        self.text_result: Optional[str] = None
        self.image_placeholders: dict = {}

        self.ignore_common_armor = self.configur.getboolean("values", "IGNORE_COMMONS")
        self.always_keep_highest_power = False
        self.build_flags = {
            "Hunter": {"MobRes": True, "ResRec": True, "MobRec": False},
            "Warlock": {"MobRes": False, "ResRec": True, "MobRec": False},
            "Titan": {"MobRes": False, "ResRec": True, "MobRec": False},
        }

        self.max_quality: float = self.configur.getfloat(
            "values", "DEFAULT_MAX_QUALITY"
        )
        self.target_discipline: int = self.configur.getint(
            "values", "DEFAULT_DISC_TARGET"
        )

        self.connect_signals()

    def connect_signals(self):
        self.ui.reload_triggered.connect(self.handle_armor_refresh)
        self.ui.process_triggered.connect(self.handle_process)
        self.ui.copy_query_triggered.connect(self.handle_copy_query)
        self.ui.disc_slider_changed.connect(self.handle_disc_slider_change)
        self.ui.quality_updated.connect(self.handle_quality_change)
        self.ui.ignore_commons_updated.connect(self.handle_ignore_commons_change)
        self.ui.checkbox_grid_triggered.connect(self.handle_checkbox_change)

    def handle_armor_refresh(self) -> None:
        self.ui.set_process_enabled_state(False)

        self.ui.clear_photo_grid()
        self.image_placeholders = {}

        self.df = self.create_armor_df()

        self.handle_process()

        self.ui.set_process_enabled_state(True)

    def start_app(self):
        self.ui.show()

        self.handle_armor_refresh()

        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.handle_armor_refresh)
        self.refresh_timer.start(30 * 1000)

    def create_armor_df(self) -> pl.DataFrame:
        assert self.mem_type is not None and self.mem_id is not None, ValueError(
            "mem_type or mem_id is None"
        )

        res = self.api.query_protected_endpoint(
            f"https://www.bungie.net/Platform/Destiny2/"
            f"{self.mem_type}/Profile/{self.mem_id}/"
            "?components=102,201,205,300,302,304,305"
        )

        vault = (
            res.get("Response", {})
            .get("profileInventory", {})
            .get("data", {})
            .get("items", {})
        )

        character_inventories = (
            res.get("Response", {}).get("characterInventories", {}).get("data", {})
        )

        equipped = res.get("Response", {}).get("characterEquipment", {}).get("data", {})

        item_instances = (
            res.get("Response", {})
            .get("itemComponents", {})
            .get("instances")
            .get("data", {})
        )
        item_sockets = (
            res.get("Response", {})
            .get("itemComponents", {})
            .get("sockets", {})
            .get("data", {})
        )

        inventory = vault

        for key in character_inventories:
            inventory += character_inventories[key].get("items", [])

        for key in equipped:
            inventory += equipped[key].get("items", [])

        item_dict = []

        for item in inventory:
            item_hash = item.get("itemHash", None)
            item_instance_id = item.get("itemInstanceId", None)
            item_def = self.api.get_inventory_item_from_hash(item_hash)

            item_type = item_def["itemType"]

            if item_type != 2:
                continue

            item_tier = item_def.get("inventory", {}).get("tierTypeName", None)
            item_sub_type = self.api.get_armor_subtype(item_hash)
            item_equippable = self.api.get_class_type(item_hash)

            item_details = self.api.get_item_details_from_hash(item_hash)
            item_name = item_details["name"]

            item_power = (
                item_instances.get(item_instance_id, {})
                .get("primaryStat", {})
                .get("value", 0)
            )

            item_energy = (
                item_instances.get(item_instance_id, {})
                .get("energy", {})
                .get("energyCapacity", 0)
            )

            is_masterworked = True if item_energy == 10 else False

            if item_tier == "Exotic":
                is_artifice = True
            else:
                is_artifice = self.api.is_artifice(item_hash)

            if not item_def.get("collectibleHash"):
                item_source_raw = item_def["displaySource"]
            else:
                item_source_raw = self.api.get_source_from_item_hash(item_hash)

            item_source = self.source_map.get(item_source_raw, None)

            item_statsheet = {
                "Name": item_name,
                "Hash": item_hash,
                "Id": item_instance_id,
                "Tier": item_tier,
                "ItemSubType": item_sub_type,
                "Source": item_source,
                "Equippable": item_equippable,
                "Power": item_power,
                "Energy Capacity": item_energy,
                "IsMasterworked": is_masterworked,
                "IsArtifice": is_artifice,
            }

            sockets = item_sockets.get(item_instance_id, {}).get("sockets", [])
            item_base_stats = self.get_base_stats_from_id(sockets)

            item_statsheet |= item_base_stats

            item_dict.append(item_statsheet)

        dataframe = pl.DataFrame(item_dict).sort("Name")

        return dataframe

    def get_base_stats_from_id(self, sockets):
        stat_totals = {
            "Mobility": 0,
            "Resilience": 0,
            "Recovery": 0,
            "Discipline": 0,
            "Intellect": 0,
            "Strength": 0,
            "Total": 0,
        }

        for plug in sockets:
            if not plug["isEnabled"]:
                continue
            plug_hash = plug["plugHash"]

            res = self.api.get_inventory_item_from_hash(plug_hash)

            if res["plug"]["plugCategoryIdentifier"] != "intrinsics":
                continue

            investment_stats = res["investmentStats"]

            for stat in investment_stats:
                stat_type_hash = stat["statTypeHash"]
                stat_data = self.api.get_destiny_stat_definition(stat_type_hash)

                stat_name = stat_data["displayProperties"]["name"]
                stat_value = stat["value"]
                stat_totals[stat_name] += stat_value
                stat_totals["Total"] += stat_value

        return stat_totals

    def handle_disc_slider_change(self, value):
        self.target_discipline = value
        self.configur.set("values", "DEFAULT_DISC_TARGET", str(value))
        with open("config.ini", "w") as configfile:
            self.configur.write(configfile)

    def handle_quality_change(self, value):
        self.max_quality = value
        self.configur.set("values", "DEFAULT_MAX_QUALITY", str(value))
        with open("config.ini", "w") as configfile:
            self.configur.write(configfile)

    def handle_ignore_commons_change(self, value):
        self.ignore_common_armor = value
        self.configur.set("values", "IGNORE_COMMONS", str(value))
        with open("config.ini", "w") as configfile:
            self.configur.write(configfile)

    def handle_copy_query(self) -> None:
        if not self.text_result:
            self.ui.show_warning(title="Error", body="Run the filter first")
            return
        self.ui.set_clipboard_contents(self.text_result)
        self.ui.output_box.setText("DIM query copied to clipboard.")

    def handle_checkbox_change(self, row, col, state):
        class_keys: list[str] = ["Hunter", "Warlock", "Titan"]
        config_keys: list[str] = ["MobRes", "MobRec", "ResRec"]

        for c, class_name in enumerate(class_keys):
            for r, config_name in enumerate(config_keys):
                if c != col or r != row:
                    continue
                self.build_flags[class_name][config_name] = state

                self.configur.set(class_name, config_name, str(state))
                with open("config.ini", "w") as configfile:
                    self.configur.write(configfile)

    def handle_process(self):
        self.ui.set_process_enabled_state(False)

        self.ui.clear_photo_grid()
        self.image_placeholders = {}

        params = FilterParams(
            target_discipline=self.target_discipline,
            max_quality=self.max_quality,
            ignore_common_armor=self.ignore_common_armor,
            always_keep_highest_power=self.always_keep_highest_power,
            build_flags=self.build_flags,
        )

        trash_armor_df = self.armor_cleaner.filter_armor_items(self.df, params)
        self.text_output = " or ".join(
            [f"id:{item}" for item in trash_armor_df["Id"].to_list()]
        )

        self.ui.set_clipboard_contents(self.text_output)

        hash_list = trash_armor_df["Hash"].to_list()

        os.makedirs("data/icons", exist_ok=True)

        self.hash_list = hash_list
        unique_hashes = list(set(hash_list))
        self.remaining_downloads = len(unique_hashes)

        if len(unique_hashes) == 0:
            self.ui.set_process_enabled_state(True)
            self.ui.write_to_status_bar("There are no armor pieces to delete!")
            return

        self.ui.write_to_status_bar(
            f"Found {len(unique_hashes)} Armor Pieces to Delete."
        )

        skeleton_path = "src/assets/placeholder.png"

        num_cols = self.ui.image_grid.get_num_cols()
        idx = 0
        for row in trash_armor_df.iter_rows(named=True):
            armor_id = row["Id"]
            hash_value = row["Hash"]
            row = idx // num_cols
            col = idx % num_cols

            placeholder = HoverImage(
                base_pixmap_path=skeleton_path,
                overlay_pixmap_path=None,
                image_size=96,
                tooltip_title="Loading...",
                tooltip_body="Fetching item details...",
            )

            self.ui.add_to_grid_at_coords(placeholder, row, col)
            self.image_placeholders[(hash_value, armor_id, row, col)] = placeholder

            idx += 1

        for hash_value in unique_hashes:
            task = IconLoaderRunnable(hash_value, self.api)
            task.signals.finished.connect(self._on_runner_finished)
            self.thread_pool.start(task)

    def get_armor_stats(self, armor_id: str) -> str:
        row = self.df.filter(pl.col("Id") == armor_id)

        if row.is_empty():
            return "Stats not found."

        stats = row.select(
            [
                pl.col("Mobility"),
                pl.col("Resilience"),
                pl.col("Recovery"),
                pl.col("Discipline"),
                pl.col("Intellect"),
                pl.col("Strength"),
            ]
        ).to_dicts()[0]

        return (
            "<table style='font-family: sans-serif; font-size: 10pt;'>"
            f"<tr><td>Mobility</td><td>{self.value_to_bar(stats['Mobility'])}</td></tr>"
            f"<tr><td>Resilience</td><td>{self.value_to_bar(stats['Resilience'])}</td></tr>"
            f"<tr><td>Recovery</td><td>{self.value_to_bar(stats['Recovery'])}</td></tr>"
            f"<tr><td>Discipline</td><td>{self.value_to_bar(stats['Discipline'])}</td></tr>"
            f"<tr><td>Intellect</td><td>{self.value_to_bar(stats['Intellect'])}</td></tr>"
            f"<tr><td>Strength</td><td>{self.value_to_bar(stats['Strength'])}</td></tr>"
            "</table>"
        )

    def value_to_bar(self, value, max_val=44, bar_length=22):
        if value is None:
            value = 0
        filled_blocks = int((value / max_val) * bar_length)
        empty_blocks = bar_length - filled_blocks

        return (
            f"<span style='font-family: monospace;'>"
            f"<span style='color: #4caf50;'>{'█' * filled_blocks}</span>"
            f"<span style='color: #ccc;'>{'█' * empty_blocks}</span> {value}</span>"
        )

    def _handle_item_loaded(self, image_path, overlay_path, item_data):
        self.ui.add_to_photo_grid(
            image_path=image_path, overlay_path=overlay_path, item_data=item_data
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
                    image_size=96,
                    tooltip_title=item_data["name"],
                    tooltip_body=item_data["flavorText"],
                    tooltip_stats=stats_block,
                    armor_id=armor_id,
                )
                self.ui.image_grid.replaceWidget(label, new_label)
                label.deleteLater()
