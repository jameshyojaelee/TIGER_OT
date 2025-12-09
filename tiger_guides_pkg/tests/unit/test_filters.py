import pandas as pd

from tiger_guides.filters.ranking import apply_filters


def test_apply_filters_basic():
    data = pd.DataFrame({
        "Gene": ["A", "A", "B"],
        "Sequence": ["AAA", "AAT", "GGG"],
        "Score": [0.9, 0.85, 0.95],
        "MM0": [3, 4, 2],
        "MM1": [0, 0, 0],
        "MM2": [0, 0, 0],
    })
    config = {
        "filtering": {
            "min_guide_score": 0.8,
            "mm1_threshold": 0,
            "mm2_threshold": 0,
            "adaptive_mm0": True,
            "mm0_tolerance": 1,
        },
        "top_n_guides": 1,
    }

    ranked, stats = apply_filters(data, config)
    assert len(ranked) == 2
    assert stats["final"] == 2


def test_apply_filters_deduplicates_sequences():
    data = pd.DataFrame({
        "Gene": ["A"] * 3,
        "Sequence": ["AAA", "AAA", "AAC"],  # duplicate AAA
        "Target": ["t1", "t1", "t2"],
        "Score": [0.95, 0.90, 0.92],
        "MM0": [2, 2, 2],
        "MM1": [0, 0, 0],
        "MM2": [0, 0, 0],
    })
    config = {
        "filtering": {
            "min_guide_score": 0.8,
            "mm1_threshold": 0,
            "mm2_threshold": 0,
            "adaptive_mm0": False,
        },
        "top_n_guides": 10,
    }

    ranked, stats = apply_filters(data, config)
    # Only two distinct sequences should remain
    assert len(ranked) == 2
    assert set(ranked["Sequence"]) == {"AAA", "AAC"}
    # Keep the best-scoring copy of the duplicate
    best_row = ranked[ranked["Sequence"] == "AAA"].iloc[0]
    assert best_row["Score"] == 0.95
