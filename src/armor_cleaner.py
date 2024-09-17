import pandas as pd
import numpy as np


def _calculate_class_specific_decays(
    class_df: pd.DataFrame, distributions: dict[str, bool]
) -> pd.DataFrame:
    class_df["Mob Res Gap"] = np.nan
    class_df["Mob Rec Gap"] = np.nan
    class_df["Res Rec Gap"] = np.nan

    for key, value in distributions.items():
        if value == "False":
            continue  # Don't run stats on values that distributions that don't matter

        if key == "mob_res":
            class_df["Mob Res Gap"] = 32 - (
                class_df["Mobility (Base)"] + class_df["Resilience (Base)"]
            )

        if key == "mob_rec":
            class_df["Mob Rec Gap"] = 32 - (
                class_df["Mobility (Base)"] + class_df["Recovery (Base)"]
            )

        if key == "res_rec":
            class_df["Res Rec Gap"] = 32 - (
                class_df["Recovery (Base)"] + class_df["Resilience (Base)"]
            )

        class_df["Top Gap"] = class_df[
            ["Mob Res Gap", "Mob Rec Gap", "Res Rec Gap"]
        ].min(axis=1)

    return class_df


def _calc_bottom_stat_score(stat, target_stat):
    score = max(5 - (5 * stat) / target_stat, 0)
    return score


def calculate_decays(
    full_df: pd.DataFrame,
    bottom_stat_target: int,
    only_disc: bool,
    hunter_dist: dict[str, bool],
    titan_dist: dict[str, bool],
    warlock_dist: dict[str, bool],
    ignore_tags: bool,
) -> pd.DataFrame:

    df = full_df.copy()

    # Filter class items, archived armor, and artifice and raid armor
    df = df[~df["Type"].isin(["Titan Mark", "Warlock Bond", "Hunter Cloak"])]
    if ignore_tags:
        df = df[~df["Tag"].isin(["archive", "infuse"])]

    # Calculate top and bottom bin gaps
    df["Top Bin Gap"] = 34 - (
        df["Mobility (Base)"] + df["Resilience (Base)"] + df["Recovery (Base)"]
    )

    df["Top Bin Gap"] = df["Top Bin Gap"].clip(0, df["Top Bin Gap"])

    df["Bottom Bin Gap"] = 34 - (
        df["Discipline (Base)"]
        + df["Intellect (Base)"]
        + df["Strength (Base)"]
    )

    df["Bottom Bin Gap"] = df["Bottom Bin Gap"].clip(0, df["Bottom Bin Gap"])

    # Calculate gaps separately per class to allow for different distribution
    # targets

    hunter_df = df[df["Equippable"] == "Hunter"].copy()
    hunter_df = _calculate_class_specific_decays(hunter_df, hunter_dist)

    warlock_df = df[df["Equippable"] == "Warlock"].copy()
    warlock_df = _calculate_class_specific_decays(warlock_df, warlock_dist)

    titan_df = df[df["Equippable"] == "Titan"].copy()
    titan_df = _calculate_class_specific_decays(titan_df, titan_dist)

    df = pd.concat([hunter_df, warlock_df, titan_df])

    if only_disc:
        df["Bottom Quality"] = df["Discipline (Base)"].apply(
            lambda x: _calc_bottom_stat_score(x, bottom_stat_target)
        )
    else:
        df["Disc Quality"] = df["Discipline (Base)"].apply(
            lambda x: _calc_bottom_stat_score(x, bottom_stat_target)
        )
        df["Int Quality"] = df["Intellect (Base)"].apply(
            lambda x: _calc_bottom_stat_score(x, bottom_stat_target)
        )
        df["Str Quality"] = df["Strength (Base)"].apply(
            lambda x: _calc_bottom_stat_score(x, bottom_stat_target)
        )
        df["Bottom Quality"] = df[
            ["Disc Quality", "Int Quality", "Str Quality"]
        ].min(axis=1)

    df["Top Decay"] = df["Top Gap"] / 7.0 + df["Top Bin Gap"] / 3.0
    df["Quality Decay"] = (
        df["Top Decay"] + (df["Bottom Bin Gap"] + df["Bottom Quality"]) / 4
    )
    return df


