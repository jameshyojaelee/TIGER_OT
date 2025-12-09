"""Guide filtering and ranking helpers."""
from __future__ import annotations

import pandas as pd
from typing import Dict, Tuple


def apply_filters(guides: pd.DataFrame, config: Dict, logger=None) -> Tuple[pd.DataFrame, Dict[str, int]]:
    stats = {}

    filtering = config.get("filtering", {})
    min_score = filtering.get("min_guide_score", 0.0)

    if logger:
        logger.info("\n" + "=" * 60)
        logger.info(f"STEP 4.1: Filter by Guide Score (>= {min_score})")
        logger.info("=" * 60)

    high_score = guides[guides["Score"] >= min_score].copy()
    stats["score_pass"] = len(high_score)

    if logger:
        logger.info(f"Guides passing score threshold: {len(high_score):,} / {len(guides):,}")

    # Off-target thresholds
    mm1_threshold = filtering.get("mm1_threshold", 0)
    mm2_threshold = filtering.get("mm2_threshold", 0)

    if logger:
        logger.info("\n" + "=" * 60)
        logger.info(f"STEP 4.2: Apply MM Filters (MM1<= {mm1_threshold}, MM2<= {mm2_threshold})")
        logger.info("=" * 60)

    filtered = high_score[
        (high_score["MM0"] >= 1) &
        (high_score["MM1"] <= mm1_threshold) &
        (high_score["MM2"] <= mm2_threshold)
    ].copy()
    stats["mm_filters"] = len(filtered)

    if filtering.get("adaptive_mm0", True):
        filtered = _apply_adaptive_mm0(filtered, filtering, logger)
        stats["adaptive_mm0"] = len(filtered)
    else:
        stats["adaptive_mm0"] = len(filtered)

    # Deduplicate guides so the same sequence (and target, when present) is not
    # returned multiple times just because it appeared at several positions in
    # the input. Keep the best-scoring, lowest-mismatch copy.
    dedup_keys = ["Gene", "Sequence"]
    if "Target" in filtered.columns:
        dedup_keys.append("Target")

    filtered = (
        filtered
        .sort_values(["Gene", "Score", "MM0", "MM1", "MM2"], ascending=[True, False, True, True, True])
        .drop_duplicates(subset=dedup_keys, keep="first")
    )
    stats["dedup_guides"] = len(filtered)

    top_n = config.get("top_n_guides", 10)
    if logger:
        logger.info("\n" + "=" * 60)
        logger.info(f"STEP 4.3: Select Top {top_n} Guides per Gene")
        logger.info("=" * 60)

    ranked = (
        filtered
        .sort_values(["Gene", "Score"], ascending=[True, False])
        .groupby("Gene")
        .head(top_n)
        .reset_index(drop=True)
    )
    stats["final"] = len(ranked)

    # Keep MM0 transcript/gene columns intact for downstream consumers
    for col in ("MM0_Transcripts", "MM0_Genes"):
        if col in ranked.columns:
            ranked[col] = ranked[col].fillna("")

    # Prefer a consistent column order when optional metadata is present
    preferred = ["Gene"]
    if "Sequence" in ranked.columns:
        preferred.append("Sequence")
    if "Target" in ranked.columns and "Target" not in preferred:
        preferred.append("Target")
    for extra in ["Score", "MM0", "MM1", "MM2", "MM3", "MM4", "MM5", "MM0_Transcripts", "MM0_Genes"]:
        if extra in ranked.columns and extra not in preferred:
            preferred.append(extra)
    ordered = preferred + [col for col in ranked.columns if col not in preferred]
    ranked = ranked[ordered]

    return ranked, stats


def _apply_adaptive_mm0(df: pd.DataFrame, filtering: Dict, logger=None) -> pd.DataFrame:
    tolerance = filtering.get("mm0_tolerance", 0)
    if tolerance == 999:
        if logger:
            logger.info("MM0 tolerance disabled (999). Keeping guides based on MM1/MM2 only.")
        return df

    selected = []
    for gene, group in df.groupby("Gene"):
        min_mm0 = group["MM0"].min()
        threshold = min_mm0 + tolerance
        subset = group[group["MM0"] <= threshold]
        selected.append(subset)
        if logger:
            logger.info(f"{gene}: MM0 range {min_mm0}–{threshold} kept {len(subset)} guides")
    if selected:
        return pd.concat(selected, ignore_index=True)
    return df
