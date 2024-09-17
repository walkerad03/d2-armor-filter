import pandas as pd
from src.armor_cleaner import (
    calculate_decays,
    find_raid_armor,
    find_low_quality_armor,
    find_artifice_armor,
    find_exotics,
)
from configparser import ConfigParser

# Read config values
configur = ConfigParser()
configur.read("config.ini")


def do_calculations(
    armor_file, min_quality, bottom_stat_target, distributions
):
    DEFAULT_MINIMUM_QUALITY = float(min_quality)
    DEFAULT_BOTTOM_STAT_TARGET = int(bottom_stat_target)
    ONLY_USE_DISCIPLINE = configur.getboolean("values", "ONLY_USE_DISCIPLINE")
    IGNORE_TAGS = configur.getboolean("values", "IGNORE_TAGS")

    HUNTER_DIST = distributions["hunter distributions"]
    TITAN_DIST = distributions["titan distributions"]
    WARLOCK_DIST = distributions["warlock distributions"]

    # Load csv and tier armor
    scored_armor = calculate_decays(
        armor_file,
        DEFAULT_BOTTOM_STAT_TARGET,
        ONLY_USE_DISCIPLINE,
        HUNTER_DIST,
        TITAN_DIST,
        WARLOCK_DIST,
        IGNORE_TAGS,
    )

    raid_armor = find_raid_armor(scored_armor, DEFAULT_MINIMUM_QUALITY)

    low_quality_armor = find_low_quality_armor(
        scored_armor, DEFAULT_MINIMUM_QUALITY
    )

    artifice_armor = find_artifice_armor(
        armor_file,
        DEFAULT_MINIMUM_QUALITY,
        DEFAULT_BOTTOM_STAT_TARGET,
        ONLY_USE_DISCIPLINE,
        HUNTER_DIST,
        TITAN_DIST,
        WARLOCK_DIST,
        IGNORE_TAGS,
    )

    exotic_armor = find_exotics(scored_armor, DEFAULT_MINIMUM_QUALITY)

    armor_to_delete = pd.concat(
        [low_quality_armor, raid_armor, artifice_armor, exotic_armor]
    )

    armor_list = " or ".join(
        "id:" + str(row["Id"]).strip('"')
        for _, row in armor_to_delete.iterrows()
    )

    return armor_list
