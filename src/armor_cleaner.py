import polars as pl
from dataclasses import dataclass
from typing import Tuple


STAT_COLS = [
    "Mobility",
    "Resilience",
    "Recovery",
    "Discipline",
    "Intellect",
    "Strength",
]

SOURCE_LIST = [
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


@dataclass
class FilterParams:
    target_discipline: int
    max_quality: float

    always_keep_highest_power: bool
    build_flags: dict[str, dict[str, bool]]


class ArmorFilter:
    def __init__(self) -> None:
        pass

    def filter_armor_items(
        self, df: pl.DataFrame, params: FilterParams
    ) -> pl.DataFrame:
        working_df = df

        if params.always_keep_highest_power:
            working_df = self.drop_highest_power_by_type(working_df)

        """
        Remove Exotic Class Items from consideration. This is not a feature I want to
        add yet.
        """
        working_df = working_df.filter(
            (
                (pl.col("Tier") == "Exotic") & (pl.col("ItemSubType") == "ClassArmor")
            ).not_()
        )

        normal_armor, artifice_armor, class_armor = self.split_armor_categories(
            working_df
        )

        normal_armor = self.compute_quality(
            df=normal_armor,
            target_disc=params.target_discipline,
            build_flags=params.build_flags,
        )

        artifice_armor = self.min_quality_with_artifice_boost(
            df=artifice_armor,
            target_disc=params.target_discipline,
            build_flags=params.build_flags,
        )

        exotics_armor_df = artifice_armor.filter(pl.col("Tier") == "Exotic")
        exotics_to_delete = self.filter_exotic_armor(
            df=exotics_armor_df, max_quality=params.max_quality
        )

        normal_and_artifice = pl.concat([normal_armor, artifice_armor])

        normal_legendaries = normal_and_artifice.filter(
            (pl.col("Source").is_null()) & (pl.col("Tier") != "Exotic")
        )

        mod_armor = normal_and_artifice.filter((pl.col("Source").is_in(SOURCE_LIST)))

        mod_armor_to_delete = self.filter_mod_armor(
            df=mod_armor, max_quality=params.max_quality
        )

        legendaries_to_delete = self.filter_normal_and_artifice(
            df=normal_legendaries,
            max_quality=params.max_quality,
        )

        class_items_to_delete = self.filter_class_items(df=class_armor)

        return pl.concat(
            [
                # class_items_to_delete,
                exotics_to_delete,
                legendaries_to_delete,
                mod_armor_to_delete,
            ]
        )

    def filter_mod_armor(self, df: pl.DataFrame, max_quality: float) -> pl.DataFrame:
        result = (
            df.with_columns(
                [
                    pl.col("Quality")
                    .rank("ordinal", descending=False)
                    .over(["Equippable", "Source", "ItemSubType"])
                    .alias("Quality Rank")
                ]
            )
            .filter(pl.col("Quality Rank") > 1)
            .filter(pl.col("Quality") > max_quality)
            .select(pl.col("Id", "Hash"))
        )

        return result

    def filter_class_items(self, df: pl.DataFrame) -> pl.DataFrame:
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

        artifice = df.filter(pl.col("IsArtifice"))
        artifice_to_drop = (
            artifice.sort(["Power", "Energy Capacity"], descending=True)
            .group_by(["Source", "Equippable"])
            .first()
        )

        source_items = df.filter(pl.col("Source").is_in(sources_to_keep))

        to_drop_source = (
            source_items.sort(
                ["Source", "Equippable", "Energy Capacity", "Power"],
                descending=True,
            )
            .group_by(["Source", "Equippable"])
            .first()
        )

        print(artifice_to_drop.columns)
        print(to_drop_source.columns)

        to_remove = pl.concat(
            [artifice_to_drop, to_drop_source], how="vertical"
        ).unique(subset=["Id"])

        output_df = to_remove.select(["Id", "Hash"])

        return to_remove

    def filter_exotic_armor(self, df: pl.DataFrame, max_quality: float) -> pl.DataFrame:
        best_exotic_rows = df.select(
            pl.all().top_k_by("Quality", k=2).over("Hash", mapping_strategy="explode")
        )

        output_df = df.join(best_exotic_rows, on=["Hash", "Quality"], how="anti")

        output_df = output_df.filter(pl.col("Quality") > max_quality)

        output_df = output_df.select(pl.col(["Id", "Hash"]))

        return output_df

    def filter_normal_and_artifice(
        self, df: pl.DataFrame, max_quality: float
    ) -> pl.DataFrame:
        best_armor_rows = df.select(
            pl.all()
            .top_k_by("Quality", k=1)
            .over("ItemSubType", mapping_strategy="explode")
        )

        output_df = df.join(best_armor_rows, on=["Hash", "Quality"], how="anti")

        output_df = output_df.filter(pl.col("Quality") > max_quality)

        output_df = output_df.select(pl.col(["Id", "Hash"]))

        return output_df

    def compute_quality(
        self,
        df: pl.DataFrame,
        target_disc: int,
        build_flags: dict[str, dict[str, bool]],
    ) -> pl.DataFrame:
        working_df = df

        working_df = self.compute_segment_gaps(working_df)

        with_build_gaps = pl.DataFrame()

        classes = ["Hunter", "Warlock", "Titan"]
        for equippable in classes:
            class_flags = build_flags[equippable]
            class_specific = self.compute_class_build_gap(
                working_df, equippable, class_flags
            )
            with_build_gaps = pl.concat([with_build_gaps, class_specific])

        working_df = self.compute_top_segment_decay(with_build_gaps)

        working_df = self.compute_discipline_quality(working_df, target_disc)

        working_df = working_df.with_columns(
            (
                pl.col("Top Segment Decay")
                + (pl.col("Bottom Segment Gap") + pl.col("Discipline Quality")) / 4
            ).alias("Quality")
        )

        return working_df

    def min_quality_with_artifice_boost(
        self,
        df: pl.DataFrame,
        target_disc: int,
        build_flags: dict[str, dict[str, bool]],
    ):
        working_df = df

        final_df = self.compute_quality(working_df, target_disc, build_flags)

        for stat in STAT_COLS:
            working_df = working_df.with_columns([(pl.col(stat) + 3).alias(stat)])
            working_df = self.compute_quality(working_df, target_disc, build_flags)

            final_df = final_df.with_columns(
                [
                    pl.min_horizontal(
                        pl.col("Quality"), pl.lit(working_df["Quality"])
                    ).alias("Quality")
                ]
            )

            working_df = working_df.with_columns([(pl.col(stat) - 3).alias(stat)])

        return final_df

    def drop_highest_power_by_type(self, df: pl.DataFrame) -> pl.DataFrame:
        highest_power_rows = (
            df.sort("Power", descending=True).group_by("ItemSubType").first()
        )

        output_df = df.join(highest_power_rows, on=["ItemSubType", "Power"], how="anti")
        return output_df

    def split_armor_categories(
        self, df: pl.DataFrame
    ) -> Tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
        normal_armor = df.filter(
            (pl.col("IsArtifice") | (pl.col("ItemSubType") == "ClassArmor")).not_()
        )

        artifice_armor = df.filter(
            pl.col("IsArtifice") & (pl.col("ItemSubType") != "ClassArmor")
        )

        class_armor = df.filter(pl.col("ItemSubType") == "ClassArmor")

        return (normal_armor, artifice_armor, class_armor)

    def compute_segment_gaps(self, df: pl.DataFrame) -> pl.DataFrame:
        working_df = df.with_columns(
            (34 - (pl.col("Mobility") + pl.col("Resilience") + pl.col("Recovery")))
            .clip(lower_bound=0, upper_bound=12)
            .alias("Top Segment Gap"),
            (34 - (pl.col("Discipline") + pl.col("Intellect") + pl.col("Strength")))
            .clip(lower_bound=0, upper_bound=12)
            .alias("Bottom Segment Gap"),
        )

        return working_df

    def compute_class_build_gap(
        self, df: pl.DataFrame, classType: str, build_flags: dict[str, bool]
    ) -> pl.DataFrame:
        working_df = df.filter(pl.col("Equippable") == classType)

        working_df = working_df.with_columns(
            [
                pl.when(build_flags["MobRes"])
                .then(32 - (pl.col("Mobility") + pl.col("Resilience")))
                .otherwise(28)
                .clip(lower_bound=0, upper_bound=28)
                .alias("Mob Res Gap"),
                pl.when(build_flags["ResRec"])
                .then(32 - (pl.col("Resilience") + pl.col("Recovery")))
                .otherwise(28)
                .clip(lower_bound=0, upper_bound=28)
                .alias("Res Rec Gap"),
                pl.when(build_flags["MobRec"])
                .then(32 - (pl.col("Mobility") + pl.col("Recovery")))
                .otherwise(28)
                .clip(lower_bound=0, upper_bound=28)
                .alias("Mob Rec Gap"),
            ]
        )

        working_df = working_df.with_columns(
            pl.min_horizontal("Mob Res Gap", "Res Rec Gap", "Mob Rec Gap").alias(
                "Build Gap"
            )
        )

        return working_df

    def compute_top_segment_decay(self, df: pl.DataFrame) -> pl.DataFrame:
        working_df = df.with_columns(
            (pl.col("Build Gap") / 7 + pl.col("Top Segment Gap") / 3).alias(
                "Top Segment Decay"
            )
        )

        return working_df

    def compute_discipline_quality(
        self, df: pl.DataFrame, target_disc: int
    ) -> pl.DataFrame:
        working_df = df.with_columns(
            (5 - (5 * pl.col("Discipline") / target_disc))
            .clip(lower_bound=0)
            .alias("Discipline Quality")
        )

        return working_df
