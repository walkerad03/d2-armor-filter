import datetime
import json
import os
import sqlite3
import zipfile

import requests
from dotenv import load_dotenv


class ManifestBrowser:
    def __init__(self) -> None:
        load_dotenv()

        self.BUNGIE_API_KEY = os.getenv("BUNGIE_API_KEY")
        self.MANIFEST_STORAGE_DIR = "data/manifest/"
        self.headers = {"X-API-KEY": self.BUNGIE_API_KEY}

        if not os.path.isdir(self.MANIFEST_STORAGE_DIR):
            os.makedirs(self.MANIFEST_STORAGE_DIR)

        if not os.path.isfile(f"{self.MANIFEST_STORAGE_DIR}manifest.content"):
            self.get_manifest()

        with open("data/manifest/last-download-date", "r") as file:
            download_date = datetime.datetime.strptime(
                file.read(), "%Y-%m-%d %H:%M:%S.%f"
            )

        if datetime.datetime.now() - download_date > datetime.timedelta(hours=24):
            self.get_manifest()

    def get_manifest(self):
        manifest_url = "http://www.bungie.net/Platform/Destiny2/Manifest/"

        r = requests.get(manifest_url, headers=self.headers)
        manifest = r.json()
        mani_url = f"https://www.bungie.net{manifest['Response']['mobileWorldContentPaths']['en']}"

        print(mani_url)

        r = requests.get(mani_url, headers=self.headers)
        with open(f"{self.MANIFEST_STORAGE_DIR}MANZIP", "wb") as zipped:
            zipped.write(r.content)
        print("Download Complete")

        with zipfile.ZipFile(f"{self.MANIFEST_STORAGE_DIR}MANZIP") as zipped:
            name = zipped.namelist()
            zipped.extractall()
        os.rename(name[0], f"{self.MANIFEST_STORAGE_DIR}manifest.content")
        print("Unzipped")

        ct = datetime.datetime.now()
        with open("data/manifest/last-download-date", "w") as file:
            file.write(str(ct))

    def get_inventory_item_from_hash(self, hash_value: int):
        id_val = int(hash_value)
        if (id_val & (1 << (32 - 1))) != 0:
            id_val = id_val - (1 << 32)

        con = sqlite3.connect(f"{self.MANIFEST_STORAGE_DIR}manifest.content")
        cur = con.cursor()
        cur.execute(f"SELECT * FROM DestinyInventoryItemDefinition WHERE id={id_val};")
        items = cur.fetchall()

        if len(items) > 1:
            raise ValueError(f"db call returned more than 1 result: {len(items)}")

        return items

    def get_item_details_from_hash(self, hash_value: int):
        id_val = int(hash_value)
        if (id_val & (1 << (32 - 1))) != 0:
            id_val = id_val - (1 << 32)

        con = sqlite3.connect(f"{self.MANIFEST_STORAGE_DIR}manifest.content")
        cur = con.cursor()
        cur.execute(f"SELECT * FROM DestinyInventoryItemDefinition WHERE id={id_val};")
        items = cur.fetchall()

        if len(items) > 1:
            raise ValueError(f"db call returned more than 1 result: {len(items)}")

        if len(items) == 0:
            raise ValueError(f"No items found: {id_val}")
        json_data = json.loads(items[0][1])

        item_data = {}
        item_data["name"] = json_data["displayProperties"]["name"]
        item_data["flavorText"] = json_data["flavorText"]

        return item_data

    def get_item_icon_from_hash(self, hash_value: int, file_name: str):
        id_val = int(hash_value)
        if (id_val & (1 << (32 - 1))) != 0:
            id_val = id_val - (1 << 32)

        con = sqlite3.connect(f"{self.MANIFEST_STORAGE_DIR}manifest.content")
        cur = con.cursor()
        cur.execute(f"SELECT * FROM DestinyInventoryItemDefinition WHERE id={id_val};")
        items = cur.fetchall()

        if len(items) > 1:
            raise ValueError(f"db call returned more than 1 result: {len(items)}")

        json_data = json.loads(items[0][1])
        icon_url = f"https://www.bungie.net{json_data['displayProperties']['icon']}"
        overlay_url = f"https://www.bungie.net{json_data['iconWatermark']}"
        query_params = {"downloadFormat": "png"}
        res = requests.get(icon_url, params=query_params)

        with open(file_name, mode="wb") as file:
            file.write(res.content)

        res = requests.get(overlay_url, params=query_params)

        with open(f"{file_name.removesuffix('.png')}_overlay.png", mode="wb") as file:
            file.write(res.content)

    def get_table_names(self) -> list[str]:
        con = sqlite3.connect(f"{self.MANIFEST_STORAGE_DIR}manifest.content")
        cur = con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")

        tables = cur.fetchall()
        return [table[0] for table in tables]

    def get_table_attributes(self, table_name: str):
        con = sqlite3.connect(f"{self.MANIFEST_STORAGE_DIR}manifest.content")
        cur = con.cursor()
        cur.execute(f"PRAGMA table_info({table_name});")

        columns = cur.fetchall()

        attributes = []
        for col in columns:
            attributes.append(
                f"Column name: {col[1]}, Type: {col[2]}, Not Null: {col[3]}, Default: {col[4]}, Primary Key: {col[5]}"
            )

        return attributes
