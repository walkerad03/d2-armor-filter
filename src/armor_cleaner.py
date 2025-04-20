import polars as pl


class ArmorFilter:
    def __init__(self):
        pass

    def calculate_decays(
        self,
        df: pl.DataFrame,
        bottom_stat_target: int,
        hunter_dist,
        titan_dist,
        warlock_dist,
        ignore_tags: bool,
        always_keep_highest_power: bool,
    ) -> pl.DataFrame:
        df = df.filter(~(pl.col("ItemSubType") == "ClassItem"))

        # Calculate "Top Bin Gap" and clip to zero
        df = df.with_columns(
            [
                (
                    (
                        34
                        - (
                            pl.col("Mobility")
                            + pl.col("Resilience")
                            + pl.col("Recovery")
                        )
                    )
                    .clip(0, None)
                    .alias("Top Bin Gap")
                )
            ]
        )

        # Calculate "Bottom Bin Gap" and clip to zero
        df = df.with_columns(
            [
                (
                    (
                        34
                        - (
                            pl.col("Discipline")
                            + pl.col("Intellect")
                            + pl.col("Strength")
                        )
                    )
                    .clip(0, None)
                    .alias("Bottom Bin Gap")
                )
            ]
        )

        # Define class distributions
        class_distributions = {
            "Hunter": hunter_dist,
            "Titan": titan_dist,
            "Warlock": warlock_dist,
        }

        # Process each class separately
        dfs = []
        for class_name, distributions in class_distributions.items():
            class_df = df.filter(pl.col("Equippable") == class_name)
            class_df = self._calculate_class_specific_decays(class_df, distributions)
            dfs.append(class_df)

        # Concatenate the processed class DataFrames
        df = pl.concat(dfs)

        df = df.with_columns(
            [
                self._calc_bottom_stat_score(
                    pl.col("Discipline"), bottom_stat_target
                ).alias("Bottom Quality")
            ]
        )

        # First, calculate "Top Decay"
        df = df.with_columns(
            [
                ((pl.col("Top Gap") / 7.0) + (pl.col("Top Bin Gap") / 3.0)).alias(
                    "Top Decay"
                )
            ]
        )

        # Then, calculate "Quality Decay" using the newly created "Top Decay" column
        df = df.with_columns(
            [
                (
                    pl.col("Top Decay")
                    + (pl.col("Bottom Bin Gap") + pl.col("Bottom Quality")) / 4
                ).alias("Quality Decay")
            ]
        )

        if always_keep_highest_power:
            df = self._keep_max_power_armor(df)

        return df

    def find_mod_armor(self, df: pl.DataFrame, min_quality: float) -> pl.DataFrame:
        sources_to_keep: list[str] = [
            "gardenofsalvation",
            "dreaming",
            "ironbanner",
            "deepstonecrypt",
            "vowofthedisciple",
            "vaultofglass",
            "salvationsedge",
            "crotasend",
            "nightmare",
            "kingsfall",
            "lastwish",
        ]

        raid_armor = df.filter(pl.col("Source").is_in(sources_to_keep))

        result = (
            raid_armor.with_columns(
                [
                    pl.col("Quality Decay")
                    .rank("ordinal", descending=False)
                    .over(["Equippable", "Source", "ItemSubType"])
                    .alias("quality_rank")
                ]
            )
            .filter(pl.col("quality_rank") > 1)
            .filter(pl.col("Quality Decay") > min_quality)
            .drop("quality_rank")
        )

        result = result.drop(
            [
                "Top Bin Gap",
                "Bottom Bin Gap",
                "Mob Res Gap",
                "Mob Rec Gap",
                "Res Rec Gap",
                "Top Gap",
                "Bottom Quality",
                "Top Decay",
            ]
        )

        return result

    def find_low_quality_armor(
        self, df: pl.DataFrame, min_quality: float
    ) -> pl.DataFrame:
        sources_to_exclude: list[str] = [
            "gardenofsalvation",
            "dreaming",
            "ironbanner",
            "deepstonecrypt",
            "vowofthedisciple",
            "vaultofglass",
            "salvationsedge",
            "crotasend",
            "nightmare",
            "kingsfall",
            "lastwish",
        ]

        armor_to_delete = df.filter(
            (pl.col("Tier") != "Exotic")
            & (pl.col("Source").is_in(sources_to_exclude).not_() | pl.col("IsArtifice"))
            & (pl.col("Quality Decay") >= min_quality)
        )

        armor_to_delete = armor_to_delete.drop(
            [
                "Top Bin Gap",
                "Bottom Bin Gap",
                "Mob Res Gap",
                "Mob Rec Gap",
                "Res Rec Gap",
                "Top Gap",
                "Bottom Quality",
                "Top Decay",
            ]
        )

        return armor_to_delete

    def find_artifice_armor(
        self,
        df: pl.DataFrame,
        min_quality: float,
        bottom_stat_target: int,
        hunter_dist,
        titan_dist,
        warlock_dist,
        ignore_tags: bool,
        always_keep_highest_power: bool,
    ) -> pl.DataFrame:
        # Filter for artifice armor that's not exotic
        artifice = df.filter(
            (pl.col("IsArtifice") == "true") & (pl.col("Tier") != "Exotic")
        )

        changable_cols = [
            "Mobility",
            "Resilience",
            "Recovery",
            "Discipline",
            "Intellect",
            "Strength",
        ]

        # List to hold modified DataFrames
        modified_dfs = []

        # Modify each stat column by adding 2 and collect the DataFrames
        for col in changable_cols:
            working_df = artifice.clone()
            working_df = working_df.with_columns((pl.col(col) + 2).alias(col))
            if working_df.height > 0:
                modified_dfs.append(working_df)

        # Concatenate all modified DataFrames
        new_df = pl.concat(modified_dfs)

        # Calculate decays using the provided function
        new_df = self.calculate_decays(
            new_df,
            bottom_stat_target,
            hunter_dist,
            titan_dist,
            warlock_dist,
            ignore_tags,
            always_keep_highest_power,
        )

        # Get the minimum "Quality Decay" per "Id"
        quality_min = new_df.group_by("Id").agg(
            pl.col("Quality Decay").min().alias("Quality Decay")
        )

        # Identify Ids to remove (those with minimum "Quality Decay" < min_quality)
        ids_to_remove = quality_min.filter(pl.col("Quality Decay") < min_quality)["Id"]

        # Filter the DataFrame to exclude the Ids to remove
        filtered_df = new_df.filter(~pl.col("Id").is_in(ids_to_remove))

        # For each "Id", select the row with the minimum "Quality Decay"
        final_df = filtered_df.sort(["Id", "Quality Decay"]).unique(
            subset=["Id"], keep="first"
        )

        final_df = final_df.drop(
            [
                "Top Bin Gap",
                "Bottom Bin Gap",
                "Mob Res Gap",
                "Mob Rec Gap",
                "Res Rec Gap",
                "Top Gap",
                "Bottom Quality",
                "Top Decay",
            ]
        )

        return final_df

    def find_exotics(self, df: pl.DataFrame, min_quality: float) -> pl.DataFrame:
        exotics_df = df.filter(pl.col("Tier") == "Exotic")

        group_sizes = (
            exotics_df.group_by("Hash").count().rename({"count": "group_size"})
        )

        ranked_df = exotics_df.with_columns(
            [
                pl.col("Quality Decay")
                .rank("ordinal", descending=False)
                .over("Hash")
                .alias("quality_rank")
            ]
        )

        ranked_df = ranked_df.join(group_sizes, on="Hash")

        result = ranked_df.filter(
            (pl.col("group_size") > 2)
            & (pl.col("quality_rank") > 2)
            & (pl.col("Quality Decay") > min_quality)
        )

        result = result.drop(["quality_rank", "group_size"])

        result = result.drop(
            [
                "Top Bin Gap",
                "Bottom Bin Gap",
                "Mob Res Gap",
                "Mob Rec Gap",
                "Res Rec Gap",
                "Top Gap",
                "Bottom Quality",
                "Top Decay",
            ]
        )

        return result

    def find_class_items(self, df: pl.DataFrame):
        class_items = df.filter(
            pl.col("Tier").is_in(["Legendary", "Rare", "Common"])
            & (pl.col("ItemSubType") == "ClassItem")
        )

        sources_to_keep = [
            "gardenofsalvation",
            "dreaming",
            "ironbanner",
            "deepstonecrypt",
            "vowofthedisciple",
            "vaultofglass",
            "salvationsedge",
            "crotasend",
            "nightmare",
            "kingsfall",
            "lastwish",
            "guardiangames",
        ]

        equippables = {
            "Hunter": "Hunter Cloak",
            "Titan": "Titan Mark",
            "Warlock": "Warlock Bond",
        }

        all_trash = []

        for class_name in equippables.keys():
            all_class_items = class_items.filter(pl.col("Equippable") == class_name)

            class_subset = class_items.filter(
                (pl.col("Equippable") == class_name)
                & (pl.col("Source").is_in(sources_to_keep))
            )

            best_per_source = class_subset.sort(
                by=["Source", "Energy Capacity", "Power"],
                descending=[False, True, True],
            ).unique(subset=["Source"], keep="first")

            artifice_item = (
                all_class_items.filter(pl.col("IsArtifice"))
                .sort(by=["Energy Capacity", "Power"], descending=[True, True])
                .limit(1)
            )

            top_power_item = all_class_items.sort(
                by=["Power", "Energy Capacity"], descending=[True, True]
            ).limit(1)

            items_to_keep = pl.concat(
                [
                    best_per_source,
                    artifice_item,
                    top_power_item,
                ]
            ).unique()

            keep_ids = items_to_keep["Id"] if "Id" in all_class_items.columns else None

            class_trash = class_items.filter(
                (pl.col("Equippable") == class_name) & ~(pl.col("Id").is_in(keep_ids))
            )

            all_trash.append(class_trash)

        to_trash = pl.concat(all_trash)

        to_trash = to_trash.with_columns([pl.lit(0.0).alias("Quality Decay")])

        return to_trash

    def _calculate_class_specific_decays(
        self, class_df: pl.DataFrame, distributions
    ) -> pl.DataFrame:
        class_df = class_df.with_columns(
            [
                pl.lit(None).alias("Mob Res Gap"),
                pl.lit(None).alias("Mob Rec Gap"),
                pl.lit(None).alias("Res Rec Gap"),
            ]
        )

        exprs = []

        if distributions.get("mob_res", False) != "False":
            exprs.append(
                (32 - (pl.col("Mobility") + pl.col("Resilience"))).alias("Mob Res Gap")
            )

        if distributions.get("mob_rec", False) != "False":
            exprs.append(
                (32 - (pl.col("Mobility") + pl.col("Recovery"))).alias("Mob Rec Gap")
            )

        if distributions.get("res_rec", False) != "False":
            exprs.append(
                (32 - (pl.col("Resilience") + pl.col("Recovery"))).alias("Res Rec Gap")
            )

        if exprs:
            class_df = class_df.with_columns(exprs)
            # Calculate "Top Gap" as the minimum of the calculated gaps
            class_df = class_df.with_columns(
                [
                    pl.min_horizontal(
                        ["Mob Res Gap", "Mob Rec Gap", "Res Rec Gap"]
                    ).alias("Top Gap")
                ]
            )
        else:
            # If no distributions are selected, set "Top Gap" to None
            class_df = class_df.with_columns([pl.lit(None).alias("Top Gap")])

        return class_df

    def _calc_bottom_stat_score(self, stat_col: pl.Expr, target_stat: int) -> pl.Expr:
        return (5 - (5 * stat_col) / target_stat).clip(0, None)

    def _keep_max_power_armor(df: pl.DataFrame):
        df = df.sort(
            by=["ItemSubType", "Equippable", "Power", "Quality Decay"],
            descending=[False, False, True, False],
        )

        max_power_per_group = df.group_by(["ItemSubType", "Equippable"]).agg(
            pl.max("Power").alias("Max Power")
        )

        filtered = (
            df.join(max_power_per_group, on=["ItemSubType", "Equippable"])
            .filter(pl.col("Power") != pl.col("Max Power"))
            .drop(["Max Power"])
        )

        return filtered