def find_low_quality_armor(
    df: pd.DataFrame, min_quality: float
) -> pd.DataFrame:
    working_df = df.copy()
    working_df = working_df[working_df["Tier"] != "Exotic"]
    working_df = working_df[
        ~(
            working_df["Seasonal Mod"].isin(
                [
                    "vaultofglass",
                    "vowofthedisciple",
                    "rootofnightmares",
                    "deepstonecrypt",
                    "lastwish",
                    "kingsfall",
                    "crotasend",
                    "gardenofsalvation",
                    "salvationsedge",
                    "artifice",
                ]
            )
            | working_df["Perks 0"].isin(["Riven's Curse*"])
        )
    ]
    armor_to_delete = working_df[working_df["Quality Decay"] >= min_quality]

    return armor_to_delete


def find_artifice_armor(
    df: pd.DataFrame,
    min_quality: float,
    bottom_stat_target: int,
    only_disc: bool,
    hunter_dist: dict[str, bool],
    titan_dist: dict[str, bool],
    warlock_dist: dict[str, bool],
    ignore_tags: bool,
) -> pd.DataFrame:
    # Check each class individually
    artifice = df[
        (df["Seasonal Mod"] == "artifice") & (df["Tier"] != "Exotic")
    ].copy()

    changable_cols = [
        "Mobility (Base)",
        "Resilience (Base)",
        "Recovery (Base)",
        "Discipline (Base)",
        "Intellect (Base)",
        "Strength (Base)",
    ]

    new_df = pd.DataFrame(columns=artifice.columns)

    for col in changable_cols:
        working_df = artifice.copy()
        working_df[col] += 2
        if not working_df.empty:
            new_df = pd.concat([new_df, working_df], ignore_index=True)

    new_df = calculate_decays(
        new_df,
        bottom_stat_target,
        only_disc,
        hunter_dist,
        titan_dist,
        warlock_dist,
        ignore_tags,
    )

    quality_min = new_df.groupby("Id")["Quality Decay"].min()
    ids_to_remove = quality_min[quality_min < min_quality].index
    filtered_df = new_df[~new_df["Id"].isin(ids_to_remove)]

    filtered_df["Quality Decay"] = pd.to_numeric(
        filtered_df["Quality Decay"], errors="coerce"
    )
    idx = filtered_df.groupby("Id")["Quality Decay"].idxmin()
    final_df = filtered_df.loc[idx]

    return final_df


def find_raid_armor(df: pd.DataFrame, min_quality: float) -> pd.DataFrame:
    raid_modslots: list[str] = [
        "vaultofglass",
        "vowofthedisciple",
        "rootofnightmares",
        "deepstonecrypt",
        "lastwish",
        "kingsfall",
        "crotasend",
        "gardenofsalvation",
        "salvationsedge",
    ]

    classes = df["Equippable"].unique()

    raid_armor = df[
        df["Seasonal Mod"].isin(raid_modslots)
        | df["Perks 0"].isin(["Riven's Curse*"])
    ]

    armor_to_delete = pd.DataFrame(columns=raid_armor.columns)

    for d2class in classes:
        class_armor = raid_armor[raid_armor["Equippable"] == d2class].copy()

        raid_sets = class_armor["Seasonal Mod"].unique()
        armor_types = class_armor["Type"].unique()

        for raid in raid_sets:
            for armor_type in armor_types:
                filtered_df = class_armor[
                    (class_armor["Seasonal Mod"] == raid)
                    & (class_armor["Type"] == armor_type)
                    & (class_armor["Equippable"] == d2class)
                ]

                if filtered_df.empty:
                    continue

                min_quality_row_index = filtered_df["Quality Decay"].idxmin()
                current_checked_armor = filtered_df.drop(min_quality_row_index)

                armor_to_delete = pd.concat(
                    [armor_to_delete, current_checked_armor]
                )

    armor_to_delete = armor_to_delete[
        armor_to_delete["Quality Decay"] > min_quality
    ]

    return armor_to_delete


def find_exotics(df: pd.DataFrame, min_quality: float) -> pd.DataFrame:
    exotic_df = df[df["Tier"] == "Exotic"].copy()
    exotics = df["Hash"].unique()

    armor_to_delete = pd.DataFrame(columns=df.columns)

    for exotic in exotics:
        working_df = exotic_df[exotic_df["Hash"] == exotic].copy()

        if len(working_df) <= 2:
            continue

        for _ in range(2):
            min_quality_row_index = working_df["Quality Decay"].idxmin()
            working_df = working_df.drop(min_quality_row_index)

        if not working_df.empty:
            frames = [armor_to_delete, working_df]
            armor_to_delete = pd.concat(frames)
        else:
            print(working_df)

    armor_to_delete = armor_to_delete[
        armor_to_delete["Quality Decay"] > min_quality
    ]

    return armor_to_delete
