import os

import polars as pl
import pytest

from src.armor_cleaner import ArmorFilter


pl.Config.set_tbl_rows(100000)
pl.Config.set_tbl_cols(100000)


@pytest.fixture
def load_csv():
    def _loader(filename: str) -> pl.DataFrame:
        filepath = os.path.join("tests", "data", filename)
        return pl.read_csv(filepath)

    return _loader


def test_class_item_selection(load_csv):
    df = load_csv("hunter_class_items.csv")
    armor_filter = ArmorFilter()

    filtered = armor_filter.filter_class_items(df=df)

    print(filtered)
